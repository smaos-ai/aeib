use crate::trust_event_broadcaster::TrustUpdateSignal;

/// Determine if a trust update signal represents a severe penalty.
pub fn is_severe_penalty(signal: &TrustUpdateSignal) -> bool {
    signal.new_score < 25 || signal.decay_component < -50 || signal.implicit_component < -30
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use uuid::Uuid;

    #[test]
    fn test_is_severe_score_below_25() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 12,
            explicit_component: 0,
            implicit_component: 0,
            decay_component: 0,
            transitive_component: None,
            timestamp: Utc::now(),
        };
        assert!(is_severe_penalty(&signal));
    }

    #[test]
    fn test_is_severe_decay_below_50() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 50,
            explicit_component: 0,
            implicit_component: 0,
            decay_component: -51,
            transitive_component: None,
            timestamp: Utc::now(),
        };
        assert!(is_severe_penalty(&signal));
    }

    #[test]
    fn test_is_severe_slash_implicit_below_30() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 50,
            explicit_component: 0,
            implicit_component: -31,
            decay_component: 0,
            transitive_component: None,
            timestamp: Utc::now(),
        };
        assert!(is_severe_penalty(&signal));
    }

    #[test]
    fn test_not_severe_above_all_thresholds() {
        let signal = TrustUpdateSignal {
            source_id: Uuid::nil(),
            target_id: Uuid::nil(),
            new_score: 30,
            explicit_component: 0,
            implicit_component: -10,
            decay_component: -10,
            transitive_component: None,
            timestamp: Utc::now(),
        };
        assert!(!is_severe_penalty(&signal));
    }
}
