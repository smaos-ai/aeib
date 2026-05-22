/// Phase 52: Sovereign Memory Plane — LightRAG & Context Cartography
/// RED gate: 9 failing tests define expected behavior for the cognitive plane.
/// Invariants: (1) Multi-agent graph sync with provenance hash
///             (2) 4-tier crystallization pipeline (Episodic→Semantic→Procedural)
///             (3) Confidence atrophy decay with GC eligibility

use siss_agent_shell::memory_crystallizer::{CrystalError, SemanticCrystallizer};
use siss_agent_shell::memory_decay::{DecayConfig, DecayEngine};
use siss_agent_shell::night_cycle::{CompactionTrigger, NightCycleEngine};
use siss_agent_shell::swarm_knowledge::{compute_provenance_hash, KnowledgeAtom, KnowledgeKind};
use siss_agent_shell::swarm_mcp_server::SwarmMcpServer;
use siss_feedback_router::crystallizer::Crystallizer;
use std::sync::Arc;
use std::time::Duration;

// Test 1: Provenance hash is deterministic
#[test]
fn test_provenance_hash_is_deterministic() {
    let content = "Ed25519 reused for non-repudiation";
    let hash1 = compute_provenance_hash(content);
    let hash2 = compute_provenance_hash(content);
    assert_eq!(hash1, hash2, "same content must produce same hash");
}

// Test 2: Atom published by worktree A is retrievable by worktree B
#[tokio::test]
async fn test_atom_published_by_worktree_a_retrievable_by_b() {
    let server = Arc::new(SwarmMcpServer::new("sqlite::memory:").await.unwrap());
    let bus_a = siss_agent_shell::swarm_knowledge::SwarmKnowledgeBus::new(server.clone());
    let bus_b = siss_agent_shell::swarm_knowledge::SwarmKnowledgeBus::new(server.clone());

    let atom = KnowledgeAtom::new(
        KnowledgeKind::ArchitecturalPattern,
        "alpha",
        "siss_gatekeeper::tokens",
        "Ed25519 is reusable",
        0.85,
    );
    let atom_id = atom.atom_id;

    bus_a.publish(atom.clone(), "alpha").await.unwrap();
    let results = bus_b.query_by_kind(&KnowledgeKind::ArchitecturalPattern).await.unwrap();

    assert_eq!(results.len(), 1);
    assert_eq!(results[0].atom_id, atom_id);
    assert_eq!(results[0].source_worktree, "alpha");
}

// Test 3: Query by confidence excludes low confidence
#[tokio::test]
async fn test_query_by_confidence_excludes_low_confidence() {
    let server = Arc::new(SwarmMcpServer::new("sqlite::memory:").await.unwrap());
    let bus = siss_agent_shell::swarm_knowledge::SwarmKnowledgeBus::new(server.clone());

    let _atom_low = KnowledgeAtom::new(
        KnowledgeKind::VulnerabilityFound,
        "alpha",
        "crate::module",
        "Low confidence finding",
        0.5,
    );
    bus.publish(_atom_low, "alpha").await.unwrap();

    let results = bus.query_by_confidence(0.8).await.unwrap();
    assert_eq!(
        results.len(),
        0,
        "query_by_confidence(0.8) should exclude confidence=0.5"
    );
}

// Test 4: Night Cycle crystallizes COMPLETE payloads to Episodic
#[test]
fn test_night_cycle_crystallizes_complete_to_episodic() {
    use siss_agent_shell::swarm_mcp_server::SwarmStatePayload;
    use siss_feedback_router::types::CrystallizedMemory;
    use siss_graph_core::node::memory::ConsolidationTier;

    struct MockCrystallizer;
    impl Crystallizer for MockCrystallizer {
        fn crystallize(
            &self,
            _context: &siss_feedback_router::crystallizer::CrystallizationContext,
        ) -> Vec<CrystallizedMemory> {
            vec![]
        }
    }

    let trigger = CompactionTrigger {
        event_count_threshold: 1,
        cycle_interval: Duration::from_secs(3600),
    };
    let engine = NightCycleEngine {
        trigger,
        crystallizer: MockCrystallizer,
    };

    let payload = SwarmStatePayload {
        idempotency_key: "test:complete:1".to_string(),
        agent_id: "alpha".to_string(),
        phase: "EXECUTION".to_string(),
        status: "COMPLETE".to_string(),
        payload_json: Some("{}".to_string()),
    };

    let (memories, keys) = engine.crystallize_batch(&[payload]).unwrap();
    assert_eq!(memories.len(), 1);
    assert_eq!(memories[0].tier, ConsolidationTier::Episodic);
    assert_eq!(keys.len(), 1);
}

