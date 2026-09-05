# SMAOS Hybrid QA Pipeline Design
**Phase 2-3 Bridge Document**  
**Date:** Sep 1, 2026  
**Status:** STRATEGIC ARCHITECTURE (non-code)

---

## EXECUTIVE SUMMARY

SMAOS requires a **cryptographically-backed QA pipeline** that runs all 8 layers (L1-L8) in parallel across 4 agents, prevents test gaming via proof attestation, and generates signed readiness reports. This document specifies the logical gate ordering, integration points, failure modes, Merkle tree structure, and deployment architecture.

**Key Innovation:** Triangular verification (code + proof + behavioral) replaces traditional binary pass/fail. Cryptographic attestation prevents retroactive test manipulation.

---

## PART A: LOGICAL GATE ORDERING

### Phase Diagram: Sequential Gates → Parallel Verification → Final Attestation

```
┌────────────────────────────────────────────────────────────────────┐
│                   GATE 0: PRE-FLIGHT VALIDATION                    │
│  (Deterministic checks: no random state, no flaky tests, clean CI)  │
│  ├─ Git state: uncommitted changes = FAIL                          │
│  ├─ Dependency lock: Cargo.lock matches mainline = FAIL            │
│  ├─ Test cache clear: no .pytest_cache or target/debug artifacts   │
│  └─ Duration baseline: measure test_suite_duration on clean build  │
│     ↓ Generate nonce: random_seed = SHA256(timestamp + repo_hash)  │
└────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────┬──────────────┬──────────────┬──────────────┐
│   AGENT 1   │   AGENT 2    │   AGENT 3    │   AGENT 4    │
│   (L1-L2)   │   (L3-L4)    │   (L5-L6)    │   (L7-L8)    │
│  Reasoning  │ Enforcement  │  Orchestration  │ Proof/RAGAS  │
└─────────────┴──────────────┴──────────────┴──────────────┘
  │                │                │                │
  ├─ GATE 1A      ├─ GATE 1B      ├─ GATE 1C      ├─ GATE 1D
  │ (Unit)        │ (Unit)        │ (Unit)        │ (Unit)
  │ 3-5s          │ 5-7s          │ 6-8s          │ 4-6s
  │               │               │               │
  │ L1: routing   │ L3: gates     │ L5: MCP       │ L7: RAGAS
  │ L2: pgvector  │ L4: orchest   │ L6: infra     │ L8: proof
  │               │               │               │
  ├─ GATE 2A      ├─ GATE 2B      ├─ GATE 2C      ├─ GATE 2D
  │ (Behavioral)  │ (Behavioral)  │ (Behavioral)  │ (Behavioral)
  │ 30-60s        │ 30-60s        │ 30-60s        │ 20-40s
  │               │               │               │
  │ Memory <3GB   │ Latency <50ms │ RPS >100      │ 87%+ acc
  │ No panics     │ No timeouts   │ No hangs      │ No regressions
  │               │               │               │
  └─ GATE 3A      ├─ GATE 3B      ├─ GATE 3C      ├─ GATE 3D
    (Proof)       │ (Proof)       │ (Proof)       │ (Proof)
    5s            │ 5s            │ 5s            │ 5s
    Ed25519 sig   │ Ed25519 sig   │ Ed25519 sig   │ Ed25519 sig
    AP2 hash      │ AP2 hash      │ AP2 hash      │ AP2 hash
    Nonce bind    │ Nonce bind    │ Nonce bind    │ Nonce bind
    ↓             │ ↓             │ ↓             │ ↓
    [Agent result] [Agent result] [Agent result] [Agent result]
    + proof trail  + proof trail  + proof trail  + proof trail
                  ↓               │               │
                  └───────────────┼───────────────┘
                                  ↓
          ┌─────────────────────────────────────────┐
          │   GATE 4: CROSS-AGENT TRIANGULATION    │
          │  (Verification phase: 60-90s)          │
          │  ├─ Consensus check: all 4 agents      │
          │  │  agree on baseline metrics?         │
          │  ├─ Proof validation: all Merkle roots │
          │  │  match expected commitment?         │
          │  ├─ Latency bound: Gate 1+2+3 < 4min  │
          │  ├─ Determinism: Run 2x with same      │
          │  │  nonce → same results?              │
          │  └─ Adversarial breaks: Try 3 attacks  │
          │     (timeout injection, timeout break) │
          └─────────────────────────────────────────┘
                           ↓
          ┌─────────────────────────────────────────┐
          │  GATE 5: FINAL ATTESTATION (30s)       │
          │  ├─ Merkle tree of all results         │
          │  ├─ Root hash computed                 │
          │  ├─ Ed25519 signature with KMS key    │
          │  ├─ Timestamp binding                  │
          │  └─ AP2 ledger entry created           │
          └─────────────────────────────────────────┘
                           ↓
          ┌─────────────────────────────────────────┐
          │  OUTPUT: Signed Readiness Report       │
          │  ├─ JSON: test_results.json            │
          │  ├─ Signature: results.sig             │
          │  ├─ Merkle proof: mp.json              │
          │  └─ Ledger entry: ap2_entry.json       │
          └─────────────────────────────────────────┘
```

