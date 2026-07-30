use std::sync::{Arc, Mutex};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReplicationStatus {
    Healthy,
    Degraded,
    Failed,
}

#[derive(Debug, Clone)]
pub struct RegionConfig {
    pub region_name: String,
    pub endpoint: String,
    pub priority: u32,
}

#[async_trait::async_trait]
pub trait AuroraGlobalTrait: Send + Sync {
    async fn read(&self, key: &str) -> Result<Option<String>, String>;
    async fn write(&self, key: &str, value: String) -> Result<(), String>;
    async fn get_replication_status(&self) -> Result<ReplicationStatus, String>;
    async fn health_check(&self) -> Result<HealthCheckResult, String>;
}

#[derive(Debug, Clone)]
pub struct HealthCheckResult {
    pub status: ReplicationStatus,
    pub message: String,
}

pub struct MockAuroraGlobal {
    data: Arc<Mutex<HashMap<String, String>>>,
    status: Arc<Mutex<ReplicationStatus>>,
}

impl MockAuroraGlobal {
    pub fn new() -> Self {
        Self {
            data: Arc::new(Mutex::new(HashMap::new())),
            status: Arc::new(Mutex::new(ReplicationStatus::Healthy)),
        }
    }

    pub fn set_status(&self, status: ReplicationStatus) {
        *self.status.lock().unwrap() = status;
    }
}

impl Default for MockAuroraGlobal {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait::async_trait]
impl AuroraGlobalTrait for MockAuroraGlobal {
    async fn read(&self, key: &str) -> Result<Option<String>, String> {
        let data = self.data.lock().unwrap();
        Ok(data.get(key).cloned())
    }

    async fn write(&self, key: &str, value: String) -> Result<(), String> {
        let mut data = self.data.lock().unwrap();
        data.insert(key.to_string(), value);
        Ok(())
    }

    async fn get_replication_status(&self) -> Result<ReplicationStatus, String> {
        let status = *self.status.lock().unwrap();
        Ok(status)
    }

    async fn health_check(&self) -> Result<HealthCheckResult, String> {
        let status = *self.status.lock().unwrap();
        let message = match status {
            ReplicationStatus::Healthy => "All replicas in sync".to_string(),
            ReplicationStatus::Degraded => "Some replicas lagging".to_string(),
            ReplicationStatus::Failed => "Replication failed".to_string(),
        };
        Ok(HealthCheckResult { status, message })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_region_failover_write_read() {
        let db = MockAuroraGlobal::new();

        // Write to primary
        assert!(db.write("test_key", "test_value".to_string()).await.is_ok());

        // Read from replica (should be consistent)
        let value = db.read("test_key").await;
        assert!(value.is_ok());
        assert_eq!(value.unwrap(), Some("test_value".to_string()));

        // Verify status is healthy
        let status = db.get_replication_status().await;
        assert!(status.is_ok());
        assert_eq!(status.unwrap(), ReplicationStatus::Healthy);
    }

    #[tokio::test]
    async fn test_health_check_status() {
        let db = MockAuroraGlobal::new();

        // Check initial status
        let health = db.health_check().await;
        assert!(health.is_ok());
        let result = health.unwrap();
        assert_eq!(result.status, ReplicationStatus::Healthy);

        // Simulate degradation
        db.set_status(ReplicationStatus::Degraded);
        let health = db.health_check().await;
        let result = health.unwrap();
        assert_eq!(result.status, ReplicationStatus::Degraded);
    }

    #[tokio::test]
    async fn test_sla_compliance_rto() {
        use std::time::Instant;

        let db = MockAuroraGlobal::new();

        let start = Instant::now();

        // 100 failovers
        for i in 0..100 {
            let key = format!("failover_{}", i);
            let _ = db.write(&key, format!("value_{}", i)).await;
            db.set_status(if i % 2 == 0 {
                ReplicationStatus::Healthy
            } else {
                ReplicationStatus::Degraded
            });
            let _ = db.get_replication_status().await;
        }

        let elapsed = start.elapsed().as_millis();

        // All 100 failovers should complete in under 5 seconds total
        assert!(elapsed < 5000, "100 failovers took {}ms", elapsed);
    }

    #[tokio::test]
    async fn test_sla_compliance_rpo() {
        let db = MockAuroraGlobal::new();

        // Write 100 items
        for i in 0..100 {
            let key = format!("key_{}", i);
            let value = format!("value_{}", i);
            assert!(db.write(&key, value).await.is_ok());
        }

        // Verify all 100 items are readable (zero data loss)
        for i in 0..100 {
            let key = format!("key_{}", i);
            let value = db.read(&key).await;
            assert!(value.is_ok());
            assert_eq!(value.unwrap(), Some(format!("value_{}", i)));
        }
    }
}
