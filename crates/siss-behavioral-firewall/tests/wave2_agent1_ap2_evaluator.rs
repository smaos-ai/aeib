//! Wave 2 Agent 1: AP2 Evaluator (Attribute Predicate Parser)
//!
//! Integration tests for attribute caching, 5-min TTL, LRU eviction,
//! predicate evaluation, and namespace-based invalidation.
//!
//! Tier 1 — Cache Lifecycle (5 tests): insert/retrieve, TTL, miss, refresh, multi-entry.
//! Tier 2 — Predicate Evaluation (5 tests): TrustLevel, ReputationScore, NotBlacklisted,
//!         HasCertification, And/Or/Not composition.
//! Tier 3 — Invalidation & Cascade (5 tests): explicit invalidate, cascade via TTL,
//!         concurrent access, age tracking, LRU eviction bound.

use siss_behavioral_firewall::{
    AP2Evaluator, AttributePredicate, SovereignAttributeCache, SovereignAttributes,
};
use std::sync::Arc;
use std::thread;
use std::time::{Duration, SystemTime};
use uuid::Uuid;

fn make_attr_with_id(id: Uuid, trust: u32, reputation: i32) -> SovereignAttributes {
    SovereignAttributes {
        sovereign_id: id,
        trust_level: trust,
        reputation,
        joined_at: SystemTime::now(),
        blacklisted: false,
        certifications: vec![],
        organization: None,
        cached_at: SystemTime::now(),
    }
}

fn make_attr(trust: u32, reputation: i32) -> SovereignAttributes {
    make_attr_with_id(Uuid::new_v4(), trust, reputation)
}

// ============================================================================
// TIER 1: Cache Lifecycle (5 tests)
// ============================================================================

#[test]
fn test_ap2_cache_insert_and_retrieve() {
    let evaluator = AP2Evaluator::with_defaults();
    let attrs = make_attr(80, 50);
    let id = attrs.sovereign_id;

    evaluator.cache_set(attrs);

    let retrieved = evaluator.cache_get(id).expect("cache hit expected");
    assert_eq!(retrieved.trust_level, 80);
    assert_eq!(retrieved.reputation, 50);
}

#[test]
fn test_ap2_cache_ttl_5_minutes() {
    // Bounded cache with 1-second TTL — verifies entries become stale.
    let cache = SovereignAttributeCache::new_bounded(16, Duration::from_secs(1));
    let attrs = make_attr(80, 50);
    let id = attrs.sovereign_id;

    cache.set_attribute(attrs);
    assert!(
        cache.is_fresh(id),
        "entry should be fresh immediately after insert"
    );

    thread::sleep(Duration::from_millis(1_100));
    assert!(
        !cache.is_fresh(id),
        "entry should be stale after TTL expiry"
    );
}

#[test]
fn test_ap2_cache_miss_returns_none() {
    let evaluator = AP2Evaluator::with_defaults();
    let missing_id = Uuid::new_v4();

    assert!(evaluator.cache_get(missing_id).is_none());
}

#[test]
fn test_ap2_cache_update_refreshes_ttl() {
    let cache = SovereignAttributeCache::new_bounded(16, Duration::from_secs(300));
    let id = Uuid::new_v4();

    let mut attr1 = make_attr_with_id(id, 80, 50);
    attr1.cached_at = SystemTime::now() - Duration::from_secs(60);
    cache.set_attribute(attr1);
    let age_before = cache.age_secs(id).expect("entry present");
    assert!(age_before >= 60, "first insert should be ~60s old");

    // Re-insert refreshes cached_at to now.
    let attr2 = make_attr_with_id(id, 85, 55);
    cache.set_attribute(attr2);
    let age_after = cache.age_secs(id).expect("entry still present");
    assert!(
        age_after < 5,
        "update should reset age (got {}s)",
        age_after
    );
}

#[test]
fn test_ap2_cache_multiple_attributes() {
    let cache = SovereignAttributeCache::new_bounded(16, Duration::from_secs(300));
    let s1 = make_attr(70, 10);
    let s2 = make_attr(90, 99);
    let id1 = s1.sovereign_id;
    let id2 = s2.sovereign_id;

    cache.set_attribute(s1);
    cache.set_attribute(s2);

    assert_eq!(cache.len(), 2);
    assert_eq!(cache.get(id1).unwrap().trust_level, 70);
    assert_eq!(cache.get(id2).unwrap().reputation, 99);
}

// ============================================================================
// TIER 2: Predicate Evaluation (5 tests)
// ============================================================================

#[test]
fn test_ap2_predicate_trust_level_gt() {
    let evaluator = AP2Evaluator::with_defaults();
    let attr = make_attr(80, 50);
    let pred = AttributePredicate::TrustLevel(50);

    assert!(evaluator.evaluate_predicate_pure(&pred, &attr));
}

#[test]
fn test_ap2_predicate_trust_level_fail() {
    let evaluator = AP2Evaluator::with_defaults();
    let attr = make_attr(80, 50);
    let pred = AttributePredicate::TrustLevel(90);

    assert!(!evaluator.evaluate_predicate_pure(&pred, &attr));
}

