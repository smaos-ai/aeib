use std::time::{Duration, Instant};
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;
use serde::{Deserialize, Serialize};
use crate::errors::{MultiRegionError, MultiRegionResult};

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum SyncStatus {
    Pending,
    InProgress,
    Completed,
    Failed,
    Timeout,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SyncRecord {
    pub sync_id: Uuid,
    pub capsule_id: Uuid,
    pub source_region: String,
    pub target_region: String,
    pub status: SyncStatus,
    pub started_at: u64,
    pub completed_at: Option<u64>,
    pub duration_ms: Option<u64>,
    pub bytes_synced: u64,
}

impl SyncRecord {
    pub fn new(capsule_id: Uuid, source: String, target: String) -> Self {
        Self {
            sync_id: Uuid::new_v4(),
            capsule_id,
            source_region: source,
            target_region: target,
            status: SyncStatus::Pending,
            started_at: current_timestamp(),
            completed_at: None,
            duration_ms: None,
            bytes_synced: 0,
        }
    }
}

pub struct CapsuleSyncManager {
    sync_records: Arc<RwLock<Vec<SyncRecord>>>,
    sync_timeout_ms: u64,
    max_concurrent_syncs: usize,
    active_syncs: Arc<RwLock<usize>>,
}

impl CapsuleSyncManager {
    pub fn new(sync_timeout_ms: u64, max_concurrent_syncs: usize) -> Self {
        Self {
            sync_records: Arc::new(RwLock::new(Vec::new())),
            sync_timeout_ms,
            max_concurrent_syncs,
            active_syncs: Arc::new(RwLock::new(0)),
        }
    }

    /// Initiate sync of a capsule between regions
    pub async fn initiate_sync(
        &self,
        capsule_id: Uuid,
        source_region: String,
        target_region: String,
        data_size_bytes: u64,
    ) -> MultiRegionResult<SyncRecord> {
        // Check if we can start a new sync
        let active = self.active_syncs.read().await;
        if *active >= self.max_concurrent_syncs {
            return Err(MultiRegionError::SyncTimeout(
                "Max concurrent syncs reached".to_string(),
            ));
        }
        drop(active);

        let mut record = SyncRecord::new(capsule_id, source_region, target_region);
        record.bytes_synced = data_size_bytes;
        record.status = SyncStatus::InProgress;

        {
            let mut records = self.sync_records.write().await;
            records.push(record.clone());
        }

        // Increment active sync counter
        {
            let mut active = self.active_syncs.write().await;
            *active += 1;
        }

        Ok(record)
    }

    /// Mark sync as completed
    pub async fn complete_sync(&self, sync_id: Uuid) -> MultiRegionResult<()> {
        let now = current_timestamp();

        {
            let mut records = self.sync_records.write().await;
            if let Some(record) = records.iter_mut().find(|r| r.sync_id == sync_id) {
                record.status = SyncStatus::Completed;
                record.completed_at = Some(now);
                record.duration_ms = Some(now - record.started_at);
            }
        }

        // Decrement active sync counter
        {
            let mut active = self.active_syncs.write().await;
            if *active > 0 {
                *active -= 1;
            }
        }

        Ok(())
    }

    /// Mark sync as failed
    pub async fn fail_sync(&self, sync_id: Uuid, _reason: &str) -> MultiRegionResult<()> {
        let now = current_timestamp();

        {
            let mut records = self.sync_records.write().await;
            if let Some(record) = records.iter_mut().find(|r| r.sync_id == sync_id) {
                record.status = SyncStatus::Failed;
                record.completed_at = Some(now);
                record.duration_ms = Some(now - record.started_at);
            }
        }

        // Decrement active sync counter
        {
            let mut active = self.active_syncs.write().await;
            if *active > 0 {
                *active -= 1;
            }
        }

        Ok(())
    }

    /// Get sync record by ID
    pub async fn get_sync_record(&self, sync_id: Uuid) -> MultiRegionResult<Option<SyncRecord>> {
        let records = self.sync_records.read().await;
        Ok(records.iter().find(|r| r.sync_id == sync_id).cloned())
    }

    /// Get all syncs for a specific capsule
    pub async fn get_capsule_syncs(&self, capsule_id: Uuid) -> MultiRegionResult<Vec<SyncRecord>> {
        let records = self.sync_records.read().await;
        Ok(records
            .iter()
            .filter(|r| r.capsule_id == capsule_id)
            .cloned()
            .collect())
    }

    /// Get sync metrics
    pub async fn get_metrics(&self) -> MultiRegionResult<SyncMetrics> {
        let records = self.sync_records.read().await;

        let total = records.len();
        let completed = records.iter().filter(|r| r.status == SyncStatus::Completed).count();
        let failed = records.iter().filter(|r| r.status == SyncStatus::Failed).count();
        let in_progress = records.iter().filter(|r| r.status == SyncStatus::InProgress).count();

        let avg_duration_ms = if completed > 0 {
            let total_duration: u64 = records
                .iter()
                .filter(|r| r.status == SyncStatus::Completed)
                .filter_map(|r| r.duration_ms)
                .sum();
            total_duration / completed as u64
        } else {
            0
        };

        let total_bytes_synced: u64 = records.iter().map(|r| r.bytes_synced).sum();

        Ok(SyncMetrics {
            total_syncs: total,
            completed_syncs: completed,
            failed_syncs: failed,
            in_progress_syncs: in_progress,
            avg_duration_ms,
            total_bytes_synced,
        })
    }

    /// Check for stalled syncs and mark as timeout
    pub async fn check_stalled_syncs(&self) -> MultiRegionResult<usize> {
        let now = current_timestamp();
        let mut stalled_count = 0;

        {
            let mut records = self.sync_records.write().await;
            for record in records.iter_mut() {
                if record.status == SyncStatus::InProgress {
                    if now - record.started_at > self.sync_timeout_ms {
                        record.status = SyncStatus::Timeout;
                        record.completed_at = Some(now);
                        record.duration_ms = Some(now - record.started_at);
                        stalled_count += 1;
                    }
                }
            }
        }

        // Adjust active sync counter
        if stalled_count > 0 {
            let mut active = self.active_syncs.write().await;
            *active = (*active).saturating_sub(stalled_count);
        }

        Ok(stalled_count)
    }

    /// Get active sync count
    pub async fn get_active_sync_count(&self) -> MultiRegionResult<usize> {
        let active = self.active_syncs.read().await;
        Ok(*active)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SyncMetrics {
    pub total_syncs: usize,
    pub completed_syncs: usize,
    pub failed_syncs: usize,
    pub in_progress_syncs: usize,
    pub avg_duration_ms: u64,
    pub total_bytes_synced: u64,
}

fn current_timestamp() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_sync_manager_initialization() {
        let manager = CapsuleSyncManager::new(100000, 10);
        let metrics = manager.get_metrics().await.unwrap();

        assert_eq!(metrics.total_syncs, 0);
        assert_eq!(metrics.completed_syncs, 0);
    }

    #[tokio::test]
    async fn test_initiate_sync() {
        let manager = CapsuleSyncManager::new(100000, 10);
        let capsule_id = Uuid::new_v4();

        let result = manager
            .initiate_sync(capsule_id, "prague".to_string(), "frankfurt".to_string(), 1000)
            .await;

        assert!(result.is_ok());
        let record = result.unwrap();
        assert_eq!(record.capsule_id, capsule_id);
        assert_eq!(record.status, SyncStatus::InProgress);
    }

    #[tokio::test]
    async fn test_complete_sync() {
        let manager = CapsuleSyncManager::new(100000, 10);
        let capsule_id = Uuid::new_v4();

        let record = manager
            .initiate_sync(capsule_id, "prague".to_string(), "frankfurt".to_string(), 1000)
            .await
            .unwrap();

        manager.complete_sync(record.sync_id).await.unwrap();

        let completed = manager.get_sync_record(record.sync_id).await.unwrap();
        assert!(completed.is_some());
        assert_eq!(completed.unwrap().status, SyncStatus::Completed);
    }

    #[tokio::test]
    async fn test_max_concurrent_syncs() {
        let manager = CapsuleSyncManager::new(100000, 2);

        let capsule1 = Uuid::new_v4();
        let capsule2 = Uuid::new_v4();
        let capsule3 = Uuid::new_v4();

        manager
            .initiate_sync(capsule1, "prague".to_string(), "frankfurt".to_string(), 1000)
            .await
            .unwrap();

        manager
            .initiate_sync(capsule2, "prague".to_string(), "frankfurt".to_string(), 1000)
            .await
            .unwrap();

        let result = manager
            .initiate_sync(capsule3, "prague".to_string(), "frankfurt".to_string(), 1000)
            .await;

        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_sync_metrics() {
        let manager = CapsuleSyncManager::new(100000, 10);
        let capsule_id = Uuid::new_v4();

        let record = manager
            .initiate_sync(capsule_id, "prague".to_string(), "frankfurt".to_string(), 5000)
            .await
            .unwrap();

        manager.complete_sync(record.sync_id).await.unwrap();

        let metrics = manager.get_metrics().await.unwrap();
        assert_eq!(metrics.total_syncs, 1);
        assert_eq!(metrics.completed_syncs, 1);
        assert_eq!(metrics.total_bytes_synced, 5000);
    }

    #[tokio::test]
    async fn test_check_stalled_syncs() {
        let manager = CapsuleSyncManager::new(100, 10); // Very short timeout
        let capsule_id = Uuid::new_v4();

        manager
            .initiate_sync(capsule_id, "prague".to_string(), "frankfurt".to_string(), 1000)
            .await
            .unwrap();

        tokio::time::sleep(tokio::time::Duration::from_millis(200)).await;

        let stalled = manager.check_stalled_syncs().await.unwrap();
        assert_eq!(stalled, 1);
    }
}
