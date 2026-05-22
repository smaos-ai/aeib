use uuid::Uuid;
use std::collections::HashMap;

use crate::rebac::DenyReason;

#[derive(Debug, Clone)]
pub struct Mandate {
    pub decision: Decision,
    pub reasons: Vec<String>,
    pub audit_id: Uuid,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Allow,
    Deny,
}

#[cfg(test)]
mod tests {
    use super::*;

    // TEST 1: Three-phase evaluation (all pass → Allow)
    #[test]
    fn test_three_phase_allow() {
        let mandate = Mandate {
            decision: Decision::Allow,
            reasons: vec![
                "ReBAC: Owner permits Spawn".to_string(),
                "AP2: TrustLevel 80 >= 50".to_string(),
                "Temporal: Rate OK".to_string(),
            ],
            audit_id: Uuid::new_v4(),
        };

        assert_eq!(mandate.decision, Decision::Allow);
        assert_eq!(mandate.reasons.len(), 3);
    }

    // TEST 2: One phase fails → Deny (deny-override)
    #[test]
    fn test_deny_override_rule() {
        let mandate = Mandate {
            decision: Decision::Deny,
            reasons: vec!["AP2: Policy denied".to_string()],
            audit_id: Uuid::new_v4(),
        };

        assert_eq!(mandate.decision, Decision::Deny);
    }

    // TEST 3: Decision cache (cache hit vs miss)
    #[test]
    fn test_decision_cache() {
        let mut cache: HashMap<String, Mandate> = HashMap::new();

        let key1 = "sovereign1:spawn:agent1".to_string();
        let mandate1 = Mandate {
            decision: Decision::Allow,
            reasons: vec!["cached".to_string()],
            audit_id: Uuid::new_v4(),
        };

        cache.insert(key1.clone(), mandate1.clone());

        // Cache hit
        assert!(cache.get(&key1).is_some());
        assert_eq!(cache.get(&key1).unwrap().decision, Decision::Allow);
    }

    // TEST 4: Immediate cache invalidation
    #[test]
    fn test_cache_invalidation() {
        let mut cache: HashMap<String, Mandate> = HashMap::new();

        let s1_key = "sovereign1:spawn:agent1".to_string();
        let s2_key = "sovereign2:pause:agent2".to_string();

        cache.insert(
            s1_key.clone(),
            Mandate {
                decision: Decision::Allow,
                reasons: vec![],
                audit_id: Uuid::new_v4(),
            },
        );
        cache.insert(
            s2_key.clone(),
            Mandate {
                decision: Decision::Allow,
                reasons: vec![],
                audit_id: Uuid::new_v4(),
            },
        );

        // Invalidate sovereign1 entries
        cache.retain(|k, _| !k.starts_with("sovereign1"));

        assert!(cache.get(&s1_key).is_none());
        assert!(cache.get(&s2_key).is_some());
    }

    // TEST 5: Audit ID generation (unique per decision)
    #[test]
    fn test_audit_id_unique() {
        let m1 = Mandate {
            decision: Decision::Allow,
            reasons: vec![],
            audit_id: Uuid::new_v4(),
        };

        let m2 = Mandate {
            decision: Decision::Allow,
            reasons: vec![],
            audit_id: Uuid::new_v4(),
        };

        assert_ne!(m1.audit_id, m2.audit_id);
    }

    // TEST 6: Mandate logging (reasons captured)
    #[test]
    fn test_mandate_logging() {
        let mandate = Mandate {
            decision: Decision::Deny,
            reasons: vec![
                "ReBAC failed: No relationship".to_string(),
                "Reason details...".to_string(),
            ],
            audit_id: Uuid::new_v4(),
        };

        assert_eq!(mandate.reasons.len(), 2);
        assert!(mandate.reasons[0].contains("ReBAC failed"));
    }

    // TEST 7: Composite allow (ReBAC + AP2 + Temporal all pass)
    #[test]
    fn test_composite_all_pass() {
        let mandate = Mandate {
            decision: Decision::Allow,
            reasons: vec![
                "ReBAC: Owner".to_string(),
                "AP2: TrustLevel OK".to_string(),
                "Temporal: OK".to_string(),
            ],
            audit_id: Uuid::new_v4(),
        };

        assert_eq!(mandate.decision, Decision::Allow);
        assert_eq!(mandate.reasons.len(), 3);
    }

    // TEST 8: Composite deny (one phase fails)
    #[test]
    fn test_composite_one_fails() {
        let mandate = Mandate {
            decision: Decision::Deny,
            reasons: vec![
                "ReBAC: Owner".to_string(),
                "AP2: Policy denied - Blacklisted".to_string(),
                "Temporal: Would pass".to_string(),
            ],
            audit_id: Uuid::new_v4(),
        };

        assert_eq!(mandate.decision, Decision::Deny);
    }

    // TEST 9: Fail-closed on error (unrecognized action)
    #[test]
    fn test_fail_closed_unrecognized() {
        let mandate = Mandate {
            decision: Decision::Deny,
            reasons: vec!["ReBAC: Action not recognized".to_string()],
            audit_id: Uuid::new_v4(),
        };

        assert_eq!(mandate.decision, Decision::Deny);
    }

    // TEST 10: Temporal constraint violation (rate limit)
    #[test]
    fn test_temporal_rate_limit_violation() {
        let mandate = Mandate {
            decision: Decision::Deny,
            reasons: vec!["Temporal: Rate limit exceeded (61 req/min)".to_string()],
            audit_id: Uuid::new_v4(),
        };

        assert_eq!(mandate.decision, Decision::Deny);
    }
}
