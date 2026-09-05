//! Dynamic resource allocation

use crate::error::{Error, Result};
use crate::types::{AgentAllocation, ResourceRequirement};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;

/// Allocation configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AllocationConfig {
    pub total_cpu_percent: f32,
    pub total_memory_mb: u32,
    pub total_bandwidth_mbps: u32,
    pub max_budget_per_agent: f64,
}

impl Default for AllocationConfig {
    fn default() -> Self {
        Self {
            total_cpu_percent: 100.0,
            total_memory_mb: 16384,
            total_bandwidth_mbps: 1000,
            max_budget_per_agent: 100.0,
        }
    }
}

/// Resource allocator
pub struct ResourceAllocator {
    config: AllocationConfig,
    allocations: Arc<RwLock<HashMap<String, AgentAllocation>>>,
}

impl ResourceAllocator {
    /// Create new allocator
    pub fn new(config: AllocationConfig) -> Self {
        Self {
            config,
            allocations: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Allocate resources to agent
    pub fn allocate(
        &self,
        agent_id: String,
        requirement: ResourceRequirement,
    ) -> Result<AgentAllocation> {
        let mut allocations = self.allocations.write();

        // Check if resources available
        let allocated_cpu: f32 = allocations.values().map(|a| a.cpu_percent).sum();
        let allocated_memory: u32 = allocations.values().map(|a| a.memory_mb).sum();
        let allocated_bandwidth: u32 = allocations.values().map(|a| a.bandwidth_mbps).sum();

        if allocated_cpu + requirement.min_cpu_percent > self.config.total_cpu_percent {
            return Err(Error::AllocationError("Insufficient CPU".to_string()));
        }

        if allocated_memory + requirement.min_memory_mb > self.config.total_memory_mb {
            return Err(Error::AllocationError("Insufficient memory".to_string()));
        }

        if allocated_bandwidth + requirement.min_bandwidth_mbps > self.config.total_bandwidth_mbps {
            return Err(Error::AllocationError("Insufficient bandwidth".to_string()));
        }

        let allocation = AgentAllocation {
            agent_id: agent_id.clone(),
            cpu_percent: requirement.min_cpu_percent,
            memory_mb: requirement.min_memory_mb,
            bandwidth_mbps: requirement.min_bandwidth_mbps,
            cost_budget_usd: self.config.max_budget_per_agent,
        };

        allocations.insert(agent_id, allocation.clone());
        Ok(allocation)
    }

    /// Deallocate resources
    pub fn deallocate(&self, agent_id: &str) -> Result<()> {
        let mut allocations = self.allocations.write();
        allocations
            .remove(agent_id)
            .ok_or(Error::AgentNotFound(agent_id.to_string()))?;
        Ok(())
    }

    /// Rebalance allocations
    pub fn rebalance(&self) -> Result<()> {
        // In real implementation, would dynamically adjust based on usage
        Ok(())
    }

    /// Get allocation for agent
    pub fn get_allocation(&self, agent_id: &str) -> Option<AgentAllocation> {
        self.allocations.read().get(agent_id).cloned()
    }

    /// Get all allocations
    pub fn get_all_allocations(&self) -> Vec<AgentAllocation> {
        self.allocations.read().values().cloned().collect()
    }

    /// Get utilization percentage
    pub fn get_utilization(&self) -> (f32, f32, f32) {
        let allocations = self.allocations.read();

        let cpu_used: f32 = allocations.iter().map(|(_, a)| a.cpu_percent).sum();
        let memory_used: u32 = allocations.iter().map(|(_, a)| a.memory_mb).sum();
        let bandwidth_used: u32 = allocations.iter().map(|(_, a)| a.bandwidth_mbps).sum();

        (
            (cpu_used / self.config.total_cpu_percent) * 100.0,
            (memory_used as f32 / self.config.total_memory_mb as f32) * 100.0,
            (bandwidth_used as f32 / self.config.total_bandwidth_mbps as f32) * 100.0,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_allocator_creation() {
        let allocator = ResourceAllocator::new(AllocationConfig::default());
        let allocations = allocator.get_all_allocations();
        assert_eq!(allocations.len(), 0);
    }

    #[test]
    fn test_allocate_resources() {
        let allocator = ResourceAllocator::new(AllocationConfig::default());
        let requirement = ResourceRequirement {
            min_cpu_percent: 10.0,
            min_memory_mb: 512,
            min_bandwidth_mbps: 100,
        };

        let result = allocator.allocate("agent1".to_string(), requirement);
        assert!(result.is_ok());
    }

    #[test]
    fn test_allocate_insufficient_cpu() {
        let mut config = AllocationConfig::default();
        config.total_cpu_percent = 10.0;
        let allocator = ResourceAllocator::new(config);

        let requirement = ResourceRequirement {
            min_cpu_percent: 20.0,
            min_memory_mb: 512,
            min_bandwidth_mbps: 100,
        };

        let result = allocator.allocate("agent1".to_string(), requirement);
        assert!(result.is_err());
    }

    #[test]
    fn test_deallocate() {
        let allocator = ResourceAllocator::new(AllocationConfig::default());
        let requirement = ResourceRequirement {
            min_cpu_percent: 10.0,
            min_memory_mb: 512,
            min_bandwidth_mbps: 100,
        };

        allocator.allocate("agent1".to_string(), requirement).unwrap();
        let result = allocator.deallocate("agent1");
        assert!(result.is_ok());
        assert_eq!(allocator.get_all_allocations().len(), 0);
    }

    #[test]
    fn test_get_utilization() {
        let allocator = ResourceAllocator::new(AllocationConfig::default());
        let requirement = ResourceRequirement {
            min_cpu_percent: 50.0,
            min_memory_mb: 8192,
            min_bandwidth_mbps: 500,
        };

        allocator.allocate("agent1".to_string(), requirement).unwrap();
        let (cpu, mem, bw) = allocator.get_utilization();

        assert!(cpu > 0.0 && cpu <= 100.0);
        assert!(mem > 0.0 && mem <= 100.0);
        assert!(bw > 0.0 && bw <= 100.0);
    }
}
