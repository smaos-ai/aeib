use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum MonitoringError {
    #[error("Chain verification failed: {0}")]
    VerificationFailed(String),
    #[error("Tampering detected: {0}")]
    TamperingDetected(String),
    #[error("Database error: {0}")]
    DatabaseError(String),
}

pub type MonitoringResult<T> = Result<T, MonitoringError>;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChainVerification {
    pub status: HealthStatus,
    pub entries_verified: usize,
    pub last_verified_at: DateTime<Utc>,
    pub next_check_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TamperAlert {
    pub entry_id: i64,
    pub expected_hash: String,
    pub actual_hash: String,
    pub detected_at: DateTime<Utc>,
    pub severity: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TamperAlerts {
    pub alerts: Vec<TamperAlert>,
    pub total_compromised: usize,
}

/// Merkle chain integrity monitor
pub struct MerkleChainMonitor {
    // In production, this would hold a PgPool
    // For testing, we use trait-based dependency injection
}

impl MerkleChainMonitor {
    pub fn new() -> Self {
        Self {}
    }

    /// Verify Merkle chain integrity by re-computing hashes
    /// Returns health status and count of verified entries
    pub async fn verify_chain_integrity(&self) -> MonitoringResult<ChainVerification> {
        // Placeholder for production implementation
        // This will:
        // 1. Fetch all exec_log entries in order
        // 2. For each entry, re-compute the merkle_hash
        // 3. Compare expected vs stored hash
        // 4. Return status and entry count
        Err(MonitoringError::DatabaseError(
            "Not implemented".to_string(),
        ))
    }

    /// Detect tampering by comparing computed vs stored hashes
    /// Fail-loud: returns all mismatches as TamperAlerts
    pub async fn detect_tampering(&self) -> MonitoringResult<TamperAlerts> {
        // Placeholder for production implementation
        // This will:
        // 1. Re-compute hash for each entry
        // 2. Compare with stored merkle_hash
        // 3. Collect all mismatches
        // 4. Return TamperAlerts with detailed info
        Err(MonitoringError::DatabaseError(
            "Not implemented".to_string(),
        ))
    }

    /// Check if chain is sound (all entries verify)
    pub async fn is_chain_sound(&self) -> MonitoringResult<bool> {
        let verification = self.verify_chain_integrity().await?;
        Ok(verification.status == HealthStatus::Healthy)
    }
}

impl Default for MerkleChainMonitor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_health_status_equality() {
        assert_eq!(HealthStatus::Healthy, HealthStatus::Healthy);
        assert_ne!(HealthStatus::Healthy, HealthStatus::Degraded);
        assert_ne!(HealthStatus::Degraded, HealthStatus::Critical);
    }

    #[test]
    fn test_health_status_serializable() {
        let status = HealthStatus::Healthy;
        let json = serde_json::to_string(&status);
        assert!(json.is_ok(), "HealthStatus should be JSON serializable");
    }

    #[test]
    fn test_chain_verification_creation() {
        let now = Utc::now();
        let verification = ChainVerification {
            status: HealthStatus::Healthy,
            entries_verified: 1000,
            last_verified_at: now,
            next_check_at: now,
        };
        assert_eq!(verification.status, HealthStatus::Healthy);
        assert_eq!(verification.entries_verified, 1000);
    }

    #[test]
    fn test_monitor_creation() {
        let monitor = MerkleChainMonitor::new();
        // Verify it's created successfully
        let _default_monitor = MerkleChainMonitor::default();
        // Both should be instantiable without error
        drop(monitor);
    }

    #[test]
    fn test_tamper_alert_structure() {
        let alert = TamperAlert {
            entry_id: 42,
            expected_hash: "aaaaaabbbbbbcccccc".to_string(),
            actual_hash: "ddddddeeeeeefffff".to_string(),
            detected_at: Utc::now(),
            severity: "critical".to_string(),
        };
        assert_eq!(alert.entry_id, 42);
        assert_ne!(alert.expected_hash, alert.actual_hash);
        assert_eq!(alert.severity, "critical");
    }

    #[test]
    fn test_tamper_alert_serializable() {
        let alert = TamperAlert {
            entry_id: 1,
            expected_hash: "abc".to_string(),
            actual_hash: "def".to_string(),
            detected_at: Utc::now(),
            severity: "critical".to_string(),
        };
        let json = serde_json::to_string(&alert);
        assert!(json.is_ok(), "TamperAlert should be JSON serializable");
    }

    #[test]
    fn test_tamper_alerts_collection() {
        let alerts = vec![
            TamperAlert {
                entry_id: 1,
                expected_hash: "aaa".to_string(),
                actual_hash: "bbb".to_string(),
                detected_at: Utc::now(),
                severity: "critical".to_string(),
            },
            TamperAlert {
                entry_id: 2,
                expected_hash: "ccc".to_string(),
                actual_hash: "ddd".to_string(),
                detected_at: Utc::now(),
                severity: "critical".to_string(),
            },
        ];
        let tamper_alerts = TamperAlerts {
            alerts: alerts.clone(),
            total_compromised: 2,
        };
        assert_eq!(tamper_alerts.alerts.len(), 2);
        assert_eq!(tamper_alerts.total_compromised, 2);
        assert!(tamper_alerts.alerts[0].expected_hash != tamper_alerts.alerts[0].actual_hash);
    }

    #[test]
    fn test_tamper_alerts_empty() {
        let alerts = TamperAlerts {
            alerts: vec![],
            total_compromised: 0,
        };
        assert_eq!(alerts.alerts.len(), 0);
        assert_eq!(alerts.total_compromised, 0);
    }

    #[test]
    fn test_monitoring_error_messages() {
        let error = MonitoringError::VerificationFailed("hash mismatch".to_string());
        assert!(format!("{}", error).contains("verification failed"));

        let tamper_error = MonitoringError::TamperingDetected("entry 42 tampered".to_string());
        assert!(format!("{}", tamper_error).contains("Tampering detected"));

        let db_error = MonitoringError::DatabaseError("query failed".to_string());
        assert!(format!("{}", db_error).contains("Database error"));
    }

    #[test]
    fn test_chain_verification_serializable() {
        let verification = ChainVerification {
            status: HealthStatus::Healthy,
            entries_verified: 500,
            last_verified_at: Utc::now(),
            next_check_at: Utc::now(),
        };
        let json = serde_json::to_string(&verification);
        assert!(
            json.is_ok(),
            "ChainVerification should be JSON serializable"
        );
    }
}
