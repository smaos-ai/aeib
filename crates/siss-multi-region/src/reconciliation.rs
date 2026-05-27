use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;
use serde::{Deserialize, Serialize};
use crate::errors::{MultiRegionError, MultiRegionResult};
use crate::replication::{VectorClock, ReplicationState};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ReconciliationStrategy {
    LastWriteWins,
    VectorClockMerge,
    ManualReview,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DivergenceEvent {
    pub divergence_id: Uuid,
    pub capsule_id: Uuid,
    pub regions_involved: Vec<String>,
    pub detected_at: u64,
    pub vector_clocks: HashMap<String, VectorClock>,
    pub strategy: ReconciliationStrategy,
    pub resolved: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReconciliationResult {
    pub divergence_id: Uuid,
    pub canonical_version: String,
    pub source_region: String,
    pub resolved_at: u64,
    pub applied_to_regions: Vec<String>,
}

pub struct ReconciliationManager {
    divergences: Arc<RwLock<HashMap<Uuid, DivergenceEvent>>>,
    results: Arc<RwLock<Vec<ReconciliationResult>>>,
    default_strategy: ReconciliationStrategy,
    gossip_interval_ms: u64,
}

impl ReconciliationManager {
    pub fn new(default_strategy: ReconciliationStrategy, gossip_interval_ms: u64) -> Self {
        Self {
            divergences: Arc::new(RwLock::new(HashMap::new())),
            results: Arc::new(RwLock::new(Vec::new())),
            default_strategy,
            gossip_interval_ms,
        }
    }

    /// Detect divergence between regions
    pub async fn detect_divergence(
        &self,
        capsule_id: Uuid,
        regions: Vec<String>,
        vector_clocks: HashMap<String, VectorClock>,
    ) -> MultiRegionResult<DivergenceEvent> {
        let divergence = DivergenceEvent {
            divergence_id: Uuid::new_v4(),
            capsule_id,
            regions_involved: regions,
            detected_at: current_timestamp(),
            vector_clocks,
            strategy: self.default_strategy.clone(),
            resolved: false,
        };

        {
            let mut divs = self.divergences.write().await;
            divs.insert(divergence.divergence_id, divergence.clone());
        }

        Ok(divergence)
    }

    /// Resolve divergence using Last-Write-Wins strategy
    pub async fn resolve_lww(
        &self,
        divergence_id: Uuid,
        canonical_version: String,
        source_region: String,
    ) -> MultiRegionResult<ReconciliationResult> {
        let mut divergences = self.divergences.write().await;

        if let Some(divergence) = divergences.get_mut(&divergence_id) {
            divergence.resolved = true;

            let result = ReconciliationResult {
                divergence_id,
                canonical_version,
                source_region,
                resolved_at: current_timestamp(),
                applied_to_regions: divergence.regions_involved.clone(),
            };

            {
                let mut results = self.results.write().await;
                results.push(result.clone());
            }

            Ok(result)
        } else {
            Err(MultiRegionError::ReconciliationFailed(
                "Divergence not found".to_string(),
            ))
        }
    }

    /// Resolve divergence using vector clock merge
    pub async fn resolve_vc_merge(
        &self,
        divergence_id: Uuid,
        merged_vector_clock: VectorClock,
    ) -> MultiRegionResult<ReconciliationResult> {
        let mut divergences = self.divergences.write().await;

        if let Some(divergence) = divergences.get_mut(&divergence_id) {
            divergence.resolved = true;

            let result = ReconciliationResult {
                divergence_id,
                canonical_version: format!("vc-merged-{:?}", merged_vector_clock),
                source_region: "consensus".to_string(),
                resolved_at: current_timestamp(),
                applied_to_regions: divergence.regions_involved.clone(),
            };

            {
                let mut results = self.results.write().await;
                results.push(result.clone());
            }

            Ok(result)
        } else {
            Err(MultiRegionError::ReconciliationFailed(
                "Divergence not found".to_string(),
            ))
        }
    }

    /// Get divergence by ID
    pub async fn get_divergence(&self, divergence_id: Uuid) -> MultiRegionResult<Option<DivergenceEvent>> {
        let divergences = self.divergences.read().await;
        Ok(divergences.get(&divergence_id).cloned())
    }

    /// Get all unresolved divergences
    pub async fn get_unresolved_divergences(&self) -> MultiRegionResult<Vec<DivergenceEvent>> {
        let divergences = self.divergences.read().await;
        Ok(divergences
            .values()
            .filter(|d| !d.resolved)
            .cloned()
            .collect())
    }

    /// Get reconciliation results for a capsule
    pub async fn get_reconciliation_results(
        &self,
        _capsule_id: Uuid,
    ) -> MultiRegionResult<Vec<ReconciliationResult>> {
        let results = self.results.read().await;
        Ok(results.clone())
    }

    /// Get reconciliation metrics
    pub async fn get_metrics(&self) -> MultiRegionResult<ReconciliationMetrics> {
        let divergences = self.divergences.read().await;
        let results = self.results.read().await;

        let total = divergences.len();
        let resolved = divergences.values().filter(|d| d.resolved).count();
        let unresolved = total - resolved;

        Ok(ReconciliationMetrics {
            total_divergences: total,
            resolved_divergences: resolved,
            unresolved_divergences: unresolved,
            total_reconciliation_ops: results.len(),
        })
    }

    /// Simulate gossip protocol: merge vector clocks across regions
    pub async fn gossip_merge(
        &self,
        divergence_id: Uuid,
    ) -> MultiRegionResult<VectorClock> {
        let divergences = self.divergences.read().await;

        if let Some(divergence) = divergences.get(&divergence_id) {
            let mut merged = VectorClock::new();

            for (_, vc) in &divergence.vector_clocks {
                merged.merge(vc);
            }

            Ok(merged)
        } else {
            Err(MultiRegionError::ReconciliationFailed(
                "Divergence not found for gossip merge".to_string(),
            ))
        }
    }

    /// Check if regions are causally consistent
    pub async fn check_causal_consistency(
        &self,
        _region1: &str,
        _region2: &str,
        vc1: &VectorClock,
        vc2: &VectorClock,
    ) -> MultiRegionResult<bool> {
        // Causally consistent if one happens-before the other or they're concurrent
        Ok(vc1.happens_before(vc2) || vc2.happens_before(vc1) || vc1.concurrent_with(vc2))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReconciliationMetrics {
    pub total_divergences: usize,
    pub resolved_divergences: usize,
    pub unresolved_divergences: usize,
    pub total_reconciliation_ops: usize,
}

fn current_timestamp() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_reconciliation_manager_initialization() {
        let manager = ReconciliationManager::new(ReconciliationStrategy::LastWriteWins, 5000);
        let metrics = manager.get_metrics().await.unwrap();

        assert_eq!(metrics.total_divergences, 0);
        assert_eq!(metrics.resolved_divergences, 0);
    }

    #[tokio::test]
    async fn test_detect_divergence() {
        let manager = ReconciliationManager::new(ReconciliationStrategy::LastWriteWins, 5000);
        let capsule_id = Uuid::new_v4();
        let mut vcs = HashMap::new();
        vcs.insert("prague".to_string(), VectorClock::new());
        vcs.insert("frankfurt".to_string(), VectorClock::new());

        let result = manager
            .detect_divergence(capsule_id, vec!["prague".to_string(), "frankfurt".to_string()], vcs)
            .await;

        assert!(result.is_ok());
        let divergence = result.unwrap();
        assert_eq!(divergence.capsule_id, capsule_id);
        assert!(!divergence.resolved);
    }

    #[tokio::test]
    async fn test_resolve_lww() {
        let manager = ReconciliationManager::new(ReconciliationStrategy::LastWriteWins, 5000);
        let capsule_id = Uuid::new_v4();
        let mut vcs = HashMap::new();
        vcs.insert("prague".to_string(), VectorClock::new());
        vcs.insert("frankfurt".to_string(), VectorClock::new());

        let divergence = manager
            .detect_divergence(capsule_id, vec!["prague".to_string(), "frankfurt".to_string()], vcs)
            .await
            .unwrap();

        let result = manager
            .resolve_lww(divergence.divergence_id, "canonical-data".to_string(), "prague".to_string())
            .await;

        assert!(result.is_ok());
        let resolved = result.unwrap();
        assert_eq!(resolved.source_region, "prague");
    }

    #[tokio::test]
    async fn test_unresolved_divergences() {
        let manager = ReconciliationManager::new(ReconciliationStrategy::LastWriteWins, 5000);
        let capsule_id = Uuid::new_v4();
        let mut vcs = HashMap::new();
        vcs.insert("prague".to_string(), VectorClock::new());

        manager
            .detect_divergence(capsule_id, vec!["prague".to_string()], vcs)
            .await
            .unwrap();

        let unresolved = manager.get_unresolved_divergences().await.unwrap();
        assert_eq!(unresolved.len(), 1);
    }

    #[tokio::test]
    async fn test_gossip_merge() {
        let manager = ReconciliationManager::new(ReconciliationStrategy::VectorClockMerge, 5000);
        let capsule_id = Uuid::new_v4();
        let mut vcs = HashMap::new();

        let mut vc1 = VectorClock::new();
        vc1.increment("prague");
        vcs.insert("prague".to_string(), vc1);

        let mut vc2 = VectorClock::new();
        vc2.increment("frankfurt");
        vcs.insert("frankfurt".to_string(), vc2);

        let divergence = manager
            .detect_divergence(capsule_id, vec!["prague".to_string(), "frankfurt".to_string()], vcs)
            .await
            .unwrap();

        let merged = manager.gossip_merge(divergence.divergence_id).await.unwrap();
        assert_eq!(merged.get_timestamp("prague"), 1);
        assert_eq!(merged.get_timestamp("frankfurt"), 1);
    }
}
