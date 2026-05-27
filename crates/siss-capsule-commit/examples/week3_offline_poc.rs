/// Week 3 Offline PoC: All 5 Agents Committing in Parallel
/// Demonstrates safe simultaneous commit orchestration through CapsuleCommitActor
///
/// Scenario: All 5 agents (Auth, Inference, KG, Mandates, Integration)
/// generate capsules with ZERO file/cluster overlap.
/// System approves all 5 in parallel (oldest-first ordering).
///
/// Run with: cargo run --example week3_offline_poc

use uuid::Uuid;
use chrono::Utc;
use sha2::{Sha256, Digest};
use std::collections::{HashMap, HashSet};

#[derive(Clone, Debug)]
pub struct CommitmentCapsule {
    pub capsule_id: Uuid,
    pub agent_id: Uuid,
    pub agent_name: String,
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
        agent_name: &str,
        affected_symbols: Vec<String>,
        target_files: Vec<String>,
        git_diff: String,
        cluster_tags: Vec<String>,
    ) -> Self {
        let capsule_hash = Self::compute_hash(&git_diff, &affected_symbols);

        Self {
            capsule_id: Uuid::new_v4(),
            agent_id,
            agent_name: agent_name.to_string(),
            affected_symbols,
            target_files,
            git_diff,
            cluster_tags,
            created_at: Utc::now().timestamp() as u64,
            capsule_hash,
        }
    }
}

#[derive(Debug, Clone)]
pub enum MergeDecision {
    Approved {
        capsule_id: Uuid,
        agent_name: String,
    },
    HaltForPhiPlus {
        capsule_id: Uuid,
        reason: String,
    },
    Rejected {
        capsule_id: Uuid,
        reason: String,
    },
}

/// CapsuleOrchestrator: Coordinates all 5 agents
pub struct CapsuleOrchestrator {
    pending_capsules: Vec<CommitmentCapsule>,
    approved_capsules: Vec<CommitmentCapsule>,
    halted_capsules: Vec<(CommitmentCapsule, String)>,
    rejected_capsules: Vec<(CommitmentCapsule, String)>,
}

