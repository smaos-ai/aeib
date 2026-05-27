/// Phase 1 Agent Integration Example
/// Demonstrates single-agent commit orchestration through CapsuleCommitActor
///
/// This example shows Agent E (Integration) generating a CommitmentCapsule
/// for orchestration changes, submitting it to CapsuleCommitActor,
/// and receiving merge decision.
///
/// Run with: cargo run --example phase1_agent_integration

use uuid::Uuid;
use chrono::Utc;
use sha2::{Sha256, Digest};

// Simulate the types from siss-capsule-commit
#[derive(Clone, Debug)]
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

impl CommitmentCapsule {
    fn compute_hash(git_diff: &str, affected_symbols: &[String]) -> String {
        let mut symbols = affected_symbols.to_vec();
        symbols.sort();
        let input = format!("{}|{}", git_diff, symbols.join("|"));
        let mut hasher = Sha256::new();
        hasher.update(input.as_bytes());
        hex::encode(hasher.finalize())
    }

    fn new(
        agent_id: Uuid,
        affected_symbols: Vec<String>,
        target_files: Vec<String>,
        git_diff: String,
        cluster_tags: Vec<String>,
    ) -> Self {
        let capsule_hash = Self::compute_hash(&git_diff, &affected_symbols);

        Self {
            capsule_id: Uuid::new_v4(),
            agent_id,
            affected_symbols,
            target_files,
            git_diff,
            cluster_tags,
            created_at: Utc::now().timestamp() as u64,
            capsule_hash,
        }
    }
}

#[derive(Debug)]
pub enum MergeDecision {
    Approved { capsule_id: Uuid },
    HaltForPhiPlus { reason: String },
    Rejected { reason: String },
}

/// Minimal CapsuleCommitActor for Phase 1 demonstration
pub struct SimpleCapsuleActor {
    pending_capsules: Vec<CommitmentCapsule>,
}

impl SimpleCapsuleActor {
    fn new() -> Self {
        Self {
            pending_capsules: Vec::new(),
        }
    }

    fn verify_hash(&self, capsule: &CommitmentCapsule) -> bool {
        let expected = CommitmentCapsule::compute_hash(
            &capsule.git_diff,
            &capsule.affected_symbols,
        );
        capsule.capsule_hash == expected
    }

    fn check_intersection(
        &self,
        incoming: &CommitmentCapsule,
    ) -> Option<Vec<String>> {
        for pending in &self.pending_capsules {
            // Level 1: Cluster tag intersection
            let incoming_clusters: std::collections::HashSet<_> =
                incoming.cluster_tags.iter().cloned().collect();
            let pending_clusters: std::collections::HashSet<_> =
                pending.cluster_tags.iter().cloned().collect();

            let cluster_overlap: Vec<_> = incoming_clusters
                .intersection(&pending_clusters)
                .cloned()
                .collect();

            if !cluster_overlap.is_empty() {
                return Some(cluster_overlap);
            }

            // Level 2: Symbol intersection
            let incoming_symbols: std::collections::HashSet<_> =
                incoming.affected_symbols.iter().cloned().collect();
            let pending_symbols: std::collections::HashSet<_> =
                pending.affected_symbols.iter().cloned().collect();

            let symbol_overlap: Vec<_> = incoming_symbols
                .intersection(&pending_symbols)
                .cloned()
                .collect();

            if !symbol_overlap.is_empty() {
                return Some(symbol_overlap);
            }
        }

        None
    }

    fn ingest_capsule(&mut self, capsule: CommitmentCapsule) -> MergeDecision {
        // Step 1: Verify hash
        if !self.verify_hash(&capsule) {
            return MergeDecision::Rejected {
                reason: format!("Hash mismatch for capsule {}", capsule.capsule_id),
            };
        }

        // Step 2: Check for intersections
        if let Some(conflicts) = self.check_intersection(&capsule) {
            return MergeDecision::HaltForPhiPlus {
                reason: format!(
                    "Intersection detected with pending capsules: conflicts = {:?}",
                    conflicts
                ),
            };
        }

        // Step 3: No conflicts - approve
        self.pending_capsules.push(capsule.clone());
        MergeDecision::Approved {
            capsule_id: capsule.capsule_id,
        }
    }
}

