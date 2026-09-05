# Agent Roles & File Ownership (Phase 1)

**Parallel Worktree Orchestration — File-Orthogonal Execution**

Each agent owns an isolated subsystem. **Zero file overlap = zero merge conflicts.**

---

## Agent A: Authentication & Access Control

**Worktree:** `.claude/worktrees/agent-auth`  
**Branch:** `auth-cluster`  
**Owner Files:**
- `crates/siss-gatekeeper/**` (complete crate)
- `crates/siss-agent-shell/src/hooks/auth_*.rs` (auth-specific hooks only)

**Blocked From:** All other crates and files.

**Week 1–2 Tasks:**
1. Verify `siss-gatekeeper` compiles with new CapsuleCommitActor integration
2. Add `generate_commitment_capsule()` function:
   ```rust
   pub fn generate_commitment_capsule(&self, git_diff: String) -> CommitmentCapsule {
       CommitmentCapsule {
           capsule_id: Uuid::new_v4(),
           agent_id: AGENT_A_ID,
           affected_symbols: vec!["enforce_access_policy", "verify_credentials"],
           target_files: vec!["crates/siss-gatekeeper/src/lib.rs"],
           git_diff,
           cluster_tags: vec!["access-control-cluster"],
           created_at: Utc::now().timestamp() as u64,
           capsule_hash: Self::compute_capsule_hash(&git_diff, &affected_symbols),
       }
   }
   ```
3. Integration test: capsule hash verification (should match SHA256)

**CapsuleCommitActor Workflow:**
```
1. Stage changes in auth-cluster worktree
2. Call generate_commitment_capsule(git_diff)
3. Submit to CapsuleCommitActor::ingest_capsule()
4. If approved: git push (capsule signed in commit message)
5. If halt: wait for φ+ Eval Court decision
6. If rejected: revert and redesign
```

---

## Agent B: Inference Engine (Rapid-MLX)

**Worktree:** `.claude/worktrees/agent-inference`  
**Branch:** `inference-cluster`  
**Owner Files:**
- `crates/siss-agent-shell/src/rapid_mlx_integration.rs` (complete)
- `crates/siss-agent-shell/src/lib.rs` (Rapid-MLX re-exports only)

**Blocked From:** All other files in siss-agent-shell; all other crates.

**Week 1–2 Tasks:**
1. Hardware integration: verify RapidMLXEngine runs on target Mac Studio Ultra nodes
2. Benchmarking:
   ```rust
   #[test]
   fn test_rapid_mlx_ttft_on_mac_studio() {
       let engine = RapidMLXEngine::new(default_config());
       let request = InferenceRequest { /* ... */ };
       
       let start = Instant::now();
       let response = engine.infer(request).unwrap();
       let elapsed = start.elapsed();
       
       assert!(response.time_to_first_token_ms <= 0.1);  // < 0.1ms for cached
       assert!(elapsed.as_millis() < 100);               // < 100ms total
   }
   ```
3. Add `generate_commitment_capsule()`:
   ```rust
   pub fn generate_commitment_capsule(&self, git_diff: String) -> CommitmentCapsule {
       CommitmentCapsule {
           capsule_id: Uuid::new_v4(),
           agent_id: AGENT_B_ID,
           affected_symbols: vec!["infer", "infer_fresh", "infer_with_snapshot"],
           target_files: vec!["crates/siss-agent-shell/src/rapid_mlx_integration.rs"],
           git_diff,
           cluster_tags: vec!["inference-cluster"],
           created_at: Utc::now().timestamp() as u64,
           capsule_hash: Self::compute_capsule_hash(&git_diff, &affected_symbols),
       }
   }
   ```

---

## Agent C: Knowledge Graph & Impact Analysis

**Worktree:** `.claude/worktrees/agent-knowledge-graph`  
**Branch:** `kg-cluster`  
**Owner Files:**
- `crates/siss-sovereign-kg/**` (complete crate)

**Blocked From:** All other crates.

**Week 1–2 Tasks:**
1. Verify all 8 unit tests pass on fresh worktree
2. Add `generate_commitment_capsule()`:
   ```rust
   pub fn generate_commitment_capsule(&self, git_diff: String) -> CommitmentCapsule {
       CommitmentCapsule {
           capsule_id: Uuid::new_v4(),
           agent_id: AGENT_C_ID,
           affected_symbols: vec!["query_impact", "detect_changes", "cluster_intersection"],
           target_files: vec!["crates/siss-sovereign-kg/src/lib.rs"],
           git_diff,
           cluster_tags: vec!["knowledge-graph-cluster"],
           created_at: Utc::now().timestamp() as u64,
           capsule_hash: Self::compute_capsule_hash(&git_diff, &affected_symbols),
       }
   }
   ```
3. GitNexus integration readiness: `gitnexus_context({name: "SovereignKG"})` must return all symbols

---

## Agent D: AP2 Mandates & Cost Control

**Worktree:** `.claude/worktrees/agent-mandates`  
**Branch:** `mandates-cluster`  
**Owner Files:**
- `crates/siss-ap2-enforcer/**` (complete crate)

