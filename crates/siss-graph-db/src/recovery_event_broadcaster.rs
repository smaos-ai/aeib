use tokio::sync::broadcast;

/// Phase 20 Recovery Events
#[derive(Debug, Clone, serde::Serialize)]
pub enum RecoveryEvent {
    /// Sovereign exits probation and enters recovery (week 0)
    RecoveryEntered {
        sovereign_id: String,
        score_at_entry: i16,
        timestamp: String,
    },
    /// Weekly sweep increments recovery progress
    RecoveryProgressed {
        sovereign_id: String,
        weeks_elapsed: u32,
        current_score: i16,
        timestamp: String,
    },
    /// 8 weeks complete; transition to active
    RecoveryCompleted {
        sovereign_id: String,
        exit_status: String, // "success" or "failure"
        score_at_exit: i16,
        timestamp: String,
    },
    /// Probation threshold breach during recovery
    RecoveryViolation {
        sovereign_id: String,
        reason: String,
        new_status: String, // "quarantined"
        timestamp: String,
    },
    /// Score computation with signal breakdown
    ScoringDecision {
        sovereign_id: String,
        score: i16,
        weeks_elapsed: u32,
        slash_penalty: i16,
        anomaly_penalty: i16,
        settlement_bonus: i16,
        timestamp: String,
    },
}

/// Broadcast channel for streaming events to SSE clients
#[derive(Clone)]
pub struct RecoveryEventBroadcaster {
    tx: broadcast::Sender<RecoveryEvent>,
}

impl RecoveryEventBroadcaster {
    /// Create new event broadcaster
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(1024);
        RecoveryEventBroadcaster { tx }
    }

    /// Emit an event to all subscribers
    pub fn emit(&self, event: RecoveryEvent) {
        let _ = self.tx.send(event);
    }

    /// Get a receiver for new events
    pub fn subscribe(&self) -> broadcast::Receiver<RecoveryEvent> {
        self.tx.subscribe()
    }
}

impl Default for RecoveryEventBroadcaster {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_broadcaster_creation() {
        let broadcaster = RecoveryEventBroadcaster::new();
        let _rx = broadcaster.subscribe();
    }

    #[test]
    fn test_recovery_event_serialization() {
        let event = RecoveryEvent::RecoveryEntered {
            sovereign_id: "test-id".to_string(),
            score_at_entry: 82,
            timestamp: "2026-05-11T12:34:56Z".to_string(),
        };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("RecoveryEntered"));
        assert!(json.contains("test-id"));
    }
}
