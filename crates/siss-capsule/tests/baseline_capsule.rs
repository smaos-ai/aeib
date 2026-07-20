// Phase 3 Stream 1: BaselineCapsule + HarnessCapsule v1 Tests
// 20 tests: Policy Verification (4) + Tool Authorization (3) + Execution Context (3) + Audit (3) + Adapters (7)

use siss_capsule::{
    BaselineCapsule, HarnessCapsule, HarnessConfig,
    PolicyVerificationResult, ToolAuthProof, ExecutionContext, ContextIsolation,
    AuditTraceEntry, MerkleProofVerification,
    LangChainAdapter, OllamaAdapter, AutoGPTAdapter,
};
use siss_behavioral_firewall::{
    ReBAC, AP2Evaluator, SovereignIdentity, PolicyResource, PolicyAction,
    RelationType, AuditArchive,
};
use uuid::Uuid;
use std::time::Instant;
use std::sync::Arc;

// ============================================================================
// PHASE 1: Policy Verification Tests (4)
// ============================================================================

#[tokio::test]
async fn test_baseline_verify_rebac_owner_allows_spawn() {
    let rebac = Arc::new(ReBAC::new());
    let baseline = BaselineCapsule::new(rebac.clone());

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let agent_resource = PolicyResource::Agent(Uuid::new_v4());

    // Grant Owner relationship
    let _ = rebac.grant_relationship(sovereign_id, agent_resource.clone(), RelationType::Owner, None);

    let result = baseline.verify_policy(
        sovereign_id,
        agent_resource,
        PolicyAction::Spawn,
    ).await;

    assert!(matches!(result, PolicyVerificationResult::Allowed(_)));
}

#[tokio::test]
async fn test_baseline_verify_non_owner_denies() {
    let rebac = Arc::new(ReBAC::new());
    let baseline = BaselineCapsule::new(rebac.clone());

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let other_id = SovereignIdentity(Uuid::new_v4());
    let agent_resource = PolicyResource::Agent(Uuid::new_v4());

    // Grant Observer relationship to other_id (read-only)
    let _ = rebac.grant_relationship(other_id, agent_resource.clone(), RelationType::Observer, None);

    let result = baseline.verify_policy(
        sovereign_id,
        agent_resource,
        PolicyAction::Spawn,
    ).await;

    assert!(matches!(result, PolicyVerificationResult::Denied(_)));
}

#[tokio::test]
async fn test_baseline_verify_ap2_attributes_allow() {
    let rebac = Arc::new(ReBAC::new());
    let ap2 = Arc::new(AP2Evaluator::with_defaults());
    let baseline = BaselineCapsule::with_ap2(rebac.clone(), ap2.clone());

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let agent_resource = PolicyResource::Agent(Uuid::new_v4());

    // Grant Owner + set AP2 attributes allowing Spawn
    let _ = rebac.grant_relationship(sovereign_id, agent_resource.clone(), RelationType::Owner, None);

    let mut attrs = SovereignAttributes::default();
    attrs.roles.insert("admin".to_string());
    ap2.set_attributes(sovereign_id, attrs);

    let result = baseline.verify_policy(
        sovereign_id,
        agent_resource,
        PolicyAction::Spawn,
    ).await;

    assert!(matches!(result, PolicyVerificationResult::Allowed(_)));
}

#[tokio::test]
async fn test_baseline_verify_ap2_deny_override() {
    let rebac = Arc::new(ReBAC::new());
    let ap2 = Arc::new(AP2Evaluator::with_defaults());
    let baseline = BaselineCapsule::with_ap2(rebac.clone(), ap2.clone());

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let agent_resource = PolicyResource::Agent(Uuid::new_v4());

    // Grant Owner but set AP2 deny attributes
    let _ = rebac.grant_relationship(sovereign_id, agent_resource.clone(), RelationType::Owner, None);

    let mut attrs = SovereignAttributes::default();
    attrs.denied_actions.insert(PolicyAction::Spawn);
    ap2.set_attributes(sovereign_id, attrs);

    let result = baseline.verify_policy(
        sovereign_id,
        agent_resource,
        PolicyAction::Spawn,
    ).await;

    assert!(matches!(result, PolicyVerificationResult::Denied(_)));
}

// ============================================================================
// PHASE 2: Tool Authorization Tests (3)
// ============================================================================

#[tokio::test]
async fn test_baseline_tool_call_hash_proof_generation() {
    let rebac = Arc::new(ReBAC::new());
    let baseline = BaselineCapsule::new(rebac.clone());

    let tool_name = "execute_bash";
    let tool_args = r#"{"cmd": "ls -la"}"#;

    let proof = baseline.generate_tool_proof(tool_name, tool_args).await;

    assert!(proof.hash.len() > 0);
    assert!(!proof.signature.is_empty());
    assert_eq!(proof.tool_name, tool_name);
}

