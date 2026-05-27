# PRAGUE POC — Phase 1 (Weeks 1–3) Developer Directives

**Status:** Hardware authorization complete. Cognitive Plane sealed (31/31 tests). Physical deployment sequence initialized.

**Phases at a Glance:**
- **Phase 1 (Weeks 1–3):** Hardware provisioning + parallel worktree orchestration (this document)
- **Phase 2 (Weeks 4–6):** Rapid-MLX cluster live + Chaos Petri Quarantine activation
- **Phase 3 (Weeks 7–9):** AP2 Economic Substrate prototype + offline document intelligence
- **Phase 4 (Weeks 10–12):** Investor narrative finalization (Deck A: sovereignty, Deck B: revenue)

---

## Phase 1 Sprint Goals

| Week | Deliverable | Owner | Gate |
|------|-------------|-------|------|
| **1–2** | 5× Mac Studio Ultra flashed with Rapid-MLX; 10Gbps local network live; HPE rack deployed | Ops | Hardware ready for software |
| **3** | 3–5 parallel git worktrees created; AP2 Mandates integration tested offline | Dev | Agents can safely commit in parallel |

---

## 1. Parallel Worktree Orchestration (Safe Concurrent Development)

### Rule 1: File-Orthogonal Task Design

When spawning 3–5 parallel agents in git worktrees:
- **Agent A (Authentication):** Modifies only `crates/siss-gatekeeper/` + auth symbols in `siss-agent-shell/`
- **Agent B (Inference):** Modifies only `crates/siss-agent-shell/src/rapid_mlx_integration.rs` + related config
- **Agent C (Knowledge Graph):** Modifies only `crates/siss-sovereign-kg/` + cluster/impact APIs
- **Agent D (Mandates):** Modifies only `crates/siss-ap2-enforcer/` + AP2 integration points
- **Agent E (Integration):** Modifies only `crates/siss-capsule-commit/src/orchestration/`

**No overlap.** Zero merge conflicts by design.

### Rule 2: CapsuleCommitActor Gateway (Mandatory Before Merge)

Every parallel agent generates a `CommitmentCapsule` before pushing. The `CapsuleCommitActor` enforces:

1. **Capsule Hash Verification:** SHA256(git_diff + sorted_symbols) must match signed hash
2. **Cluster Intersection Detection:**
   - Level 1: `capsule.cluster_tags ∩ pending_capsule.cluster_tags ≠ ∅` → HALT for φ+ review
   - Level 2: `capsule.affected_symbols ∩ pending_capsule.affected_symbols ≠ ∅` → HALT for φ+ review
3. **φ+ Eval Court Arbitration:**
   - Both Safe → approve oldest-first (by `created_at`)
   - Safe + Unsafe → reject unsafe, approve safe
   - Both Unsafe → fail-closed (reject both)

**Workflow:**
```
Agent A generates capsule → CapsuleCommitActor.ingest_capsule()
  ├─ Hash verified? No → reject (ActorError::InvalidHash)
  ├─ Cluster/symbol intersection? Yes → EvalCourt.evaluate() on both
  │   ├─ φ+ votes Safe/Safe → approve oldest-first
  │   ├─ φ+ votes Safe/Unsafe → reject unsafe
  │   └─ φ+ votes Unsafe/Unsafe → reject both (FAIL-CLOSED)
  └─ No intersection? → approve immediately
```

### Rule 3: Impact Analysis Before Edit (GitNexus)

Before any agent modifies a symbol:
```bash
gitnexus impact {symbol_name} --direction upstream
```

If result contains HIGH or CRITICAL:
- Agent must escalate to Eval Court for pre-approval
- Cannot proceed without φ+ vote (Safe)
- Prevents silent breakage of downstream callers

### Rule 4: Audit Every Mandate

Each cloud burst or high-risk operation requires:
```rust
let mandate_id = ap2_engine.create_intent_mandate(
    agent_id,
    "cloud_burst_hypothesis_generation",
    ResourceType::CloudBurst,
    estimated_cost: 500.0,     // USD
    spending_limit: 600.0,     // 20% margin
    authorized_by: "human@example.com",
)?;
```

- **80% threshold:** System alerts when spent >= $480
- **100% hard limit:** System aborts if spent >= $600 (fail-closed)
- **Audit log:** All events recorded immutably (SHA256 chaining)

---

## 2. AP2 Mandates Integration (Cost Control)

### Offline PoC (Week 3)

No cloud calls. Test the full mandate lifecycle locally:

```rust
// Week 3 test script: test_ap2_offline_scenarios()

#[test]
fn test_offline_ap2_mandate_flow() {
    let mut engine = AP2MandateEngine::new();
    
    // Agent requests inference burst (estimated $100, limit $200)
    let mandate = engine.create_intent_mandate(
        agent_id: Uuid::new_v4(),
        intent: "night_cycle_hypothesis_generation",
        resource_type: ResourceType::CloudBurst,
        estimated_cost: 100.0,
        spending_limit: 200.0,
        authorized_by: "ceo@sovereignai.eu"
    ).unwrap();
    
    // Human authorizes
    engine.authorize_mandate(mandate).ok();
    
    // First payment: $75 (within limit)
    assert!(engine.process_payment(mandate, 75.0).is_ok());
    
    // Second payment: $75 (accumulates to $150; triggers 80% warning)
    let payment_2 = engine.process_payment(mandate, 75.0).unwrap();
    
    // Check audit log
    let audit = engine.audit_log();
    assert!(audit.iter().any(|e| 
        e.event_type == AuditEventType::ThresholdWarning
    ));
    
    // Third payment: $60 (would exceed $200 limit) → FAIL-CLOSED
    assert!(engine.process_payment(mandate, 60.0).is_err());
    
    // Verify immutable proof chain
    let (_, guard) = engine.get_mandate_status(mandate).unwrap();
    assert_eq!(guard.accumulated_cost_usd, 150.0);
}
```

**Test matrix (10 scenarios):**
1. Create mandate with limit >= estimate ✓
2. Reject mandate with limit < estimate ✓
3. Authorize and process payment within limit ✓
4. Reject payment exceeding limit ✓
5. Accumulate multiple payments up to threshold warning ✓
6. Block payment at hard limit ✓
7. Audit log captures all events ✓
8. Multiple mandates tracked independently ✓
9. Revoke active mandate ✓
10. Cryptographic proof chain verified ✓

---

## 3. Rapid-MLX Local Inference (0.08s TTFT)

### Hardware Target (Week 1–2)

| Node | Spec | Purpose |
|------|------|---------|
| **Mac Studio Ultra #1** | 128GB unified memory, M4 Max GPU | Primary Rapid-MLX inference |
| **Mac Studio Ultra #2–5** | Same | Failover + horizontal scaling |

### Integration Checklist (Week 2)

- [ ] Flash 5 nodes with `RapidMLXEngine::new(default_config())`
- [ ] Load Qwen 3.5-4B (Q4 quantization) into each node's VRAM
- [ ] Test fresh inference: `infer_fresh()` → 150 tokens, <100ms latency
- [ ] Test cached prompt: `infer_with_cached_prompt()` → 128 tokens from cache, 0.08ms TTFT
- [ ] Test snapshot recovery: `infer_with_snapshot()` → resume from DeltaNet state, 0.1ms recovery
- [ ] Test tool calling: 100% of tool definitions → ToolCall structs with confidence scores
- [ ] Verify metrics: `tokens_per_second` > 0 for all inference paths

### Operational Protocol

Every agent inference request:
```rust
let response = engine.infer(InferenceRequest {
    request_id: Uuid::new_v4(),
    model_config: RapidMLXConfig {
        model_name: "Qwen3.5-4B".to_string(),
        quantization: Quantization::Q4,
        context_window: 4096,
        max_tokens: 512,
        temperature: 0.7,
        top_p: 0.9,
    },
    prompt: agent_prompt,
    system_prompt: Some("You are a sovereign code assistant...".to_string()),
    tools: vec![/* available tools for this context */],
    use_cached_prompt: false,
    resume_from_snapshot: None,
})?;

// Snapshots enable stateful inference without re-encoding context
if let Some(snapshot_id) = response.snapshot_created {
    // Next inference can resume from this snapshot (0.1ms recovery)
    // Enables long conversations with minimal recomputation
}
```

---

## 4. Phase 1 Test Harness

Run this before end of Week 3:

```bash
# All Cognitive Plane tests must pass
cargo test -p siss-capsule-commit --lib -q
# → 10/10 passing (CapsuleCommitActor + intersection detection)

cargo test -p siss-sovereign-kg --lib -q
# → 8/8 passing (impact chains, cluster detection)

cargo test -p siss-ap2-enforcer --lib -q
# → 6/6 passing (mandate lifecycle, cost control)

cargo test -p siss-agent-shell --lib rapid_mlx_integration -q
# → 6/6 passing (inference paths, snapshots, tool calling)

# Full workspace
cargo test --lib -q
# → ALL PASSING (target: 30/30)

# Type checking
cargo check -p siss-capsule-commit
cargo check -p siss-sovereign-kg
cargo check -p siss-ap2-enforcer
cargo check -p siss-agent-shell
# → 0 errors, 0 warnings
```

