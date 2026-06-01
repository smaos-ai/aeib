pub mod consent;
pub mod eu_ai_act;
pub mod hipaa;
pub mod retention;
pub mod tests;

pub use consent::{ConsentRecord, DataSubject, PurposeBasis};
pub use eu_ai_act::{
    AuditLogEntry, HumanOversightGate, RiskLevel, RiskManagementRecord, TransparencyRecord,
};
pub use hipaa::{BusinessAssociateAgreement, PhiAccessLog, PhiClassification};
pub use retention::RetentionPolicy;
