// Audit event schema (who, what, when, why)

use crate::rebac::{SovereignIdentity, PolicyAction, PolicyResource};
use serde::{Deserialize, Serialize};
use std::time::SystemTime;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EventType {
    ReBAC,
    AP2,
    Temporal,
    Policy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEvent {
    pub id: Uuid,
    pub event_type: EventType,
    pub sovereign_id: SovereignIdentity,
    pub action: PolicyAction,
    pub resource: Option<PolicyResource>,
    pub decision: bool, // true = Allow, false = Deny
    pub reason: String,
    pub timestamp: SystemTime,
}

impl AuditEvent {
    pub fn new(
        event_type: EventType,
        sovereign_id: SovereignIdentity,
        action: PolicyAction,
        resource: Option<PolicyResource>,
        decision: bool,
        reason: String,
    ) -> Self {
        AuditEvent {
            id: Uuid::new_v4(),
            event_type,
            sovereign_id,
            action,
            resource,
            decision,
            reason,
            timestamp: SystemTime::now(),
        }
    }

    pub fn to_bytes(&self) -> Vec<u8> {
        serde_json::to_vec(self).unwrap_or_default()
    }
}
