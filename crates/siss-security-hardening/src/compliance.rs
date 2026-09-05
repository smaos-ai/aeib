use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// EU AI Act Annex III Requirement categories
#[derive(Clone, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum AnnexIIIRequirement {
    HighRiskSystemClassification,
    RiskAssessmentAndMitigation,
    HumanOversightProcedures,
    TransparencyAndExplainability,
    DocumentationAndTechnicalRecords,
    DataGovernanceAndQuality,
    PerformanceMonitoring,
    CybersecurityAndRobustness,
    CorrectiveActionsMechanism,
}

/// Status of a compliance requirement
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ComplianceStatus {
    Met,
    PartiallyMet,
    NotMet,
    NotApplicable,
}

/// Compliance evidence for an Annex III requirement
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ComplianceEvidence {
    pub requirement: AnnexIIIRequirement,
    pub status: ComplianceStatus,
    pub evidence_description: String,
    pub verification_date: String,
    pub responsible_team: String,
}

/// Compliance checker for EU AI Act Annex III requirements
pub struct ComplianceChecker {
    requirements: HashMap<AnnexIIIRequirement, ComplianceEvidence>,
}

impl ComplianceChecker {
    pub fn new() -> Self {
        Self {
            requirements: HashMap::new(),
        }
    }

    /// Record compliance evidence for a requirement
    pub fn record_evidence(&mut self, evidence: ComplianceEvidence) {
        self.requirements
            .insert(evidence.requirement.clone(), evidence);
    }

    /// Get compliance status for a requirement
    pub fn get_status(&self, requirement: &AnnexIIIRequirement) -> Option<ComplianceStatus> {
        self.requirements.get(requirement).map(|e| e.status.clone())
    }

    /// Get all requirements and their statuses
    pub fn get_all_requirements(&self) -> Vec<ComplianceEvidence> {
        self.requirements.values().cloned().collect()
    }

    /// Check overall compliance score (percentage of Met requirements)
    pub fn overall_compliance_score(&self) -> f64 {
        if self.requirements.is_empty() {
            return 0.0;
        }

        let met_count = self
            .requirements
            .values()
            .filter(|e| e.status == ComplianceStatus::Met)
            .count();

        (met_count as f64 / self.requirements.len() as f64) * 100.0
    }

    /// Check if all critical requirements are met
    pub fn are_critical_requirements_met(&self) -> bool {
        // Critical requirements for high-risk AI systems
        let critical = vec![
            AnnexIIIRequirement::HighRiskSystemClassification,
            AnnexIIIRequirement::RiskAssessmentAndMitigation,
            AnnexIIIRequirement::HumanOversightProcedures,
            AnnexIIIRequirement::CybersecurityAndRobustness,
            AnnexIIIRequirement::DataGovernanceAndQuality,
        ];

        critical.iter().all(|req| {
            self.get_status(req)
                .map(|status| status == ComplianceStatus::Met)
                .unwrap_or(false)
        })
    }

    /// Generate compliance report
    pub fn generate_report(&self) -> String {
        let mut report = String::new();
        report.push_str("# EU AI Act Annex III Compliance Report\n\n");

        report.push_str("## Overall Compliance Score\n");
        report.push_str(&format!(
            "**{:.1}%** - {}\n\n",
            self.overall_compliance_score(),
            if self.are_critical_requirements_met() {
                "COMPLIANT - All critical requirements met"
            } else {
                "NON-COMPLIANT - Critical requirements not fully met"
            }
        ));

        report.push_str("## Requirement Status\n\n");

        let mut requirements = self.get_all_requirements();
        requirements.sort_by_key(|r| format!("{:?}", r.requirement));

        for req in requirements {
            report.push_str(&format!("### {:?}\n", req.requirement));
            report.push_str(&format!("- **Status:** {:?}\n", req.status));
            report.push_str(&format!("- **Evidence:** {}\n", req.evidence_description));
            report.push_str(&format!("- **Verified:** {}\n", req.verification_date));
            report.push_str(&format!("- **Owner:** {}\n\n", req.responsible_team));
        }

        report
    }
}

impl Default for ComplianceChecker {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compliance_evidence_recording() {
        let mut checker = ComplianceChecker::new();
        let evidence = ComplianceEvidence {
            requirement: AnnexIIIRequirement::CybersecurityAndRobustness,
            status: ComplianceStatus::Met,
            evidence_description: "AES-256 encryption at rest and TLS 1.3 in transit".to_string(),
            verification_date: "2026-05-27".to_string(),
            responsible_team: "Security Team".to_string(),
        };

        checker.record_evidence(evidence);

        let status = checker.get_status(&AnnexIIIRequirement::CybersecurityAndRobustness);
        assert_eq!(status, Some(ComplianceStatus::Met));
    }

    #[test]
    fn test_compliance_score() {
        let mut checker = ComplianceChecker::new();

        // Add 3 met requirements
        for i in 0..3 {
            checker.record_evidence(ComplianceEvidence {
                requirement: match i {
                    0 => AnnexIIIRequirement::RiskAssessmentAndMitigation,
                    1 => AnnexIIIRequirement::DataGovernanceAndQuality,
                    _ => AnnexIIIRequirement::CybersecurityAndRobustness,
                },
                status: ComplianceStatus::Met,
                evidence_description: "Evidence".to_string(),
                verification_date: "2026-05-27".to_string(),
                responsible_team: "Team".to_string(),
            });
        }

        // Add 1 not met requirement
        checker.record_evidence(ComplianceEvidence {
            requirement: AnnexIIIRequirement::HumanOversightProcedures,
            status: ComplianceStatus::NotMet,
            evidence_description: "Not yet implemented".to_string(),
            verification_date: "2026-05-27".to_string(),
            responsible_team: "Team".to_string(),
        });

        let score = checker.overall_compliance_score();
        assert_eq!(score, 75.0); // 3 met out of 4
    }

    #[test]
    fn test_critical_requirements_check() {
        let mut checker = ComplianceChecker::new();

        // Record all critical requirements as Met
        let critical_reqs = vec![
            AnnexIIIRequirement::HighRiskSystemClassification,
            AnnexIIIRequirement::RiskAssessmentAndMitigation,
            AnnexIIIRequirement::HumanOversightProcedures,
            AnnexIIIRequirement::CybersecurityAndRobustness,
            AnnexIIIRequirement::DataGovernanceAndQuality,
        ];

        for req in critical_reqs {
            checker.record_evidence(ComplianceEvidence {
                requirement: req,
                status: ComplianceStatus::Met,
                evidence_description: "Verified".to_string(),
                verification_date: "2026-05-27".to_string(),
                responsible_team: "Security".to_string(),
            });
        }

        assert!(checker.are_critical_requirements_met());
    }

    #[test]
    fn test_report_generation() {
        let mut checker = ComplianceChecker::new();
        checker.record_evidence(ComplianceEvidence {
            requirement: AnnexIIIRequirement::CybersecurityAndRobustness,
            status: ComplianceStatus::Met,
            evidence_description: "TLS 1.3 + AES-256 encryption".to_string(),
            verification_date: "2026-05-27".to_string(),
            responsible_team: "Security Team".to_string(),
        });

        let report = checker.generate_report();
        assert!(report.contains("Compliance Report"));
        assert!(report.contains("CybersecurityAndRobustness"));
    }
}
