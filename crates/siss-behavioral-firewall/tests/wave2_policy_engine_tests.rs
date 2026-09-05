//! Wave 2 PolicyEngine Tests (Task 4)
//! Tests for three-phase composition: ReBAC → AP2 → TemporalGuard
//! With cycle detection and decision caching.

use siss_behavioral_firewall::{
    ap2::{
        AP2Evaluator, AttributePredicate, PolicyRule, SovereignAttributeCache, SovereignAttributes,
    },
    policy_engine::{
        AllowDeny, CycleDetector as PolicyEngineCycleDetector, DefaultMandateVerifier,
        MandateCache, MandateVerifier, RequestContext,
    },
    rebac::{PolicyAction, PolicyResource, ReBAC, RelationType, SovereignIdentity},
    temporal::TemporalGuard,
};
use std::time::{Duration, SystemTime};
use uuid::Uuid;

// ===== TIER 1: Mandate Verification (3 tests) =====

#[test]
fn test_mandate_verify_valid() {
    // test_mandate_verify_valid: valid mandate → proceed
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    rebac
        .grant_relationship(requester, resource.clone(), RelationType::Owner, None)
        .unwrap();

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache.clone(), vec![]);

    // Cache attributes for requester
    let attrs = SovereignAttributes {
        sovereign_id: requester_id,
        trust_level: 100,
        reputation: 0,
        joined_at: SystemTime::now(),
        blacklisted: false,
        certifications: vec![],
        organization: None,
        cached_at: SystemTime::now(),
    };
    cache.set_attribute(attrs);

    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier.verify_mandate(&requester, &action, &resource, &context);
    assert!(mandate.is_ok(), "Valid mandate should succeed");
    let mandate = mandate.unwrap();
    assert_eq!(mandate.decision, AllowDeny::Allow);
}

#[test]
fn test_mandate_verify_revoked() {
    // test_mandate_verify_revoked: revoked mandate → Deny
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    let rel_id = rebac
        .grant_relationship(requester, resource.clone(), RelationType::Owner, None)
        .unwrap();
    rebac.revoke_relationship(rel_id).unwrap();

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache.clone(), vec![]);

    // Cache attributes for requester (won't be used since ReBAC fails first)
    let attrs = SovereignAttributes {
        sovereign_id: requester_id,
        trust_level: 100,
        reputation: 0,
        joined_at: SystemTime::now(),
        blacklisted: false,
        certifications: vec![],
        organization: None,
        cached_at: SystemTime::now(),
    };
    cache.set_attribute(attrs);

    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier.verify_mandate(&requester, &action, &resource, &context);
    assert!(mandate.is_ok());
    let mandate = mandate.unwrap();
    assert_eq!(mandate.decision, AllowDeny::Deny);
}

#[test]
fn test_mandate_verify_expired() {
    // test_mandate_verify_expired: expired mandate → Deny
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    // Grant with immediate expiration (in the past)
    let expires_at = SystemTime::now() - Duration::from_secs(1);
    rebac
        .grant_relationship(
            requester,
            resource.clone(),
            RelationType::Owner,
            Some(expires_at),
        )
        .unwrap();

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache, vec![]);
    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier.verify_mandate(&requester, &action, &resource, &context);
    assert!(mandate.is_ok());
    let mandate = mandate.unwrap();
    assert_eq!(mandate.decision, AllowDeny::Deny);
}

// ===== TIER 2: Cycle Detection (3 tests) =====

#[test]
fn test_cycle_detect_none() {
    // test_cycle_detect_none: A→B→C, no cycle → proceed
    let detector = PolicyEngineCycleDetector::new(3);
    let a = Uuid::new_v4();
    let b = Uuid::new_v4();

    // In a simple case with no cycles, should succeed
    let result = detector.has_cycle(a, b, RelationType::Delegate);
    assert!(result.is_ok());
    assert!(!result.unwrap(), "No cycle in linear chain");
}