---

## 5. Week 3 Deliverable: Offline PoC Demo

Demonstrate (to investor or internal stakeholders):

1. **CapsuleCommitActor in action:**
   - Two agents generate conflicting capsules (same cluster_tag)
   - System halts both
   - φ+ Eval Court votes (both safe → approve oldest)
   - Oldest commits, second waits for second attempt

2. **AP2 Mandates in action:**
   - Agent requests $500 mandate
   - Makes three payments: $200, $200, $150 (exceeds $500)
   - Third payment blocked → audit log shows HardLimitExceeded
   - Human can increase limit + re-sign

3. **Rapid-MLX inference in action:**
   - 5 nodes respond to query simultaneously
   - Each generates response in <100ms (cached)
   - Tool calls execute (e.g., "create_test_file", "run_cargo_test")
   - Snapshot created for next conversation turn

---

## 6. GitNexus Workflow for Phase 1

Before any agent commits:

1. **Run impact analysis:**
   ```bash
   gitnexus impact {primary_symbol} --direction upstream --depth 3
   ```
   
2. **Check blast radius:**
   - `caller_count` > 10? → requires φ+ pre-approval
   - `risk_level: Critical`? → requires φ+ pre-approval
   - Confidence < 0.80? → analysis blocked (retry with more context)

3. **Generate capsule:**
   ```rust
   let capsule = CommitmentCapsule {
       capsule_id: Uuid::new_v4(),
       agent_id: agent.id(),
       affected_symbols: vec!["infer", "process_payment", "create_mandate"],
       target_files: vec!["src/rapid_mlx_integration.rs", "src/mandates.rs"],
       git_diff: git.diff_staged(),
       cluster_tags: vec!["inference-cluster", "mandate-cluster"],
       created_at: Utc::now().timestamp() as u64,
       capsule_hash: sha256(&format!("{:?}{:?}", git_diff, affected_symbols)),
   };
   ```

4. **Submit to CapsuleCommitActor:**
   ```rust
   match actor.ingest_capsule(capsule)? {
       MergeDecision::Approved { entry } => {
           git.commit_and_push(&entry)?;
           println!("✓ Capsule approved, committed to main");
       }
       MergeDecision::HaltForPhiPlus { intersection } => {
           println!("⚠ Halt for φ+ review: intersection in clusters {:?}", 
               intersection.intersecting_clusters);
           // Escalate to human for evaluation
       }
       MergeDecision::Rejected { reason } => {
           eprintln!("✗ Capsule rejected: {}", reason);
           // Retry with reduced scope or design change
       }
   }
   ```

---

## 7. Success Criteria (Week 3 Completion)

| Criterion | Target | Status |
|-----------|--------|--------|
| All 30 Cognitive Plane tests pass | 30/30 | TBD |
| 5 parallel git worktrees operational | 5/5 | TBD |
| AP2 offline PoC demo runs without errors | 100% success | TBD |
| Rapid-MLX inference on all 5 nodes: <100ms TTFT (cached) | ✓ on all | TBD |
| CapsuleCommitActor gates 2+ concurrent commits safely | ✓ | TBD |
| Zero merge conflicts across agent worktrees | 0 conflicts | TBD |

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Agent A and B both modify symbol X | File-orthogonal task design (Rule 1) eliminates this |
| Capsule hash tampered in transit | Hash verification (Rule 2) fails-closed if mismatch |
| Cost overruns on cloud burst | AP2 hard limits (Rule 4) block excess automatically |
| Rapid-MLX inference on node fails | 4 failover nodes + local replication cover downtime |
| φ+ Eval Court deadlocks | Timeout: if no vote in 5min, conservative (Unsafe) default |

---

## 9. Handoff to Phase 2

End of Week 3:
- Hardware validated (5 nodes, 10Gbps networking, HPE rack)
- Cognitive Plane fully operational (CapsuleCommitActor + AP2 + Rapid-MLX)
- Offline PoC demo ready for investors
- Parallel worktree orchestration proven safe

**Phase 2 Entry Gate:** All tests passing + demo successful + hardware sign-off.

---

**Prepared by:** Sovereign Architect  
**Status:** Ready for execution  
**Next Review:** End of Week 2 (hardware delivery checkpoint)
