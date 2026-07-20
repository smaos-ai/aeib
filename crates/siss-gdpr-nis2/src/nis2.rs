use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IncidentSeverity { Low, Significant, Critical }

pub struct BreachNotification {
    pub incident_id: Uuid,
    pub severity: IncidentSeverity,
    pub detected_at: u64,
    pub deadline_72h: u64,
}

const SEVENTY_TWO_HOURS_SECS: u64 = 72 * 3600;

impl BreachNotification {
    pub fn new(severity: IncidentSeverity) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        Self::with_detected_at(severity, now)
    }

    pub fn with_detected_at(severity: IncidentSeverity, detected_at: u64) -> Self {
        Self {
            incident_id: Uuid::new_v4(),
            severity,
            detected_at,
            deadline_72h: detected_at + SEVENTY_TWO_HOURS_SECS,
        }
    }

    pub fn is_overdue(&self) -> bool {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        now > self.deadline_72h
    }

    pub fn schedule_notification(&self) -> Result<(), String> {
        match self.severity {
            IncidentSeverity::Low => Ok(()),
            IncidentSeverity::Significant | IncidentSeverity::Critical => Ok(()),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SecurityEventType { AuthAttempt, DataAccess, ConfigChange, IncidentDetected }

#[derive(Debug, Clone)]
pub struct SecurityAuditEvent {
    pub event_type: SecurityEventType,
    pub timestamp: u64,
    pub actor_id: String,
    pub details: String,
}

pub struct SecurityAuditLogger {
    pub events: Vec<SecurityAuditEvent>,
    pub merkle_root: String,
}

impl SecurityAuditLogger {
    pub fn new() -> Self {
        Self { events: Vec::new(), merkle_root: String::new() }
    }

    pub fn log_event(&mut self, event: SecurityAuditEvent) {
        self.events.push(event);
        self.merkle_root = self.build_merkle_tree();
    }

    pub fn build_merkle_tree(&self) -> String {
        let mut hasher = Sha256::new();
        for event in &self.events {
            let leaf = format!(
                "{}:{}:{}:{}",
                event.timestamp, event.actor_id, event.details, event.event_type as u8,
            );
            hasher.update(leaf.as_bytes());
        }
        hex::encode(hasher.finalize())
    }
}

impl Default for SecurityAuditLogger {
    fn default() -> Self {
        Self::new()
    }
}
