use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::{SystemTime, Duration};
use uuid::Uuid;
use dashmap::DashMap;

use crate::rebac::DenyReason;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PolicyAction {
    Spawn,
    Pause,
    Resume,
    Abort,
    Terminate,
    AssignTask,
    CancelTask,
    FinalizeTask,
    InitiateConsent,
    VoteConsent,
    RevokeGrant,
    ReadMetrics,
    StreamEvents,
    CreatePolicy,
    UpdatePolicy,
    DeletePolicy,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SovereignAttributes {
    pub sovereign_id: Uuid,
    pub trust_level: u32,      // 0-100
    pub reputation: i32,        // can be negative
    pub joined_at: SystemTime,
    pub blacklisted: bool,
    pub certifications: Vec<String>,
    pub organization: Option<String>,
    pub cached_at: SystemTime,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AttributePredicate {
    TrustLevel(u32),
    ReputationScore(i32),
    SenioritySince(SystemTime),
    NotBlacklisted,
    HasCertification(String),
    And(Box<AttributePredicate>, Box<AttributePredicate>),
    Or(Box<AttributePredicate>, Box<AttributePredicate>),
    Not(Box<AttributePredicate>),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyRule {
    pub id: Uuid,
    pub name: String,
    pub predicate: AttributePredicate,
    pub applies_to: PolicyAction,
    pub priority: u32,
    pub enabled: bool,
}

#[derive(Debug, Clone)]
pub struct SovereignAttributeCache {
    cache: Arc<DashMap<Uuid, CachedAttribute>>,
    freshness_window: Duration,
}

#[derive(Debug, Clone)]
struct CachedAttribute {
    attrs: SovereignAttributes,
}

impl SovereignAttributeCache {
    pub fn new(freshness_window: Duration) -> Self {
        SovereignAttributeCache {
            cache: Arc::new(DashMap::new()),
            freshness_window,
        }
    }

    pub fn get(&self, sovereign_id: Uuid) -> Result<SovereignAttributes, DenyReason> {
        // Check cache
        if let Some(cached) = self.cache.get(&sovereign_id) {
            if cached.attrs.cached_at.elapsed().unwrap_or(Duration::MAX) < self.freshness_window {
                return Ok(cached.attrs.clone());
            } else {
                // Expired, remove from cache
                drop(cached);
                self.cache.remove(&sovereign_id);
            }
        }

        // Fetch fresh from DB (simulated)
        self.fetch_from_db(sovereign_id)
    }

    pub fn set_attribute(&self, attrs: SovereignAttributes) {
        self.cache.insert(attrs.sovereign_id, CachedAttribute { attrs });
    }

    pub fn invalidate(&self, sovereign_id: Uuid) {
        self.cache.remove(&sovereign_id);
    }

    fn fetch_from_db(&self, sovereign_id: Uuid) -> Result<SovereignAttributes, DenyReason> {
        // In real implementation, fetch from PostgreSQL
        Err(DenyReason::AP2(format!("Attributes not found for sovereign {}", sovereign_id)))
    }
}

pub struct AP2Evaluator {
    attribute_cache: Arc<SovereignAttributeCache>,
    policy_rules: Arc<Vec<PolicyRule>>,
}

impl AP2Evaluator {
    pub fn new(cache: SovereignAttributeCache, rules: Vec<PolicyRule>) -> Self {
        AP2Evaluator {
            attribute_cache: Arc::new(cache),
            policy_rules: Arc::new(rules),
        }
    }

    pub fn evaluate(
        &self,
        sovereign_id: Uuid,
        action: PolicyAction,
    ) -> Result<String, DenyReason> {
        let attrs = self.attribute_cache.get(sovereign_id)?;

        let applicable_rules: Vec<_> = self.policy_rules
            .iter()
            .filter(|r| r.applies_to == action && r.enabled)
            .collect();

        if applicable_rules.is_empty() {
            return Ok("No AP2 restrictions apply".to_string());
        }

        let mut sorted = applicable_rules;
        sorted.sort_by_key(|r| std::cmp::Reverse(r.priority));

        for rule in sorted {
            if !self.evaluate_predicate(&rule.predicate, &attrs)? {
                return Err(DenyReason::AP2(format!(
                    "Policy '{}' denied: {}",
                    rule.name, rule.id
                )));
            }
        }

        Ok("All AP2 policies satisfied".to_string())
    }

    fn evaluate_predicate(
        &self,
        predicate: &AttributePredicate,
        attrs: &SovereignAttributes,
    ) -> Result<bool, DenyReason> {
        match predicate {
            AttributePredicate::TrustLevel(required) => Ok(attrs.trust_level >= *required),
            AttributePredicate::ReputationScore(required) => Ok(attrs.reputation >= *required),
            AttributePredicate::SenioritySince(cutoff) => Ok(attrs.joined_at <= *cutoff),
            AttributePredicate::NotBlacklisted => Ok(!attrs.blacklisted),
            AttributePredicate::HasCertification(cert) => Ok(attrs.certifications.contains(cert)),
            AttributePredicate::And(left, right) => {
                Ok(self.evaluate_predicate(left, attrs)? &&
                   self.evaluate_predicate(right, attrs)?)
            }
            AttributePredicate::Or(left, right) => {
                Ok(self.evaluate_predicate(left, attrs)? ||
                   self.evaluate_predicate(right, attrs)?)
            }
            AttributePredicate::Not(inner) => {
                Ok(!self.evaluate_predicate(inner, attrs)?)
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sovereign(id: u64) -> Uuid {
        Uuid::from_u64_pair(id, 0)
    }

    // TEST 1: Attribute cache hit (within freshness window)
    #[test]
    fn test_attribute_cache_hit() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let s1 = sovereign(1);

        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 80,
            reputation: 50,
            joined_at: SystemTime::now() - Duration::from_secs(3600),
            blacklisted: false,
            certifications: vec!["certified".to_string()],
            organization: Some("acme".to_string()),
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs.clone());
        let retrieved = cache.get(s1).unwrap();

        assert_eq!(retrieved.trust_level, 80);
        assert_eq!(retrieved.reputation, 50);
    }

    // TEST 2: Attribute cache expiry (beyond freshness window)
    #[test]
    fn test_attribute_cache_expiry() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(1));
        let s1 = sovereign(1);

        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 80,
            reputation: 50,
            joined_at: SystemTime::now(),
            blacklisted: false,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now() - Duration::from_secs(2), // Expired
        };

        cache.set_attribute(attrs.clone());

        // Wait to ensure expiry
        std::thread::sleep(Duration::from_millis(100));

        // Should fail (attribute expired, not in DB)
        let result = cache.get(s1);
        assert!(result.is_err());
    }

    // TEST 3: Attribute invalidation
    #[test]
    fn test_attribute_invalidation() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let s1 = sovereign(1);

        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 80,
            reputation: 50,
            joined_at: SystemTime::now(),
            blacklisted: false,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);
        assert!(cache.get(s1).is_ok());

        // Invalidate
        cache.invalidate(s1);

        // Should now fail (not in cache or DB)
        assert!(cache.get(s1).is_err());
    }

    // TEST 4: TrustLevel predicate evaluation
    #[test]
    fn test_trust_level_predicate() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "min_trust".to_string(),
            predicate: AttributePredicate::TrustLevel(50),
            applies_to: PolicyAction::Spawn,
            priority: 1,
            enabled: true,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 60,
            reputation: 0,
            joined_at: SystemTime::now(),
            blacklisted: false,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should pass (trust_level 60 >= 50)
        assert!(evaluator.evaluate(s1, PolicyAction::Spawn).is_ok());
    }

    // TEST 5: Reputation score predicate
    #[test]
    fn test_reputation_score_predicate() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "min_rep".to_string(),
            predicate: AttributePredicate::ReputationScore(30),
            applies_to: PolicyAction::VoteConsent,
            priority: 1,
            enabled: true,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 100,
            reputation: 20,
            joined_at: SystemTime::now(),
            blacklisted: false,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should fail (reputation 20 < 30)
        assert!(evaluator.evaluate(s1, PolicyAction::VoteConsent).is_err());
    }

    // TEST 6: NotBlacklisted predicate
    #[test]
    fn test_not_blacklisted_predicate() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "not_blacklisted".to_string(),
            predicate: AttributePredicate::NotBlacklisted,
            applies_to: PolicyAction::Spawn,
            priority: 1,
            enabled: true,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 100,
            reputation: 100,
            joined_at: SystemTime::now(),
            blacklisted: true,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should fail (blacklisted)
        assert!(evaluator.evaluate(s1, PolicyAction::Spawn).is_err());
    }

    // TEST 7: HasCertification predicate
    #[test]
    fn test_has_certification_predicate() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "needs_cert".to_string(),
            predicate: AttributePredicate::HasCertification("security".to_string()),
            applies_to: PolicyAction::CreatePolicy,
            priority: 1,
            enabled: true,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 100,
            reputation: 100,
            joined_at: SystemTime::now(),
            blacklisted: false,
            certifications: vec!["other".to_string()],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should fail (missing "security" cert)
        assert!(evaluator.evaluate(s1, PolicyAction::CreatePolicy).is_err());
    }

    // TEST 8: And predicate (both must be true)
    #[test]
    fn test_and_predicate() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "both_required".to_string(),
            predicate: AttributePredicate::And(
                Box::new(AttributePredicate::TrustLevel(50)),
                Box::new(AttributePredicate::ReputationScore(30)),
            ),
            applies_to: PolicyAction::Spawn,
            priority: 1,
            enabled: true,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 60,
            reputation: 20,
            joined_at: SystemTime::now(),
            blacklisted: false,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should fail (reputation 20 < 30, even though trust 60 >= 50)
        assert!(evaluator.evaluate(s1, PolicyAction::Spawn).is_err());
    }

    // TEST 9: Or predicate (either can be true)
    #[test]
    fn test_or_predicate() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "either_works".to_string(),
            predicate: AttributePredicate::Or(
                Box::new(AttributePredicate::TrustLevel(100)),
                Box::new(AttributePredicate::ReputationScore(50)),
            ),
            applies_to: PolicyAction::VoteConsent,
            priority: 1,
            enabled: true,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 30,
            reputation: 60,
            joined_at: SystemTime::now(),
            blacklisted: false,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should pass (reputation 60 >= 50, even though trust 30 < 100)
        assert!(evaluator.evaluate(s1, PolicyAction::VoteConsent).is_ok());
    }

    // TEST 10: Not predicate (negation)
    #[test]
    fn test_not_predicate() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "not_low_trust".to_string(),
            predicate: AttributePredicate::Not(Box::new(AttributePredicate::TrustLevel(30))),
            applies_to: PolicyAction::Spawn,
            priority: 1,
            enabled: true,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 20,
            reputation: 100,
            joined_at: SystemTime::now(),
            blacklisted: false,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should succeed (NOT (trust >= 30) is true because 20 < 30)
        assert!(evaluator.evaluate(s1, PolicyAction::Spawn).is_ok());
    }

    // TEST 11: Priority-ordered rule evaluation (highest priority first)
    #[test]
    fn test_priority_ordered_evaluation() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![
            PolicyRule {
                id: Uuid::new_v4(),
                name: "low_priority".to_string(),
                predicate: AttributePredicate::TrustLevel(100),
                applies_to: PolicyAction::Spawn,
                priority: 1,
                enabled: true,
            },
            PolicyRule {
                id: Uuid::new_v4(),
                name: "high_priority".to_string(),
                predicate: AttributePredicate::ReputationScore(200),
                applies_to: PolicyAction::Spawn,
                priority: 10,
                enabled: true,
            },
        ];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 100,
            reputation: 50,
            joined_at: SystemTime::now(),
            blacklisted: false,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should fail on high-priority rule first (reputation 50 < 200)
        assert!(evaluator.evaluate(s1, PolicyAction::Spawn).is_err());
    }

    // TEST 12: Deny-override rule (one fail = entire fail)
    #[test]
    fn test_deny_override_rule() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![
            PolicyRule {
                id: Uuid::new_v4(),
                name: "rule1".to_string(),
                predicate: AttributePredicate::TrustLevel(50),
                applies_to: PolicyAction::Spawn,
                priority: 1,
                enabled: true,
            },
            PolicyRule {
                id: Uuid::new_v4(),
                name: "rule2".to_string(),
                predicate: AttributePredicate::NotBlacklisted,
                applies_to: PolicyAction::Spawn,
                priority: 1,
                enabled: true,
            },
        ];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 80,
            reputation: 100,
            joined_at: SystemTime::now(),
            blacklisted: true,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should fail (one rule fails, deny-override)
        assert!(evaluator.evaluate(s1, PolicyAction::Spawn).is_err());
    }

    // TEST 13: No applicable rules (allow by default)
    #[test]
    fn test_no_applicable_rules() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "other_action".to_string(),
            predicate: AttributePredicate::TrustLevel(50),
            applies_to: PolicyAction::Pause,
            priority: 1,
            enabled: true,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 10,
            reputation: 10,
            joined_at: SystemTime::now(),
            blacklisted: true,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should pass (no rules apply to Spawn)
        assert!(evaluator.evaluate(s1, PolicyAction::Spawn).is_ok());
    }

    // TEST 14: Disabled rule (should be skipped)
    #[test]
    fn test_disabled_rule_skipped() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "disabled_rule".to_string(),
            predicate: AttributePredicate::TrustLevel(100),
            applies_to: PolicyAction::Spawn,
            priority: 1,
            enabled: false,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 10,
            reputation: 10,
            joined_at: SystemTime::now(),
            blacklisted: true,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should pass (disabled rule is skipped)
        assert!(evaluator.evaluate(s1, PolicyAction::Spawn).is_ok());
    }

    // TEST 15: SenioritySince predicate (joined before cutoff)
    #[test]
    fn test_seniority_since_predicate() {
        let cache = SovereignAttributeCache::new(Duration::from_secs(300));
        let cutoff = SystemTime::now() - Duration::from_secs(86400); // 1 day ago

        let rules = vec![PolicyRule {
            id: Uuid::new_v4(),
            name: "senior_only".to_string(),
            predicate: AttributePredicate::SenioritySince(cutoff),
            applies_to: PolicyAction::CreatePolicy,
            priority: 1,
            enabled: true,
        }];

        let evaluator = AP2Evaluator::new(cache.clone(), rules);

        let s1 = sovereign(1);
        let attrs = SovereignAttributes {
            sovereign_id: s1,
            trust_level: 100,
            reputation: 100,
            joined_at: cutoff - Duration::from_secs(3600), // 1 hour before cutoff
            blacklisted: false,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        };

        cache.set_attribute(attrs);

        // Should pass (joined before cutoff)
        assert!(evaluator.evaluate(s1, PolicyAction::CreatePolicy).is_ok());
    }
}
