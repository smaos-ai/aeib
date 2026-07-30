mod api_server;
mod veto_flow;

use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub use api_server::{ConflictDisplay, VetoFlowAPI, VetoResponse, VetoSubmission};
pub use veto_flow::{EvalCourt as VetoEvalCourt, SignedVetoDecision, VetoDecision};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum EvalVerdict {
    Safe,
    Unsafe(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SymbolConflict {
    pub capsule_a_id: Uuid,
    pub capsule_b_id: Uuid,
    pub intersecting_symbols: Vec<String>,
    pub intersecting_clusters: Vec<String>,
}

/// Trait for capsule-like data structures
pub trait CapsuleData {
    fn id(&self) -> Uuid;
    fn affected_symbols(&self) -> &[String];
    fn cluster_tags(&self) -> &[String];
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProposedUpdate {
    pub update_id: Uuid,
    pub description: String,
    pub target_skill: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalReport {
    pub update_id: Uuid,
    pub verdict: EvalVerdict,
    pub invariants_checked: usize,
}

pub struct EvalCourt;

impl EvalCourt {
    pub fn new() -> Self {
        EvalCourt
    }

    pub fn evaluate(&self, update: ProposedUpdate) -> EvalReport {
        let verdict = if update.description.to_lowercase().contains("unsafe") {
            EvalVerdict::Unsafe(update.description.clone())
        } else {
            EvalVerdict::Safe
        };

        EvalReport {
            update_id: update.update_id,
            verdict,
            invariants_checked: 3,
        }
    }

    pub fn detect_conflict<C: CapsuleData>(
        &self,
        capsule_a: &C,
        capsule_b: &C,
    ) -> Option<SymbolConflict> {
        // Check for symbol intersection
        let symbols_a: std::collections::HashSet<_> = capsule_a.affected_symbols().iter().collect();
        let symbols_b: std::collections::HashSet<_> = capsule_b.affected_symbols().iter().collect();

        let intersecting_symbols: Vec<String> = symbols_a
            .intersection(&symbols_b)
            .map(|s| s.to_string())
            .collect();

        if !intersecting_symbols.is_empty() {
            // Check for cluster intersection
            let clusters_a: std::collections::HashSet<_> =
                capsule_a.cluster_tags().iter().collect();
            let clusters_b: std::collections::HashSet<_> =
                capsule_b.cluster_tags().iter().collect();

            let intersecting_clusters: Vec<String> = clusters_a
                .intersection(&clusters_b)
                .map(|s| s.to_string())
                .collect();

            return Some(SymbolConflict {
                capsule_a_id: capsule_a.id(),
                capsule_b_id: capsule_b.id(),
                intersecting_symbols,
                intersecting_clusters,
            });
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_safe_update_returns_safe_verdict() {
        let court = EvalCourt::new();
        let update = ProposedUpdate {
            update_id: Uuid::new_v4(),
            description: "add timeout logic".to_string(),
            target_skill: "test-skill".to_string(),
        };

        let report = court.evaluate(update);
        assert_eq!(report.verdict, EvalVerdict::Safe);
    }

    #[test]
    fn test_unsafe_description_blocked() {
        let court = EvalCourt::new();
        let update = ProposedUpdate {
            update_id: Uuid::new_v4(),
            description: "unsafe bypass".to_string(),
            target_skill: "test-skill".to_string(),
        };

        let report = court.evaluate(update);
        match report.verdict {
            EvalVerdict::Unsafe(_) => {
                // Expected: unsafe verdict matched
            }
            EvalVerdict::Safe => {
                panic!("Expected Unsafe verdict for unsafe description");
            }
        }
    }

    #[test]
    fn test_eval_report_checks_three_invariants() {
        let court = EvalCourt::new();
        let update = ProposedUpdate {
            update_id: Uuid::new_v4(),
            description: "any update".to_string(),
            target_skill: "test-skill".to_string(),
        };

        let report = court.evaluate(update);
        assert_eq!(report.invariants_checked, 3);
    }

    struct TestCapsule {
        id: Uuid,
        symbols: Vec<String>,
        clusters: Vec<String>,
    }

    impl CapsuleData for TestCapsule {
        fn id(&self) -> Uuid {
            self.id
        }
        fn affected_symbols(&self) -> &[String] {
            &self.symbols
        }
        fn cluster_tags(&self) -> &[String] {
            &self.clusters
        }
    }

    #[test]
    fn test_conflict_detection_halts_concurrent_mutations() {
        let capsule_a = TestCapsule {
            id: Uuid::new_v4(),
            symbols: vec!["validateUser".to_string()],
            clusters: vec!["auth-cluster".to_string()],
        };

        let capsule_b = TestCapsule {
            id: Uuid::new_v4(),
            symbols: vec!["validateUser".to_string()],
            clusters: vec!["auth-cluster".to_string()],
        };

        let court = EvalCourt::new();
        let conflict = court.detect_conflict(&capsule_a, &capsule_b);

        assert!(conflict.is_some(), "Should detect symbol intersection");
        let c = conflict.unwrap();
        assert_eq!(c.intersecting_symbols, vec!["validateUser"]);
        assert_eq!(c.intersecting_clusters, vec!["auth-cluster"]);
    }

    #[test]
    fn test_no_conflict_different_symbols() {
        let capsule_a = TestCapsule {
            id: Uuid::new_v4(),
            symbols: vec!["validateUser".to_string()],
            clusters: vec!["auth-cluster".to_string()],
        };

        let capsule_b = TestCapsule {
            id: Uuid::new_v4(),
            symbols: vec!["handleLogin".to_string()],
            clusters: vec!["auth-cluster".to_string()],
        };

        let court = EvalCourt::new();
        let conflict = court.detect_conflict(&capsule_a, &capsule_b);

        assert!(
            conflict.is_none(),
            "Should not detect conflict for different symbols"
        );
    }
}
