pub mod compliance_dashboard;
pub mod compliance_integration;
pub mod data_residency;
pub mod data_subject_rights;
pub mod gdpr;
pub mod nis2;
pub mod nis2_mapping;
#[cfg(test)]
mod tests;

pub use compliance_dashboard::{ComplianceDashboard, ComplianceMetrics, ComplianceStatus};
pub use compliance_integration::{ComplianceIntegration, ComplianceReport};
pub use data_residency::{DomainValidator, EUDataGuard};
pub use data_subject_rights::{DataSubject, DataSubjectRightsService, RightType};
pub use gdpr::{DataRegion, DataResidencyPolicy, DsarRequest, DsarType};
pub use nis2::{
    BreachNotification, IncidentSeverity, SecurityAuditEvent, SecurityAuditLogger,
    SecurityEventType,
};
pub use nis2_mapping::{CriticalAsset, CriticalAssetType, NIS2AssetMapper};