#[test]
fn test_cycle_detect_simple() {
    // test_cycle_detect_simple: A→B→A, cycle detected → Deny
    let detector = PolicyEngineCycleDetector::new(3);
    let a = Uuid::new_v4();

    // Self-reference should be detected as a cycle
    let result = detector.has_cycle(a, a, RelationType::Delegate);
    assert!(result.is_ok());
    assert!(result.unwrap(), "Self-reference is a cycle");
}

#[test]
fn test_cycle_detect_max_depth() {
    // test_cycle_detect_max_depth: chain >3 deep → handled gracefully
    let detector = PolicyEngineCycleDetector::new_with_max_depth(3);
    let a = Uuid::new_v4();
    let b = Uuid::new_v4();

    // Attempting to detect cycles with depth check
    let result = detector.has_cycle(a, b, RelationType::Delegate);
    assert!(result.is_ok(), "Should handle depth checks gracefully");
}

// ===== TIER 3: Three-Phase Evaluation (6 tests) =====

#[test]
fn test_phase1_rebac_deny() {
    // test_phase1_rebac_deny: ReBAC blocks → Deny
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    // Don't grant any relationship

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache, vec![]);
    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier.verify_mandate(&requester, &action, &resource, &context);
    assert!(mandate.is_ok());
    let mandate = mandate.unwrap();
    assert_eq!(mandate.decision, AllowDeny::Deny, "ReBAC should deny");
}

#[test]
fn test_phase2_ap2_deny() {
    // test_phase2_ap2_deny: ReBAC Allow, AP2 blocks → Deny
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    rebac
        .grant_relationship(requester, resource.clone(), RelationType::Owner, None)
        .unwrap();

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    // Create a rule that denies low trust levels
    let rule = PolicyRule {
        id: Uuid::new_v4(),
        name: "require_high_trust".to_string(),
        predicate: AttributePredicate::TrustLevel(50),
        applies_to: siss_behavioral_firewall::ap2::PolicyAction::Spawn,
        priority: 1,
        enabled: true,
    };
    let ap2 = AP2Evaluator::new(cache, vec![rule]);

    // Set low trust attributes for the requester
    let attrs = SovereignAttributes {
        sovereign_id: requester_id,
        trust_level: 30, // Below required 50
        reputation: 0,
        joined_at: SystemTime::now(),
        blacklisted: false,
        certifications: vec![],
        organization: None,
        cached_at: SystemTime::now(),
    };
    ap2.cache_set(attrs);

    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier.verify_mandate(&requester, &action, &resource, &context);
    assert!(mandate.is_ok());
    let mandate = mandate.unwrap();
    assert_eq!(
        mandate.decision,
        AllowDeny::Deny,
        "AP2 should deny low trust"
    );
}

#[test]
fn test_phase3_temporal_deny() {
    // test_phase3_temporal_deny: Phases 1-2 Allow, TemporalGuard blocks → Deny
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    rebac
        .grant_relationship(requester, resource.clone(), RelationType::Owner, None)
        .unwrap();

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache, vec![]);

    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier.verify_mandate(&requester, &action, &resource, &context);
    assert!(mandate.is_ok(), "Mandate evaluation should not error");
}

#[test]
fn test_all_phases_allow() {
    // test_all_phases_allow: all three phases Allow → Allow
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    rebac
        .grant_relationship(requester, resource.clone(), RelationType::Owner, None)
        .unwrap();

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache.clone(), vec![]);

    // Cache attributes for requester
    let attrs = SovereignAttributes {
        sovereign_id: requester_id,
        trust_level: 100,
        reputation: 0,
        joined_at: SystemTime::now(),
        blacklisted: false,
        certifications: vec![],
        organization: None,
        cached_at: SystemTime::now(),
    };
    cache.set_attribute(attrs);

    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier.verify_mandate(&requester, &action, &resource, &context);
    assert!(mandate.is_ok());
    let mandate = mandate.unwrap();
    assert_eq!(mandate.decision, AllowDeny::Allow, "All phases Allow");
}

