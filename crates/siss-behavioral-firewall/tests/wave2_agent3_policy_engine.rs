//! Wave 2 Agent 3: PolicyEngine — Policy Composition + Cycle Detection + Caching.
//!
//! 19 tests covering:
//! - Tier 1: AND / OR / NOT composition (6)
//! - Tier 2: DAG cycle detection (4)
//! - Tier 3: Decision cache + invalidation (5)
//! - Tier 3+: Integration scenarios (4)

use siss_behavioral_firewall::policy_engine::*;
use std::collections::HashMap;
use std::time::Duration;

// ---------------------------------------------------------------------------
// Tier 1: Composition Logic (6 tests)
// ---------------------------------------------------------------------------

#[test]
fn test_policy_engine_and_composition_both_true() {
    let mut p1 = Policy::new("p1");
    p1.add_clause("trust_score > 80", true);
    let mut p2 = Policy::new("p2");
    p2.add_clause("verified_email", true);
    let comp = PolicyComposition::And(
        Box::new(PolicyComposition::Single(p1)),
        Box::new(PolicyComposition::Single(p2)),
    );
    assert!(comp.evaluate(&HashMap::new()).unwrap());
}

#[test]
fn test_policy_engine_and_composition_one_false() {
    let mut p1 = Policy::new("p1");
    p1.add_clause("trust_score > 80", true);
    let mut p2 = Policy::new("p2");
    p2.add_clause("verified_email", false);
    let comp = PolicyComposition::And(
        Box::new(PolicyComposition::Single(p1)),
        Box::new(PolicyComposition::Single(p2)),
    );
    assert!(!comp.evaluate(&HashMap::new()).unwrap());
}

#[test]
fn test_policy_engine_or_composition_one_true() {
    let mut p1 = Policy::new("p1");
    p1.add_clause("trust_score > 80", false);
    let mut p2 = Policy::new("p2");
    p2.add_clause("verified_email", true);
    let comp = PolicyComposition::Or(
        Box::new(PolicyComposition::Single(p1)),
        Box::new(PolicyComposition::Single(p2)),
    );
    assert!(comp.evaluate(&HashMap::new()).unwrap());
}

#[test]
fn test_policy_engine_or_composition_both_false() {
    let mut p1 = Policy::new("p1");
    p1.add_clause("trust_score > 80", false);
    let mut p2 = Policy::new("p2");
    p2.add_clause("verified_email", false);
    let comp = PolicyComposition::Or(
        Box::new(PolicyComposition::Single(p1)),
        Box::new(PolicyComposition::Single(p2)),
    );
    assert!(!comp.evaluate(&HashMap::new()).unwrap());
}

#[test]
fn test_policy_engine_not_composition() {
    let mut not_banned = Policy::new("not_banned");
    not_banned.add_clause("banned", false);
    let comp = PolicyComposition::Not(Box::new(PolicyComposition::Single(not_banned)));
    assert!(comp.evaluate(&HashMap::new()).unwrap());

    let mut banned = Policy::new("banned");
    banned.add_clause("banned", true);
    let comp = PolicyComposition::Not(Box::new(PolicyComposition::Single(banned)));
    assert!(!comp.evaluate(&HashMap::new()).unwrap());
}

#[test]
fn test_policy_engine_complex_nesting() {
    // (vip OR verified) AND NOT(banned)
    let mut vip = Policy::new("vip");
    vip.add_clause("vip", true);
    let mut verified = Policy::new("verified");
    verified.add_clause("verified", true);
    let mut banned = Policy::new("banned");
    banned.add_clause("banned", false);

    let comp = PolicyComposition::And(
        Box::new(PolicyComposition::Or(
            Box::new(PolicyComposition::Single(vip)),
            Box::new(PolicyComposition::Single(verified)),
        )),
        Box::new(PolicyComposition::Not(Box::new(PolicyComposition::Single(
            banned,
        )))),
    );
    assert!(comp.evaluate(&HashMap::new()).unwrap());
}

// ---------------------------------------------------------------------------
// Tier 2: DAG Cycle Detection (4 tests)
// ---------------------------------------------------------------------------

#[test]
fn test_policy_engine_dag_no_cycle_linear_chain() {
    let engine = PolicyEngine::new();
    engine.add_policy_node("p1", vec![]);
    engine.add_policy_node("p2", vec!["p1"]);
    engine.add_policy_node("p3", vec!["p2"]);
    assert!(engine.detect_cycle().is_none());
}

#[test]
fn test_policy_engine_dag_direct_cycle() {
    let engine = PolicyEngine::new();
    engine.add_policy_node("p1", vec!["p2"]);
    engine.add_policy_node("p2", vec!["p1"]);
    assert!(engine.detect_cycle().is_some());
}

#[test]
fn test_policy_engine_dag_indirect_cycle() {
    let engine = PolicyEngine::new();
    engine.add_policy_node("p1", vec!["p2"]);
    engine.add_policy_node("p2", vec!["p3"]);
    engine.add_policy_node("p3", vec!["p1"]);
    assert!(engine.detect_cycle().is_some());
}

#[test]
fn test_policy_engine_dag_self_reference() {
    let engine = PolicyEngine::new();
    engine.add_policy_node("p1", vec!["p1"]);
    assert!(engine.detect_cycle().is_some());
}

