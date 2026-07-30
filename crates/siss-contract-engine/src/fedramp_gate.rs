use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FedRampAuditReport {
    pub contract_id: Uuid,
    pub passed: bool,
    pub failed_controls: Vec<String>,
    pub remediation_time_days: u32,
    pub audit_timestamp: chrono::DateTime<chrono::Utc>,
}

pub struct FedRampGate {
    controls: Arc<DashMap<String, bool>>, // control_id -> is_compliant
}

impl FedRampGate {
    pub fn new() -> Self {
        Self {
            controls: Arc::new(DashMap::new()),
        }
    }

    pub fn bind_control(&self, control_id: &str, is_compliant: bool) {
        self.controls.insert(control_id.to_string(), is_compliant);
    }

    pub fn get_control_status(&self, control_id: &str) -> Option<bool> {
        self.controls.get(control_id).map(|entry| *entry.value())
    }

    pub async fn audit_compliance(&self, contract_id: Uuid) -> Result<FedRampAuditReport, crate::error::ContractError> {
        let mut failed_controls = Vec::new();

        for entry in self.controls.iter() {
            let (control_id, is_compliant) = (entry.key().clone(), *entry.value());
            if !is_compliant {
                failed_controls.push(control_id);
            }
        }

        let passed = failed_controls.is_empty();
        let remediation_time_days = if passed { 0 } else { 30 }; // 30-day remediation window

        Ok(FedRampAuditReport {
            contract_id,
            passed,
            failed_controls,
            remediation_time_days,
            audit_timestamp: chrono::Utc::now(),
        })
    }

    pub fn get_all_controls(&self) -> Vec<(String, bool)> {
        self.controls
            .iter()
            .map(|entry| (entry.key().clone(), *entry.value()))
            .collect()
    }

    pub fn get_compliant_count(&self) -> usize {
        self.controls
            .iter()
            .filter(|entry| *entry.value())
            .count()
    }

    pub fn get_non_compliant_count(&self) -> usize {
        self.controls
            .iter()
            .filter(|entry| !*entry.value())
            .count()
    }
}

impl Default for FedRampGate {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_fedramp_gate_all_compliant() {
        let gate = FedRampGate::new();
        let contract_id = Uuid::new_v4();

        gate.bind_control("AC-2", true);
        gate.bind_control("AC-3", true);
        gate.bind_control("AU-2", true);
        gate.bind_control("SC-7", true);

        let report = gate.audit_compliance(contract_id).await.unwrap();

        assert!(report.passed);
        assert_eq!(report.failed_controls.len(), 0);
        assert_eq!(report.remediation_time_days, 0);
    }

    #[tokio::test]
    async fn test_fedramp_gate_one_failed_control() {
        let gate = FedRampGate::new();
        let contract_id = Uuid::new_v4();

        gate.bind_control("AC-2", true);
        gate.bind_control("AC-3", true);
        gate.bind_control("AU-2", false);
        gate.bind_control("SC-7", true);

        let report = gate.audit_compliance(contract_id).await.unwrap();

        assert!(!report.passed);
        assert_eq!(report.failed_controls.len(), 1);
        assert!(report.failed_controls.contains(&"AU-2".to_string()));
        assert_eq!(report.remediation_time_days, 30);
    }

    #[tokio::test]
    async fn test_fedramp_gate_multiple_failed_controls() {
        let gate = FedRampGate::new();
        let contract_id = Uuid::new_v4();

        gate.bind_control("AC-2", false);
        gate.bind_control("AC-3", true);
        gate.bind_control("AU-2", false);
        gate.bind_control("SC-7", true);

        let report = gate.audit_compliance(contract_id).await.unwrap();

        assert!(!report.passed);
        assert_eq!(report.failed_controls.len(), 2);
        assert!(report.failed_controls.contains(&"AC-2".to_string()));
        assert!(report.failed_controls.contains(&"AU-2".to_string()));
    }

    #[test]
    fn test_fedramp_gate_bind_control() {
        let gate = FedRampGate::new();

        gate.bind_control("AC-2", true);

        let status = gate.get_control_status("AC-2");
        assert_eq!(status, Some(true));
    }

    #[test]
    fn test_fedramp_gate_control_counts() {
        let gate = FedRampGate::new();

        gate.bind_control("AC-2", true);
        gate.bind_control("AC-3", true);
        gate.bind_control("AU-2", false);
        gate.bind_control("SC-7", false);

        assert_eq!(gate.get_compliant_count(), 2);
        assert_eq!(gate.get_non_compliant_count(), 2);
    }

    #[test]
    fn test_fedramp_gate_get_all_controls() {
        let gate = FedRampGate::new();

        gate.bind_control("AC-2", true);
        gate.bind_control("AC-3", false);

        let controls = gate.get_all_controls();
        assert_eq!(controls.len(), 2);
        assert!(controls.iter().any(|(id, _)| id == "AC-2"));
        assert!(controls.iter().any(|(id, _)| id == "AC-3"));
    }
}