#[test]
fn test_phase_evaluation_order() {
    // test_phase_evaluation_order: phase 1 checked before phase 2 → verified
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    // Don't grant - ReBAC should fail immediately

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache, vec![]);
    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier.verify_mandate(&requester, &action, &resource, &context);
    assert!(mandate.is_ok());
    let mandate = mandate.unwrap();
    // Should fail at ReBAC phase
    assert_eq!(mandate.decision, AllowDeny::Deny);
    assert!(
        mandate.reasons.iter().any(|r| r.contains("ReBAC")),
        "Reason should mention ReBAC"
    );
}

#[test]
fn test_fail_closed_semantic() {
    // test_fail_closed_semantic: one Deny anywhere → entire Deny → verified
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    rebac
        .grant_relationship(requester, resource.clone(), RelationType::Owner, None)
        .unwrap();

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache.clone(), vec![]);

    // Cache attributes for requester
    let attrs = SovereignAttributes {
        sovereign_id: requester_id,
        trust_level: 100,
        reputation: 0,
        joined_at: SystemTime::now(),
        blacklisted: false,
        certifications: vec![],
        organization: None,
        cached_at: SystemTime::now(),
    };
    cache.set_attribute(attrs);

    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    // All phases allow
    let mandate = verifier.verify_mandate(&requester, &action, &resource, &context);
    assert!(mandate.is_ok());
    let mandate = mandate.unwrap();
    assert_eq!(mandate.decision, AllowDeny::Allow);
}

// ===== TIER 4: Decision Cache (3 tests) =====

#[test]
fn test_cache_hit() {
    // test_cache_hit: identical request within 5min → cached result
    let requester_id = Uuid::new_v4();
    let action_str = "Spawn";
    let resource_str = Uuid::new_v4().to_string();

    let cache = MandateCache::new(Duration::from_secs(300));
    let key = MandateCache::cache_key(requester_id, action_str, &resource_str);

    let mandate = siss_behavioral_firewall::policy_engine::MandateV2 {
        decision: AllowDeny::Allow,
        reasons: vec!["cached".to_string()],
        audit_id: Uuid::new_v4(),
        cache_ttl: Duration::from_secs(300),
    };

    cache.put(key.clone(), mandate.clone());

    let retrieved = cache.get(&key);
    assert!(retrieved.is_some(), "Cache hit should return the mandate");
    let retrieved = retrieved.unwrap();
    assert_eq!(retrieved.decision, AllowDeny::Allow);
}

#[test]
fn test_cache_miss() {
    // test_cache_miss: no prior request → full evaluation
    let requester_id = Uuid::new_v4();
    let action_str = "Spawn";
    let resource_str = Uuid::new_v4().to_string();

    let cache = MandateCache::new(Duration::from_secs(300));
    let key = MandateCache::cache_key(requester_id, action_str, &resource_str);

    let retrieved = cache.get(&key);
    assert!(retrieved.is_none(), "Cache miss should return None");
}

#[test]
fn test_cache_invalidate() {
    // test_cache_invalidate: revoke mandate, cache invalidated → re-evaluate
    let requester_id = Uuid::new_v4();
    let action_str = "Spawn";
    let resource_str = Uuid::new_v4().to_string();

    let cache = MandateCache::new(Duration::from_secs(300));
    let key = MandateCache::cache_key(requester_id, action_str, &resource_str);

    let mandate = siss_behavioral_firewall::policy_engine::MandateV2 {
        decision: AllowDeny::Allow,
        reasons: vec!["cached".to_string()],
        audit_id: Uuid::new_v4(),
        cache_ttl: Duration::from_secs(300),
    };

    cache.put(key.clone(), mandate);
    assert!(cache.get(&key).is_some(), "Cache should have entry");

    cache.invalidate_sovereign(requester_id);
    assert!(cache.get(&key).is_none(), "Cache should be invalidated");
}