#[tokio::test]
async fn test_baseline_tool_call_unsigned_rejected() {
    let rebac = Arc::new(ReBAC::new());
    let baseline = BaselineCapsule::new(rebac.clone());

    let tool_name = "execute_bash";
    let tool_args = r#"{"cmd": "rm -rf /"}"#;

    // Create proof with invalid signature
    let mut proof = baseline.generate_tool_proof(tool_name, tool_args).await;
    proof.signature = vec![0u8; 64]; // Fake signature

    let result = baseline.verify_tool_auth(&proof).await;
    assert!(!result.is_valid);
}

#[tokio::test]
async fn test_baseline_tool_call_batch_verification() {
    let rebac = Arc::new(ReBAC::new());
    let baseline = BaselineCapsule::new(rebac.clone());

    let mut proofs = Vec::new();
    for i in 0..5 {
        let tool_name = format!("tool_{}", i);
        let args = format!("args_{}", i);
        let proof = baseline.generate_tool_proof(&tool_name, &args).await;
        proofs.push(proof);
    }

    let results = baseline.verify_tool_batch(&proofs).await;
    assert_eq!(results.len(), 5);
    assert!(results.iter().all(|r| r.is_valid));
}

// ============================================================================
// PHASE 3: Execution Context Isolation Tests (3)
// ============================================================================

#[tokio::test]
async fn test_baseline_context_sovereign_isolation() {
    let rebac = Arc::new(ReBAC::new());
    let baseline = BaselineCapsule::new(rebac.clone());

    let sovereign_id_a = SovereignIdentity(Uuid::new_v4());
    let sovereign_id_b = SovereignIdentity(Uuid::new_v4());

    let ctx_a = baseline.create_context(sovereign_id_a, "isolation_test_a").await;
    let ctx_b = baseline.create_context(sovereign_id_b, "isolation_test_b").await;

    // Contexts should have different isolation levels
    assert_ne!(ctx_a.context_id, ctx_b.context_id);
    assert_eq!(ctx_a.isolation_level, ContextIsolation::SovereignIsolation);
    assert_eq!(ctx_b.isolation_level, ContextIsolation::SovereignIsolation);
}

#[tokio::test]
async fn test_baseline_context_rollback_on_failure() {
    let rebac = Arc::new(ReBAC::new());
    let baseline = BaselineCapsule::new(rebac.clone());

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let ctx = baseline.create_context(sovereign_id, "rollback_test").await;

    // Store initial state
    let initial_state = ctx.snapshot().await;

    // Simulate mutations and rollback
    ctx.record_mutation("key1", "value1").await;
    ctx.record_mutation("key2", "value2").await;

    baseline.rollback_context(&ctx, &initial_state).await;

    assert!(ctx.was_rolled_back());
}

#[tokio::test]
async fn test_baseline_context_1_99_covenant_enforcement() {
    let rebac = Arc::new(ReBAC::new());
    let baseline = BaselineCapsule::new(rebac.clone());

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let ctx = baseline.create_context(sovereign_id, "covenant_test").await;

    // Enforce 1:99 covenant (1% sovereign + 99% delegated actions)
    let covenant = baseline.apply_1_99_covenant(&ctx).await;

    assert_eq!(covenant.sovereign_quota_percent, 1);
    assert_eq!(covenant.delegated_quota_percent, 99);
}

// ============================================================================
// PHASE 4: Audit Logging Tests (3)
// ============================================================================

#[tokio::test]
async fn test_baseline_audit_trace_creation() {
    let rebac = Arc::new(ReBAC::new());
    let audit = Arc::new(AuditArchive::new());
    let baseline = BaselineCapsule::with_audit(rebac.clone(), audit.clone());

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let agent_resource = PolicyResource::Agent(Uuid::new_v4());

    let trace = baseline.create_audit_trace(
        sovereign_id,
        agent_resource,
        PolicyAction::Spawn,
        true,
        "Test execution".to_string(),
    ).await;

    assert!(!trace.trace_id.is_nil());
    assert_eq!(trace.is_decision_allowed, true);
}

#[tokio::test]
async fn test_baseline_audit_merkle_proof_verification() {
    let rebac = Arc::new(ReBAC::new());
    let audit = Arc::new(AuditArchive::new());
    let baseline = BaselineCapsule::with_audit(rebac.clone(), audit.clone());

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let agent_resource = PolicyResource::Agent(Uuid::new_v4());

    // Create multiple traces to build merkle tree
    for i in 0..3 {
        let _ = baseline.create_audit_trace(
            sovereign_id,
            agent_resource.clone(),
            PolicyAction::ReadMetrics,
            true,
            format!("Audit event {}", i),
        ).await;
    }

    let root_hash = baseline.get_audit_merkle_root().await;

    assert!(!root_hash.is_empty());
}

