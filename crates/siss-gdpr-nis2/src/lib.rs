pub mod gdpr;
pub mod nis2;
pub mod data_residency;
pub mod nis2_mapping;
pub mod data_subject_rights;
pub mod compliance_dashboard;
pub mod compliance_integration;
#[cfg(test)]
mod tests;

pub use gdpr::{DataRegion, DataResidencyPolicy, DsarRequest, DsarType};
pub use nis2::{
    BreachNotification, IncidentSeverity, SecurityAuditEvent, SecurityAuditLogger,
    SecurityEventType,
};
pub use data_residency::{EUDataGuard, DomainValidator};
pub use nis2_mapping::{NIS2AssetMapper, CriticalAssetType, CriticalAsset};
pub use data_subject_rights::{DataSubjectRightsService, RightType, DataSubject};
pub use compliance_dashboard::{ComplianceDashboard, ComplianceMetrics, ComplianceStatus};
pub use compliance_integration::{ComplianceIntegration, ComplianceReport};