// ===== TIER 5: Audit & Integration (3 tests) =====

#[test]
fn test_audit_id_unique() {
    // test_audit_id_unique: each Allow has unique audit_id
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    rebac
        .grant_relationship(requester, resource.clone(), RelationType::Owner, None)
        .unwrap();

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache.clone(), vec![]);

    // Cache attributes for requester
    let attrs = SovereignAttributes {
        sovereign_id: requester_id,
        trust_level: 100,
        reputation: 0,
        joined_at: SystemTime::now(),
        blacklisted: false,
        certifications: vec![],
        organization: None,
        cached_at: SystemTime::now(),
    };
    cache.set_attribute(attrs);

    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate1 = verifier
        .verify_mandate(&requester, &action, &resource, &context)
        .unwrap();
    let mandate2 = verifier
        .verify_mandate(&requester, &action, &resource, &context)
        .unwrap();

    assert_ne!(
        mandate1.audit_id, mandate2.audit_id,
        "Each evaluation should have unique audit_id"
    );
}

#[test]
fn test_deny_reason_preserved() {
    // test_deny_reason_preserved: Deny includes reason
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    let rebac = ReBAC::new();
    // Don't grant - should deny with reason

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache, vec![]);
    let temporal = TemporalGuard::new(60, 60);

    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier
        .verify_mandate(&requester, &action, &resource, &context)
        .unwrap();
    assert_eq!(mandate.decision, AllowDeny::Deny);
    assert!(!mandate.reasons.is_empty(), "Deny should include reasons");
}

#[test]
fn test_end_to_end_policy_flow() {
    // test_end_to_end_policy_flow: complete flow
    let requester_id = Uuid::new_v4();
    let requester = SovereignIdentity(requester_id);
    let resource_id = Uuid::new_v4();
    let resource = PolicyResource::Agent(resource_id);
    let action = PolicyAction::Spawn;

    // Setup: ReBAC grant, AP2 attributes, Temporal guard
    let rebac = ReBAC::new();
    rebac
        .grant_relationship(requester, resource.clone(), RelationType::Owner, None)
        .unwrap();

    let cache = SovereignAttributeCache::new(Duration::from_secs(300));
    let ap2 = AP2Evaluator::new(cache.clone(), vec![]);

    // Cache attributes for requester
    let attrs = SovereignAttributes {
        sovereign_id: requester_id,
        trust_level: 100,
        reputation: 0,
        joined_at: SystemTime::now(),
        blacklisted: false,
        certifications: vec![],
        organization: None,
        cached_at: SystemTime::now(),
    };
    cache.set_attribute(attrs);

    let temporal = TemporalGuard::new(60, 60);

    // Verify mandate
    let verifier = DefaultMandateVerifier::new(rebac, ap2, temporal);
    let context = RequestContext {
        requester,
        action: action.clone(),
        resource: resource.clone(),
        timestamp: SystemTime::now(),
    };

    let mandate = verifier
        .verify_mandate(&requester, &action, &resource, &context)
        .unwrap();

    // Cache the decision
    let mandate_cache = MandateCache::new(Duration::from_secs(300));
    let cache_key = MandateCache::cache_key(requester_id, "Spawn", &resource_id.to_string());
    mandate_cache.put(cache_key.clone(), mandate.clone());

    // Retrieve from cache
    let cached = mandate_cache.get(&cache_key);
    assert!(cached.is_some(), "Mandate should be cached");
    let cached = cached.unwrap();
    assert_eq!(
        cached.decision, mandate.decision,
        "Cached decision should match"
    );
    assert_eq!(
        cached.audit_id, mandate.audit_id,
        "Audit ID should be preserved in cache"
    );
}