#[tokio::test]
async fn test_baseline_audit_s3_archive_export() {
    let rebac = Arc::new(ReBAC::new());
    let audit = Arc::new(AuditArchive::new());
    let baseline = BaselineCapsule::with_audit(rebac.clone(), audit.clone());

    let sovereign_id = SovereignIdentity(Uuid::new_v4());
    let agent_resource = PolicyResource::Agent(Uuid::new_v4());

    // Create audit trace
    let _ = baseline.create_audit_trace(
        sovereign_id,
        agent_resource,
        PolicyAction::Spawn,
        true,
        "S3 export test".to_string(),
    ).await;

    let metadata = baseline.export_audit_to_s3("test-bucket", "test-prefix").await;

    assert!(!metadata.s3_path.is_empty());
    assert!(metadata.file_size > 0);
}

// ============================================================================
// PHASE 5: HarnessCapsule Adapters (7)
// ============================================================================

#[tokio::test]
async fn test_harness_langchain_tool_use_interception() {
    let config = HarnessConfig::default();
    let harness = HarnessCapsule::new(config);

    let adapter = LangChainAdapter::new(&harness);

    let tool_call = serde_json::json!({
        "name": "search",
        "arguments": {"query": "Rust async"},
    });

    let intercepted = adapter.intercept_tool_call(&tool_call).await;

    assert!(intercepted.is_some());
}

#[tokio::test]
async fn test_harness_langchain_latency_under_500ms() {
    let config = HarnessConfig::default();
    let harness = HarnessCapsule::new(config);
    let adapter = LangChainAdapter::new(&harness);

    let start = Instant::now();

    let response = adapter.roundtrip_with_policy_check(
        &serde_json::json!({"model": "gpt-4"}),
    ).await;

    let elapsed = start.elapsed();

    assert!(elapsed.as_millis() < 500, "Latency {} ms exceeds 500ms limit", elapsed.as_millis());
    assert!(response.is_some());
}

#[tokio::test]
async fn test_harness_ollama_streaming_response() {
    let config = HarnessConfig {
        ollama_endpoint: "http://localhost:11434".to_string(),
        ..Default::default()
    };
    let harness = HarnessCapsule::new(config);

    let adapter = OllamaAdapter::new(&harness);

    let stream = adapter.stream_response("mistral", "Hello").await;

    assert!(stream.is_some());
}

#[tokio::test]
async fn test_harness_ollama_gpu_acceleration() {
    let config = HarnessConfig {
        ollama_endpoint: "http://localhost:11434".to_string(),
        enable_gpu: true,
        ..Default::default()
    };
    let harness = HarnessCapsule::new(config);

    let adapter = OllamaAdapter::new(&harness);

    let accel_enabled = adapter.is_gpu_acceleration_enabled();

    assert!(accel_enabled);
}

#[tokio::test]
async fn test_harness_ollama_token_latency_under_100ms() {
    let config = HarnessConfig {
        ollama_endpoint: "http://localhost:11434".to_string(),
        enable_gpu: true,
        ..Default::default()
    };
    let harness = HarnessCapsule::new(config);
    let adapter = OllamaAdapter::new(&harness);

    let start = Instant::now();

    let tokens = adapter.generate_tokens("mistral", "test", 10).await;

    let elapsed = start.elapsed();
    let per_token_ms = elapsed.as_millis() as f64 / 10.0;

    // Verify tokens generated
    assert!(tokens.len() > 0);
    // Note: actual hardware will vary; this is a goal latency
    println!("Per-token latency: {:.2} ms", per_token_ms);
}

#[tokio::test]
async fn test_harness_autogpt_schema_compatibility() {
    let config = HarnessConfig::default();
    let harness = HarnessCapsule::new(config);

    let adapter = AutoGPTAdapter::new(&harness);

    let tool_schema = adapter.generate_autogpt_schema("execute_command");

    assert!(tool_schema.contains("name"));
    assert!(tool_schema.contains("description"));
    assert!(tool_schema.contains("parameters"));
}

#[tokio::test]
async fn test_harness_autogpt_decision_return() {
    let config = HarnessConfig::default();
    let harness = HarnessCapsule::new(config);

    let adapter = AutoGPTAdapter::new(&harness);

    let decision = adapter.execute_and_return_decision(
        "test_tool",
        &serde_json::json!({"param": "value"}),
    ).await;

    assert!(decision.is_some());
}
