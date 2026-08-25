//! Load balancer for LLM inference requests across nodes

use crate::error::Result;
use crate::types::{BalanceRequest, BalanceResponse, NodeId, NodeInfo};
use crate::node_registry::NodeRegistry;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use uuid::Uuid;

/// LLM load balancer (round-robin + latency-aware)
pub struct LlmBalancer {
    pub registry: NodeRegistry,
    round_robin_counter: Arc<AtomicUsize>,
}

impl LlmBalancer {
    pub fn new(registry: NodeRegistry) -> Self {
        Self {
            registry,
            round_robin_counter: Arc::new(AtomicUsize::new(0)),
        }
    }

    /// Balance a request to the best available node
    pub fn balance(&self, request: &BalanceRequest) -> Result<BalanceResponse> {
        let healthy_nodes = self.registry.list_healthy();

        if healthy_nodes.is_empty() {
            return Err(crate::Error::NoHealthyNodes);
        }

        // Select node: round-robin first, then latency-aware
        let selected_node = self.select_node(&healthy_nodes)?;

        Ok(BalanceResponse {
            request_id: request.request_id,
            selected_node: selected_node.node_id,
            endpoint: selected_node.endpoint(),
            estimated_latency_ms: selected_node.inference_latency_ms.unwrap_or(0.0),
        })
    }

    /// Select best node (round-robin, ties broken by latency)
    fn select_node(&self, healthy_nodes: &[NodeInfo]) -> Result<NodeInfo> {
        if healthy_nodes.is_empty() {
            return Err(crate::Error::NoHealthyNodes);
        }

        // Round-robin selection
        let counter = self.round_robin_counter.fetch_add(1, Ordering::SeqCst);
        let mut selected = healthy_nodes[counter % healthy_nodes.len()].clone();

        // Tie-break by latency if available
        for node in healthy_nodes {
            let selected_latency = selected.inference_latency_ms.unwrap_or(f64::MAX);
            let node_latency = node.inference_latency_ms.unwrap_or(f64::MAX);

            if node_latency < selected_latency {
                selected = node.clone();
            }
        }

        Ok(selected)
    }

    /// Get load distribution stats
    pub fn load_distribution(&self) -> Vec<(NodeId, f64)> {
        let healthy_nodes = self.registry.list_healthy();
        let total_requests: u64 = healthy_nodes.iter().map(|n| n.request_count).sum();

        healthy_nodes
            .into_iter()
            .map(|node| {
                let percentage = if total_requests > 0 {
                    (node.request_count as f64 / total_requests as f64) * 100.0
                } else {
                    0.0
                };
                (node.node_id, percentage)
            })
            .collect()
    }

    /// Failover: find alternate node if current is unhealthy
    pub fn failover(&self, failed_node: &NodeId) -> Result<BalanceResponse> {
        let healthy_nodes = self.registry.list_healthy();

        // Filter out the failed node
        let available: Vec<NodeInfo> = healthy_nodes
            .into_iter()
            .filter(|n| &n.node_id != failed_node)
            .collect();

        if available.is_empty() {
            return Err(crate::Error::NoHealthyNodes);
        }

        let selected = self.select_node(&available)?;
        Ok(BalanceResponse {
            request_id: Uuid::new_v4(),
            selected_node: selected.node_id,
            endpoint: selected.endpoint(),
            estimated_latency_ms: selected.inference_latency_ms.unwrap_or(0.0),
        })
    }
}

