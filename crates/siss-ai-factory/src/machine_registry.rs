use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

use crate::error::{AiFactoryError, Result};

/// Machine health status
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Offline,
}

/// Health check report for a single machine
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MachineHealth {
    pub machine_id: Uuid,
    pub status: HealthStatus,
    pub last_check: DateTime<Utc>,
    pub uptime_seconds: u64,
    pub message_latency_ms: u64,
}

/// Overall health report for all machines
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HealthReport {
    pub timestamp: DateTime<Utc>,
    pub machines: Vec<MachineHealth>,
    pub primary_healthy: bool,
    pub replicas_healthy: usize,
}

/// Mac Studio machine metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MachineMeta {
    pub id: Uuid,
    pub hostname: String,
    pub mac_model: String,          // "Mac Studio M2 Ultra"
    pub region: String,             // "EU" | "US" | "APAC"
    pub ip_address: String,
    pub ssh_key_hash: [u8; 32],     // ed25519 public key hash
    pub enrolled_at: DateTime<Utc>,
}

/// Machine registry for 3x Mac Studio enrollment and management
pub struct MachineRegistry {
    machines: Arc<DashMap<Uuid, MachineMeta>>,
}

impl MachineRegistry {
    /// Create new machine registry
    pub fn new() -> Self {
        Self {
            machines: Arc::new(DashMap::new()),
        }
    }

    /// Enroll a new machine
    pub fn enroll(&self, meta: MachineMeta) -> Result<Uuid> {
        let id = meta.id;
        self.machines.insert(id, meta);
        Ok(id)
    }

    /// Get machine by ID
    pub fn get(&self, id: Uuid) -> Result<MachineMeta> {
        self.machines
            .get(&id)
            .map(|ref_multi| ref_multi.clone())
            .ok_or(AiFactoryError::MachineNotFound(id))
    }

    /// Get primary region machine (EU)
    pub fn get_primary_region(&self) -> Result<MachineMeta> {
        self.machines
            .iter()
            .find(|ref_multi| ref_multi.region == "EU")
            .map(|ref_multi| ref_multi.clone())
            .ok_or(AiFactoryError::NoPrimaryRegion)
    }

    /// Get replica machines (US, APAC)
    pub fn get_replicas(&self) -> Result<Vec<MachineMeta>> {
        Ok(self
            .machines
            .iter()
            .filter(|ref_multi| ref_multi.region != "EU")
            .map(|ref_multi| ref_multi.clone())
            .collect())
    }

    /// Get all machines
    pub fn get_all(&self) -> Vec<MachineMeta> {
        self.machines.iter().map(|ref_multi| ref_multi.clone()).collect()
    }

    /// Get machine count
    pub fn machine_count(&self) -> usize {
        self.machines.len()
    }

    /// Health check all machines (simulated)
    pub fn health_check_all(&self) -> Result<HealthReport> {
        let machines = self.get_all();

        if machines.is_empty() {
            return Ok(HealthReport {
                timestamp: Utc::now(),
                machines: Vec::new(),
                primary_healthy: false,
                replicas_healthy: 0,
            });
        }

        let mut report = Vec::new();
        let mut primary_healthy = false;
        let mut replicas_healthy = 0;

        for machine in machines {
            let status = if machine.region == "EU" {
                primary_healthy = true;
                HealthStatus::Healthy
            } else {
                replicas_healthy += 1;
                HealthStatus::Healthy
            };

            report.push(MachineHealth {
                machine_id: machine.id,
                status,
                last_check: Utc::now(),
                uptime_seconds: 86400,  // simulated 1 day uptime
                message_latency_ms: match machine.region.as_str() {
                    "EU" => 5,
                    "US" => 120,
                    "APAC" => 180,
                    _ => 100,
                },
            });
        }

        Ok(HealthReport {
            timestamp: Utc::now(),
            machines: report,
            primary_healthy,
            replicas_healthy,
        })
    }

    /// Get machines by region
    pub fn get_by_region(&self, region: &str) -> Vec<MachineMeta> {
        self.machines
            .iter()
            .filter(|ref_multi| ref_multi.region == region)
            .map(|ref_multi| ref_multi.clone())
            .collect()
    }

    /// Remove a machine from registry (unenroll)
    pub fn remove(&self, id: Uuid) -> Result<MachineMeta> {
        self.machines
            .remove(&id)
            .map(|(_, meta)| meta)
            .ok_or(AiFactoryError::MachineNotFound(id))
    }
}

