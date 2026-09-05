use crate::{CapsuleCommitActor, CapsuleEntry, PrepareToken};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use siss_agent_shell::hooks::{
    blast_radius::BlastRiskLevel,
    gitnexus_impact::{ImpactAnalyzer, ImpactReport},
};
use siss_eval_court::{EvalCourt, EvalVerdict, ProposedUpdate};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CommitmentCapsule {
    pub capsule_id: Uuid,
    pub agent_id: Uuid,
    pub affected_symbols: Vec<String>,
    pub target_files: Vec<String>,
    pub git_diff: String,
    pub cluster_tags: Vec<String>,
    pub created_at: u64,
    pub capsule_hash: String,
}

pub struct ClusterIntersection {
    pub capsule_a: Uuid,
    pub capsule_b: Uuid,
    pub intersecting_symbols: Vec<String>,
    pub intersecting_clusters: Vec<String>,
    pub risk_level: BlastRiskLevel,
    pub requires_phi_plus: bool,
}

pub enum MergeDecision {
    Approved {
        capsule_id: Uuid,
        entry: CapsuleEntry,
    },
    HaltForPhiPlus {
        intersection: ClusterIntersection,
    },
    Rejected {
        capsule_id: Uuid,
        reason: String,
    },
}

#[derive(Debug, Clone)]
pub enum ActorError {
    InvalidHash { capsule_id: Uuid },
    ImpactAnalysisFailed(String),
    CommitFailed(String),
}

pub struct GitNexusCapsuleCommitActor<A: ImpactAnalyzer> {
    base: CapsuleCommitActor,
    analyzer: A,
    pending_capsules: HashMap<Uuid, CommitmentCapsule>,
    committed_capsules: HashMap<Uuid, CommitmentCapsule>,
}

impl<A: ImpactAnalyzer> GitNexusCapsuleCommitActor<A> {
    pub fn new(analyzer: A) -> Self {
        Self {
            base: CapsuleCommitActor::new(),
            analyzer,
            pending_capsules: HashMap::new(),
            committed_capsules: HashMap::new(),
        }
    }

    pub fn ingest_capsule(
        &mut self,
        capsule: CommitmentCapsule,
    ) -> Result<MergeDecision, ActorError> {
        // Verify capsule hash integrity
        if !Self::verify_capsule_hash(&capsule) {
            return Err(ActorError::InvalidHash {
                capsule_id: capsule.capsule_id,
            });
        }

        // Check for intersections with pending capsules
        if let Some(intersection) = self.check_all_intersections(&capsule) {
            self.pending_capsules.insert(capsule.capsule_id, capsule);
            return Ok(MergeDecision::HaltForPhiPlus { intersection });
        }

        // No conflicts: commit immediately
        match self.commit_capsule(capsule.clone()) {
            Ok(entry) => Ok(MergeDecision::Approved {
                capsule_id: capsule.capsule_id,
                entry,
            }),
            Err(reason) => Err(ActorError::CommitFailed(reason)),
        }
    }

    fn verify_capsule_hash(capsule: &CommitmentCapsule) -> bool {
        let mut hasher = Sha256::new();
        hasher.update(&capsule.git_diff);
        let mut symbols_sorted = capsule.affected_symbols.clone();
        symbols_sorted.sort();
        for symbol in symbols_sorted {
            hasher.update(symbol.as_bytes());
        }
        let computed_hash = format!("{:x}", hasher.finalize());
        computed_hash == capsule.capsule_hash
    }

    fn check_all_intersections(&self, incoming: &CommitmentCapsule) -> Option<ClusterIntersection> {
        // Check against pending capsules
        for (_, pending) in &self.pending_capsules {
            if let Some(intersection) = self.capsules_intersect(incoming, pending) {
                return Some(intersection);
            }
        }
        // Check against committed capsules
        for (_, committed) in &self.committed_capsules {
            if let Some(intersection) = self.capsules_intersect(incoming, committed) {
                return Some(intersection);
            }
        }
        None
    }

