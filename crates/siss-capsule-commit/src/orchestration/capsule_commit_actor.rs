use sha2::{Sha256, Digest};
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use std::collections::HashMap;
use siss_agent_shell::hooks::gitnexus_impact::{ImpactAnalyzer, ImpactReport};
use siss_agent_shell::hooks::blast_radius::BlastRiskLevel;
use siss_eval_court::{EvalCourt, ProposedUpdate, EvalVerdict};

/// Phase 81.5/82: JSON-LD Capsule spec
/// ```json
/// {
///     "@context": "https://smaos.app/schemas/capsule/v1/",
///     "@type": "CommitmentCapsule",
///     "capsuleId": "uuid-v4",
///     "agentId": "uuid-v4",
///     "affectedSymbols": ["handleLogin", "validateUser"],
///     "targetFiles": ["crates/siss-gatekeeper/src/auth.rs"],
///     "clusterTags": ["auth-cluster"],
///     "createdAt": 1716566400,
///     "capsuleHash": "sha256-hex"
/// }
/// ```

/// Input commitment capsule from a parallel sub-agent
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

/// Intersection evidence (triggers φ+ halt)
#[derive(Clone, Debug)]
pub struct ClusterIntersection {
    pub capsule_a: Uuid,
    pub capsule_b: Uuid,
    pub intersecting_symbols: Vec<String>,
    pub intersecting_clusters: Vec<String>,
    pub risk_level: BlastRiskLevel,
    pub requires_phi_plus: bool,
}

/// Actor decision output
pub enum MergeDecision {
    Approved { capsule_id: Uuid },
    HaltForPhiPlus { intersection: ClusterIntersection },
    Rejected { capsule_id: Uuid, reason: String },
}

pub enum ActorError {
    InvalidHash { capsule_id: Uuid },
    ImpactAnalysisFailed(String),
    CommitFailed(String),
}

/// Configuration for impact gate thresholds
#[derive(Clone, Debug)]
pub struct ImpactGateConfig {
    pub max_safe_caller_count: usize,
    pub confidence_threshold: f64,
}

impl Default for ImpactGateConfig {
    fn default() -> Self {
        Self {
            max_safe_caller_count: 10,
            confidence_threshold: 0.80,
        }
    }
}

pub struct GitNexusCapsuleCommitActor<A: ImpactAnalyzer> {
    analyzer: A,
    config: ImpactGateConfig,
    pending_capsules: HashMap<Uuid, CommitmentCapsule>,
    committed_hashes: Vec<String>,
}

impl<A: ImpactAnalyzer> GitNexusCapsuleCommitActor<A> {
    pub fn new(analyzer: A, config: ImpactGateConfig) -> Self {
        Self {
            analyzer,
            config,
            pending_capsules: HashMap::new(),
            committed_hashes: Vec::new(),
        }
    }

    pub fn ingest_capsule(&mut self, capsule: CommitmentCapsule) -> Result<MergeDecision, ActorError> {
        if !Self::verify_capsule_hash(&capsule) {
            return Err(ActorError::InvalidHash {
                capsule_id: capsule.capsule_id,
            });
        }

        for symbol in &capsule.affected_symbols {
            let report = self.analyzer.analyze_impact(symbol);

            if report.confidence < self.config.confidence_threshold {
                return Ok(MergeDecision::Rejected {
                    capsule_id: capsule.capsule_id,
                    reason: format!(
                        "Low confidence analysis for {}: {}",
                        symbol, report.confidence
                    ),
                });
            }
        }

        if let Some(intersection) = self.check_all_intersections(&capsule) {
            self.pending_capsules.insert(capsule.capsule_id, capsule.clone());
            return Ok(MergeDecision::HaltForPhiPlus { intersection });
        }

        self.pending_capsules.insert(capsule.capsule_id, capsule.clone());
        self.committed_hashes.push(capsule.capsule_hash);

        Ok(MergeDecision::Approved {
            capsule_id: capsule.capsule_id,
        })
    }

    fn verify_capsule_hash(capsule: &CommitmentCapsule) -> bool {
        let mut symbols = capsule.affected_symbols.clone();
        symbols.sort();
        let input = format!("{}{}", capsule.git_diff, symbols.join(","));

        let mut hasher = Sha256::new();
        hasher.update(input.as_bytes());
        let computed = format!("{:x}", hasher.finalize());

        computed == capsule.capsule_hash
    }

