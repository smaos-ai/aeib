//! Central node registry for cluster state management

use crate::error::Result;
use crate::types::{NodeHealth, NodeId, NodeInfo};
use chrono::Utc;
use dashmap::DashMap;
use std::net::IpAddr;
use std::sync::Arc;

/// Central registry of all nodes in the cluster
pub struct NodeRegistry {
    nodes: Arc<DashMap<NodeId, NodeInfo>>,
}

impl NodeRegistry {
    pub fn new() -> Self {
        Self {
            nodes: Arc::new(DashMap::new()),
        }
    }

    /// Register or update a node
    pub fn register(&self, node_id: NodeId, hostname: String, local_ip: IpAddr, port: u16) -> NodeInfo {
        let node_info = NodeInfo::new(node_id, hostname, local_ip, port);
        self.nodes.insert(node_id, node_info.clone());
        node_info
    }

    /// Get node information
    pub fn get(&self, node_id: &NodeId) -> Option<NodeInfo> {
        self.nodes.get(node_id).map(|n| n.clone())
    }

    /// List all nodes
    pub fn list_all(&self) -> Vec<NodeInfo> {
        self.nodes.iter().map(|n| n.value().clone()).collect()
    }

    /// Get healthy nodes only
    pub fn list_healthy(&self) -> Vec<NodeInfo> {
        self.nodes
            .iter()
            .filter(|n| n.value().is_healthy())
            .map(|n| n.value().clone())
            .collect()
    }

    /// Update node health status
    pub fn set_health(&self, node_id: &NodeId, health: NodeHealth) -> Result<()> {
        if let Some(mut node) = self.nodes.get_mut(node_id) {
            node.health = health;
            node.last_heartbeat = Utc::now();
            Ok(())
        } else {
            Err(crate::Error::NodeNotFound(format!("{:?}", node_id)))
        }
    }

    /// Record successful inference request
    pub fn record_request(&self, node_id: &NodeId, latency_ms: f64) -> Result<()> {
        if let Some(mut node) = self.nodes.get_mut(node_id) {
            node.request_count += 1;
            node.inference_latency_ms = Some(latency_ms);
            Ok(())
        } else {
            Err(crate::Error::NodeNotFound(format!("{:?}", node_id)))
        }
    }

    /// Count total nodes
    pub fn count(&self) -> usize {
        self.nodes.len()
    }

    /// Check if quorum is met
    pub fn has_quorum(&self, quorum_size: usize) -> bool {
        let healthy_count = self.list_healthy().len();
        healthy_count >= quorum_size
    }
}

impl Default for NodeRegistry {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for NodeRegistry {
    fn clone(&self) -> Self {
        Self {
            nodes: Arc::clone(&self.nodes),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::str::FromStr;

    #[test]
    fn test_register_node() {
        let registry = NodeRegistry::new();
        let node_id = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();

        let node = registry.register(node_id, "mac-studio-1".to_string(), ip, 8080);

        assert_eq!(node.node_id, node_id);
        assert_eq!(node.hostname, "mac-studio-1");
        assert_eq!(node.health, NodeHealth::Healthy);
    }

    #[test]
    fn test_get_node() {
        let registry = NodeRegistry::new();
        let node_id = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();
        registry.register(node_id, "mac-studio-1".to_string(), ip, 8080);

        let retrieved = registry.get(&node_id).expect("node not found");
        assert_eq!(retrieved.node_id, node_id);
    }

    #[test]
    fn test_list_all_nodes() {
        let registry = NodeRegistry::new();
        let id1 = NodeId::new();
        let id2 = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();

        registry.register(id1, "node1".to_string(), ip, 8080);
        registry.register(id2, "node2".to_string(), ip, 8081);

        let all = registry.list_all();
        assert_eq!(all.len(), 2);
    }

    #[test]
    fn test_set_health() {
        let registry = NodeRegistry::new();
        let node_id = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();
        registry.register(node_id, "test".to_string(), ip, 8080);

        registry
            .set_health(&node_id, NodeHealth::Degraded)
            .expect("set_health failed");

        let node = registry.get(&node_id).expect("node not found");
        assert_eq!(node.health, NodeHealth::Degraded);
    }

    #[test]
    fn test_list_healthy_nodes() {
        let registry = NodeRegistry::new();
        let id1 = NodeId::new();
        let id2 = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();

        registry.register(id1, "node1".to_string(), ip, 8080);
        registry.register(id2, "node2".to_string(), ip, 8081);

        registry
            .set_health(&id2, NodeHealth::Unhealthy)
            .expect("set_health failed");

        let healthy = registry.list_healthy();
        assert_eq!(healthy.len(), 1);
        assert_eq!(healthy[0].node_id, id1);
    }

    #[test]
    fn test_record_request() {
        let registry = NodeRegistry::new();
        let node_id = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();
        registry.register(node_id, "test".to_string(), ip, 8080);

        registry
            .record_request(&node_id, 45.5)
            .expect("record_request failed");

        let node = registry.get(&node_id).expect("node not found");
        assert_eq!(node.request_count, 1);
        assert!(node.inference_latency_ms.is_some());
        assert!((node.inference_latency_ms.unwrap() - 45.5).abs() < 0.1);
    }

    #[test]
    fn test_has_quorum() {
        let registry = NodeRegistry::new();
        let id1 = NodeId::new();
        let id2 = NodeId::new();
        let id3 = NodeId::new();
        let ip = IpAddr::from_str("192.168.1.10").unwrap();

        registry.register(id1, "node1".to_string(), ip, 8080);
        registry.register(id2, "node2".to_string(), ip, 8081);
        registry.register(id3, "node3".to_string(), ip, 8082);

        assert!(registry.has_quorum(2)); // 3 healthy >= 2
        registry.set_health(&id3, NodeHealth::Offline).ok();
        assert!(registry.has_quorum(2)); // 2 healthy >= 2
        registry.set_health(&id2, NodeHealth::Offline).ok();
        assert!(!registry.has_quorum(2)); // 1 healthy < 2
    }
}