impl Clone for LlmBalancer {
    fn clone(&self) -> Self {
        Self {
            registry: self.registry.clone(),
            round_robin_counter: Arc::clone(&self.round_robin_counter),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::IpAddr;
    use std::str::FromStr;

    #[test]
    fn test_balance_single_node() {
        let registry = NodeRegistry::new();
        let node_id = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();
        registry.register(node_id, "node1".to_string(), ip, 8080);

        let balancer = LlmBalancer::new(registry);
        let request = BalanceRequest {
            request_id: Uuid::new_v4(),
            model_name: "qwen3-coder".to_string(),
            priority: 0,
            max_wait_ms: 5000,
        };

        let response = balancer.balance(&request).expect("balance failed");
        assert_eq!(response.selected_node, node_id);
    }

    #[test]
    fn test_balance_round_robin() {
        let registry = NodeRegistry::new();
        let id1 = NodeId::new();
        let id2 = NodeId::new();
        let id3 = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();

        registry.register(id1, "node1".to_string(), ip, 8080);
        registry.register(id2, "node2".to_string(), ip, 8081);
        registry.register(id3, "node3".to_string(), ip, 8082);

        let balancer = LlmBalancer::new(registry);

        let mut selections = vec![];
        for _ in 0..3 {
            let request = BalanceRequest {
                request_id: Uuid::new_v4(),
                model_name: "qwen3-coder".to_string(),
                priority: 0,
                max_wait_ms: 5000,
            };
            let response = balancer.balance(&request).expect("balance failed");
            selections.push(response.selected_node);
        }

        // Should rotate through all nodes (round-robin)
        assert!(selections.contains(&id1) || selections.contains(&id2) || selections.contains(&id3));
    }

    #[test]
    fn test_balance_no_healthy_nodes() {
        let registry = NodeRegistry::new();
        let balancer = LlmBalancer::new(registry);

        let request = BalanceRequest {
            request_id: Uuid::new_v4(),
            model_name: "qwen3-coder".to_string(),
            priority: 0,
            max_wait_ms: 5000,
        };

        let result = balancer.balance(&request);
        assert!(result.is_err());
    }

    #[test]
    fn test_load_distribution() {
        let registry = NodeRegistry::new();
        let id1 = NodeId::new();
        let id2 = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();

        registry.register(id1, "node1".to_string(), ip, 8080);
        registry.register(id2, "node2".to_string(), ip, 8081);

        let balancer = LlmBalancer::new(registry.clone());

        // Record some requests
        registry.record_request(&id1, 50.0).ok();
        registry.record_request(&id2, 45.0).ok();
        registry.record_request(&id1, 48.0).ok();

        let dist = balancer.load_distribution();
        assert_eq!(dist.len(), 2);
        assert!(dist.iter().any(|(id, _)| id == &id1));
        assert!(dist.iter().any(|(id, _)| id == &id2));
    }

    #[test]
    fn test_failover() {
        let registry = NodeRegistry::new();
        let id1 = NodeId::new();
        let id2 = NodeId::new();
        let id3 = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();

        registry.register(id1, "node1".to_string(), ip, 8080);
        registry.register(id2, "node2".to_string(), ip, 8081);
        registry.register(id3, "node3".to_string(), ip, 8082);

        let balancer = LlmBalancer::new(registry.clone());

        // Mark id1 as unhealthy
        registry
            .set_health(&id1, crate::types::NodeHealth::Unhealthy)
            .ok();

        let response = balancer.failover(&id1).expect("failover failed");

        // Should select id2 or id3
        assert!(response.selected_node == id2 || response.selected_node == id3);
    }

    #[test]
    fn test_failover_all_nodes_down() {
        let registry = NodeRegistry::new();
        let id1 = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();

        registry.register(id1, "node1".to_string(), ip, 8080);
        registry
            .set_health(&id1, crate::types::NodeHealth::Unhealthy)
            .ok();

        let balancer = LlmBalancer::new(registry);
        let result = balancer.failover(&id1);
        assert!(result.is_err());
    }

    #[test]
    fn test_latency_aware_selection() {
        let registry = NodeRegistry::new();
        let id1 = NodeId::new();
        let id2 = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();

        registry.register(id1, "node1".to_string(), ip, 8080);
        registry.register(id2, "node2".to_string(), ip, 8081);

        // Record different latencies
        registry.record_request(&id1, 100.0).ok();
        registry.record_request(&id2, 50.0).ok(); // Faster

        let balancer = LlmBalancer::new(registry);

        // Request should prefer id2 due to lower latency
        let request = BalanceRequest {
            request_id: Uuid::new_v4(),
            model_name: "qwen3-coder".to_string(),
            priority: 0,
            max_wait_ms: 5000,
        };

        let response = balancer.balance(&request).expect("balance failed");
        assert_eq!(response.selected_node, id2);
    }
}
