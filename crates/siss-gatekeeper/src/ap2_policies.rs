use siss_behavioral_firewall::ap2::{
    SovereignAttributes, AttributePredicate, PolicyRule, PolicyAction,
};
use std::time::SystemTime;
use uuid::Uuid;

#[derive(Debug, PartialEq)]
pub enum PolicyDecision {
    Allow,
    Deny(String),
}

pub struct PolicySet {
    rules: Vec<PolicyRule>,
}

impl PolicySet {
    pub fn new() -> Self {
        PolicySet { rules: vec![] }
    }

    pub fn add_rule(&mut self, rule: PolicyRule) {
        self.rules.push(rule);
        // Sort by priority descending (highest priority first)
        self.rules.sort_by(|a, b| b.priority.cmp(&a.priority));
    }

    pub fn evaluate(
        &self,
        attrs: &SovereignAttributes,
        action: &PolicyAction,
    ) -> PolicyDecision {
        let mut allow_found = false;

        // Iterate rules in sorted order (highest priority first)
        for rule in &self.rules {
            // Only evaluate rules that apply to this action
            if rule.applies_to != *action {
                continue;
            }

            // Evaluate the predicate
            if Self::evaluate_predicate(&rule.predicate, attrs) {
                // Predicate matched
                if rule.enabled {
                    // Check if this is an ALLOW rule
                    // For now, we treat all matching rules as ALLOW
                    // But we need to check if rule indicates DENY
                    // Since PolicyRule doesn't have an action field, we check the rule name pattern
                    // or we need a way to distinguish ALLOW from DENY
                    allow_found = true;
                }
            } else {
                // Predicate did not match - this is a DENY
                if rule.enabled {
                    return PolicyDecision::Deny(format!("Policy '{}' denied", rule.name));
                }
            }
        }

        // Fail-closed default: if no allow found, deny
        if allow_found {
            PolicyDecision::Allow
        } else if self.rules.iter().any(|r| r.applies_to == *action) {
            // If there are applicable rules but none allowed, deny
            PolicyDecision::Deny("No applicable allow policy found".to_string())
        } else {
            // No rules apply, default to deny (fail-closed)
            PolicyDecision::Deny("No applicable policies".to_string())
        }
    }

    fn evaluate_predicate(predicate: &AttributePredicate, attrs: &SovereignAttributes) -> bool {
        match predicate {
            AttributePredicate::TrustLevel(required) => attrs.trust_level >= *required,
            AttributePredicate::ReputationScore(required) => attrs.reputation >= *required,
            AttributePredicate::SenioritySince(cutoff) => attrs.joined_at <= *cutoff,
            AttributePredicate::NotBlacklisted => !attrs.blacklisted,
            AttributePredicate::HasCertification(cert) => attrs.certifications.contains(cert),
            AttributePredicate::And(left, right) => {
                Self::evaluate_predicate(left, attrs) && Self::evaluate_predicate(right, attrs)
            }
            AttributePredicate::Or(left, right) => {
                Self::evaluate_predicate(left, attrs) || Self::evaluate_predicate(right, attrs)
            }
            AttributePredicate::Not(inner) => !Self::evaluate_predicate(inner, attrs),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    fn sovereign_attrs(trust_level: u32, blacklisted: bool) -> SovereignAttributes {
        SovereignAttributes {
            sovereign_id: Uuid::new_v4(),
            trust_level,
            reputation: 50,
            joined_at: SystemTime::now() - Duration::from_secs(3600),
            blacklisted,
            certifications: vec![],
            organization: None,
            cached_at: SystemTime::now(),
        }
    }

    // TEST 1: Compound predicate allows trusted non-blacklisted agent
    #[test]
    fn test_compound_predicate_allow() {
        let mut policy_set = PolicySet::new();
        let rule = PolicyRule {
            id: Uuid::new_v4(),
            name: "allow_trusted_clean".to_string(),
            predicate: AttributePredicate::And(
                Box::new(AttributePredicate::TrustLevel(80)),
                Box::new(AttributePredicate::NotBlacklisted),
            ),
            applies_to: PolicyAction::Spawn,
            priority: 10,
            enabled: true,
        };
        policy_set.add_rule(rule);

        let attrs = sovereign_attrs(85, false);
        let decision = policy_set.evaluate(&attrs, &PolicyAction::Spawn);

        assert_eq!(decision, PolicyDecision::Allow);
    }

    // TEST 2: Deny overrides allow when conflicting rules exist
    #[test]
    fn test_deny_overrides_allow() {
        let mut policy_set = PolicySet::new();

        // Allow rule: trust >= 50
        let allow_rule = PolicyRule {
            id: Uuid::new_v4(),
            name: "allow".to_string(),
            predicate: AttributePredicate::TrustLevel(50),
            applies_to: PolicyAction::Spawn,
            priority: 5,
            enabled: true,
        };

        // Deny rule: must not be blacklisted (denies if blacklisted)
        let deny_rule = PolicyRule {
            id: Uuid::new_v4(),
            name: "deny_blacklisted".to_string(),
            predicate: AttributePredicate::NotBlacklisted,
            applies_to: PolicyAction::Spawn,
            priority: 10, // Higher priority
            enabled: true,
        };

        policy_set.add_rule(allow_rule);
        policy_set.add_rule(deny_rule);

        // Agent with high trust but blacklisted
        let attrs = sovereign_attrs(80, true);
        let decision = policy_set.evaluate(&attrs, &PolicyAction::Spawn);

        assert_eq!(decision, PolicyDecision::Deny("Policy 'deny_blacklisted' denied".to_string()));
    }

    // TEST 3: 1000 evaluations of same PolicySet complete under 10ms
    #[test]
    fn test_policy_1000_evaluations_under_10ms() {
        let mut policy_set = PolicySet::new();

        // Add multiple rules
        for i in 0..5 {
            let rule = PolicyRule {
                id: Uuid::new_v4(),
                name: format!("rule_{}", i),
                predicate: if i % 2 == 0 {
                    AttributePredicate::TrustLevel(50)
                } else {
                    AttributePredicate::NotBlacklisted
                },
                applies_to: PolicyAction::Spawn,
                priority: (5 - i) as u32,
                enabled: true,
            };
            policy_set.add_rule(rule);
        }

        let attrs = sovereign_attrs(80, false);

        let start = std::time::Instant::now();
        for _ in 0..1000 {
            let _ = policy_set.evaluate(&attrs, &PolicyAction::Spawn);
        }
        let elapsed = start.elapsed();

        assert!(
            elapsed.as_millis() < 10,
            "1000 evaluations took {}ms (expected < 10ms)",
            elapsed.as_millis()
        );
    }
}
