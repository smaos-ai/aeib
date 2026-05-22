/// Phase 56: Sovereign Skill Pack Compilation & AP2 Syndication — The Crafter Economy Layer
/// RED gate: 9 failing tests define expected behavior for skill compilation, AP2 routing, and human covenant approval.

use siss_agent_shell::ap2_syndication::{Ap2Syndication, CreatorDid};
use siss_agent_shell::covenant_charter::CovenantCharter;
use siss_agent_shell::hooks::LifecycleHook;
use siss_agent_shell::skill_compiler::SkillCompiler;
use siss_gatekeeper::tokens::IntentMandate;
use ed25519_dalek::SigningKey;
use uuid::Uuid;

// Test 1: SkillCompiler parses valid SKILL.md frontmatter
#[test]
fn test_skill_compiler_parses_frontmatter() {
    let content = r#"---
name: test_skill
description: A test skill for Phase 56
allowed-tools: [Read, Edit, Bash]
disallowedTools: [Write]
---
# Skill Implementation
This is the skill body."#;

    let (fm, body) = SkillCompiler::parse_frontmatter(content).unwrap();
    assert_eq!(fm.name, "test_skill");
    assert_eq!(fm.description, "A test skill for Phase 56");
    assert_eq!(fm.allowed_tools, vec!["Read", "Edit", "Bash"]);
    assert_eq!(fm.disallowed_tools, Some(vec!["Write".to_string()]));
    assert!(body.contains("Skill Implementation"));
}

// Test 2: SkillCompiler rejects malformed YAML
#[test]
fn test_skill_compiler_rejects_malformed_yaml() {
    let content = "no frontmatter here";
    let result = SkillCompiler::parse_frontmatter(content);
    assert!(result.is_err());
}

// Test 3: SkillCompiler compiles and signs SkillPack
#[test]
fn test_skill_compiler_compiles_and_signs() {
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);

    let content = r#"---
name: secure_skill
description: Cryptographically secured skill
allowed-tools: [Read]
---
# Secure implementation"#;

    let pack = SkillCompiler::compile(content, &signing_key).unwrap();
    assert_eq!(pack.frontmatter.name, "secure_skill");
    assert!(!pack.signature.is_empty());
    assert_eq!(pack.creator_public_key.len(), 32);
}

// Test 4: SkillCompiler rejects empty body
#[test]
fn test_skill_compiler_rejects_empty_body() {
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);

    let content = r#"---
name: empty_skill
description: No body
allowed-tools: [Read]
---
"#;

    let result = SkillCompiler::compile(content, &signing_key);
    assert!(result.is_err());
}

// Test 5: SkillCompiler verifies valid signature
#[test]
fn test_skill_compiler_verifies_valid_signature() {
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);

    let content = r#"---
name: verified_skill
description: Signature verification test
allowed-tools: [Read, Edit]
---
# Implementation body with content"#;

    let pack = SkillCompiler::compile(content, &signing_key).unwrap();
    assert!(SkillCompiler::verify(&pack));
}

// Test 6: Ap2Syndication validates and routes with valid mandate
#[test]
fn test_ap2_syndication_validates_with_valid_mandate() {
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);

    let content = r#"---
name: routable_skill
description: Can be routed via AP2
allowed-tools: [Read]
---
# Routable implementation"#;

    let pack = SkillCompiler::compile(content, &signing_key).unwrap();

    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 10000,
        budget_spent: 5000,
        risk_class: "LOW".to_string(),
        allowed_tools: vec![],
    };

    let creator_did = CreatorDid {
        did: format!("did:sovereign:{}", Uuid::new_v4()),
        agent_id: Uuid::new_v4(),
        public_key_bytes: vec![0u8; 32],
    };

    let result = Ap2Syndication::validate_and_route(&pack, Some(&mandate), &creator_did, 500);
    assert!(result.is_ok());
    let record = result.unwrap();
    assert_eq!(record.micro_transaction_amount, 500);
}

// Test 7: Ap2Syndication rejects missing mandate (fail-closed)
#[test]
fn test_ap2_syndication_rejects_missing_mandate() {
    let mut rng = rand::thread_rng();
    let signing_key = SigningKey::generate(&mut rng);

    let content = r#"---
name: unroutable
description: No mandate provided
allowed-tools: [Read]
---
# Body"#;

    let pack = SkillCompiler::compile(content, &signing_key).unwrap();

    let creator_did = CreatorDid {
        did: format!("did:sovereign:{}", Uuid::new_v4()),
        agent_id: Uuid::new_v4(),
        public_key_bytes: vec![0u8; 32],
    };

    let result = Ap2Syndication::validate_and_route(&pack, None, &creator_did, 100);
    assert!(result.is_err());
}

// Test 8: CovenantCharter halts unapproved syndication (human gate)
#[test]
fn test_covenant_charter_halts_unapproved_syndication() {
    use siss_agent_shell::hooks::{HookResult, ToolUseContext};
    use siss_graph_core::node::NodeId;
    use serde_json::json;

    let charter = CovenantCharter::new();
    let pack_id = Uuid::new_v4();

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "Syndicate".to_string(),
        tool_input: json!({ "skill_pack_id": pack_id.to_string() }),
        tool_output: None,
    };

    let result = charter.on_pre_tool_use(&ctx);
    assert_eq!(
        result,
        HookResult::Halt {
            reason: "human_approval_required".to_string()
        }
    );
}

// Test 9: CovenantCharter allows approved syndication
#[test]
fn test_covenant_charter_allows_approved_syndication() {
    use siss_agent_shell::hooks::{HookResult, ToolUseContext};
    use siss_graph_core::node::NodeId;
    use serde_json::json;

    let charter = CovenantCharter::new();
    let pack_id = Uuid::new_v4();

    // Register human approval
    let _ = charter.register_approval(pack_id, vec![0u8; 64]);

    let ctx = ToolUseContext {
        task_id: NodeId::new(),
        tool_id: Uuid::new_v4(),
        tool_name: "Syndicate".to_string(),
        tool_input: json!({ "skill_pack_id": pack_id.to_string() }),
        tool_output: None,
    };

    let result = charter.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}
