/// Phase 40: A2A Discovery — Autonomous-to-Autonomous Service Registry
/// Enables service discovery across network boundaries.

use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum NetworkBoundary {
    Local,
    Regional,
    Global,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentServiceRecord {
    pub agent_id: Uuid,
    pub service_name: String,
    pub region: String,
    pub network_boundary: NetworkBoundary,
    pub capabilities: Vec<String>,
    pub last_heartbeat: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveryQuery {
    pub service_name: String,
    pub required_region: Option<String>,
    pub required_boundary: Option<NetworkBoundary>,
    pub required_capabilities: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveryResult {
    pub agents: Vec<AgentServiceRecord>,
    pub search_time_ms: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DiscoveryError {
    ServiceNotFound,
    BoundaryViolation,
    RegistryUnavailable,
}

pub struct A2ADiscoveryRegistry {
    // service_name -> vec of agents providing that service
    agents_by_service: Arc<DashMap<String, Vec<AgentServiceRecord>>>,
    // agent_id -> record (for quick lookup)
    agents_by_id: Arc<DashMap<Uuid, AgentServiceRecord>>,
}

impl A2ADiscoveryRegistry {
    pub fn new() -> Self {
        Self {
            agents_by_service: Arc::new(DashMap::new()),
            agents_by_id: Arc::new(DashMap::new()),
        }
    }

    /// Register an agent service
    pub fn register_agent(&self, record: AgentServiceRecord) -> Result<(), DiscoveryError> {
        self.agents_by_id.insert(record.agent_id, record.clone());

        let mut entry = self
            .agents_by_service
            .entry(record.service_name.clone())
            .or_insert_with(Vec::new);
        entry.push(record);

        Ok(())
    }

    /// Discover service locally
    pub fn discover_service(&self, query: &DiscoveryQuery) -> Result<DiscoveryResult, DiscoveryError> {
        let start = std::time::Instant::now();

        let agents = self
            .agents_by_service
            .get(&query.service_name)
            .ok_or(DiscoveryError::ServiceNotFound)?
            .clone();

        // Apply filters
        let filtered = agents
            .iter()
            .filter(|agent| {
                if let Some(region) = &query.required_region {
                    if agent.region != *region {
                        return false;
                    }
                }

                if let Some(boundary) = query.required_boundary {
                    if agent.network_boundary != boundary {
                        return false;
                    }
                }

                if !query.required_capabilities.is_empty() {
                    for req_cap in &query.required_capabilities {
                        if !agent.capabilities.contains(req_cap) {
                            return false;
                        }
                    }
                }

                true
            })
            .cloned()
            .collect();

        let elapsed = start.elapsed().as_millis() as u64;

        Ok(DiscoveryResult {
            agents: filtered,
            search_time_ms: elapsed,
        })
    }

    /// Cross-boundary discovery across multiple registries
    pub fn discover_cross_boundary(
        &self,
        query: &DiscoveryQuery,
        remote_registries: &[Arc<A2ADiscoveryRegistry>],
    ) -> Result<DiscoveryResult, DiscoveryError> {
        let start = std::time::Instant::now();

        // Try local first
        let mut all_agents = match self.discover_service(query) {
            Ok(result) => result.agents,
            Err(_) => vec![],
        };

        // Try remote registries
        for remote in remote_registries {
            if let Ok(result) = remote.discover_service(query) {
                all_agents.extend(result.agents);
            }
        }

        if all_agents.is_empty() {
            return Err(DiscoveryError::ServiceNotFound);
        }

        let elapsed = start.elapsed().as_millis() as u64;

        Ok(DiscoveryResult {
            agents: all_agents,
            search_time_ms: elapsed,
        })
    }

    /// Remove stale entries (heartbeat > 60s old)
    pub fn cleanup_stale_entries(&self) {
        let now = Utc::now();
        let stale_threshold = chrono::Duration::seconds(60);

        let mut to_remove = Vec::new();

        for entry in self.agents_by_id.iter() {
            let time_since_heartbeat = now.signed_duration_since(entry.last_heartbeat);
            if time_since_heartbeat > stale_threshold {
                to_remove.push(entry.agent_id);
            }
        }

        for agent_id in to_remove {
            if let Some((_, record)) = self.agents_by_id.remove(&agent_id) {
                // Also remove from service index
                if let Some(mut service_agents) = self.agents_by_service.get_mut(&record.service_name) {
                    service_agents.retain(|a| a.agent_id != agent_id);
                }
            }
        }
    }
}

impl Default for A2ADiscoveryRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_registry() {
        let _registry = A2ADiscoveryRegistry::new();
    }
}