**Blocked From:** All other crates.

**Week 1–2 Tasks:**
1. Verify all 6 unit tests pass on fresh worktree
2. Add `generate_commitment_capsule()`:
   ```rust
   pub fn generate_commitment_capsule(&self, git_diff: String) -> CommitmentCapsule {
       CommitmentCapsule {
           capsule_id: Uuid::new_v4(),
           agent_id: AGENT_D_ID,
           affected_symbols: vec!["process_payment", "authorize_mandate", "create_intent_mandate"],
           target_files: vec!["crates/siss-ap2-enforcer/src/mandates.rs"],
           git_diff,
           cluster_tags: vec!["mandates-cluster"],
           created_at: Utc::now().timestamp() as u64,
           capsule_hash: Self::compute_capsule_hash(&git_diff, &affected_symbols),
       }
   }
   ```
3. Hardening: ensure all cryptographic proof chains are immutable (no modifications after Executed status)

---

## Agent E: Orchestration & Merge Coordination

**Worktree:** `.claude/worktrees/agent-integration`  
**Branch:** `integration-cluster`  
**Owner Files:**
- `crates/siss-capsule-commit/src/orchestration/**` (complete)
- `crates/siss-capsule-commit/src/lib.rs` (re-exports only)

**Blocked From:** Base CapsuleCommitActor (read-only); all other crates.

**Week 1–2 Tasks:**
1. Verify all 10 unit tests pass on fresh worktree
2. Add orchestration glue: `CapsuleOrchestrator` struct:
   ```rust
   pub struct CapsuleOrchestrator {
       actors: HashMap<AgentId, GitNexusCapsuleCommitActor>,
       eval_court: EvalCourt,
       pending_capsules: Vec<CommitmentCapsule>,
   }
   
   impl CapsuleOrchestrator {
       pub fn ingest_all(&mut self, capsules: Vec<CommitmentCapsule>) -> Vec<MergeDecision> {
           // Ingest all capsules, detect intersections, return decisions
       }
       
       pub fn execute_decisions(&mut self, decisions: Vec<MergeDecision>) -> Result<(), String> {
           // Apply approved decisions to main branch (git merge)
       }
   }
   ```
3. Add `generate_commitment_capsule()` for orchestration changes itself

---

## Phase 1 Constraint Rules (All Agents)

### Rule 1: Impact Analysis Before Commit

Before staging changes:
```bash
cd .claude/worktrees/agent-{X}
gitnexus impact {symbol_name} --direction upstream --depth 3
# If HIGH/CRITICAL: escalate to Eval Court
# If confidence < 0.80: retry with more context
```

### Rule 2: Capsule Hash Must Match

```rust
let expected = SHA256(git_diff + sorted(affected_symbols));
assert_eq!(capsule.capsule_hash, expected);
// Failure → ActorError::InvalidHash → reject
```

### Rule 3: No Cross-Crate Imports (Except siss-agent-shell as Base)

- Agent A cannot import from siss-sovereign-kg
- Agent B cannot import from siss-ap2-enforcer
- Agent C cannot import from siss-gatekeeper
- Agent D cannot import from siss-capsule-commit
- Agent E can import all (but read-only from others)

### Rule 4: Cluster Tag Discipline

Each agent's capsules use ONLY its assigned cluster tag:
- Agent A: `"access-control-cluster"` only
- Agent B: `"inference-cluster"` only
- Agent C: `"knowledge-graph-cluster"` only
- Agent D: `"mandates-cluster"` only
- Agent E: `"orchestration-cluster"` only

If your changes affect multiple clusters, **split into multiple capsules** (one per cluster).

### Rule 5: Atomic Commits

Each capsule = atomic commit (one logical change). No bundling unrelated work.

Bad:
```
git commit "Add inference + fix gatekeeper bug + refactor AP2"
```

Good:
```
# Capsule 1
git commit "Add inference hot path optimization"
# Capsule 2
git commit "Add AP2 threshold warning logic"
```

---

## Week 3 Offline PoC Integration Test

All 5 agents submit capsules simultaneously. System detects:
- ✓ No cluster tag intersection (all different)
- ✓ No symbol overlap (different affected_symbols)
- ✓ All hashes valid
- ✓ φ+ votes all Safe
- ✓ All committed to main in age order

**Script:**
```bash
#!/bin/bash
cd /Users/andriileukhin/Documents/SovereignNexus

# Stage changes in each worktree
for agent in auth inference knowledge-graph mandates integration; do
    cd .claude/worktrees/agent-${agent}
    cargo test --lib -q
    git add -A
done

# Generate capsules and submit to CapsuleCommitActor
# (implementation in siss-capsule-commit/examples/offline_poc.rs)
cargo run --example offline_poc

# Expected output:
# Agent A capsule approved ✓
# Agent B capsule approved ✓
# Agent C capsule approved ✓
# Agent D capsule approved ✓
# Agent E capsule approved ✓
# All 5 capsules merged to main in age order
```

---

**Sign-Off:** Agent roles finalized. Ready for Week 1–2 hardware integration work.
