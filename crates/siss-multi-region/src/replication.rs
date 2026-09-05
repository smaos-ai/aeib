use crate::errors::{MultiRegionError, MultiRegionResult};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// Represents a causality-tracking vector clock for eventual consistency
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct VectorClock {
    clock: HashMap<String, u64>,
}

impl VectorClock {
    pub fn new() -> Self {
        VectorClock {
            clock: HashMap::new(),
        }
    }

    pub fn increment(&mut self, region: &str) {
        let entry = self.clock.entry(region.to_string()).or_insert(0);
        *entry += 1;
    }

    pub fn merge(&mut self, other: &VectorClock) {
        for (region, other_time) in &other.clock {
            let entry = self.clock.entry(region.clone()).or_insert(0);
            *entry = (*entry).max(*other_time);
        }
    }

    pub fn happens_before(&self, other: &VectorClock) -> bool {
        let mut some_lt = false;

        for (region, time) in &self.clock {
            let other_time = other.clock.get(region).copied().unwrap_or(0);
            if time > &other_time {
                return false;
            }
            if time < &other_time {
                some_lt = true;
            }
        }

        for region in other.clock.keys() {
            if !self.clock.contains_key(region) {
                some_lt = true;
            }
        }

        some_lt
    }

    pub fn concurrent_with(&self, other: &VectorClock) -> bool {
        !self.happens_before(other) && !other.happens_before(self)
    }

    pub fn get_timestamp(&self, region: &str) -> u64 {
        self.clock.get(region).copied().unwrap_or(0)
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string(&self.clock).unwrap_or_default()
    }
}

impl Default for VectorClock {
    fn default() -> Self {
        Self::new()
    }
}