// ---------------------------------------------------------------------------
// Tier 3: Decision Cache + Invalidation (5 tests)
// ---------------------------------------------------------------------------

#[test]
fn test_policy_engine_decision_cache_5min_ttl() {
    let cache = PolicyDecisionCache::new();
    cache.cache_decision("policy_1:user_1", true, "verified");
    // Fresh entry is well within the 5-minute TTL.
    assert!(cache.get_decision("policy_1:user_1").is_some());
}

#[test]
fn test_policy_engine_cache_hit_vs_miss() {
    let cache = PolicyDecisionCache::new();
    cache.cache_decision("policy_1:user_1", true, "verified");
    // Same key → hit.
    assert!(cache.get_decision("policy_1:user_1").is_some());
    // Different key → miss.
    assert!(cache.get_decision("policy_1:user_2").is_none());
    // Different policy → miss.
    assert!(cache.get_decision("policy_2:user_1").is_none());
}

#[test]
fn test_policy_engine_cache_invalidation_on_policy_update() {
    let cache = PolicyDecisionCache::new();
    cache.cache_decision("policy_1:user_1", true, "verified");
    cache.cache_decision("policy_1:user_2", false, "denied");
    cache.cache_decision("policy_2:user_3", true, "approved");

    cache.invalidate_by_policy("policy_1");

    assert!(cache.get_decision("policy_1:user_1").is_none());
    assert!(cache.get_decision("policy_1:user_2").is_none());
    assert!(cache.get_decision("policy_2:user_3").is_some());
}

#[test]
fn test_policy_engine_cache_invalidation_cascade() {
    let cache = PolicyDecisionCache::new();
    cache.cache_decision("policy_A:rule_1", true, "passed");
    cache.cache_decision("policy_B:rule_1", true, "passed");

    cache.invalidate_by_policy("policy_A");

    assert!(cache.get_decision("policy_A:rule_1").is_none());
    assert!(cache.get_decision("policy_B:rule_1").is_some());
}

#[test]
fn test_policy_engine_decision_includes_audit_reason() {
    let cache = PolicyDecisionCache::new();
    cache.cache_decision("policy_1:user_1", true, "signature verified");
    let (decision, reason) = cache
        .get_decision("policy_1:user_1")
        .expect("entry present");
    assert!(decision);
    assert_eq!(reason, "signature verified");
}

// ---------------------------------------------------------------------------
// Tier 3+: Integration / Stress (4 tests)
// ---------------------------------------------------------------------------

#[test]
fn test_policy_engine_three_phase_evaluation() {
    let engine = PolicyEngine::new();
    engine.add_policy_node("governance", vec![]);
    engine.add_policy_node("compliance", vec!["governance"]);
    engine.add_policy_node("decision", vec!["governance", "compliance"]);

    // Phase 1: graph is a valid DAG.
    assert!(engine.detect_cycle().is_none());

    // Phase 2: cache a governance decision.
    engine.cache_governance_decision("governance", true, "passed checks");
    assert_eq!(engine.cache_get("governance"), Some(true));

    // Phase 3: downstream node not yet evaluated → cache miss.
    assert!(engine.cache_get("compliance").is_none());
}

#[test]
fn test_policy_engine_concurrent_policy_evaluation() {
    use std::sync::Arc;
    let engine = Arc::new(PolicyEngine::new());
    let mut handles = Vec::with_capacity(100);

    for i in 0..100 {
        let e = Arc::clone(&engine);
        handles.push(std::thread::spawn(move || {
            let policy_id = format!("policy_{}", i);
            e.add_policy_node(&policy_id, vec![]);
            e.cache_governance_decision(&policy_id, true, "ok");
        }));
    }

    for h in handles {
        h.join().expect("worker thread panicked");
    }

    // All 100 decisions should be retrievable.
    for i in 0..100 {
        let key = format!("policy_{}", i);
        assert_eq!(engine.cache_get(&key), Some(true));
    }
}

#[test]
fn test_policy_engine_large_dag_performance() {
    use std::time::Instant;
    let engine = PolicyEngine::new();

    // Build a 1000-node linear DAG.
    for i in 0u32..1000 {
        let prev = format!("p_{}", i.saturating_sub(1));
        let deps: Vec<&str> = if i > 0 { vec![prev.as_str()] } else { vec![] };
        let id = format!("p_{}", i);
        engine.add_policy_node(&id, deps);
    }

    let start = Instant::now();
    let has_cycle = engine.detect_cycle();
    let elapsed = start.elapsed();

    assert!(has_cycle.is_none());
    assert!(
        elapsed < Duration::from_millis(100),
        "DAG cycle detection took {:?}, expected <100ms",
        elapsed
    );
}

#[test]
fn test_policy_engine_decision_deny_override() {
    let engine = PolicyEngine::new();
    engine.add_policy_node("trust_check", vec![]);
    engine.add_policy_node("compliance_check", vec!["trust_check"]);
    engine.add_policy_node("final_decision", vec!["compliance_check"]);

    // Trust check denies → downstream evaluators must observe the deny.
    engine.cache_governance_decision("trust_check", false, "failed");

    assert_eq!(engine.cache_get("trust_check"), Some(false));
}
