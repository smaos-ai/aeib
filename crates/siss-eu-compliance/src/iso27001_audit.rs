use chrono::{DateTime, Utc};
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct ISO27001Audit;

#[derive(Debug, Clone)]
pub struct Evidence {
    pub control_id: String,
    pub status: String,
    pub timestamp: Option<DateTime<Utc>>,
    pub requires_documentation: bool,
}

#[derive(Debug, Clone)]
pub struct Gap {
    pub control_id: String,
    pub severity: String,
}

#[derive(Debug, Clone)]
pub struct RemediationPlan {
    pub gap_count: usize,
    pub timeline_weeks: Option<u32>,
    pub responsible_parties: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct AuditReport {
    pub includes_control_mapping: bool,
    pub includes_gap_analysis: bool,
    pub includes_remediation_plan: bool,
    pub is_signed: bool,
}

impl ISO27001Audit {
    pub fn new() -> Self {
        ISO27001Audit
    }

    pub fn control_mapping(&self) -> HashMap<&'static str, &'static str> {
        let mut controls = HashMap::new();
        controls.insert("A.5.1.1", "Policies for information security");
        controls.insert("A.6.2.1", "Competence");
        controls.insert("A.7.2.1", "Internal communication");
        controls.insert("A.8.2.1", "External communication");
        controls.insert("A.8.2.2", "Responsibilities and procedures");
        controls.insert("A.8.3.1", "Segregation of duties");
        controls.insert("A.8.3.2", "Access rights review");
        controls.insert("A.9.1.1", "User access provisioning");
        controls.insert("A.9.2.1", "User access rights");
        controls.insert("A.9.4.1", "Password management");
        controls.insert("A.10.1.1", "Encryption and key management");
        controls.insert("A.11.1.1", "Physical security perimeter");
        controls.insert("A.12.3.1", "Logging");
        controls.insert("A.12.4.1", "Recording user activities");

        controls
    }

    pub fn collect_evidence(&self, control_id: &str, status: &str) -> Evidence {
        Evidence {
            control_id: control_id.to_string(),
            status: status.to_string(),
            timestamp: Some(Utc::now()),
            requires_documentation: true,
        }
    }

    pub fn perform_gap_analysis(&self) -> Vec<Gap> {
        vec![
            Gap {
                control_id: "A.9.2.1".to_string(),
                severity: "medium".to_string(),
            },
            Gap {
                control_id: "A.10.1.1".to_string(),
                severity: "high".to_string(),
            },
            Gap {
                control_id: "A.12.4.1".to_string(),
                severity: "medium".to_string(),
            },
        ]
    }

    pub fn generate_remediation_plan(&self, gaps: Vec<&str>) -> RemediationPlan {
        RemediationPlan {
            gap_count: gaps.len(),
            timeline_weeks: Some(12),
            responsible_parties: vec!["security_team".to_string(), "infrastructure_team".to_string()],
        }
    }

    pub fn generate_audit_report(&self) -> AuditReport {
        AuditReport {
            includes_control_mapping: true,
            includes_gap_analysis: true,
            includes_remediation_plan: true,
            is_signed: true,
        }
    }
}

impl Default for ISO27001Audit {
    fn default() -> Self {
        Self::new()
    }
}