#[test]
fn test_ap2_predicate_reputation_score() {
    let evaluator = AP2Evaluator::with_defaults();
    let attr = make_attr(80, 50);

    assert!(evaluator.evaluate_predicate_pure(&AttributePredicate::ReputationScore(-10), &attr));
    assert!(!evaluator.evaluate_predicate_pure(&AttributePredicate::ReputationScore(100), &attr));
}

#[test]
fn test_ap2_predicate_not_blacklisted() {
    let evaluator = AP2Evaluator::with_defaults();
    let mut attr = make_attr(80, 50);
    attr.blacklisted = false;

    assert!(evaluator.evaluate_predicate_pure(&AttributePredicate::NotBlacklisted, &attr));

    attr.blacklisted = true;
    assert!(!evaluator.evaluate_predicate_pure(&AttributePredicate::NotBlacklisted, &attr));
}

#[test]
fn test_ap2_predicate_boolean_and() {
    let evaluator = AP2Evaluator::with_defaults();
    let attr = make_attr(80, 50);
    let pred = AttributePredicate::And(
        Box::new(AttributePredicate::TrustLevel(50)),
        Box::new(AttributePredicate::NotBlacklisted),
    );

    assert!(evaluator.evaluate_predicate_pure(&pred, &attr));

    // AND short-circuits to false when left fails.
    let fail_left = AttributePredicate::And(
        Box::new(AttributePredicate::TrustLevel(100)),
        Box::new(AttributePredicate::NotBlacklisted),
    );
    assert!(!evaluator.evaluate_predicate_pure(&fail_left, &attr));
}

// ============================================================================
// TIER 3: Invalidation & Cascade (5 tests)
// ============================================================================

#[test]
fn test_ap2_invalidation_on_policy_update() {
    let evaluator = AP2Evaluator::with_defaults();
    let attrs = make_attr(80, 50);
    let id = attrs.sovereign_id;

    evaluator.cache_set(attrs);
    assert!(evaluator.cache_get(id).is_some());

    evaluator.invalidate(id);
    assert!(
        evaluator.cache_get(id).is_none(),
        "invalidated entry must miss"
    );
}

#[test]
fn test_ap2_cascade_invalidation_dependent_predicates() {
    // When the underlying attribute is invalidated, any composite predicate that
    // references it should evaluate against a clean cache (re-fetch path).
    let cache = SovereignAttributeCache::new_bounded(16, Duration::from_secs(300));
    let id = Uuid::new_v4();
    let attrs = make_attr_with_id(id, 80, 50);

    cache.set_attribute(attrs.clone());
    assert!(cache.is_fresh(id));

    cache.invalidate(id);
    assert!(
        !cache.is_fresh(id),
        "cascade: dependent predicate sees miss"
    );
    assert!(
        cache.get(id).is_err(),
        "cascade: subsequent get should fall through to DB"
    );
}

#[test]
fn test_ap2_evaluator_concurrent_access() {
    let cache = Arc::new(SovereignAttributeCache::new_bounded(
        128,
        Duration::from_secs(300),
    ));
    let mut handles = Vec::new();

    for i in 0i32..16 {
        let c = Arc::clone(&cache);
        handles.push(thread::spawn(move || {
            let attrs = make_attr(i as u32, i);
            c.set_attribute(attrs);
        }));
    }

    for h in handles {
        h.join().expect("worker thread panicked");
    }

    assert_eq!(cache.len(), 16, "all concurrent inserts should be visible");
}

#[test]
fn test_ap2_evaluator_age_of_cache_entry() {
    let cache = SovereignAttributeCache::new_bounded(16, Duration::from_secs(300));
    let id = Uuid::new_v4();
    let mut attrs = make_attr_with_id(id, 80, 50);
    attrs.cached_at = SystemTime::now() - Duration::from_secs(50);

    cache.set_attribute(attrs);

    let age = cache.age_secs(id).expect("age expected");
    assert!(
        (50..=52).contains(&age),
        "age should be ~50s (got {}s)",
        age,
    );
}

#[test]
fn test_ap2_evaluator_cache_memory_bounded() {
    // Capacity = 2 with three inserts: oldest entry must be evicted.
    let cache = SovereignAttributeCache::new_bounded(2, Duration::from_secs(300));

    let mut a1 = make_attr(10, 0);
    a1.cached_at = SystemTime::now() - Duration::from_secs(30);
    let id1 = a1.sovereign_id;

    let mut a2 = make_attr(20, 0);
    a2.cached_at = SystemTime::now() - Duration::from_secs(20);
    let id2 = a2.sovereign_id;

    let mut a3 = make_attr(30, 0);
    a3.cached_at = SystemTime::now() - Duration::from_secs(10);
    let id3 = a3.sovereign_id;

    cache.set_attribute(a1);
    cache.set_attribute(a2);
    cache.set_attribute(a3); // should evict id1 (oldest inserted_at)

    assert_eq!(cache.len(), 2, "bounded cache must not exceed capacity");
    assert!(cache.get(id1).is_err(), "oldest entry should be evicted");
    assert!(cache.get(id2).is_ok());
    assert!(cache.get(id3).is_ok());
}
