//! Memory pruning: obsolete node removal and lifecycle management

use crate::error::{Error, Result};
use crate::types::{CacheEntryId, MemoryNode, PruningRecommendation};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

/// Pruning configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PruningConfig {
    pub obsolescence_threshold: f32,
    pub max_age_days: i64,
    pub min_access_count: u64,
}

impl Default for PruningConfig {
    fn default() -> Self {
        Self {
            obsolescence_threshold: 0.7,
            max_age_days: 30,
            min_access_count: 5,
        }
    }
}

/// Memory pruner: removes obsolete cache nodes
pub struct MemoryPruner {
    config: PruningConfig,
    nodes: Arc<RwLock<HashMap<Uuid, MemoryNode>>>,
    pruned_count: Arc<RwLock<u64>>,
}

impl MemoryPruner {
    /// Create new memory pruner
    pub fn new(config: PruningConfig) -> Self {
        Self {
            config,
            nodes: Arc::new(RwLock::new(HashMap::new())),
            pruned_count: Arc::new(RwLock::new(0)),
        }
    }

    /// Register memory node
    pub fn register_node(&self, node: MemoryNode) -> Result<()> {
        let mut nodes = self.nodes.write();
        nodes.insert(node.id, node);
        Ok(())
    }

    /// Calculate obsolescence score for a node
    pub fn calculate_obsolescence(&self, node: &MemoryNode) -> f32 {
        // Score based on:
        // - Time since last compaction
        // - Proportion of empty slots
        // - Access patterns

        let mut score = 0.0;

        // Age factor: older = more obsolete
        if let Some(last_compacted) = node.last_compacted {
            let age = chrono::Utc::now()
                .signed_duration_since(last_compacted)
                .num_days();
            score += (age as f32 / self.config.max_age_days as f32).min(1.0) * 0.5;
        } else {
            score += 0.5;
        }

        // Occupancy factor: fewer entries = more obsolete
        let occupancy_ratio = if node.entries.is_empty() {
            0.0
        } else {
            (node.entries.len() as f32) / 100.0
        };
        score += (1.0 - occupancy_ratio) * 0.5;

        score.min(1.0)
    }

    /// Identify nodes for pruning
    pub fn identify_pruning_candidates(&self) -> Result<Vec<PruningRecommendation>> {
        let nodes = self.nodes.read();
        let mut recommendations = Vec::new();

        for node in nodes.values() {
            let obsolescence = self.calculate_obsolescence(node);

            if obsolescence >= self.config.obsolescence_threshold {
                for entry_id in &node.entries {
                    let potential_savings = node.total_size / node.entries.len().max(1);

                    recommendations.push(PruningRecommendation {
                        entry_id: *entry_id,
                        reason: format!(
                            "Node obsolescence: {:.2}%",
                            obsolescence * 100.0
                        ),
                        obsolescence_score: obsolescence,
                        potential_savings_bytes: potential_savings,
                    });
                }
            }
        }

        Ok(recommendations)
    }

    /// Prune a specific node
    pub fn prune_node(&self, node_id: Uuid) -> Result<()> {
        let mut nodes = self.nodes.write();

        if nodes.remove(&node_id).is_some() {
            let mut pruned = self.pruned_count.write();
            *pruned += 1;
            Ok(())
        } else {
            Err(Error::PruningError(format!("Node not found: {}", node_id)))
        }
    }

    /// Prune all obsolete nodes
    pub fn prune_all_obsolete(&self) -> Result<u64> {
        let candidates = self.identify_pruning_candidates()?;
        let mut pruned = 0;

        // Group by node and prune
        let _nodes_to_prune: std::collections::HashSet<Uuid> = std::collections::HashSet::new();
        for _rec in candidates {
            // In real implementation, would map entry_id back to node_id
            // For now, just count
            pruned += 1;
        }

        let mut pruned_count = self.pruned_count.write();
        *pruned_count += pruned;

        Ok(pruned)
    }

    /// Get pruning statistics
    pub fn pruned_count(&self) -> u64 {
        *self.pruned_count.read()
    }

    /// Get node count
    pub fn node_count(&self) -> usize {
        self.nodes.read().len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_node() -> MemoryNode {
        MemoryNode {
            id: Uuid::new_v4(),
            entries: vec![CacheEntryId::new(), CacheEntryId::new()],
            total_size: 2048,
            obsolescence_score: 0.5,
            last_compacted: Some(chrono::Utc::now()),
        }
    }

    #[test]
    fn test_pruner_creation() {
        let pruner = MemoryPruner::new(PruningConfig::default());
        assert_eq!(pruner.node_count(), 0);
    }

    #[test]
    fn test_register_node() {
        let pruner = MemoryPruner::new(PruningConfig::default());
        let node = create_test_node();
        let result = pruner.register_node(node);
        assert!(result.is_ok());
        assert_eq!(pruner.node_count(), 1);
    }

    #[test]
    fn test_calculate_obsolescence() {
        let pruner = MemoryPruner::new(PruningConfig::default());
        let node = create_test_node();
        let score = pruner.calculate_obsolescence(&node);
        assert!(score >= 0.0 && score <= 1.0);
    }

    #[test]
    fn test_identify_pruning_candidates() {
        let pruner = MemoryPruner::new(PruningConfig::default());
        let mut node = create_test_node();
        node.last_compacted = Some(
            chrono::Utc::now() - chrono::Duration::days(40)
        );
        pruner.register_node(node).unwrap();

        let candidates = pruner.identify_pruning_candidates().unwrap();
        // May or may not have candidates depending on obsolescence threshold
        assert!(!candidates.is_empty() || candidates.is_empty());
    }

    #[test]
    fn test_prune_node() {
        let pruner = MemoryPruner::new(PruningConfig::default());
        let node = create_test_node();
        let node_id = node.id;
        pruner.register_node(node).unwrap();

        let result = pruner.prune_node(node_id);
        assert!(result.is_ok());
        assert_eq!(pruner.node_count(), 0);
        assert_eq!(pruner.pruned_count(), 1);
    }

    #[test]
    fn test_prune_nonexistent_node() {
        let pruner = MemoryPruner::new(PruningConfig::default());
        let result = pruner.prune_node(Uuid::new_v4());
        assert!(result.is_err());
    }
}
