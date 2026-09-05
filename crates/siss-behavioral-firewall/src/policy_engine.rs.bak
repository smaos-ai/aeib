//! Policy composition, DAG cycle detection, and decision caching.
//!
//! This module defines the foundational types used by the AXIOM Protocol
//! policy composition layer:
//! - [`Policy`] / [`PolicyComposition`]: boolean composition of policies (AND/OR/NOT)
//! - [`PolicyEngine`]: DAG-backed engine with cycle detection and governance cache
//! - [`PolicyDecisionCache`]: 5-minute TTL cache with per-policy invalidation
//!
//! [`Mandate`] and [`Decision`] are kept for downstream callers (notably
//! `policy::engine::PolicyEngine`, which composes ReBAC + AP2 + Temporal phases).

use std::collections::{HashMap, HashSet};
use std::sync::Mutex;
use std::time::{Duration, SystemTime};
use uuid::Uuid;

/// TTL applied to entries in [`PolicyDecisionCache`].
const DECISION_TTL: Duration = Duration::from_secs(300);

// ---------------------------------------------------------------------------
// Mandate / Decision (preserved for policy::engine three-phase pipeline)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Policy + PolicyComposition (Tier 1)
// ---------------------------------------------------------------------------

/// A named policy made up of one or more boolean clauses.
///
/// Each clause is a (description, pre-evaluated result) pair. The policy is
/// satisfied when every clause is `true` (AND semantics within a policy).
#[derive(Debug, Clone)]
pub struct Policy {
    id: String,
    clauses: Vec<(String, bool)>,
}

impl Policy {
    pub fn new(id: &str) -> Self {
        Self {
            id: id.to_string(),
            clauses: Vec::new(),
        }
    }

    pub fn id(&self) -> &str {
        &self.id
    }

    pub fn add_clause(&mut self, clause: &str, result: bool) {
        self.clauses.push((clause.to_string(), result));
    }

    /// All clauses must hold for the policy to evaluate `true`.
    pub fn evaluate(&self) -> bool {
        self.clauses.iter().all(|(_, result)| *result)
    }
}

/// Recursive boolean composition of policies.
pub enum PolicyComposition {
    Single(Policy),
    And(Box<PolicyComposition>, Box<PolicyComposition>),
    Or(Box<PolicyComposition>, Box<PolicyComposition>),
    Not(Box<PolicyComposition>),
}

impl PolicyComposition {
    /// Evaluate the composition. `attrs` is reserved for future attribute-based
    /// predicates; current clauses are pre-resolved booleans, but the parameter
    /// remains in the public API so callers can begin threading attributes in.
    #[allow(clippy::only_used_in_recursion)]
    pub fn evaluate(&self, attrs: &HashMap<String, String>) -> Result<bool, String> {
        match self {
            Self::Single(policy) => Ok(policy.evaluate()),
            Self::And(left, right) => Ok(left.evaluate(attrs)? && right.evaluate(attrs)?),
            Self::Or(left, right) => Ok(left.evaluate(attrs)? || right.evaluate(attrs)?),
            Self::Not(inner) => Ok(!inner.evaluate(attrs)?),
        }
    }
}

/// Convenience so a bare [`Policy`] composes directly when wrapped in a `Box`.
impl From<Policy> for PolicyComposition {
    fn from(policy: Policy) -> Self {
        PolicyComposition::Single(policy)
    }
}

// ---------------------------------------------------------------------------
// PolicyEngine (Tier 2: DAG + cycle detection, Tier 3: governance cache)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
struct PolicyNode {
    dependencies: Vec<String>,
}

#[derive(Debug, Clone)]
struct CachedDecision {
    decision: bool,
    #[allow(dead_code)]
    reason: String,
    #[allow(dead_code)]
    cached_at: SystemTime,
}

/// DAG-backed policy engine with cycle detection and governance cache.
///
/// All mutating methods take `&self`; concurrency is handled via internal
/// `Mutex` so the engine can be wrapped in `Arc` and shared across threads.
#[derive(Default)]
pub struct PolicyEngine {
    nodes: Mutex<HashMap<String, PolicyNode>>,
    cache: Mutex<HashMap<String, CachedDecision>>,
}

impl PolicyEngine {
    pub fn new() -> Self {
        Self::default()
    }

    /// Add or replace a policy node and its dependency list.
    pub fn add_policy_node(&self, id: &str, dependencies: Vec<&str>) {
        let mut nodes = self.nodes.lock().expect("policy nodes mutex poisoned");
        nodes.insert(
            id.to_string(),
            PolicyNode {
                dependencies: dependencies.into_iter().map(String::from).collect(),
            },
        );
    }

    /// Detect a cycle in the dependency graph using iterative DFS.
    ///
    /// Returns `Some(node_id)` for the node where the cycle was discovered,
    /// or `None` if the graph is a valid DAG.
    pub fn detect_cycle(&self) -> Option<String> {
        let nodes = self.nodes.lock().expect("policy nodes mutex poisoned");
        let mut visited: HashSet<String> = HashSet::new();
        let mut rec_stack: HashSet<String> = HashSet::new();

        for node_id in nodes.keys() {
            if visited.contains(node_id) {
                continue;
            }
            if dfs_has_cycle(node_id, &nodes, &mut visited, &mut rec_stack) {
                return Some(node_id.clone());
            }
        }
        None
    }