### Parallel Gate Timing

**Walls Clock Time: 2m 30s - 3m 30s total**
- Gate 0: 5s (serial, all agents blocked)
- Gate 1A/1B/1C/1D: ~7s (parallel, max agent time)
- Gate 2A/2B/2C/2D: ~60s (parallel)
- Gate 3A/3B/3C/3D: ~5s (parallel, proof signing)
- Gate 4 (triangulation): ~60-90s (serial, requires all Gate 3 outputs)
- Gate 5 (attestation): ~30s (serial, final Merkle + signing)

**Total:** 2:45 (optimized) to 3:30 (worst case with retries)

---

## PART B: INTEGRATION POINTS

### B.1 Where Each Research Pattern Fits

| Gate | Pattern | Integration | Library |
|------|---------|-----------|---------|
| **0** | Cargo determinism | Clean build, lock versions | `cargo-tree`, `cargo-audit` |
| **1A-1D** | Unit testing | `cargo test` for L1-L8 | pytest (Python), `cargo test` (Rust) |
| **2A-2D** | Behavioral: memory/latency | profiling hooks in code | `perf`, `valgrind`, custom timers |
| **2A-2D** | Behavioral: chaos injection | timeout/error injection | custom agent harness |
| **3A-3D** | Proof: Ed25519 signing | agentacct module per agent | `ed25519-dalek` crate |
| **3A-3D** | Proof: AP2 ledger entry | append result hash to chain | custom AP2 client |
| **4** | Triangular: consensus | all 4 agents publish results | MCP consensus protocol |
| **4** | Triangular: Merkle check | verify all proofs | `sha2` crate |
| **4** | Adversarial breaks | fuzz, timeout, latency attacks | custom test harness |
| **5** | Final attestation | sign Merkle root + ledger | Ed25519 + KMS integration |

### B.2 Agent Communication Flow

```
Each Agent writes to shared queue (in-memory or Redis):
┌──────────────┐
│   Agent 1    │  GATE 1A output → {tests_passed: 27, passed_count: 27}
│   (L1-L2)    │  GATE 2A output → {mem_peak_mb: 1250, latency_p99: 23ms}
│              │  GATE 3A output → {sig: "ed25519...", ap2_hash: "abc123"}
└──────────────┘                  ↓
                         ┌─────────────────┐
                         │ Consensus Queue │
                         │   (Redis/RAM)   │
                         └─────────────────┘
                                  ↑
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Agent 2    │  │   Agent 3    │  │   Agent 4    │
│   (L3-L4)    │  │   (L5-L6)    │  │   (L7-L8)    │
└──────────────┘  └──────────────┘  └──────────────┘

Gate 4 (Triangulation Agent) waits for all 4 agents:
  for agent in [Agent1, Agent2, Agent3, Agent4]:
    wait_for(agent.gate3_result, timeout=5m)
    verify(agent.proof)
    merge(results[agent])
```

---

## PART C: FAILURE MODES PER GATE

