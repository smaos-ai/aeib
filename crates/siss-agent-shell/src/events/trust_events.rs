use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Trust topology events emitted by Phase 21 trust system.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TrustTopologyEvent {
    TrustEntered {
        source_id: Uuid,
        target_id: Uuid,
        initial_score: i16,
        timestamp: DateTime<Utc>,
    },
    TrustScoreUpdated {
        source_id: Uuid,
        target_id: Uuid,
        new_score: i16,
        explicit_component: i16,
        implicit_component: i16,
        decay_component: i16,
        transitive_component: Option<i16>,
        timestamp: DateTime<Utc>,
    },
    TrustDecayed {
        source_id: Uuid,
        target_id: Uuid,
        final_score: i16,
        timestamp: DateTime<Utc>,
    },
}

impl TrustTopologyEvent {
    /// Get the event type name for logging/filtering.
    pub fn event_type(&self) -> &'static str {
        match self {
            Self::TrustEntered { .. } => "trust_entered",
            Self::TrustScoreUpdated { .. } => "trust_score_updated",
            Self::TrustDecayed { .. } => "trust_decayed",
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trust_event_types() {
        let now = Utc::now();
        let event = TrustTopologyEvent::TrustEntered {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            initial_score: 75,
            timestamp: now,
        };
        assert_eq!(event.event_type(), "trust_entered");
    }

    #[test]
    fn test_trust_event_serialization() {
        let now = Utc::now();
        let event = TrustTopologyEvent::TrustScoreUpdated {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 80,
            explicit_component: 80,
            implicit_component: 0,
            decay_component: 0,
            transitive_component: None,
            timestamp: now,
        };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("TrustScoreUpdated") || json.contains("trust_score_updated"));
    }
}
