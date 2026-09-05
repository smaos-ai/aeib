use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// CSA 5 Core Elements (Cloud Security Alliance Framework)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum CSACoreElement {
    People,
    Process,
    Technology,
    Business,
    Legal,
}

impl CSACoreElement {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::People => "People",
            Self::Process => "Process",
            Self::Technology => "Technology",
            Self::Business => "Business",
            Self::Legal => "Legal",
        }
    }
}

/// CSA Control Level (1-3, with 3 being highest maturity)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum CSAControlLevel {
    Level1,
    Level2,
    Level3,
}

impl CSAControlLevel {
    pub fn as_u8(&self) -> u8 {
        match self {
            Self::Level1 => 1,
            Self::Level2 => 2,
            Self::Level3 => 3,
        }
    }
}

/// A single CSA control mapping
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CSAControl {
    pub id: String,
    pub name: String,
    pub element: CSACoreElement,
    pub level: CSAControlLevel,
    pub description: String,
    pub smaos_implementations: Vec<String>, // e.g., ["L1-policy-routing", "L3-permit-gates"]
    pub test_evidence: Option<String>,      // Path to test file proving implementation
    pub status: ControlStatus,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ControlStatus {
    NotImplemented,
    PartiallyImplemented,
    FullyImplemented,
    Verified,
}

/// CSA Compliance Scorecard
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CSAScorecard {
    pub organization: String,
    pub assessment_date: String,
    pub total_controls: usize,
    pub implemented_count: usize,
    pub verified_count: usize,
    pub controls_by_element: HashMap<String, CSAElementScore>,
    pub overall_level: CSAControlLevel,
    pub maturity_percentage: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CSAElementScore {
    pub element: String,
    pub total: usize,
    pub implemented: usize,
    pub verified: usize,
    pub percentage: f64,
}

pub struct CSAMapper {
    controls: Vec<CSAControl>,
}

impl CSAMapper {
    pub fn new() -> Self {
        Self {
            controls: Self::default_controls(),
        }
    }

    /// Define SMAOS-specific CSA control mappings
    fn default_controls() -> Vec<CSAControl> {
        vec![
            // PEOPLE CONTROLS
            CSAControl {
                id: "CSA-P-01".to_string(),
                name: "Personnel Security".to_string(),
                element: CSACoreElement::People,
                level: CSAControlLevel::Level3,
                description: "Team members have appropriate security clearance and training".to_string(),
                smaos_implementations: vec![
                    "onboarding-identity-verification".to_string(),
                    "role-based-access".to_string(),
                ],
                test_evidence: Some("crates/siss-gatekeeper/tests/identity_tests.rs".to_string()),
                status: ControlStatus::Verified,
            },
            CSAControl {
                id: "CSA-P-02".to_string(),
                name: "Competence Requirements".to_string(),
                element: CSACoreElement::People,
                level: CSAControlLevel::Level2,
                description: "Security competence documented for key roles".to_string(),
                smaos_implementations: vec!["role-capability-registry".to_string()],
                test_evidence: None,
                status: ControlStatus::PartiallyImplemented,
            },
            // PROCESS CONTROLS
            CSAControl {
                id: "CSA-PR-01".to_string(),
                name: "Policy & Procedures".to_string(),
                element: CSACoreElement::Process,
                level: CSAControlLevel::Level3,
                description: "Comprehensive security policies documented and enforced".to_string(),
                smaos_implementations: vec![
                    "l1-policy-routing".to_string(),
                    "l3-permit-gates".to_string(),
                ],
                test_evidence: Some("crates/l1-policy/tests/policy_routing_tests.rs".to_string()),
                status: ControlStatus::Verified,
            },
            CSAControl {
                id: "CSA-PR-02".to_string(),
                name: "Incident Response".to_string(),
                element: CSACoreElement::Process,
                level: CSAControlLevel::Level3,
                description: "Incident detection and response procedures in place".to_string(),
                smaos_implementations: vec![
                    "l8-proof-ledger".to_string(),
                    "siss-event-log".to_string(),
                ],
                test_evidence: Some("crates/l8-proof/tests/incident_tests.rs".to_string()),
                status: ControlStatus::Verified,
            },
            CSAControl {
                id: "CSA-PR-03".to_string(),
                name: "Change Management".to_string(),
                element: CSACoreElement::Process,
                level: CSAControlLevel::Level2,
                description: "Changes to systems are tracked and approved".to_string(),
                smaos_implementations: vec!["git-signed-commits".to_string()],
                test_evidence: None,
                status: ControlStatus::FullyImplemented,
            },
            // TECHNOLOGY CONTROLS
            CSAControl {
                id: "CSA-T-01".to_string(),
                name: "Egress Controls".to_string(),
                element: CSACoreElement::Technology,
                level: CSAControlLevel::Level3,
                description: "Outbound network traffic whitelisted and monitored".to_string(),
                smaos_implementations: vec![
                    "siss-behavioral-firewall".to_string(),
                    "l4-job-router".to_string(),
                ],
                test_evidence: Some("crates/l4-orchestration/tests/egress_controls_tests.rs".to_string()),
                status: ControlStatus::Verified,
            },
            CSAControl {
                id: "CSA-T-02".to_string(),
                name: "Cryptographic Controls".to_string(),
                element: CSACoreElement::Technology,
                level: CSAControlLevel::Level3,
                description: "Ed25519 PQC signing for all ledger entries and agent communications".to_string(),
                smaos_implementations: vec![
                    "l8-proof-ledger".to_string(),
                    "siss-vault-integration".to_string(),
                ],
                test_evidence: Some("crates/l8-proof/tests/crypto_tests.rs".to_string()),
                status: ControlStatus::Verified,
            },
            CSAControl {
                id: "CSA-T-03".to_string(),
                name: "Sandboxing & Isolation".to_string(),
                element: CSACoreElement::Technology,
                level: CSAControlLevel::Level3,
                description: "gVisor-based sandboxing for untrusted tool execution".to_string(),
                smaos_implementations: vec![
                    "l3-permit-gates".to_string(),
                    "siss-enclave".to_string(),
                ],
                test_evidence: Some("crates/l3-permit-gates/tests/sandbox_tests.rs".to_string()),
                status: ControlStatus::Verified,
            },
            CSAControl {
                id: "CSA-T-04".to_string(),
                name: "Audit Logging".to_string(),
                element: CSACoreElement::Technology,
                level: CSAControlLevel::Level3,
                description: "Immutable audit trail of all decisions and agent actions".to_string(),
                smaos_implementations: vec![
                    "l8-proof-ledger".to_string(),
                    "siss-event-log".to_string(),
                ],
                test_evidence: Some("crates/l8-proof/tests/audit_tests.rs".to_string()),
                status: ControlStatus::Verified,
            },
            // BUSINESS CONTROLS
            CSAControl {
                id: "CSA-B-01".to_string(),
                name: "Risk Assessment".to_string(),
                element: CSACoreElement::Business,
                level: CSAControlLevel::Level2,
                description: "Regular risk assessments for AI/agent operations".to_string(),
                smaos_implementations: vec![
                    "l2-knowledge-base".to_string(),
                    "siss-compliance".to_string(),
                ],
                test_evidence: None,
                status: ControlStatus::PartiallyImplemented,
            },
            CSAControl {
                id: "CSA-B-02".to_string(),
                name: "SLA Management".to_string(),
                element: CSACoreElement::Business,
                level: CSAControlLevel::Level1,
                description: "Service level agreements define availability and performance targets".to_string(),
                smaos_implementations: vec!["siss-sla-monitor".to_string()],
                test_evidence: None,
                status: ControlStatus::NotImplemented,
            },
            // LEGAL CONTROLS
            CSAControl {
                id: "CSA-L-01".to_string(),
                name: "Regulatory Compliance".to_string(),
                element: CSACoreElement::Legal,
                level: CSAControlLevel::Level3,
                description: "EU AI Act (Annex I/III) and GDPR compliance documented".to_string(),
                smaos_implementations: vec![
                    "ai-act-analyzer".to_string(),
                    "gdpr-mapper".to_string(),
                ],
                test_evidence: Some("crates/siss-eu-compliance/src/tests/ai_act_tests.rs".to_string()),
                status: ControlStatus::Verified,
            },
            CSAControl {
                id: "CSA-L-02".to_string(),
                name: "Data Processing Agreements".to_string(),
                element: CSACoreElement::Legal,
                level: CSAControlLevel::Level2,
                description: "DPA/DBAs in place for all data processing activities".to_string(),
                smaos_implementations: vec!["gdpr-mapper".to_string()],
                test_evidence: None,
                status: ControlStatus::PartiallyImplemented,
            },
        ]
    }

    /// Get a control by ID
    pub fn get_control(&self, id: &str) -> Option<&CSAControl> {
        self.controls.iter().find(|c| c.id == id)
    }

    /// Get all controls for a specific element
    pub fn get_controls_by_element(&self, element: CSACoreElement) -> Vec<&CSAControl> {
        self.controls
            .iter()
            .filter(|c| c.element == element)
            .collect()
    }

    /// Get all verified controls
    pub fn get_verified_controls(&self) -> Vec<&CSAControl> {
        self.controls
            .iter()
            .filter(|c| c.status == ControlStatus::Verified)
            .collect()
    }

    /// Generate compliance scorecard
    pub fn generate_scorecard(&self, organization: &str) -> CSAScorecard {
        let total_controls = self.controls.len();
        let implemented_count = self
            .controls
            .iter()
            .filter(|c| {
                c.status == ControlStatus::FullyImplemented
                    || c.status == ControlStatus::Verified
            })
            .count();
        let verified_count = self
            .controls
            .iter()
            .filter(|c| c.status == ControlStatus::Verified)
            .count();

        let mut controls_by_element = HashMap::new();

        for element in &[
            CSACoreElement::People,
            CSACoreElement::Process,
            CSACoreElement::Technology,
            CSACoreElement::Business,
            CSACoreElement::Legal,
        ] {
            let element_controls: Vec<&CSAControl> = self
                .controls
                .iter()
                .filter(|c| &c.element == element)
                .collect();

            let total = element_controls.len();
            let implemented = element_controls
                .iter()
                .filter(|c| {
                    c.status == ControlStatus::FullyImplemented
                        || c.status == ControlStatus::Verified
                })
                .count();
            let verified = element_controls
                .iter()
                .filter(|c| c.status == ControlStatus::Verified)
                .count();
            let percentage = if total > 0 {
                (implemented as f64 / total as f64) * 100.0
            } else {
                0.0
            };

            controls_by_element.insert(
                element.as_str().to_string(),
                CSAElementScore {
                    element: element.as_str().to_string(),
                    total,
                    implemented,
                    verified,
                    percentage,
                },
            );
        }

        let maturity_percentage = if total_controls > 0 {
            (implemented_count as f64 / total_controls as f64) * 100.0
        } else {
            0.0
        };

        let overall_level = if maturity_percentage >= 80.0 {
            CSAControlLevel::Level3
        } else if maturity_percentage >= 50.0 {
            CSAControlLevel::Level2
        } else {
            CSAControlLevel::Level1
        };

        CSAScorecard {
            organization: organization.to_string(),
            assessment_date: chrono::Utc::now().to_rfc3339(),
            total_controls,
            implemented_count,
            verified_count,
            controls_by_element,
            overall_level,
            maturity_percentage,
        }
    }

    /// Update control status from test evidence
    pub fn update_control_status(&mut self, control_id: &str, new_status: ControlStatus) -> bool {
        if let Some(control) = self.controls.iter_mut().find(|c| c.id == control_id) {
            control.status = new_status;
            true
        } else {
            false
        }
    }
}

impl Default for CSAMapper {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_csa_mapper_initialization() {
        let mapper = CSAMapper::new();
        assert!(!mapper.controls.is_empty());
        assert!(mapper.controls.len() >= 14);
    }

    #[test]
    fn test_get_control_by_id() {
        let mapper = CSAMapper::new();
        let control = mapper.get_control("CSA-T-01");
        assert!(control.is_some());
        assert_eq!(control.unwrap().name, "Egress Controls");
    }

    #[test]
    fn test_get_controls_by_element() {
        let mapper = CSAMapper::new();
        let tech_controls = mapper.get_controls_by_element(CSACoreElement::Technology);
        assert!(!tech_controls.is_empty());
        assert!(tech_controls.iter().all(|c| c.element == CSACoreElement::Technology));
    }

    #[test]
    fn test_get_verified_controls() {
        let mapper = CSAMapper::new();
        let verified = mapper.get_verified_controls();
        assert!(!verified.is_empty());
        assert!(verified.iter().all(|c| c.status == ControlStatus::Verified));
    }

    #[test]
    fn test_generate_scorecard() {
        let mapper = CSAMapper::new();
        let scorecard = mapper.generate_scorecard("SMAOS");

        assert_eq!(scorecard.organization, "SMAOS");
        assert!(scorecard.total_controls > 0);
        assert!(scorecard.implemented_count > 0);
        assert!(scorecard.maturity_percentage > 0.0);
        assert!(scorecard.controls_by_element.len() == 5);
    }

    #[test]
    fn test_scorecard_calculation() {
        let mapper = CSAMapper::new();
        let scorecard = mapper.generate_scorecard("Test");

        // Calculate expected implemented count
        let expected_impl = mapper
            .controls
            .iter()
            .filter(|c| {
                c.status == ControlStatus::FullyImplemented || c.status == ControlStatus::Verified
            })
            .count();

        assert_eq!(scorecard.implemented_count, expected_impl);
    }

    #[test]
    fn test_update_control_status() {
        let mut mapper = CSAMapper::new();
        let success = mapper.update_control_status("CSA-T-01", ControlStatus::NotImplemented);
        assert!(success);

        let control = mapper.get_control("CSA-T-01").unwrap();
        assert_eq!(control.status, ControlStatus::NotImplemented);
    }

    #[test]
    fn test_update_nonexistent_control() {
        let mut mapper = CSAMapper::new();
        let success = mapper.update_control_status("CSA-FAKE-01", ControlStatus::NotImplemented);
        assert!(!success);
    }

    #[test]
    fn test_all_elements_represented() {
        let mapper = CSAMapper::new();
        let elements = [
            CSACoreElement::People,
            CSACoreElement::Process,
            CSACoreElement::Technology,
            CSACoreElement::Business,
            CSACoreElement::Legal,
        ];

        for element in &elements {
            let controls = mapper.get_controls_by_element(*element);
            assert!(!controls.is_empty(), "No controls for {:?}", element);
        }
    }

    #[test]
    fn test_csa_element_score_calculation() {
        let mapper = CSAMapper::new();
        let scorecard = mapper.generate_scorecard("Test");

        for (_, element_score) in scorecard.controls_by_element {
            if element_score.total > 0 {
                let expected_percentage = (element_score.implemented as f64
                    / element_score.total as f64)
                    * 100.0;
                assert!((element_score.percentage - expected_percentage).abs() < 0.1);
            }
        }
    }

    #[test]
    fn test_control_has_smaos_implementations() {
        let mapper = CSAMapper::new();
        for control in mapper.get_verified_controls() {
            assert!(!control.smaos_implementations.is_empty());
        }
    }

    #[test]
    fn test_control_levels_are_ordered() {
        assert!(CSAControlLevel::Level1 < CSAControlLevel::Level2);
        assert!(CSAControlLevel::Level2 < CSAControlLevel::Level3);
    }

    #[test]
    fn test_csa_core_element_as_str() {
        assert_eq!(CSACoreElement::People.as_str(), "People");
        assert_eq!(CSACoreElement::Technology.as_str(), "Technology");
    }
}