| Gate | Failure Mode | Detection | Recovery | Severity |
|------|--------------|-----------|----------|----------|
| **0** | Uncommitted changes on main | `git status --porcelain` returns non-empty | FAIL immediately, require clean state | CRITICAL |
| **0** | Stale Cargo.lock | Hash mismatch vs. mainline | `git checkout Cargo.lock` or FAIL | CRITICAL |
| **0** | Nonce collision | Same nonce as previous run | Reject, regenerate, retry | HIGH |
| **1A** | Unit test fails (L1 or L2) | Assertion error, panic, timeout | Report agent, log to AP2, fail gate | HIGH |
| **1B** | Unit test fails (L3 or L4) | Assertion error, enforcement logic broken | Report agent, log to AP2, fail gate | HIGH |
| **1C** | Unit test fails (L5 or L6) | MCP error, infrastructure broken | Report agent, log to AP2, fail gate | HIGH |
| **1D** | Unit test fails (L7 or L8) | RAGAS eval or proof logic broken | Report agent, log to AP2, fail gate | HIGH |
| **2A** | Memory spike (>4GB) | Peak memory in Gate 2 measurement | Retry once; if still fails, agent blacklist | MEDIUM |
| **2A** | Panic detected in logs | `panic!()` or `unwrap()` triggered | Log event, mark agent, escalate | HIGH |
| **2B** | Latency p99 >100ms | Measurement from perf timer | Retry; if >3 retries, escalate | MEDIUM |
| **2B** | Timeout during test | Test hangs >10s | Kill process, log as timeout, increment retry | MEDIUM |
| **2C** | RPS <50 (expected >100) | Throughput measurement low | Check agent health; if repeated, mark flaky | LOW |
| **2D** | RAGAS accuracy <87% | Golden set evaluation failed | Log regression; if >2% below baseline, alert | HIGH |
| **3A-3D** | Ed25519 signing fails | Signature operation returns error | Check KMS connection; retry up to 3x | HIGH |
| **3A-3D** | AP2 append fails | Ledger write timeout or rejection | Retry with exponential backoff | MEDIUM |
| **3A-3D** | Nonce mismatch | Proof nonce ≠ Gate 0 nonce | Reject proof, require Gate 3 re-run | CRITICAL |
| **4** | Agent 2 or 3 never responds | Timeout on consensus queue > 5m | Escalate, mark agent down, fail pipeline | CRITICAL |
| **4** | Merkle root mismatch | One agent's proof doesn't match others | Isolate agent, run adversarial test to diagnose | HIGH |
| **4** | Timeout attack succeeds (latency >4min) | Total time exceeds budget | Log attack, increment attack counter, escalate | HIGH |
| **5** | KMS signing fails | Key material unavailable or corrupted | Retry with fallback key; log incident | CRITICAL |
| **5** | Ledger write fails | AP2 append returns error | Retry; if persists, file ticket, use backup proof | MEDIUM |

---

## PART D: MERKLE TREE STRUCTURE FOR PROOF ATTESTATION

### Data Model: 4-Agent Proof Tree

