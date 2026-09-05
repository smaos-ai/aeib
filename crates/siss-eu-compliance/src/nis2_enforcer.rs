use chrono::{DateTime, Utc};
use std::collections::HashSet;

#[derive(Debug, Clone)]
pub struct NIS2Enforcer;

#[derive(Debug, Clone)]
pub struct SegmentationRules {
    rules: HashSet<String>,
    pub enforcement_mode: String,
}

#[derive(Debug, Clone)]
pub struct CloudRequirements {
    pub requires_data_residency_eu: bool,
    pub requires_encryption_at_rest: bool,
    pub requires_encryption_in_transit: bool,
    pub requires_access_logging: bool,
    pub minimum_redundancy_zones: u32,
}

#[derive(Debug, Clone)]
pub struct IncidentReport {
    pub incident_type: String,
    pub category: String,
    pub severity: String,
    pub timestamp: Option<DateTime<Utc>>,
    pub competent_authority_notification_hours: u32,
}

#[derive(Debug, Clone)]
pub struct SupplyChainAssessment {
    pub vendors_count: usize,
    pub service_categories_count: usize,
    pub risk_score: f64,
    pub mitigation_status: String,
}

#[derive(Debug, Clone)]
pub struct MFAPolicy {
    pub required_factors: u32,
    pub supports_hardware_keys: bool,
    pub supports_biometric: bool,
    pub allows_sms_only: bool,
}

#[derive(Debug, Clone)]
pub struct VulnerabilityDisclosure {
    pub cve_id: Option<String>,
    pub severity: String,
    pub disclosure_deadline_days: u32,
    pub requires_customer_notification: bool,
}

impl NIS2Enforcer {
    pub fn new() -> Self {
        NIS2Enforcer
    }

    pub fn network_segmentation_rules(&self) -> SegmentationRules {
        let mut rules = HashSet::new();
        rules.insert("isolate_critical_systems".to_string());
        rules.insert("encrypt_inter_segment_traffic".to_string());
        rules.insert("monitor_segment_boundaries".to_string());

        SegmentationRules {
            rules,
            enforcement_mode: "fail_closed".to_string(),
        }
    }

    pub fn cloud_infrastructure_requirements(&self) -> CloudRequirements {
        CloudRequirements {
            requires_data_residency_eu: true,
            requires_encryption_at_rest: true,
            requires_encryption_in_transit: true,
            requires_access_logging: true,
            minimum_redundancy_zones: 2,
        }
    }

    pub fn create_incident_report(
        &self,
        incident_type: &str,
        category: &str,
        severity: &str,
    ) -> IncidentReport {
        IncidentReport {
            incident_type: incident_type.to_string(),
            category: category.to_string(),
            severity: severity.to_string(),
            timestamp: Some(Utc::now()),
            competent_authority_notification_hours: 72,
        }
    }

    pub fn assess_supply_chain_risk(
        &self,
        vendors: Vec<&str>,
        service_categories: Vec<&str>,
    ) -> SupplyChainAssessment {
        SupplyChainAssessment {
            vendors_count: vendors.len(),
            service_categories_count: service_categories.len(),
            risk_score: 0.45,
            mitigation_status: "pending".to_string(),
        }
    }

    pub fn mfa_enforcement_policy(&self) -> MFAPolicy {
        MFAPolicy {
            required_factors: 2,
            supports_hardware_keys: true,
            supports_biometric: true,
            allows_sms_only: false,
        }
    }

    pub fn vulnerability_disclosure(
        &self,
        cve_id: &str,
        severity: &str,
    ) -> VulnerabilityDisclosure {
        VulnerabilityDisclosure {
            cve_id: Some(cve_id.to_string()),
            severity: severity.to_string(),
            disclosure_deadline_days: 90,
            requires_customer_notification: true,
        }
    }
}

impl SegmentationRules {
    pub fn contains_rule(&self, rule: &str) -> bool {
        self.rules.contains(rule)
    }
}

impl Default for NIS2Enforcer {
    fn default() -> Self {
        Self::new()
    }
}