// Test 5: SemanticCrystallizer promotes above threshold
#[test]
fn test_semantic_crystallizer_promotes_above_threshold() {
    let crystallizer = SemanticCrystallizer {
        min_confidence: 0.90,
        min_reinforcements: 2,
    };

    let mut atom = KnowledgeAtom::new(
        KnowledgeKind::ArchitecturalPattern,
        "alpha",
        "siss_gatekeeper::tokens",
        "high confidence pattern",
        0.92,
    );
    atom.reinforcement_count = 3;

    let result = crystallizer.promote(&atom).unwrap();
    assert_eq!(result.tier, siss_graph_core::node::memory::ConsolidationTier::Semantic);
    assert_eq!(result.confidence, 0.92);
}

// Test 6: SemanticCrystallizer rejects low confidence
#[test]
fn test_semantic_crystallizer_rejects_low_confidence() {
    let crystallizer = SemanticCrystallizer {
        min_confidence: 0.90,
        min_reinforcements: 2,
    };

    let atom = KnowledgeAtom::new(
        KnowledgeKind::VulnerabilityFound,
        "alpha",
        "crate::module",
        "low confidence finding",
        0.75,
    );

    let result = crystallizer.promote(&atom);
    assert!(matches!(result, Err(CrystalError::ConfidenceTooLow { .. })));
}

// Test 7: Effective confidence decays over time
#[test]
fn test_effective_confidence_decays_over_time() {
    let atom = KnowledgeAtom::new(
        KnowledgeKind::ArchitecturalPattern,
        "alpha",
        "siss_gatekeeper",
        "test content",
        1.0,
    );

    let initial_confidence = atom.confidence;

    let now_plus_96h = atom.discovered_at + chrono::Duration::hours(96);
    let decayed_confidence = atom.effective_confidence(now_plus_96h);

    assert!(decayed_confidence < initial_confidence, "decayed < initial");
    assert!(decayed_confidence > 0.0, "decayed > 0");
}

// Test 8: Reinforce boosts confidence asymptotically
#[test]
fn test_reinforce_boosts_confidence_asymptotically() {
    let mut atom = KnowledgeAtom::new(
        KnowledgeKind::ArchitecturalPattern,
        "alpha",
        "siss_gatekeeper",
        "test",
        0.5,
    );

    let initial = atom.confidence;
    atom.reinforce();
    atom.reinforce();
    atom.reinforce();
    atom.reinforce();
    atom.reinforce();

    let final_confidence = atom.confidence;
    assert!(final_confidence > initial, "reinforced > initial");
    assert!(final_confidence < 1.0, "reinforced < 1.0 (asymptotic)");
    assert_eq!(atom.reinforcement_count, 5);
}

// Test 9: GC eligible after decay below threshold
#[test]
fn test_gc_eligible_after_decay() {
    let atom = KnowledgeAtom::new(
        KnowledgeKind::VulnerabilityFound,
        "alpha",
        "crate::module",
        "old finding",
        1.0,
    );

    let config = DecayConfig {
        gc_threshold: 0.10,
        stability_hours: 48.0,
    };

    let now_plus_200h = atom.discovered_at + chrono::Duration::hours(200);
    let (survived, gc_eligible) = DecayEngine::run_pass(&[atom.clone()], &config, now_plus_200h);

    assert_eq!(survived, 0, "old atom should not survive");
    assert_eq!(gc_eligible.len(), 1, "old atom should be GC eligible");
    assert_eq!(gc_eligible[0], atom.atom_id);
}