```
                        ┌────────────────────────────┐
                        │     FINAL ROOT HASH        │
                        │ Merkle256(L0 || TimeStamp) │
                        └────────────────────────────┘
                                      │
                  ┌───────────────────┼───────────────────┐
                  │                   │                   │
         ┌────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
         │   L0: Agent     │ │   L0: Agent     │ │   L0: Agent     │
         │   Proof Hashes  │ │   Proof Hashes  │ │   Proof Hashes  │
         │ (4 leaf nodes)  │ │                 │ │                 │
         └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
                  │                   │                   │
      ┌───────────┼───────────┐       │       ┌───────────┼───────────┐
      │           │           │       │       │           │           │
   ┌──▼─┐     ┌──▼─┐     ┌──▼─┐  ┌──▼─┐  ┌──▼─┐     ┌──▼─┐     ┌──▼─┐
   │ A1 │     │ A1 │     │ A1 │  │ A2 │  │ A3 │     │ A3 │     │ A4 │
   │ L1 │     │ L2 │     │ L3 │  │ L4 │  │ L5 │     │ L6 │     │ L7 │
   └────┘     └────┘     └────┘  └────┘  └────┘     └────┘     └────┘

Agent 1 (L1-L2):    Agent 2 (L3-L4):    Agent 3 (L5-L6):    Agent 4 (L7-L8):
├─ A1_L1_hash      ├─ A2_L3_hash      ├─ A3_L5_hash      ├─ A4_L7_hash
│  Gate1A result   │  Gate1B result   │  Gate1C result   │  Gate1D result
├─ A1_L2_hash      ├─ A2_L4_hash      ├─ A3_L6_hash      ├─ A4_L8_hash
│  Gate1A result   │  Gate1B result   │  Gate1C result   │  Gate1D result
├─ A1_Behavioral   ├─ A2_Behavioral  ├─ A3_Behavioral  ├─ A4_Behavioral
│  Gate2A result   │  Gate2B result   │  Gate2C result   │  Gate2D result
└─ A1_Sig_Proof    └─ A2_Sig_Proof   └─ A3_Sig_Proof   └─ A4_Sig_Proof
   Gate3A Ed25519     Gate3B Ed25519    Gate3C Ed25519     Gate3D Ed25519
   + nonce_seed       + nonce_seed      + nonce_seed       + nonce_seed
```

### Merkle Hash Computation

**For each agent:**

```
L0 Agent Proof Hash = Merkle256(
  Unit_Hash(Gate1_results) ||
  Behavioral_Hash(Gate2_results) ||
  Ed25519_Signature(Gate3_proof) ||
  Nonce_seed
)

Where:
  Unit_Hash = SHA256(
    SHA256(L1_gate1_tests) ||
    SHA256(L2_gate1_tests) ||
    ...
  )
  
  Behavioral_Hash = SHA256(
    SHA256(L1_memory_metrics) ||
    SHA256(L2_latency_metrics) ||
    SHA256(L3_error_metrics) ||
    ...
  )
```

**Final Root (Gate 5):**

```
Root_Hash = Merkle256(
  Merkle256(Agent1_Hash, Agent2_Hash, Agent3_Hash, Agent4_Hash) ||
  Timestamp_ms ||
  Consensus_Vote (4/4 agents agree: 1 = yes, 0 = no)
)

Stored in AP2 ledger as:
{
  "type": "qa_pipeline_attestation",
  "root_hash": "abc123...",
  "timestamp": "2026-09-01T12:30:45.123Z",
  "agent_count": 4,
  "agents": ["Agent1", "Agent2", "Agent3", "Agent4"],
  "gate_0_nonce": "seed123...",
  "consensus": {"passing": 4, "total": 4},
  "signature": "ed25519_sig..."
}
```

---

## PART E: RECOMMENDED TOOL CHOICES

### E.1 Unit Testing (Gate 1)

| Platform | Tool | Role | Invocation |
|----------|------|------|-----------|
| **Rust** | `cargo test` | Run all L1-L8 tests in parallel | `cargo test --all --jobs 4` |
| **Python** | pytest + hypothesis | Test Layer properties (L3, L5) | `pytest -n auto --hypothesis-seed=$NONCE` |
| **Python** | pytest-timeout | Prevent hanging tests | `pytest --timeout=10` |
| **Shared** | `cargo-audit` | Dependency vulnerability scan | `cargo audit --deny warnings` |

### E.2 Behavioral Testing (Gate 2)

| Aspect | Tool | Role |
|--------|------|------|
| Memory profiling | `perf`, `valgrind` | Peak memory measurement |
| Latency measurement | Custom hooks in code | p50/p99 latency capture |
| Determinism | Custom harness | 2x run with same seed |
| Chaos injection | Custom agent harness | Timeout + error simulation |
| Throughput | Apache JMeter / custom | RPS measurement |

### E.3 Proof & Signing (Gate 3)