/// Event triggered during replication
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplicationEvent {
    pub event_id: Uuid,
    pub capsule_id: Uuid,
    pub source_region: String,
    pub target_region: String,
    pub timestamp: u64,
    pub vector_clock: VectorClock,
    pub capsule_hash: String,
    pub status: ReplicationStatus,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ReplicationStatus {
    Pending,
    InProgress,
    Completed,
    Failed,
    Acknowledged,
}

/// Tracks replication state across regions
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplicationState {
    pub capsule_id: Uuid,
    pub source_region: String,
    pub target_regions: Vec<String>,
    pub replicated_to: HashMap<String, ReplicationStatus>,
    pub vector_clock: VectorClock,
    pub capsule_hash: String,
}

impl ReplicationState {
    pub fn new(capsule_id: Uuid, source_region: String, target_regions: Vec<String>) -> Self {
        let mut replicated_to = HashMap::new();
        for region in &target_regions {
            replicated_to.insert(region.clone(), ReplicationStatus::Pending);
        }

        Self {
            capsule_id,
            source_region,
            target_regions,
            replicated_to,
            vector_clock: VectorClock::new(),
            capsule_hash: String::new(),
        }
    }

    pub fn all_replicated(&self) -> bool {
        self.replicated_to
            .values()
            .all(|s| *s == ReplicationStatus::Completed)
    }

    pub fn any_failed(&self) -> bool {
        self.replicated_to
            .values()
            .any(|s| *s == ReplicationStatus::Failed)
    }

    pub fn mark_progress(&mut self, region: &str, status: ReplicationStatus) {
        self.replicated_to.insert(region.to_string(), status);
    }
}

/// Core multi-region replication engine
pub struct MultiRegionReplicator {
    primary_region: String,
    replica_regions: Vec<String>,
    events: Arc<RwLock<Vec<ReplicationEvent>>>,
    replication_states: Arc<RwLock<HashMap<Uuid, ReplicationState>>>,
    crdt_store: Arc<RwLock<CRDTStore>>,
}

/// Simple CRDT store for Last-Write-Wins conflict resolution
pub struct CRDTStore {
    values: HashMap<String, (String, u64)>, // (value, timestamp)
}

impl CRDTStore {
    pub fn new() -> Self {
        Self {
            values: HashMap::new(),
        }
    }

    pub fn merge(&mut self, key: &str, value: String, timestamp: u64) {
        if let Some((_, existing_ts)) = self.values.get(key) {
            if timestamp > *existing_ts {
                self.values.insert(key.to_string(), (value, timestamp));
            }
        } else {
            self.values.insert(key.to_string(), (value, timestamp));
        }
    }

    pub fn get(&self, key: &str) -> Option<String> {
        self.values.get(key).map(|(v, _)| v.clone())
    }
}

impl MultiRegionReplicator {
    pub fn new(primary_region: String, replica_regions: Vec<String>) -> Self {
        Self {
            primary_region,
            replica_regions,
            events: Arc::new(RwLock::new(Vec::new())),
            replication_states: Arc::new(RwLock::new(HashMap::new())),
            crdt_store: Arc::new(RwLock::new(CRDTStore::new())),
        }
    }

    /// Initiate replication of a capsule across all regions
    pub async fn replicate_capsule(
        &self,
        capsule_id: Uuid,
        capsule_data: &str,
        capsule_hash: &str,
    ) -> MultiRegionResult<ReplicationState> {
        // Validate hash
        let computed_hash = Self::compute_hash(capsule_data);
        if computed_hash != capsule_hash {
            return Err(MultiRegionError::InvalidCapsuleHash);
        }

        // Create replication state
        let mut state = ReplicationState::new(
            capsule_id,
            self.primary_region.clone(),
            self.replica_regions.clone(),
        );
        state.capsule_hash = capsule_hash.to_string();

        // Store replication state
        {
            let mut states = self.replication_states.write().await;
            states.insert(capsule_id, state.clone());
        }

        // Create replication event
        let event = ReplicationEvent {
            event_id: Uuid::new_v4(),
            capsule_id,
            source_region: self.primary_region.clone(),
            target_region: self.replica_regions.join(","),
            timestamp: current_timestamp(),
            vector_clock: VectorClock::new(),
            capsule_hash: capsule_hash.to_string(),
            status: ReplicationStatus::InProgress,
        };

        {
            let mut events = self.events.write().await;
            events.push(event);
        }

        Ok(state)
    }

    /// Acknowledge replication on a specific region
    pub async fn acknowledge_replication(
        &self,
        capsule_id: Uuid,
        region: &str,
    ) -> MultiRegionResult<()> {
        let mut states = self.replication_states.write().await;

        if let Some(state) = states.get_mut(&capsule_id) {
            state.mark_progress(region, ReplicationStatus::Completed);
            Ok(())
        } else {
            Err(MultiRegionError::ReplicationFailed {
                capsule_id: capsule_id.to_string(),
                reason: "Replication state not found".to_string(),
            })
        }
    }

    /// Mark replication failed on a region
    pub async fn mark_replication_failed(
        &self,
        capsule_id: Uuid,
        region: &str,
        reason: &str,
    ) -> MultiRegionResult<()> {
        let mut states = self.replication_states.write().await;

        if let Some(state) = states.get_mut(&capsule_id) {
            state.mark_progress(region, ReplicationStatus::Failed);
            Ok(())
        } else {
            Err(MultiRegionError::ReplicationFailed {
                capsule_id: capsule_id.to_string(),
                reason: reason.to_string(),
            })
        }
    }

    /// Check if replication is complete (all regions acknowledged)
    pub async fn is_replication_complete(&self, capsule_id: Uuid) -> MultiRegionResult<bool> {
        let states = self.replication_states.read().await;

        Ok(states
            .get(&capsule_id)
            .map(|s| s.all_replicated())
            .unwrap_or(false))
    }

    /// Get replication state for a capsule
    pub async fn get_replication_state(
        &self,
        capsule_id: Uuid,
    ) -> MultiRegionResult<Option<ReplicationState>> {
        let states = self.replication_states.read().await;
        Ok(states.get(&capsule_id).cloned())
    }

    /// Get all replication events for a capsule
    pub async fn get_replication_events(
        &self,
        capsule_id: Uuid,
    ) -> MultiRegionResult<Vec<ReplicationEvent>> {
        let events = self.events.read().await;
        Ok(events
            .iter()
            .filter(|e| e.capsule_id == capsule_id)
            .cloned()
            .collect())
    }

    /// Helper: compute SHA256 hash of capsule data
    fn compute_hash(data: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Get current replication metrics
    pub async fn get_metrics(&self) -> MultiRegionResult<ReplicationMetrics> {
        let states = self.replication_states.read().await;
        let events = self.events.read().await;

        let total_capsules = states.len();
        let replicated = states.values().filter(|s| s.all_replicated()).count();
        let failed = states.values().filter(|s| s.any_failed()).count();

        Ok(ReplicationMetrics {
            total_capsules,
            successfully_replicated: replicated,
            failed_replications: failed,
            total_events: events.len(),
        })
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplicationMetrics {
    pub total_capsules: usize,
    pub successfully_replicated: usize,
    pub failed_replications: usize,
    pub total_events: usize,
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

    #[test]
    fn test_vector_clock_happens_before() {
        let mut vc1 = VectorClock::new();
        vc1.increment("prague");

        let mut vc2 = VectorClock::new();
        vc2.increment("prague");
        vc2.increment("prague");

        assert!(vc1.happens_before(&vc2));
        assert!(!vc2.happens_before(&vc1));
    }

    #[test]
    fn test_vector_clock_concurrent() {
        let mut vc1 = VectorClock::new();
        vc1.increment("prague");

        let mut vc2 = VectorClock::new();
        vc2.increment("frankfurt");

        assert!(vc1.concurrent_with(&vc2));
    }

    #[tokio::test]
    async fn test_replicate_capsule_valid_hash() {
        let replicator =
            MultiRegionReplicator::new("prague".to_string(), vec!["frankfurt".to_string()]);

        let data = "test-capsule-data";
        let hash = MultiRegionReplicator::compute_hash(data);
        let capsule_id = Uuid::new_v4();

        let result = replicator.replicate_capsule(capsule_id, data, &hash).await;

        assert!(result.is_ok());
        let state = result.unwrap();
        assert_eq!(state.capsule_id, capsule_id);
    }

    #[tokio::test]
    async fn test_replicate_capsule_invalid_hash() {
        let replicator =
            MultiRegionReplicator::new("prague".to_string(), vec!["frankfurt".to_string()]);

        let capsule_id = Uuid::new_v4();
        let result = replicator
            .replicate_capsule(capsule_id, "data", "invalid-hash")
            .await;

        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_acknowledge_replication() {
        let replicator =
            MultiRegionReplicator::new("prague".to_string(), vec!["frankfurt".to_string()]);

        let data = "test";
        let hash = MultiRegionReplicator::compute_hash(data);
        let capsule_id = Uuid::new_v4();

        replicator
            .replicate_capsule(capsule_id, data, &hash)
            .await
            .unwrap();

        replicator
            .acknowledge_replication(capsule_id, "frankfurt")
            .await
            .unwrap();

        let is_complete = replicator
            .is_replication_complete(capsule_id)
            .await
            .unwrap();

        assert!(is_complete);
    }

    #[tokio::test]
    async fn test_crdt_last_write_wins() {
        let mut store = CRDTStore::new();
        store.merge("key1", "value1".to_string(), 100);
        store.merge("key1", "value2".to_string(), 200);

        assert_eq!(store.get("key1"), Some("value2".to_string()));

        store.merge("key1", "value3".to_string(), 150);
        assert_eq!(store.get("key1"), Some("value2".to_string()));
    }
}