impl Default for MachineRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_machine_registry_new() {
        let registry = MachineRegistry::new();
        assert_eq!(registry.machine_count(), 0);
    }

    #[test]
    fn test_machine_registry_enroll() {
        let registry = MachineRegistry::new();
        let id = Uuid::new_v4();
        let meta = MachineMeta {
            id,
            hostname: "mac-studio-1".to_string(),
            mac_model: "Mac Studio M2 Ultra".to_string(),
            region: "EU".to_string(),
            ip_address: "192.168.1.1".to_string(),
            ssh_key_hash: [0u8; 32],
            enrolled_at: Utc::now(),
        };

        let enrolled_id = registry.enroll(meta).unwrap();
        assert_eq!(enrolled_id, id);
        assert_eq!(registry.machine_count(), 1);
    }

    #[test]
    fn test_machine_registry_get_primary() {
        let registry = MachineRegistry::new();
        let eu_id = Uuid::new_v4();
        registry
            .enroll(MachineMeta {
                id: eu_id,
                hostname: "mac-eu".to_string(),
                mac_model: "Mac Studio M2 Ultra".to_string(),
                region: "EU".to_string(),
                ip_address: "192.168.1.1".to_string(),
                ssh_key_hash: [0u8; 32],
                enrolled_at: Utc::now(),
            })
            .unwrap();

        let primary = registry.get_primary_region().unwrap();
        assert_eq!(primary.id, eu_id);
        assert_eq!(primary.region, "EU");
    }

    #[test]
    fn test_machine_registry_enroll_3_regions() {
        let registry = MachineRegistry::new();

        let eu_id = Uuid::new_v4();
        let us_id = Uuid::new_v4();
        let apac_id = Uuid::new_v4();

        registry
            .enroll(MachineMeta {
                id: eu_id,
                hostname: "mac-eu".to_string(),
                mac_model: "Mac Studio M2 Ultra".to_string(),
                region: "EU".to_string(),
                ip_address: "192.168.1.1".to_string(),
                ssh_key_hash: [0u8; 32],
                enrolled_at: Utc::now(),
            })
            .unwrap();

        registry
            .enroll(MachineMeta {
                id: us_id,
                hostname: "mac-us".to_string(),
                mac_model: "Mac Studio M2 Ultra".to_string(),
                region: "US".to_string(),
                ip_address: "192.168.1.2".to_string(),
                ssh_key_hash: [1u8; 32],
                enrolled_at: Utc::now(),
            })
            .unwrap();

        registry
            .enroll(MachineMeta {
                id: apac_id,
                hostname: "mac-apac".to_string(),
                mac_model: "Mac Studio M2 Ultra".to_string(),
                region: "APAC".to_string(),
                ip_address: "192.168.1.3".to_string(),
                ssh_key_hash: [2u8; 32],
                enrolled_at: Utc::now(),
            })
            .unwrap();

        assert_eq!(registry.machine_count(), 3);

        let primary = registry.get_primary_region().unwrap();
        assert_eq!(primary.region, "EU");

        let replicas = registry.get_replicas().unwrap();
        assert_eq!(replicas.len(), 2);
    }

    #[test]
    fn test_machine_registry_health_check_all() {
        let registry = MachineRegistry::new();

        registry
            .enroll(MachineMeta {
                id: Uuid::new_v4(),
                hostname: "mac-eu".to_string(),
                mac_model: "Mac Studio M2 Ultra".to_string(),
                region: "EU".to_string(),
                ip_address: "192.168.1.1".to_string(),
                ssh_key_hash: [0u8; 32],
                enrolled_at: Utc::now(),
            })
            .unwrap();

        registry
            .enroll(MachineMeta {
                id: Uuid::new_v4(),
                hostname: "mac-us".to_string(),
                mac_model: "Mac Studio M2 Ultra".to_string(),
                region: "US".to_string(),
                ip_address: "192.168.1.2".to_string(),
                ssh_key_hash: [1u8; 32],
                enrolled_at: Utc::now(),
            })
            .unwrap();

        let report = registry.health_check_all().unwrap();
        assert_eq!(report.machines.len(), 2);
        assert!(report.primary_healthy);
        assert_eq!(report.replicas_healthy, 1);
    }
}