| Component | Tool | Role |
|-----------|------|------|
| Ed25519 signing | `ed25519-dalek` (Rust) | Sign proof hashes |
| Merkle trees | `sha2` crate (Rust) | Compute proof hashes |
| AP2 ledger | Custom Python client | Append proof entries |
| KMS integration | AWS KMS or HashiCorp Vault | Key material (final attestation) |
| Timestamp | `chrono` crate | Proof freshness binding |

### E.4 Triangulation & Adversarial (Gate 4)

| Function | Tool | Role |
|----------|------|------|
| Consensus protocol | Custom MCP server | Collect + validate all agent proofs |
| Merkle validation | `sha2` + custom logic | Verify proof tree structure |
| Timeout attack sim | Thread::sleep() injection | Simulate deadline stress |
| Latency attack sim | Artificial delay + measurement | Detect timing side channels |
| Behavioral divergence | Diff tool on proof sets | Identify malicious drift |

### E.5 Final Attestation (Gate 5)

| Component | Tool | Role |
|----------|------|------|
| Root hash signing | Ed25519 + KMS | Cryptographic attestation |
| Readiness report | Jinja2 template (Python) | Generate JSON + PDF |
| Signature verification | Custom verifier | Emit proof artifact |
| Ledger archival | AP2 client | Persistent proof audit trail |

---