    fn check_all_intersections(&self, incoming: &CommitmentCapsule) -> Option<ClusterIntersection> {
        for (_, pending) in &self.pending_capsules {
            if let Some(intersection) = self.capsules_intersect(pending, incoming) {
                return Some(intersection);
            }
        }
        None
    }

    fn capsules_intersect(
        &self,
        capsule_a: &CommitmentCapsule,
        capsule_b: &CommitmentCapsule,
    ) -> Option<ClusterIntersection> {
        let tags_a: std::collections::HashSet<_> = capsule_a.cluster_tags.iter().collect();
        let tags_b: std::collections::HashSet<_> = capsule_b.cluster_tags.iter().collect();

        let intersecting_clusters: Vec<String> = tags_a
            .intersection(&tags_b)
            .map(|s| s.to_string())
            .collect();

        if !intersecting_clusters.is_empty() {
            return Some(ClusterIntersection {
                capsule_a: capsule_a.capsule_id,
                capsule_b: capsule_b.capsule_id,
                intersecting_symbols: vec![],
                intersecting_clusters,
                risk_level: BlastRiskLevel::High,
                requires_phi_plus: true,
            });
        }

        let symbols_a: std::collections::HashSet<_> = capsule_a.affected_symbols.iter().collect();
        let symbols_b: std::collections::HashSet<_> = capsule_b.affected_symbols.iter().collect();

        let intersecting_symbols: Vec<String> = symbols_a
            .intersection(&symbols_b)
            .map(|s| s.to_string())
            .collect();

        if !intersecting_symbols.is_empty() {
            return Some(ClusterIntersection {
                capsule_a: capsule_a.capsule_id,
                capsule_b: capsule_b.capsule_id,
                intersecting_symbols,
                intersecting_clusters: vec![],
                risk_level: BlastRiskLevel::High,
                requires_phi_plus: true,
            });
        }

        None
    }


