// Immutable event stream with query capabilities

use super::events::{AuditEvent, EventType};
use crate::rebac::{SovereignIdentity, PolicyAction, PolicyResource};
use std::sync::RwLock;
use std::sync::Arc;
use uuid::Uuid;

pub struct AuditLogger {
    events: Arc<RwLock<Vec<AuditEvent>>>,
}

impl AuditLogger {
    pub fn new() -> Self {
        AuditLogger {
            events: Arc::new(RwLock::new(Vec::new())),
        }
    }

    pub fn log_rebac_decision(
        &self,
        sovereign_id: SovereignIdentity,
        action: PolicyAction,
        resource: PolicyResource,
        decision: bool,
        reason: String,
    ) -> Option<Uuid> {
        let event = AuditEvent::new(
            EventType::ReBAC,
            sovereign_id,
            action,
            Some(resource),
            decision,
            reason,
        );
        let event_id = event.id;

        if let Ok(mut events) = self.events.write() {
            events.push(event);
            Some(event_id)
        } else {
            None
        }
    }

    pub fn log_ap2_evaluation(
        &self,
        sovereign_id: SovereignIdentity,
        action: PolicyAction,
        resource: PolicyResource,
        decision: bool,
        reason: String,
    ) -> Option<Uuid> {
        let event = AuditEvent::new(
            EventType::AP2,
            sovereign_id,
            action,
            Some(resource),
            decision,
            reason,
        );
        let event_id = event.id;

        if let Ok(mut events) = self.events.write() {
            events.push(event);
            Some(event_id)
        } else {
            None
        }
    }

    pub fn log_temporal_check(
        &self,
        sovereign_id: SovereignIdentity,
        action: PolicyAction,
        decision: bool,
        reason: String,
    ) -> Option<Uuid> {
        let event = AuditEvent::new(
            EventType::Temporal,
            sovereign_id,
            action,
            None, // Temporal checks don't have a specific resource
            decision,
            reason,
        );
        let event_id = event.id;

        if let Ok(mut events) = self.events.write() {
            events.push(event);
            Some(event_id)
        } else {
            None
        }
    }

    pub fn log_policy_decision(
        &self,
        sovereign_id: SovereignIdentity,
        action: PolicyAction,
        resource: PolicyResource,
        decision: bool,
        reason: String,
    ) -> Option<Uuid> {
        let event = AuditEvent::new(
            EventType::Policy,
            sovereign_id,
            action,
            Some(resource),
            decision,
            reason,
        );
        let event_id = event.id;

        if let Ok(mut events) = self.events.write() {
            events.push(event);
            Some(event_id)
        } else {
            None
        }
    }

    pub fn event_count(&self) -> usize {
        self.events.read().map(|e| e.len()).unwrap_or(0)
    }

    pub fn get_events(&self) -> Vec<AuditEvent> {
        self.events.read().map(|e| e.clone()).unwrap_or_default()
    }

    pub fn query_by_identity(&self, sovereign_id: SovereignIdentity) -> Vec<AuditEvent> {
        self.events
            .read()
            .map(|e| {
                e.iter()
                    .filter(|event| event.sovereign_id == sovereign_id)
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn query_by_action(&self, action: PolicyAction) -> Vec<AuditEvent> {
        self.events
            .read()
            .map(|e| {
                e.iter()
                    .filter(|event| event.action == action)
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn query_by_event_type(&self, event_type: EventType) -> Vec<AuditEvent> {
        self.events
            .read()
            .map(|e| {
                e.iter()
                    .filter(|event| event.event_type == event_type)
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn query_by_decision(&self, decision: bool) -> Vec<AuditEvent> {
        self.events
            .read()
            .map(|e| {
                e.iter()
                    .filter(|event| event.decision == decision)
                    .cloned()
                    .collect()
            })
            .unwrap_or_default()
    }
}

impl Default for AuditLogger {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for AuditLogger {
    fn clone(&self) -> Self {
        AuditLogger {
            events: Arc::clone(&self.events),
        }
    }
}