## PART F: ASCII DEPLOYMENT ARCHITECTURE

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         SMAOS QA PIPELINE (LOCAL-FIRST)                  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     ORCHESTRATOR PROCESS                        │   │
│  │  (Single, serial: coordinating all gates and agents)           │   │
│  │                                                                 │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │ Gate 0: Pre-Flight (determinism baseline)              │  │   │
│  │  │ - git status check                                     │  │   │
│  │  │ - Cargo.lock validate                                 │  │   │
│  │  │ - Generate nonce_seed = SHA256(time || repo_hash)    │  │   │
│  │  │ - Duration baseline measurement                        │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                           ↓                                      │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │ Spawn 4 Agent Processes (PARALLEL)                     │  │   │
│  │  │                                                         │  │   │
│  │  │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │  │   │
│  │  │ │ Agent-1     │ │ Agent-2     │ │ Agent-3     │       │  │   │
│  │  │ │ (L1-L2)     │ │ (L3-L4)     │ │ (L5-L6)     │ ...  │  │   │
│  │  │ │             │ │             │ │             │       │  │   │
│  │  │ │ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │       │  │   │
│  │  │ │ │ Gate 1A │ │ │ │ Gate 1B │ │ │ │ Gate 1C │ │       │  │   │
│  │  │ │ │ (unit)  │ │ │ │ (unit)  │ │ │ │ (unit)  │ │       │  │   │
│  │  │ │ └────┬────┘ │ │ └────┬────┘ │ │ └────┬────┘ │       │  │   │
│  │  │ │      ↓      │ │      ↓      │ │      ↓      │       │  │   │
│  │  │ │ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │       │  │   │
│  │  │ │ │ Gate 2A │ │ │ │ Gate 2B │ │ │ │ Gate 2C │ │       │  │   │
│  │  │ │ │ (behav) │ │ │ │ (behav) │ │ │ │ (behav) │ │       │  │   │
│  │  │ │ └────┬────┘ │ │ └────┬────┘ │ │ └────┬────┘ │       │  │   │
│  │  │ │      ↓      │ │      ↓      │ │      ↓      │       │  │   │
│  │  │ │ ┌─────────┐ │ │ ┌─────────┐ │ │ ┌─────────┐ │       │  │   │
│  │  │ │ │ Gate 3A │ │ │ │ Gate 3B │ │ │ │ Gate 3C │ │       │  │   │
│  │  │ │ │ (proof) │ │ │ │ (proof) │ │ │ │ (proof) │ │       │  │   │
│  │  │ │ └────┬────┘ │ │ └────┬────┘ │ │ └────┬────┘ │       │  │   │
│  │  │ │      │      │ │      │      │ │      │      │       │  │   │
│  │  │ │    [result] │ │    [result] │ │    [result] │       │  │   │
│  │  │ │   + sig + A │ │   + sig + A │ │   + sig + A │       │  │   │
│  │  │ │      P2     │ │      P2     │ │      P2     │       │  │   │
│  │  │ └─────────────┘ │ └─────────────┘ │ └─────────────┘       │  │   │
│  │  │                 │                 │                 │       │  │   │
│  │  └─────────────────┼─────────────────┼─────────────────┘      │  │   │
│  │                    ↓                 ↓                         │  │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │ Consensus Queue (in-memory or Redis)                   │  │   │
│  │  │  - Agent1 result: {gate1_tests: 27, gate2_mem: 1.2GB}  │  │   │
│  │  │  - Agent2 result: {gate1_tests: 32, gate2_latency: 40} │  │   │
│  │  │  - Agent3 result: {gate1_tests: 28, gate2_rps: 150}    │  │   │
│  │  │  - Agent4 result: {gate1_tests: 50, gate2_acc: 89%}    │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                           ↓                                      │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │ Gate 4: Triangulation (SERIAL, all agents blocked)      │  │   │
│  │  │                                                         │  │   │
│  │  │ For each agent in [1, 2, 3, 4]:                       │  │   │
│  │  │   - Fetch proof from queue (wait if missing)          │  │   │
│  │  │   - Verify Ed25519 signature                          │  │   │
│  │  │   - Check Merkle root against commitment              │  │   │
│  │  │   - Measure total elapsed time (budget: 4 min)        │  │   │
│  │  │                                                         │  │   │
│  │  │ Consensus: All 4 proofs valid? → Proceed to Gate 5   │  │   │
│  │  │                                                         │  │   │
│  │  │ Adversarial Tests:                                     │  │   │
│  │  │   [1] Timeout attack: inject 30s delay, re-run gates  │  │   │
│  │  │   [2] Latency attack: measure clock jitter            │  │   │
│  │  │   [3] Proof tampering: flip one bit in Merkle root   │  │   │
│  │  │                                                         │  │   │
│  │  │ Determinism Check:                                     │  │   │
│  │  │   Run 2x with same nonce_seed, compare outputs        │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                           ↓                                      │   │
│  │  ┌──────────────────────────────────────────────────────────┐  │   │
│  │  │ Gate 5: Final Attestation (SERIAL)                     │  │   │
│  │  │                                                         │  │   │
│  │  │ 1. Compute Merkle root:                               │  │   │
│  │  │    root = Merkle256(                                  │  │   │
│  │  │      Agent1_proof_hash ||                             │  │   │
│  │  │      Agent2_proof_hash ||                             │  │   │
│  │  │      Agent3_proof_hash ||                             │  │   │
│  │  │      Agent4_proof_hash ||                             │  │   │
│  │  │      timestamp ||                                     │  │   │
│  │  │      consensus_vote                                   │  │   │
│  │  │    )                                                   │  │   │
│  │  │                                                         │  │   │
│  │  │ 2. Sign root with Ed25519 (KMS key):                 │  │   │
│  │  │    sig = Ed25519.sign(root, kms_key)                 │  │   │
│  │  │                                                         │  │   │
│  │  │ 3. Append to AP2 ledger:                              │  │   │
│  │  │    ap2_entry = {                                       │  │   │
│  │  │      "type": "qa_pipeline_attestation",               │  │   │
│  │  │      "root": root,                                     │  │   │
│  │  │      "sig": sig,                                       │  │   │
│  │  │      "timestamp": now,                                 │  │   │
│  │  │      "consensus": {passing: 4, total: 4}              │  │   │
│  │  │    }                                                    │  │   │
│  │  │                                                         │  │   │
│  │  │ 4. Generate signed readiness report:                  │  │   │
│  │  │    - JSON (test_results.json)                        │  │   │
│  │  │    - Signature (results.sig)                         │  │   │
│  │  │    - Merkle proof tree (mp.json)                     │  │   │
│  │  │    - AP2 ledger entry (ap2_entry.json)               │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ OUTPUT ARTIFACTS (All Signed & Cryptographically Verified)     │  │
│  │                                                                  │  │
│  │ .qa-artifacts/                                                  │  │
│  │ ├── test_results.json ..................... full results tree  │  │
│  │ ├── test_results.sig ...................... Ed25519 sig        │  │
│  │ ├── merkle_proof.json ..................... proof tree         │  │
│  │ ├── ap2_entry.json ........................ ledger record       │  │
│  │ ├── readiness_report.json ................. summary (signed)    │  │
│  │ ├── readiness_report.pdf .................. human-readable      │  │
│  │ └── timeline.json ......................... Gate execution log   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  TEMPORAL DURABILITY (48-Hour Recovery):                              │
│  - All Gate outputs written to disk immediately                      │
│  - AP2 ledger entries are immutable (append-only)                    │
│  - If pipeline dies: restart from last completed gate                │
│  - Merkle tree allows partial proof reconstruction                   │
│  - Nonce seed persisted to allow deterministic re-runs               │
│                                                                         │
│  LOCAL-FIRST ARCHITECTURE:                                            │
│  - No cloud dependency (KMS optional for final signing)              │
│  - All computation on local machine (CPU-bound)                      │
│  - Redis optional (in-memory queue sufficient for 4 agents)          │
│  - Fallback: file-based queue if Redis unavailable                  │
│                                                                         │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## PART G: IMPLEMENTATION PHASES

