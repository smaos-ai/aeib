// Phase 25 Wave 3: Audit + Archive Infrastructure
// Immutable audit logging with merkle tree archival + S3 export

mod events;
mod logger;
mod archive;
mod s3_exporter;

pub use events::{AuditEvent, EventType};
pub use logger::AuditLogger;
pub use archive::MerkleArchive;
pub use s3_exporter::{S3Exporter, S3ArchiveMetadata};

use crate::rebac::{SovereignIdentity, PolicyAction, PolicyResource};

/// Integrated audit archive combining logger + merkle archive
pub struct AuditArchive {
    logger: AuditLogger,
    merkle: MerkleArchive,
}

impl AuditArchive {
    pub fn new() -> Self {
        AuditArchive {
            logger: AuditLogger::new(),
            merkle: MerkleArchive::new(),
        }
    }

    pub fn log_rebac_decision(
        &self,
        sovereign_id: SovereignIdentity,
        action: PolicyAction,
        resource: PolicyResource,
        decision: bool,
        reason: String,
    ) -> Option<uuid::Uuid> {
        self.logger.log_rebac_decision(sovereign_id, action, resource, decision, reason)
    }

    pub fn log_ap2_evaluation(
        &self,
        sovereign_id: SovereignIdentity,
        action: PolicyAction,
        resource: PolicyResource,
        decision: bool,
        reason: String,
    ) -> Option<uuid::Uuid> {
        self.logger.log_ap2_evaluation(sovereign_id, action, resource, decision, reason)
    }

    pub fn log_temporal_check(
        &self,
        sovereign_id: SovereignIdentity,
        action: PolicyAction,
        decision: bool,
        reason: String,
    ) -> Option<uuid::Uuid> {
        self.logger.log_temporal_check(sovereign_id, action, decision, reason)
    }

    pub fn log_policy_decision(
        &self,
        sovereign_id: SovereignIdentity,
        action: PolicyAction,
        resource: PolicyResource,
        decision: bool,
        reason: String,
    ) -> Option<uuid::Uuid> {
        self.logger.log_policy_decision(sovereign_id, action, resource, decision, reason)
    }

    pub fn event_count(&self) -> usize {
        self.logger.event_count()
    }

    pub fn get_events(&self) -> Vec<AuditEvent> {
        self.logger.get_events()
    }

    pub fn create_snapshot(&self) -> Vec<u8> {
        let events = self.logger.get_events();
        self.merkle.add_snapshot(events)
    }

    pub fn get_root_hash(&self) -> Vec<u8> {
        self.merkle.root_hash()
    }

    pub fn query_by_identity(&self, sovereign_id: SovereignIdentity) -> Vec<AuditEvent> {
        self.logger.query_by_identity(sovereign_id)
    }

    pub fn query_by_action(&self, action: PolicyAction) -> Vec<AuditEvent> {
        self.logger.query_by_action(action)
    }

    pub fn query_by_event_type(&self, event_type: EventType) -> Vec<AuditEvent> {
        self.logger.query_by_event_type(event_type)
    }

    pub fn query_by_decision(&self, decision: bool) -> Vec<AuditEvent> {
        self.logger.query_by_decision(decision)
    }
}

impl Default for AuditArchive {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for AuditArchive {
    fn clone(&self) -> Self {
        AuditArchive {
            logger: self.logger.clone(),
            merkle: self.merkle.clone(),
        }
    }
}
