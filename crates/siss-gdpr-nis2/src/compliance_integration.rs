/// End-to-end EU compliance integration
/// Demonstrates: Data Residency + NIS2 Mapping + GDPR Rights + Dashboard

use uuid::Uuid;
use crate::data_residency::EUDataGuard;
use crate::nis2_mapping::NIS2AssetMapper;
use crate::data_subject_rights::DataSubjectRightsService;
use crate::compliance_dashboard::ComplianceDashboard;

pub struct ComplianceIntegration {
    eu_guard: EUDataGuard,
    nis2_mapper: NIS2AssetMapper,
    dsr_service: DataSubjectRightsService,
    dashboard: ComplianceDashboard,
}

impl ComplianceIntegration {
    pub fn new() -> Self {
        Self {
            eu_guard: EUDataGuard::new(),
            nis2_mapper: NIS2AssetMapper::new(),
            dsr_service: DataSubjectRightsService::new(),
            dashboard: ComplianceDashboard::new(),
        }
    }

    /// Full compliance check: residency + NIS2 + GDPR
    pub fn run_compliance_audit(&self) -> Result<ComplianceReport, String> {
        // 1. Verify EU data residency
        let residency_check = self.eu_guard
            .validate_frankfurt_residency("eu-central-1.amazonaws.com")
            .is_ok();

        // 2. Assess NIS2 readiness
        let nis2_score = self.nis2_mapper.calculate_readiness_score();

        // 3. Check GDPR compliance metrics
        let metrics = self.dashboard.get_metrics();

        Ok(ComplianceReport {
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
            residency_verified: residency_check,
            nis2_readiness_score: nis2_score,
            gdpr_consent_rate: metrics.gdpr_consent_percentage,
            audit_events_count: metrics.audit_events_logged,
            overall_status: if residency_check && nis2_score >= 85.0 && metrics.gdpr_consent_percentage >= 80.0 {
                "COMPLIANT".to_string()
            } else {
                "NEEDS_REMEDIATION".to_string()
            },
        })
    }

    /// Processes a GDPR data subject request end-to-end
    pub fn handle_data_subject_request(
        &self,
        subject_id: Uuid,
        request_type: &str,
    ) -> Result<String, String> {
        match request_type {
            "access" => {
                self.dsr_service.execute_right_to_access(subject_id)?;
                Ok("Data access request processed".to_string())
            }
            "erasure" => {
                self.dsr_service.execute_right_to_be_forgotten(subject_id)?;
                Ok("Right to be forgotten executed".to_string())
            }
            "portability" => {
                self.dsr_service.execute_data_portability(subject_id)?;
                Ok("Data portability export generated".to_string())
            }
            _ => Err("Unknown request type".to_string()),
        }
    }
}

impl Default for ComplianceIntegration {
    fn default() -> Self {
        Self::new()
    }
}

#[derive(Debug, Clone)]
pub struct ComplianceReport {
    pub timestamp: u64,
    pub residency_verified: bool,
    pub nis2_readiness_score: f64,
    pub gdpr_consent_rate: f64,
    pub audit_events_count: usize,
    pub overall_status: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_full_compliance_audit() {
        let integration = ComplianceIntegration::new();
        let report = integration.run_compliance_audit().expect("audit must succeed");

        assert!(report.residency_verified);
        assert!(report.nis2_readiness_score > 0.0);
        assert!(report.gdpr_consent_rate > 0.0);
        assert_eq!(report.overall_status, "COMPLIANT");
    }

    #[test]
    fn test_data_subject_request_flow() {
        let integration = ComplianceIntegration::new();
        let subject_id = Uuid::new_v4();

        let access_result = integration.handle_data_subject_request(subject_id, "access");
        assert!(access_result.is_ok());

        let erasure_result = integration.handle_data_subject_request(subject_id, "erasure");
        assert!(erasure_result.is_ok());

        let portability_result = integration.handle_data_subject_request(subject_id, "portability");
        assert!(portability_result.is_ok());
    }
}