    /// Cache a governance-level decision for a policy node.
    pub fn cache_governance_decision(&self, id: &str, decision: bool, reason: &str) {
        let mut cache = self.cache.lock().expect("policy cache mutex poisoned");
        cache.insert(
            id.to_string(),
            CachedDecision {
                decision,
                reason: reason.to_string(),
                cached_at: SystemTime::now(),
            },
        );
    }

    /// Look up a cached governance decision. Returns the boolean result if
    /// present (TTL is not applied here — governance caches are explicitly
    /// invalidated; cf. [`PolicyDecisionCache`] for TTL semantics).
    pub fn cache_get(&self, id: &str) -> Option<bool> {
        let cache = self.cache.lock().expect("policy cache mutex poisoned");
        cache.get(id).map(|d| d.decision)
    }
}

/// Iterative DFS cycle check. Uses an explicit work stack to keep recursion
/// bounded (important for large DAGs — see `test_engine_large_dag_perf_under_100ms`).
fn dfs_has_cycle(
    start: &str,
    nodes: &HashMap<String, PolicyNode>,
    visited: &mut HashSet<String>,
    rec_stack: &mut HashSet<String>,
) -> bool {
    // Each stack frame: (node id, index of next dep to visit).
    let mut stack: Vec<(String, usize)> = Vec::new();
    stack.push((start.to_string(), 0));
    visited.insert(start.to_string());
    rec_stack.insert(start.to_string());

    while let Some((node_id, dep_idx)) = stack.last().cloned() {
        let next_dep = nodes
            .get(&node_id)
            .and_then(|n| n.dependencies.get(dep_idx).cloned());

        match next_dep {
            Some(dep) => {
                // Advance current frame past this dep before descending.
                if let Some(last) = stack.last_mut() {
                    last.1 += 1;
                }
                if rec_stack.contains(&dep) {
                    return true;
                }
                if !visited.contains(&dep) {
                    visited.insert(dep.clone());
                    rec_stack.insert(dep.clone());
                    stack.push((dep, 0));
                }
            }
            None => {
                rec_stack.remove(&node_id);
                stack.pop();
            }
        }
    }
    false
}

// ---------------------------------------------------------------------------
// PolicyDecisionCache (Tier 3: TTL cache + cascade invalidation)
// ---------------------------------------------------------------------------

/// Decision cache with a 5-minute TTL and per-policy invalidation.
///
/// Keys are expected to follow the convention `"<policy_id>:<subject>"`,
/// which is what [`invalidate_by_policy`](Self::invalidate_by_policy) keys off.
#[derive(Debug, Default)]
pub struct PolicyDecisionCache {
    decisions: Mutex<HashMap<String, CachedDecision>>,
}

impl PolicyDecisionCache {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn cache_decision(&self, key: &str, decision: bool, reason: &str) {
        let mut decisions = self
            .decisions
            .lock()
            .expect("decision cache mutex poisoned");
        decisions.insert(
            key.to_string(),
            CachedDecision {
                decision,
                reason: reason.to_string(),
                cached_at: SystemTime::now(),
            },
        );
    }

    /// Fetch a cached decision if it is within TTL. Returns `(decision, reason)`.
    pub fn get_decision(&self, key: &str) -> Option<(bool, String)> {
        let decisions = self
            .decisions
            .lock()
            .expect("decision cache mutex poisoned");
        let entry = decisions.get(key)?;
        let age = SystemTime::now()
            .duration_since(entry.cached_at)
            .unwrap_or_default();
        if age < DECISION_TTL {
            Some((entry.decision, entry.reason.clone()))
        } else {
            None
        }
    }

    /// Invalidate every entry whose key starts with `"<policy_id>:"`.
    pub fn invalidate_by_policy(&self, policy_id: &str) {
        let prefix = format!("{}:", policy_id);
        let mut decisions = self
            .decisions
            .lock()
            .expect("decision cache mutex poisoned");
        decisions.retain(|key, _| !key.starts_with(&prefix));
    }
}

// ---------------------------------------------------------------------------
// Internal Mandate / Decision smoke tests (preserved from prior module)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mandate_allow_records_reasons() {
        let mandate = Mandate {
            decision: Decision::Allow,
            reasons: vec!["ReBAC: Owner".to_string(), "Temporal: OK".to_string()],
            audit_id: Uuid::new_v4(),
        };
        assert_eq!(mandate.decision, Decision::Allow);
        assert_eq!(mandate.reasons.len(), 2);
    }

    #[test]
    fn test_mandate_deny_unique_audit_ids() {
        let m1 = Mandate {
            decision: Decision::Deny,
            reasons: vec!["denied".to_string()],
            audit_id: Uuid::new_v4(),
        };
        let m2 = Mandate {
            decision: Decision::Deny,
            reasons: vec!["denied".to_string()],
            audit_id: Uuid::new_v4(),
        };
        assert_ne!(m1.audit_id, m2.audit_id);
    }

    #[test]
    fn test_policy_single_clause_true() {
        let mut p = Policy::new("p");
        p.add_clause("trust > 80", true);
        assert!(p.evaluate());
    }

    #[test]
    fn test_policy_clause_false_short_circuits() {
        let mut p = Policy::new("p");
        p.add_clause("ok", true);
        p.add_clause("denied", false);
        assert!(!p.evaluate());
    }
}
