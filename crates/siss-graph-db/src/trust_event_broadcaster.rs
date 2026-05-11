use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tokio::sync::broadcast;
use uuid::Uuid;

/// Trust network update signal for AutoResearch anomaly detection.
/// Lives in siss-graph-db (not siss-agent-shell) to avoid circular dependency.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrustUpdateSignal {
    pub source_id: Uuid,
    pub target_id: Uuid,
    pub new_score: i16,
    pub explicit_component: i16,
    pub implicit_component: i16,
    pub decay_component: i16,
    pub transitive_component: Option<i16>,
    pub timestamp: DateTime<Utc>,
}

/// Broadcast channel for emitting trust update signals to subscribers (e.g. AutoResearch watcher).
/// Pattern matches EventBroadcaster in siss-agent-card/src/events.rs.
pub struct TrustEventBroadcaster {
    tx: broadcast::Sender<TrustUpdateSignal>,
}

impl TrustEventBroadcaster {
    /// Create a new trust event broadcaster with 256 capacity.
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(256);
        TrustEventBroadcaster { tx }
    }

    /// Emit a trust update signal to all subscribers.
    /// Fire-and-forget: if no subscribers, signal is dropped silently.
    pub fn emit(&self, signal: TrustUpdateSignal) {
        let _ = self.tx.send(signal);
    }

    /// Get a receiver for new trust signals.
    /// Each caller gets an independent receiver.
    pub fn subscribe(&self) -> broadcast::Receiver<TrustUpdateSignal> {
        self.tx.subscribe()
    }
}

impl Default for TrustEventBroadcaster {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_broadcaster_creation() {
        let broadcaster = TrustEventBroadcaster::new();
        let _rx = broadcaster.subscribe();
    }

    #[test]
    fn test_broadcaster_emit_fire_and_forget() {
        let broadcaster = TrustEventBroadcaster::new();
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 50,
            explicit_component: 60,
            implicit_component: -10,
            decay_component: 0,
            transitive_component: None,
            timestamp: Utc::now(),
        };
        // Should not panic even with no subscribers
        broadcaster.emit(signal);
    }

    #[test]
    fn test_signal_serialization() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 75,
            explicit_component: 80,
            implicit_component: 0,
            decay_component: -5,
            transitive_component: Some(10),
            timestamp: Utc::now(),
        };
        let json = serde_json::to_string(&signal);
        assert!(json.is_ok());
    }
}