### Phase 2A: Gates 0-3 (Baseline Proof)
- **Duration:** 2 weeks
- **Scope:** Implement Gates 0-3 for single agent (L1-L2)
- **Deliverable:** Single-agent pipeline with Ed25519 signing + AP2 entry
- **Tests:** 12+ test cases for Gate 0-3 logic
- **Output:** `gate0_to_3.rs` (~400 lines)

### Phase 2B: Gate 4 (Triangulation)
- **Duration:** 1 week
- **Scope:** Consensus protocol + adversarial tests
- **Deliverable:** Merkle tree validation + 3 attack simulations
- **Tests:** 8+ adversarial test cases
- **Output:** `gate4_triangulation.rs` (~300 lines)

### Phase 2C: Gate 5 + Integration
- **Duration:** 1 week
- **Scope:** Final attestation + readiness report generation
- **Deliverable:** Signed JSON + PDF report + AP2 integration
- **Tests:** 6+ integration tests
- **Output:** `gate5_attestation.rs` + Jinja2 template (~250 lines)

### Phase 2D: Orchestration + 4-Agent Harness
- **Duration:** 1 week
- **Scope:** Spawn 4 agents, manage consensus queue, measure E2E timing
- **Deliverable:** Working 4-agent pipeline with <3m 30s total time
- **Tests:** End-to-end pipeline test + stress tests
- **Output:** `orchestrator.rs` + agent launcher (~500 lines)

---

## PART H: VERIFICATION CHECKLIST

Gate 0 Pre-Flight:
- [ ] Git state clean (no uncommitted changes)
- [ ] Cargo.lock matches mainline
- [ ] No stale build artifacts
- [ ] Nonce generated and persisted

Gate 1 (All Agents):
- [ ] All unit tests pass (227+ baseline)
- [ ] No panics in logs
- [ ] All assertions green

Gate 2 (All Agents):
- [ ] Memory peak <4GB per agent
- [ ] Latency p99 within budget
- [ ] No timeout errors
- [ ] Throughput meets target (RPS >100 or equivalent)

Gate 3 (All Agents):
- [ ] Ed25519 signature generated
- [ ] Signature verifies on spot-check
- [ ] AP2 entry appended successfully
- [ ] Nonce matches Gate 0 seed

Gate 4 (Triangulation):
- [ ] All 4 proofs received within 5m timeout
- [ ] Merkle roots match across agents
- [ ] Timeout attack detected (if injected)
- [ ] Latency attack detected (if injected)
- [ ] Proof tampering detected (if attempted)
- [ ] Determinism verified (2x runs match)

Gate 5 (Attestation):
- [ ] Root hash computed correctly
- [ ] KMS signature generated
- [ ] AP2 ledger entry created
- [ ] Readiness report generated (JSON + PDF)
- [ ] All artifacts signed

---

## PART I: RISK MITIGATION