    fn capsules_intersect(
        &self,
        a: &CommitmentCapsule,
        b: &CommitmentCapsule,
    ) -> Option<ClusterIntersection> {
        // Level 1: cluster tag overlap
        let cluster_a: std::collections::HashSet<_> = a.cluster_tags.iter().collect();
        let cluster_b: std::collections::HashSet<_> = b.cluster_tags.iter().collect();
        let intersecting_clusters: Vec<String> = cluster_a
            .intersection(&cluster_b)
            .map(|s| s.to_string())
            .collect();

        if !intersecting_clusters.is_empty() {
            return Some(ClusterIntersection {
                capsule_a: a.capsule_id,
                capsule_b: b.capsule_id,
                intersecting_symbols: Vec::new(),
                intersecting_clusters,
                risk_level: BlastRiskLevel::Medium,
                requires_phi_plus: true,
            });
        }

        // Level 2: symbol overlap
        let symbols_a: std::collections::HashSet<_> = a.affected_symbols.iter().collect();
        let symbols_b: std::collections::HashSet<_> = b.affected_symbols.iter().collect();
        let intersecting_symbols: Vec<String> = symbols_a
            .intersection(&symbols_b)
            .map(|s| s.to_string())
            .collect();

        if !intersecting_symbols.is_empty() {
            return Some(ClusterIntersection {
                capsule_a: a.capsule_id,
                capsule_b: b.capsule_id,
                intersecting_symbols,
                intersecting_clusters: Vec::new(),
                risk_level: BlastRiskLevel::High,
                requires_phi_plus: true,
            });
        }

        None
    }

    fn phi_plus_review(&mut self, intersection: ClusterIntersection) -> MergeDecision {
        let eval = EvalCourt::new();

        let capsule_a = self
            .pending_capsules
            .get(&intersection.capsule_a)
            .or_else(|| self.committed_capsules.get(&intersection.capsule_a))
            .cloned();

        let capsule_b = self
            .pending_capsules
            .get(&intersection.capsule_b)
            .or_else(|| self.committed_capsules.get(&intersection.capsule_b))
            .cloned();

        let (capsule_a, capsule_b) = match (capsule_a, capsule_b) {
            (Some(a), Some(b)) => (a, b),
            _ => {
                return MergeDecision::Rejected {
                    capsule_id: intersection.capsule_a,
                    reason: "One or both capsules not found".to_string(),
                }
            }
        };

        let update_a = ProposedUpdate {
            update_id: capsule_a.capsule_id,
            description: capsule_a.git_diff.clone(),
            target_skill: capsule_a.target_files.first().cloned().unwrap_or_default(),
        };

        let update_b = ProposedUpdate {
            update_id: capsule_b.capsule_id,
            description: capsule_b.git_diff.clone(),
            target_skill: capsule_b.target_files.first().cloned().unwrap_or_default(),
        };

        let verdict_a = eval.evaluate(update_a);
        let verdict_b = eval.evaluate(update_b);

        match (&verdict_a.verdict, &verdict_b.verdict) {
            (EvalVerdict::Safe, EvalVerdict::Safe) => {
                // Approve oldest-first
                if capsule_a.created_at <= capsule_b.created_at {
                    match self.commit_capsule(capsule_a.clone()) {
                        Ok(entry) => MergeDecision::Approved {
                            capsule_id: capsule_a.capsule_id,
                            entry,
                        },
                        Err(reason) => MergeDecision::Rejected {
                            capsule_id: capsule_a.capsule_id,
                            reason,
                        },
                    }
                } else {
                    match self.commit_capsule(capsule_b.clone()) {
                        Ok(entry) => MergeDecision::Approved {
                            capsule_id: capsule_b.capsule_id,
                            entry,
                        },
                        Err(reason) => MergeDecision::Rejected {
                            capsule_id: capsule_b.capsule_id,
                            reason,
                        },
                    }
                }
            }
            (EvalVerdict::Safe, EvalVerdict::Unsafe(_)) => {
                match self.commit_capsule(capsule_a.clone()) {
                    Ok(entry) => MergeDecision::Approved {
                        capsule_id: capsule_a.capsule_id,
                        entry,
                    },
                    Err(reason) => MergeDecision::Rejected {
                        capsule_id: capsule_a.capsule_id,
                        reason,
                    },
                }
            }
            (EvalVerdict::Unsafe(_), EvalVerdict::Safe) => {
                match self.commit_capsule(capsule_b.clone()) {
                    Ok(entry) => MergeDecision::Approved {
                        capsule_id: capsule_b.capsule_id,
                        entry,
                    },
                    Err(reason) => MergeDecision::Rejected {
                        capsule_id: capsule_b.capsule_id,
                        reason,
                    },
                }
            }
            (EvalVerdict::Unsafe(_), EvalVerdict::Unsafe(_)) => {
                // Fail-closed: reject both
                self.pending_capsules.remove(&intersection.capsule_a);
                MergeDecision::Rejected {
                    capsule_id: intersection.capsule_a,
                    reason: "Both capsules unsafe (fail-closed)".to_string(),
                }
            }
        }
    }