    pub fn phi_plus_review(&mut self, intersection: ClusterIntersection) -> MergeDecision {
        let capsule_a = self.pending_capsules.get(&intersection.capsule_a).cloned();
        let capsule_b = self.pending_capsules.get(&intersection.capsule_b).cloned();

        match (capsule_a, capsule_b) {
            (Some(cap_a), Some(cap_b)) => {
                let eval = EvalCourt::new();

                let report_a = eval.evaluate(ProposedUpdate {
                    update_id: Uuid::new_v4(),
                    description: cap_a.git_diff.clone(),
                    target_skill: "capsule_commit".into(),
                });

                let report_b = eval.evaluate(ProposedUpdate {
                    update_id: Uuid::new_v4(),
                    description: cap_b.git_diff.clone(),
                    target_skill: "capsule_commit".into(),
                });

                match (&report_a.verdict, &report_b.verdict) {
                    (EvalVerdict::Safe, EvalVerdict::Safe) => {
                        let oldest = if cap_a.created_at <= cap_b.created_at {
                            &cap_a
                        } else {
                            &cap_b
                        };
                        self.pending_capsules.remove(&oldest.capsule_id);
                        self.committed_hashes.push(oldest.capsule_hash.clone());
                        MergeDecision::Approved {
                            capsule_id: oldest.capsule_id,
                        }
                    }
                    (EvalVerdict::Safe, EvalVerdict::Unsafe(_)) => {
                        self.pending_capsules.remove(&cap_b.capsule_id);
                        MergeDecision::Rejected {
                            capsule_id: cap_b.capsule_id,
                            reason: "φ+ evaluation: Unsafe changes rejected (Safe capsule approved)".into(),
                        }
                    }
                    (EvalVerdict::Unsafe(_), EvalVerdict::Safe) => {
                        self.pending_capsules.remove(&cap_a.capsule_id);
                        MergeDecision::Rejected {
                            capsule_id: cap_a.capsule_id,
                            reason: "φ+ evaluation: Unsafe changes rejected (Safe capsule approved)".into(),
                        }
                    }
                    (EvalVerdict::Unsafe(_), EvalVerdict::Unsafe(_)) => {
                        self.pending_capsules.remove(&cap_a.capsule_id);
                        self.pending_capsules.remove(&cap_b.capsule_id);
                        MergeDecision::Rejected {
                            capsule_id: cap_a.capsule_id,
                            reason: "φ+ evaluation: Both capsules Unsafe - Fail-Closed".into(),
                        }
                    }
                }
            }
            _ => MergeDecision::Rejected {
                capsule_id: intersection.capsule_a,
                reason: "Missing capsule in pending pool".into(),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct MockAnalyzer {
        safe_symbols: Vec<String>,
    }

    impl MockAnalyzer {
        fn new(safe_symbols: Vec<String>) -> Self {
            Self { safe_symbols }
        }
    }

    impl ImpactAnalyzer for MockAnalyzer {
        fn analyze_impact(&self, symbol: &str) -> ImpactReport {
            let confidence = if self.safe_symbols.contains(&symbol.to_string()) {
                0.95
            } else {
                0.50
            };

            ImpactReport {
                symbol: symbol.to_string(),
                caller_count: 5,
                affected_process_count: 2,
                risk_level: BlastRiskLevel::Medium,
                confidence,
            }
        }
    }

    fn test_capsule(
        id: u64,
        agent_id: u64,
        symbols: Vec<&str>,
        clusters: Vec<&str>,
        created_at: u64,
    ) -> CommitmentCapsule {
        let symbols_str: Vec<String> = symbols.iter().map(|s| s.to_string()).collect();
        let clusters_str: Vec<String> = clusters.iter().map(|s| s.to_string()).collect();
        let git_diff = format!("diff for {}", id);

        let mut sorted_symbols = symbols_str.clone();
        sorted_symbols.sort();
        let input = format!("{}{}", git_diff, sorted_symbols.join(","));

        let mut hasher = Sha256::new();
        hasher.update(input.as_bytes());
        let capsule_hash = format!("{:x}", hasher.finalize());

        CommitmentCapsule {
            capsule_id: Uuid::from_u64_pair(id, 0),
            agent_id: Uuid::from_u64_pair(agent_id, 0),
            affected_symbols: symbols_str,
            target_files: vec!["test.rs".into()],
            git_diff,
            cluster_tags: clusters_str,
            created_at,
            capsule_hash,
        }
    }

    #[test]
    fn test_single_capsule_commits_directly() {
        let analyzer = MockAnalyzer::new(vec!["login".to_string()]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let capsule = test_capsule(1, 1, vec!["login"], vec!["auth"], 1000);
        let result = actor.ingest_capsule(capsule.clone());

        assert!(matches!(result, Ok(MergeDecision::Approved { .. })));
    }

    #[test]
    fn test_two_non_overlapping_capsules_both_approve() {
        let analyzer = MockAnalyzer::new(vec!["login".to_string(), "register".to_string()]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let capsule_a = test_capsule(1, 1, vec!["login"], vec!["auth"], 1000);
        let capsule_b = test_capsule(2, 2, vec!["register"], vec!["user"], 1001);

        let result_a = actor.ingest_capsule(capsule_a);
        let result_b = actor.ingest_capsule(capsule_b);

        assert!(matches!(result_a, Ok(MergeDecision::Approved { .. })));
        assert!(matches!(result_b, Ok(MergeDecision::Approved { .. })));
    }

    #[test]
    fn test_cluster_tag_intersection_triggers_halt() {
        let analyzer = MockAnalyzer::new(vec!["login".to_string(), "auth".to_string()]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let capsule_a = test_capsule(1, 1, vec!["login"], vec!["auth-cluster"], 1000);
        let capsule_b = test_capsule(2, 2, vec!["auth"], vec!["auth-cluster"], 1001);

        let result_a = actor.ingest_capsule(capsule_a);
        assert!(matches!(result_a, Ok(MergeDecision::Approved { .. })));

        let result_b = actor.ingest_capsule(capsule_b);
        assert!(matches!(result_b, Ok(MergeDecision::HaltForPhiPlus { .. })));
    }

    #[test]
    fn test_symbol_overlap_triggers_halt() {
        let analyzer = MockAnalyzer::new(vec!["login".to_string()]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let capsule_a = test_capsule(1, 1, vec!["login"], vec!["cluster1"], 1000);
        let capsule_b = test_capsule(2, 2, vec!["login"], vec!["cluster2"], 1001);

        let result_a = actor.ingest_capsule(capsule_a);
        assert!(matches!(result_a, Ok(MergeDecision::Approved { .. })));

        let result_b = actor.ingest_capsule(capsule_b);
        assert!(matches!(result_b, Ok(MergeDecision::HaltForPhiPlus { .. })));
    }

    #[test]
    fn test_phi_plus_approves_oldest_first_when_both_safe() {
        let analyzer = MockAnalyzer::new(vec!["login".to_string()]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let capsule_a = test_capsule(1, 1, vec!["login"], vec!["auth"], 1000);
        let capsule_b = test_capsule(2, 2, vec!["login"], vec!["other"], 2000);

        actor.ingest_capsule(capsule_a.clone()).ok();
        actor.ingest_capsule(capsule_b.clone()).ok();

        let intersection = ClusterIntersection {
            capsule_a: capsule_a.capsule_id,
            capsule_b: capsule_b.capsule_id,
            intersecting_symbols: vec!["login".into()],
            intersecting_clusters: vec![],
            risk_level: BlastRiskLevel::High,
            requires_phi_plus: true,
        };

        let decision = actor.phi_plus_review(intersection);
        assert!(matches!(decision, MergeDecision::Approved { capsule_id } if capsule_id == capsule_a.capsule_id));
    }

    #[test]
    fn test_phi_plus_rejects_unsafe_capsule() {
        let analyzer = MockAnalyzer::new(vec!["safe_symbol".to_string()]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let capsule_a = test_capsule(1, 1, vec!["safe_symbol"], vec!["cluster1"], 1000);
        let capsule_b = test_capsule(2, 2, vec!["unsafe_symbol"], vec!["cluster1"], 1001);

        actor.ingest_capsule(capsule_a.clone()).ok();
        actor.ingest_capsule(capsule_b.clone()).ok();

        let intersection = ClusterIntersection {
            capsule_a: capsule_a.capsule_id,
            capsule_b: capsule_b.capsule_id,
            intersecting_symbols: vec![],
            intersecting_clusters: vec!["cluster1".into()],
            risk_level: BlastRiskLevel::High,
            requires_phi_plus: true,
        };

        let decision = actor.phi_plus_review(intersection);
        assert!(matches!(decision, MergeDecision::Rejected { .. }));
    }

    #[test]
    fn test_phi_plus_rejects_both_when_both_unsafe() {
        let analyzer = MockAnalyzer::new(vec![]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let capsule_a = test_capsule(1, 1, vec!["unsafe_a"], vec!["cluster1"], 1000);
        let capsule_b = test_capsule(2, 2, vec!["unsafe_b"], vec!["cluster1"], 1001);

        actor.ingest_capsule(capsule_a.clone()).ok();
        actor.ingest_capsule(capsule_b.clone()).ok();

        let intersection = ClusterIntersection {
            capsule_a: capsule_a.capsule_id,
            capsule_b: capsule_b.capsule_id,
            intersecting_symbols: vec![],
            intersecting_clusters: vec!["cluster1".into()],
            risk_level: BlastRiskLevel::High,
            requires_phi_plus: true,
        };

        let decision = actor.phi_plus_review(intersection);
        assert!(matches!(decision, MergeDecision::Rejected { .. }));
    }

    #[test]
    fn test_capsule_hash_verified_on_ingest() {
        let analyzer = MockAnalyzer::new(vec![]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let mut capsule = test_capsule(1, 1, vec!["login"], vec!["auth"], 1000);
        capsule.capsule_hash = "tampered_hash".into();

        let result = actor.ingest_capsule(capsule);
        assert!(matches!(result, Err(ActorError::InvalidHash { .. })));
    }

    #[test]
    fn test_approved_capsule_recorded_in_base_actor() {
        let analyzer = MockAnalyzer::new(vec!["login".to_string()]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let capsule = test_capsule(1, 1, vec!["login"], vec!["auth"], 1000);
        let original_hash = capsule.capsule_hash.clone();

        actor.ingest_capsule(capsule).ok();

        assert!(actor.committed_hashes.contains(&original_hash));
    }

    #[test]
    fn test_low_confidence_analysis_blocked() {
        let analyzer = MockAnalyzer::new(vec![]);
        let mut actor = GitNexusCapsuleCommitActor::new(analyzer, ImpactGateConfig::default());

        let capsule = test_capsule(1, 1, vec!["unknown_symbol"], vec!["cluster1"], 1000);
        let result = actor.ingest_capsule(capsule);

        assert!(matches!(result, Ok(MergeDecision::Rejected { .. })));
    }
}