### Risk 1: Test Gaming (Retroactive Manipulation)
**Mitigation:** Nonce-based commitment + immediate AP2 entry (immutable)
- Nonce generated at Gate 0 before any tests run
- All Gate 1-3 outputs bound to nonce via Ed25519 signature
- AP2 entry appended before Gate 4 triangulation
- Attempting to retroactively modify: signature breaks, AP2 entry timestamp prevents rollback

### Risk 2: Timeout Attacks (Agent Hung)
**Mitigation:** Timeout injection in Gate 4 adversarial tests + budget enforcement
- Intentionally inject delays, verify detection works
- Total Gate 4 time budget: 90s (fail if exceeded)
- Per-agent timeout: 5m (fail if agent silent)

### Risk 3: Determinism Loss (Flaky Tests)
**Mitigation:** 2x determinism check in Gate 4 + chaos injection
- Run Gates 1-3 twice with same nonce_seed
- Abort if outputs differ (indicates flaky test or race condition)
- Chaos injection tests ensure detection works under adversarial conditions

### Risk 4: Consensus Failure (Agents Disagree)
**Mitigation:** Majority vote + isolated investigation
- Require 4/4 agents to pass (no quorum logic)
- If 3/4 pass: isolate failing agent, run adversarial test to diagnose
- Log diagnosis to AP2 ledger for post-mortem

### Risk 5: AP2 Ledger Unavailable
**Mitigation:** Graceful degradation + fallback signing
- Try AP2 append; if fails, write to backup ledger file
- Continue Gate 5 with local-only proof (no external dependency)
- Ledger sync once AP2 comes back online

---

## PART J: METRICS & MONITORING

**Captured per QA run:**

```json
{
  "run_id": "qa-20260901-001",
  "timestamp": "2026-09-01T12:30:45.123Z",
  "gate_0": {
    "duration_ms": 5234,
    "nonce_seed": "abc123...",
    "git_clean": true,
    "lock_valid": true
  },
  "gates_1_3": {
    "agent_1": {
      "gate_1_duration_ms": 4532,
      "gate_1_tests_passed": 27,
      "gate_2_duration_ms": 58000,
      "gate_2_memory_peak_mb": 1250,
      "gate_2_latency_p99_ms": 23,
      "gate_3_duration_ms": 4800,
      "gate_3_signature": "ed25519_...",
      "gate_3_ap2_hash": "abc123..."
    },
    "agent_2": { ... },
    "agent_3": { ... },
    "agent_4": { ... }
  },
  "gate_4": {
    "duration_ms": 67234,
    "consensus_result": "passed",
    "agents_responding": 4,
    "merkle_roots_match": true,
    "determinism_check": "passed",
    "adversarial_attacks": [
      { "type": "timeout_injection", "detected": true },
      { "type": "latency_attack", "detected": true },
      { "type": "proof_tampering", "detected": true }
    ]
  },
  "gate_5": {
    "duration_ms": 29340,
    "root_hash": "xyz789...",
    "signature": "ed25519_...",
    "ap2_ledger_entry_created": true,
    "readiness_report_generated": true
  },
  "total_duration_ms": 169540,
  "total_duration_formatted": "2m 49.5s",
  "result": "PASS",
  "consensus": "4/4 agents passed"
}
```

---

## CONCLUSION

This hybrid QA pipeline **proves system correctness cryptographically** rather than relying on traditional test reporting. Key advantages:

1. **Prevents test gaming:** Nonce commitment + immediate AP2 ledger entry blocks retroactive manipulation
2. **Catches adversarial breaks:** Triangular verification (code + proof + behavior) + intentional attacks in Gate 4
3. **Supports temporal durability:** All outputs persisted; can recover from 48-hour downtime by replaying from last ledger entry
4. **Local-first:** Runs entirely on-machine (except optional KMS for final signing)
5. **Cryptographically signed:** Every output is Ed25519-signed and linked to AP2 ledger

**Estimated Implementation:** 5-6 weeks for Phases 2A-2D (500-1500 lines Rust/Python, 30+ test cases)

**Ready to integrate into Phase 2-3 as soon as Phase 1 L1-L8 layers stabilize.**