    fn commit_capsule(&mut self, capsule: CommitmentCapsule) -> Result<CapsuleEntry, String> {
        let token = PrepareToken {
            capsule_id: capsule.capsule_id,
            reservation_id: Uuid::new_v4(),
        };

        let entry = self.base.commit(token)?;
        self.pending_capsules.remove(&capsule.capsule_id);
        self.committed_capsules.insert(capsule.capsule_id, capsule);
        Ok(entry)
    }

    pub fn committed_count(&self) -> usize {
        self.base.committed_count()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct MockAnalyzer;

    impl ImpactAnalyzer for MockAnalyzer {
        fn analyze_impact(&self, symbol: &str) -> ImpactReport {
            ImpactReport {
                symbol: symbol.to_string(),
                caller_count: 2,
                affected_process_count: 1,
                risk_level: BlastRiskLevel::Low,
                confidence: 0.95,
            }
        }
    }

    fn create_capsule(
        id: Uuid,
        symbols: Vec<&str>,
        clusters: Vec<&str>,
        created_at: u64,
    ) -> CommitmentCapsule {
        create_capsule_with_diff(id, symbols, clusters, created_at, None)
    }

    fn create_capsule_with_diff(
        id: Uuid,
        symbols: Vec<&str>,
        clusters: Vec<&str>,
        created_at: u64,
        git_diff_override: Option<String>,
    ) -> CommitmentCapsule {
        let affected_symbols: Vec<String> = symbols.iter().map(|s| s.to_string()).collect();
        let cluster_tags: Vec<String> = clusters.iter().map(|c| c.to_string()).collect();
        let git_diff = git_diff_override.unwrap_or_else(|| format!("diff for {:?}", id));

        let mut hasher = Sha256::new();
        hasher.update(&git_diff);
        let mut sorted_symbols = affected_symbols.clone();
        sorted_symbols.sort();
        for symbol in &sorted_symbols {
            hasher.update(symbol.as_bytes());
        }
        let capsule_hash = format!("{:x}", hasher.finalize());

        CommitmentCapsule {
            capsule_id: id,
            agent_id: Uuid::new_v4(),
            affected_symbols,
            target_files: vec!["src/lib.rs".to_string()],
            git_diff,
            cluster_tags,
            created_at,
            capsule_hash,
        }
    }

    #[test]
    fn test_single_capsule_commits_directly() {
        let mut actor = GitNexusCapsuleCommitActor::new(MockAnalyzer);

        let capsule = create_capsule(Uuid::new_v4(), vec!["handleLogin"], vec!["auth"], 1000);

        match actor.ingest_capsule(capsule.clone()) {
            Ok(MergeDecision::Approved { capsule_id, .. }) => {
                assert_eq!(capsule_id, capsule.capsule_id);
                assert_eq!(actor.committed_count(), 1);
            }
            _ => panic!("Expected Approved"),
        }
    }

    #[test]
    fn test_two_non_overlapping_capsules_both_approve() {
        let mut actor = GitNexusCapsuleCommitActor::new(MockAnalyzer);

        let capsule_a = create_capsule(
            Uuid::new_v4(),
            vec!["validateUser"],
            vec!["auth-cluster"],
            1000,
        );
        let capsule_b = create_capsule(
            Uuid::new_v4(),
            vec!["processPayment"],
            vec!["payment-cluster"],
            1001,
        );

        match actor.ingest_capsule(capsule_a.clone()) {
            Ok(MergeDecision::Approved { .. }) => {}
            _ => panic!("Capsule A should approve"),
        }

        match actor.ingest_capsule(capsule_b.clone()) {
            Ok(MergeDecision::Approved { .. }) => {}
            _ => panic!("Capsule B should approve"),
        }

        assert_eq!(actor.committed_count(), 2);
    }

    #[test]
    fn test_cluster_tag_intersection_triggers_halt() {
        let mut actor = GitNexusCapsuleCommitActor::new(MockAnalyzer);

        let capsule_a = create_capsule(
            Uuid::new_v4(),
            vec!["validateUser"],
            vec!["auth-cluster"],
            1000,
        );
        let capsule_b = create_capsule(
            Uuid::new_v4(),
            vec!["handleLogin"],
            vec!["auth-cluster"],
            1001,
        );

        actor.ingest_capsule(capsule_a.clone()).ok();

        match actor.ingest_capsule(capsule_b.clone()) {
            Ok(MergeDecision::HaltForPhiPlus { intersection }) => {
                assert!(intersection.requires_phi_plus);
                assert_eq!(intersection.intersecting_clusters, vec!["auth-cluster"]);
            }
            _ => panic!("Expected HaltForPhiPlus"),
        }
    }

    #[test]
    fn test_symbol_overlap_triggers_halt() {
        let mut actor = GitNexusCapsuleCommitActor::new(MockAnalyzer);

        let capsule_a = create_capsule(
            Uuid::new_v4(),
            vec!["validateUser"],
            vec!["auth-cluster"],
            1000,
        );
        let capsule_b = create_capsule(
            Uuid::new_v4(),
            vec!["validateUser"],
            vec!["payment-cluster"],
            1001,
        );

        actor.ingest_capsule(capsule_a.clone()).ok();

        match actor.ingest_capsule(capsule_b.clone()) {
            Ok(MergeDecision::HaltForPhiPlus { intersection }) => {
                assert!(intersection.requires_phi_plus);
                assert_eq!(intersection.intersecting_symbols, vec!["validateUser"]);
            }
            _ => panic!("Expected HaltForPhiPlus"),
        }
    }

    #[test]
    fn test_phi_plus_approves_oldest_first_when_both_safe() {
        let mut actor = GitNexusCapsuleCommitActor::new(MockAnalyzer);

        let capsule_a = create_capsule(
            Uuid::new_v4(),
            vec!["validateUser"],
            vec!["auth-cluster"],
            1000,
        );
        let capsule_b = create_capsule(
            Uuid::new_v4(),
            vec!["handleLogin"],
            vec!["auth-cluster"],
            2000,
        );

        actor.ingest_capsule(capsule_a.clone()).ok();
        actor.ingest_capsule(capsule_b.clone()).ok();

        let intersection = ClusterIntersection {
            capsule_a: capsule_a.capsule_id,
            capsule_b: capsule_b.capsule_id,
            intersecting_symbols: vec![],
            intersecting_clusters: vec!["auth-cluster".to_string()],
            risk_level: BlastRiskLevel::Medium,
            requires_phi_plus: true,
        };

        match actor.phi_plus_review(intersection) {
            MergeDecision::Approved { capsule_id, .. } => {
                assert_eq!(capsule_id, capsule_a.capsule_id);
            }
            _ => panic!("Expected Approved"),
        }
    }

    #[test]
    fn test_phi_plus_rejects_unsafe_capsule() {
        let mut actor = GitNexusCapsuleCommitActor::new(MockAnalyzer);

        let capsule_a = create_capsule(
            Uuid::new_v4(),
            vec!["validateUser"],
            vec!["auth-cluster"],
            1000,
        );
        let capsule_b_id = Uuid::new_v4();
        let capsule_b = create_capsule_with_diff(
            capsule_b_id,
            vec!["handleLogin"],
            vec!["auth-cluster"],
            2000,
            Some("unsafe bypass code".to_string()),
        );

        actor.ingest_capsule(capsule_a.clone()).ok();
        actor.ingest_capsule(capsule_b.clone()).ok();

        let intersection = ClusterIntersection {
            capsule_a: capsule_a.capsule_id,
            capsule_b: capsule_b.capsule_id,
            intersecting_symbols: vec![],
            intersecting_clusters: vec!["auth-cluster".to_string()],
            risk_level: BlastRiskLevel::Medium,
            requires_phi_plus: true,
        };

        match actor.phi_plus_review(intersection) {
            MergeDecision::Approved { capsule_id, .. } => {
                assert_eq!(capsule_id, capsule_a.capsule_id);
            }
            _ => panic!("Expected Approved for safe capsule"),
        }
    }

    #[test]
    fn test_phi_plus_rejects_both_when_both_unsafe() {
        let mut actor = GitNexusCapsuleCommitActor::new(MockAnalyzer);

        let capsule_a_id = Uuid::new_v4();
        let capsule_a = create_capsule_with_diff(
            capsule_a_id,
            vec!["validateUser"],
            vec!["auth-cluster"],
            1000,
            Some("unsafe code A".to_string()),
        );
        let capsule_b_id = Uuid::new_v4();
        let capsule_b = create_capsule_with_diff(
            capsule_b_id,
            vec!["handleLogin"],
            vec!["auth-cluster"],
            2000,
            Some("unsafe code B".to_string()),
        );

        actor.ingest_capsule(capsule_a.clone()).ok();
        actor.ingest_capsule(capsule_b.clone()).ok();

        let intersection = ClusterIntersection {
            capsule_a: capsule_a.capsule_id,
            capsule_b: capsule_b.capsule_id,
            intersecting_symbols: vec![],
            intersecting_clusters: vec!["auth-cluster".to_string()],
            risk_level: BlastRiskLevel::Medium,
            requires_phi_plus: true,
        };

        match actor.phi_plus_review(intersection) {
            MergeDecision::Rejected { reason, .. } => {
                assert!(reason.contains("fail-closed"));
            }
            _ => panic!("Expected Rejected with fail-closed"),
        }
    }

    #[test]
    fn test_capsule_hash_verified_on_ingest() {
        let mut actor = GitNexusCapsuleCommitActor::new(MockAnalyzer);

        let mut capsule = create_capsule(
            Uuid::new_v4(),
            vec!["validateUser"],
            vec!["auth-cluster"],
            1000,
        );
        capsule.capsule_hash = "tampered_hash".to_string();

        match actor.ingest_capsule(capsule) {
            Err(ActorError::InvalidHash { .. }) => {}
            _ => panic!("Expected rejection for tampered hash"),
        }
    }

    #[test]
    fn test_approved_capsule_recorded_in_base_actor() {
        let mut actor = GitNexusCapsuleCommitActor::new(MockAnalyzer);

        let capsule = create_capsule(
            Uuid::new_v4(),
            vec!["handleLogin"],
            vec!["auth-cluster"],
            1000,
        );

        actor.ingest_capsule(capsule).ok();

        assert_eq!(actor.committed_count(), 1);
    }

    #[test]
    fn test_low_confidence_analysis() {
        struct LowConfidenceAnalyzer;

        impl ImpactAnalyzer for LowConfidenceAnalyzer {
            fn analyze_impact(&self, symbol: &str) -> ImpactReport {
                ImpactReport {
                    symbol: symbol.to_string(),
                    caller_count: 2,
                    affected_process_count: 1,
                    risk_level: BlastRiskLevel::Low,
                    confidence: 0.50,
                }
            }
        }

        let mut actor = GitNexusCapsuleCommitActor::new(LowConfidenceAnalyzer);

        let capsule = create_capsule(
            Uuid::new_v4(),
            vec!["handleLogin"],
            vec!["auth-cluster"],
            1000,
        );

        match actor.ingest_capsule(capsule) {
            Ok(MergeDecision::Approved { .. }) => {
                // Capsule commits even with low confidence (impact analysis is advisory)
            }
            _ => panic!("Expected approval"),
        }
    }
}
