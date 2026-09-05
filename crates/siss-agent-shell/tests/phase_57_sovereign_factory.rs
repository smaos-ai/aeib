use ed25519_dalek::SigningKey;
use siss_agent_shell::batch_orchestrator::{ClaimError, InMemoryClaimLedger};
use siss_agent_shell::hooks::LifecycleHook;
/// Phase 57: Sovereign Factory — Air-Gap, Batch, Sneakernet (9 RED→GREEN tests)
use siss_agent_shell::mlx_hardware::AirGapMembrane;
use siss_agent_shell::skill_compiler::SkillCompiler;
use siss_agent_shell::sneakernet_ingress::SneakernetIngress;
use uuid::Uuid;

// ─── AIR-GAP MEMBRANE TESTS ─────────────────────────────────────────

#[test]
fn test_air_gap_membrane_blocks_openai() {
    let membrane = AirGapMembrane::default();
    assert!(membrane.is_blocked("api.openai.com"));
    assert!(membrane.is_blocked("chat.openai.com"));
    assert!(membrane.is_blocked("openai.com"));
}

#[test]
fn test_air_gap_membrane_allows_localhost() {
    let membrane = AirGapMembrane::default();
    assert!(!membrane.is_blocked("localhost"));
    assert!(!membrane.is_blocked("127.0.0.1"));
    assert!(!membrane.is_blocked("internal.sovereign.ai"));
}

#[test]
fn test_air_gap_membrane_hook_halts_fetch() {
    use serde_json::json;
    use siss_agent_shell::hooks::{HookResult, ToolUseContext};
    use siss_graph_core::node::NodeId;

    let membrane = AirGapMembrane::default();
    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "HttpFetch".to_string(),
        tool_input: json!({ "url": "https://api.openai.com/chat" }),
        tool_output: None,
    };

    let result = membrane.on_pre_tool_use(&ctx);
    assert_eq!(
        result,
        HookResult::Halt {
            reason: "air_gap_violation".to_string()
        }
    );
}

// ─── BATCH ORCHESTRATOR TESTS ──────────────────────────────────────

#[tokio::test]
async fn test_claim_ledger_grants_exclusive_file() {
    let ledger = InMemoryClaimLedger::new();
    let agent_id = Uuid::new_v4();

    let claim = ledger.claim_file("workspace/agent1.lock", agent_id).await;
    assert!(claim.is_ok());
    assert_eq!(claim.unwrap().owner_id, agent_id);
}

#[tokio::test]
async fn test_claim_ledger_rejects_collision() {
    let ledger = InMemoryClaimLedger::new();
    let agent1 = Uuid::new_v4();
    let agent2 = Uuid::new_v4();

    let _ = ledger.claim_file("collision.txt", agent1).await;
    let result = ledger.claim_file("collision.txt", agent2).await;

    assert_eq!(result, Err(ClaimError::AlreadyClaimed { owner_id: agent1 }));
}

#[tokio::test]
async fn test_claim_ledger_allows_release_by_owner() {
    let ledger = InMemoryClaimLedger::new();
    let owner = Uuid::new_v4();

    let _ = ledger.claim_file("release.txt", owner).await;
    let result = ledger.release_file("release.txt", owner).await;

    assert!(result.is_ok());
    let get = ledger.get_claim("release.txt").await;
    assert!(get.is_none());
}

// ─── SNEAKERNET INGRESS TESTS ──────────────────────────────────────

#[test]
fn test_sneakernet_gate_1_signature() {
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);

    let content = r#"---
name: test_skill
description: test
allowed-tools: [Read]
---
# test"#;

    let pack = SkillCompiler::compile(content, &signing_key).unwrap();
    let result = SneakernetIngress::gate_1_verify_signature(&pack);
    assert!(result.is_ok());
}

#[test]
fn test_sneakernet_gate_2_frontmatter() {
    let pack = siss_agent_shell::skill_compiler::SkillPack {
        pack_id: Uuid::new_v4(),
        creator_public_key: vec![0u8; 32],
        frontmatter: siss_agent_shell::skill_compiler::SkillFrontmatter {
            name: "valid_name".to_string(),
            description: "valid desc".to_string(),
            allowed_tools: vec!["Read".to_string()],
            disallowed_tools: None,
        },
        content_hash: "abc123".to_string(),
        signature: vec![0u8; 64],
    };

    let result = SneakernetIngress::gate_2_validate_frontmatter(&pack);
    assert!(result.is_ok());
}

#[test]
fn test_sneakernet_quarantine_all_gates() {
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);

    let content = r#"---
name: complete_skill
description: All gates pass
allowed-tools: [Read, Edit]
---
# Complete"#;

    let pack = SkillCompiler::compile(content, &signing_key).unwrap();
    let result = SneakernetIngress::quarantine(&pack, true);

    assert!(result.is_ok());
    let record = result.unwrap();
    assert!(record.gate_1_signature_verified);
    assert!(record.gate_2_frontmatter_valid);
    assert!(record.gate_3_dry_run_passed);
    assert!(record.gate_4_human_approved);
}