impl CapsuleOrchestrator {
    fn new() -> Self {
        Self {
            pending_capsules: Vec::new(),
            approved_capsules: Vec::new(),
            halted_capsules: Vec::new(),
            rejected_capsules: Vec::new(),
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
    ) -> Option<(String, Vec<String>)> {
        // Check against pending capsules
        for pending in &self.pending_capsules {
            // Level 1: Cluster tag intersection
            let incoming_clusters: HashSet<_> =
                incoming.cluster_tags.iter().cloned().collect();
            let pending_clusters: HashSet<_> =
                pending.cluster_tags.iter().cloned().collect();

            let cluster_overlap: Vec<_> = incoming_clusters
                .intersection(&pending_clusters)
                .cloned()
                .collect();

            if !cluster_overlap.is_empty() {
                return Some((
                    format!(
                        "Cluster intersection with {} (clusters: {:?})",
                        pending.agent_name, cluster_overlap
                    ),
                    cluster_overlap,
                ));
            }

            // Level 2: Symbol intersection
            let incoming_symbols: HashSet<_> =
                incoming.affected_symbols.iter().cloned().collect();
            let pending_symbols: HashSet<_> =
                pending.affected_symbols.iter().cloned().collect();

            let symbol_overlap: Vec<_> = incoming_symbols
                .intersection(&pending_symbols)
                .cloned()
                .collect();

            if !symbol_overlap.is_empty() {
                return Some((
                    format!(
                        "Symbol intersection with {} (symbols: {:?})",
                        pending.agent_name, symbol_overlap
                    ),
                    symbol_overlap,
                ));
            }
        }

        None
    }

    fn ingest_capsule(&mut self, capsule: CommitmentCapsule) -> MergeDecision {
        // Step 1: Verify hash
        if !self.verify_hash(&capsule) {
            let reason = format!("Hash mismatch");
            self.rejected_capsules.push((capsule.clone(), reason.clone()));
            return MergeDecision::Rejected {
                capsule_id: capsule.capsule_id,
                reason,
            };
        }

        // Step 2: Check for intersections
        if let Some((reason, _conflicts)) = self.check_intersection(&capsule) {
            self.halted_capsules.push((capsule.clone(), reason.clone()));
            return MergeDecision::HaltForPhiPlus {
                capsule_id: capsule.capsule_id,
                reason,
            };
        }

        // Step 3: No conflicts - approve and add to pending
        self.pending_capsules.push(capsule.clone());
        self.approved_capsules.push(capsule.clone());

        MergeDecision::Approved {
            capsule_id: capsule.capsule_id,
            agent_name: capsule.agent_name.clone(),
        }
    }

    fn finalize_approvals(&mut self) {
        // Sort approved capsules by created_at (oldest first)
        self.approved_capsules.sort_by_key(|c| c.created_at);
    }

    fn report(&self) {
        println!("\n=== ORCHESTRATOR FINAL REPORT ===\n");
        println!(
            "Approved: {} | Halted: {} | Rejected: {}",
            self.approved_capsules.len(),
            self.halted_capsules.len(),
            self.rejected_capsules.len()
        );

        if !self.approved_capsules.is_empty() {
            println!("\nApproved (merge order by age):");
            for (idx, c) in self.approved_capsules.iter().enumerate() {
                println!(
                    "  {}. [{}] {} @ {}",
                    idx + 1,
                    &c.capsule_id.to_string()[..8],
                    c.agent_name,
                    c.created_at
                );
            }
        }

        if !self.halted_capsules.is_empty() {
            println!("\nHalted for Φ+ Review:");
            for (c, reason) in &self.halted_capsules {
                println!(
                    "  [{}] {}: {}",
                    &c.capsule_id.to_string()[..8],
                    c.agent_name,
                    reason
                );
            }
        }

        if !self.rejected_capsules.is_empty() {
            println!("\nRejected:");
            for (c, reason) in &self.rejected_capsules {
                println!(
                    "  [{}] {}: {}",
                    &c.capsule_id.to_string()[..8],
                    c.agent_name,
                    reason
                );
            }
        }
    }
}

fn main() {
    println!("╔══════════════════════════════════════════════════════════════╗");
    println!("║  PHASE 1 WEEK 3: OFFLINE POC - PARALLEL AGENT ORCHESTRATION  ║");
    println!("║  All 5 agents commit simultaneously (file-orthogonal)        ║");
    println!("╚══════════════════════════════════════════════════════════════╝\n");

    // Create agent identities
    let agents = vec![
        (Uuid::nil(), "Agent A"),
        (Uuid::new_v4(), "Agent B"),
        (Uuid::new_v4(), "Agent C"),
        (Uuid::new_v4(), "Agent D"),
        (Uuid::new_v4(), "Agent E"),
    ];

    // Agent A: Access Control (siss-gatekeeper)
    let capsule_a = CommitmentCapsule::new(
        agents[0].0,
        agents[0].1,
        vec!["enforce_access_policy".to_string(), "verify_credentials".to_string()],
        vec!["crates/siss-gatekeeper/src/lib.rs".to_string()],
        "diff --git a/crates/siss-gatekeeper/src/lib.rs".to_string(),
        vec!["access-control-cluster".to_string()],
    );

    // Agent B: Inference Engine (siss-agent-shell/rapid_mlx_integration.rs)
    let capsule_b = CommitmentCapsule::new(
        agents[1].0,
        agents[1].1,
        vec!["infer".to_string(), "infer_fresh".to_string()],
        vec!["crates/siss-agent-shell/src/rapid_mlx_integration.rs".to_string()],
        "diff --git a/crates/siss-agent-shell/src/rapid_mlx_integration.rs".to_string(),
        vec!["inference-cluster".to_string()],
    );

    // Agent C: Knowledge Graph (siss-sovereign-kg)
    let capsule_c = CommitmentCapsule::new(
        agents[2].0,
        agents[2].1,
        vec!["query_impact".to_string(), "detect_changes".to_string()],
        vec!["crates/siss-sovereign-kg/src/lib.rs".to_string()],
        "diff --git a/crates/siss-sovereign-kg/src/lib.rs".to_string(),
        vec!["knowledge-graph-cluster".to_string()],
    );

    // Agent D: AP2 Mandates (siss-ap2-enforcer)
    let capsule_d = CommitmentCapsule::new(
        agents[3].0,
        agents[3].1,
        vec!["process_payment".to_string(), "authorize_mandate".to_string()],
        vec!["crates/siss-ap2-enforcer/src/mandates.rs".to_string()],
        "diff --git a/crates/siss-ap2-enforcer/src/mandates.rs".to_string(),
        vec!["mandates-cluster".to_string()],
    );

    // Agent E: Orchestration (siss-capsule-commit)
    let capsule_e = CommitmentCapsule::new(
        agents[4].0,
        agents[4].1,
        vec!["ingest_capsule".to_string(), "execute_decisions".to_string()],
        vec!["crates/siss-capsule-commit/src/orchestration/capsule_commit_actor.rs".to_string()],
        "diff --git a/crates/siss-capsule-commit/src/orchestration".to_string(),
        vec!["orchestration-cluster".to_string()],
    );

    let capsules = vec![capsule_a, capsule_b, capsule_c, capsule_d, capsule_e];

    // Display all capsules
    println!("┌─ CAPSULES GENERATED BY ALL 5 AGENTS ─────────────────────────┐\n");
    for capsule in &capsules {
        println!(
            "  {} [{}]",
            capsule.agent_name,
            &capsule.capsule_id.to_string()[..8]
        );
        println!(
            "    Cluster: {:?} | Symbols: {} | Hash: {}",
            capsule.cluster_tags[0],
            capsule.affected_symbols.len(),
            &capsule.capsule_hash[..12]
        );
    }
    println!();

    // Verify no overlaps
    println!("┌─ INTERSECTION ANALYSIS ──────────────────────────────────────┐\n");

    let mut all_clusters = HashSet::new();
    let mut all_symbols = HashSet::new();
    let mut cluster_map: HashMap<String, Vec<String>> = HashMap::new();
    let mut symbol_map: HashMap<String, Vec<String>> = HashMap::new();

    for capsule in &capsules {
        for cluster in &capsule.cluster_tags {
            cluster_map
                .entry(cluster.clone())
                .or_insert_with(Vec::new)
                .push(capsule.agent_name.clone());
            all_clusters.insert(cluster.clone());
        }
        for symbol in &capsule.affected_symbols {
            symbol_map
                .entry(symbol.clone())
                .or_insert_with(Vec::new)
                .push(capsule.agent_name.clone());
            all_symbols.insert(symbol.clone());
        }
    }

    println!("  Clusters: {} unique", all_clusters.len());
    for (cluster, agents) in &cluster_map {
        println!("    - {} (agent: {})", cluster, agents[0]);
    }

    println!("\n  Symbols: {} unique", all_symbols.len());
    for (symbol, agents) in symbol_map.iter().take(3) {
        println!("    - {} (agent: {})", symbol, agents[0]);
    }
    println!("    ... and {} more\n", symbol_map.len().saturating_sub(3));

    // Check for overlaps
    let cluster_overlaps = cluster_map.values().filter(|v| v.len() > 1).count();
    let symbol_overlaps = symbol_map.values().filter(|v| v.len() > 1).count();

    if cluster_overlaps == 0 && symbol_overlaps == 0 {
        println!("  ✓ ZERO OVERLAPS: All agents are file-orthogonal\n");
    } else {
        println!(
            "  ⚠ FOUND OVERLAPS: {} cluster, {} symbol\n",
            cluster_overlaps, symbol_overlaps
        );
    }

    // Ingest all capsules through orchestrator
    println!("┌─ INGESTING CAPSULES INTO ORCHESTRATOR ─────────────────────┐\n");

    let mut orchestrator = CapsuleOrchestrator::new();
    let mut decisions = Vec::new();

    for capsule in capsules {
        let decision = orchestrator.ingest_capsule(capsule.clone());

        match &decision {
            MergeDecision::Approved { agent_name, .. } => {
                println!("  ✓ {} APPROVED", agent_name);
            }
            MergeDecision::HaltForPhiPlus { capsule_id: _, reason } => {
                println!("  ⚠ HALT: {}", reason);
            }
            MergeDecision::Rejected { capsule_id: _, reason } => {
                println!("  ✗ REJECTED: {}", reason);
            }
        }

        decisions.push(decision);
    }
    println!();

    // Finalize and report
    orchestrator.finalize_approvals();
    orchestrator.report();

    println!("\n╔══════════════════════════════════════════════════════════════╗");
    if orchestrator.approved_capsules.len() == 5
        && orchestrator.halted_capsules.is_empty()
        && orchestrator.rejected_capsules.is_empty()
    {
        println!("║  ✓ SUCCESS: All 5 agents approved for merge (parallel safe)  ║");
    } else {
        println!(
            "║  ⚠ PARTIAL: {} approved, {} halted, {} rejected           ║",
            orchestrator.approved_capsules.len(),
            orchestrator.halted_capsules.len(),
            orchestrator.rejected_capsules.len()
        );
    }
    println!("╚══════════════════════════════════════════════════════════════╝");
}