fn main() {
    println!("=== Phase 1: Agent Integration Example ===\n");

    // Agent E ID (Integration agent)
    let agent_e_id = Uuid::nil();

    // Create a capsule for orchestration changes
    let capsule = CommitmentCapsule::new(
        agent_e_id,
        vec![
            "ingest_capsule".to_string(),
            "execute_decisions".to_string(),
        ],
        vec!["crates/siss-capsule-commit/src/orchestration/capsule_commit_actor.rs".to_string()],
        "diff --git a/crates/siss-capsule-commit/src/orchestration/capsule_commit_actor.rs b/crates/siss-capsule-commit/src/orchestration/capsule_commit_actor.rs\nindex abc1234..def5678 100644\n--- a/crates/siss-capsule-commit/src/orchestration/capsule_commit_actor.rs\n+++ b/crates/siss-capsule-commit/src/orchestration/capsule_commit_actor.rs\n@@ -10,6 +10,10 @@ impl CapsuleOrchestrator {\n     pub fn ingest_all(&mut self, capsules: Vec<CommitmentCapsule>) -> Vec<MergeDecision> {\n+        // New: batch intersection detection\n+        let intersections = self.detect_all_intersections(&capsules);\n+        println!(\"Detected {} intersections\", intersections.len());\n     }\n }".to_string(),
        vec!["orchestration-cluster".to_string()],
    );

    println!("Agent E Generated Capsule:");
    println!("  ID: {}", capsule.capsule_id);
    println!("  Symbols: {:?}", capsule.affected_symbols);
    println!("  Cluster: {:?}", capsule.cluster_tags);
    println!("  Hash: {}", &capsule.capsule_hash[..16]);
    println!("  Created: {}\n", capsule.created_at);

    // Submit to CapsuleCommitActor
    let mut actor = SimpleCapsuleActor::new();

    println!("Submitting capsule to CapsuleCommitActor...");
    let decision = actor.ingest_capsule(capsule.clone());

    match decision {
        MergeDecision::Approved { capsule_id } => {
            println!("✓ APPROVED: Capsule {} ready for merge to main", capsule_id);
        }
        MergeDecision::HaltForPhiPlus { reason } => {
            println!("⚠ HALT FOR Φ+: {}", reason);
        }
        MergeDecision::Rejected { reason } => {
            println!("✗ REJECTED: {}", reason);
        }
    }

    println!("\n=== Test: Hash Tampering Detection ===\n");

    // Test: Try to submit a capsule with wrong hash (should be rejected)
    let mut bad_capsule = capsule.clone();
    bad_capsule.capsule_hash = "0000000000000000".to_string();

    let mut actor2 = SimpleCapsuleActor::new();
    println!("Submitting capsule with tampered hash...");
    let decision2 = actor2.ingest_capsule(bad_capsule);

    match decision2 {
        MergeDecision::Rejected { reason } => {
            println!("✓ CORRECTLY REJECTED: {}", reason);
        }
        _ => {
            println!("✗ ERROR: Should have rejected tampered hash");
        }
    }

    println!("\n=== Test: Cluster Intersection Detection ===\n");

    // Create two capsules in same cluster
    let capsule_1 = CommitmentCapsule::new(
        Uuid::new_v4(),
        vec!["function_a".to_string()],
        vec!["file_a.rs".to_string()],
        "diff for a".to_string(),
        vec!["shared-cluster".to_string()],
    );

    let capsule_2 = CommitmentCapsule::new(
        Uuid::new_v4(),
        vec!["function_b".to_string()],
        vec!["file_b.rs".to_string()],
        "diff for b".to_string(),
        vec!["shared-cluster".to_string()],
    );

    let mut actor3 = SimpleCapsuleActor::new();

    println!("Submitting capsule 1 (shared-cluster)...");
    let d1 = actor3.ingest_capsule(capsule_1.clone());
    match d1 {
        MergeDecision::Approved { .. } => println!("✓ Approved"),
        _ => println!("✗ Unexpected"),
    }

    println!("Submitting capsule 2 (also shared-cluster)...");
    let d2 = actor3.ingest_capsule(capsule_2);
    match d2 {
        MergeDecision::HaltForPhiPlus { reason } => {
            println!("✓ HALT FOR Φ+: {}", reason);
        }
        _ => println!("✗ Should have detected intersection"),
    }

    println!("\n=== Phase 1 Demonstration Complete ===");
    println!("✓ Hash verification works");
    println!("✓ Cluster intersection detection works");
    println!("✓ Capsule approval works");
}
