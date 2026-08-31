# SMAOS Hybrid QA Pipeline — Executive Summary & Timeline
**Phase 2-3 Integration**  
**Date:** Sep 1, 2026

---

## THE PROBLEM

Traditional QA pipelines have 3 critical weaknesses:

1. **Test Gaming:** Retroactively modify test results after execution (modify assertion, re-run, swap artifacts)
2. **Adversarial Breaks:** Attackers exploit timing side channels or inject delays to break test assumptions
3. **No Proof Trail:** Can't prove tests ran deterministically at a specific time on a specific machine

**SMAOS needs:** Cryptographically-backed QA that produces immutable proof of readiness.

---

## THE SOLUTION: 5-GATE ARCHITECTURE

### Gate 0: Pre-Flight (5s)
**What:** Determinism baseline + nonce generation
- Git state clean
- Dependencies locked
- Cache cleared
- Generate nonce = SHA256(timestamp || repo_hash)
- **Output:** immutable nonce_seed

### Gates 1-3: Agent Execution (Parallel, 7s + 60s + 5s)
**What:** 4 agents run in parallel (each does Gates 1-3 independently)
- Gate 1 (5-7s): Unit tests (cargo test, pytest)
- Gate 2 (30-60s): Behavioral tests (memory, latency, chaos injection)
- Gate 3 (5s): Sign proof with Ed25519 + append to AP2 ledger
- **Output:** 4 signed proofs with nonce binding

### Gate 4: Triangulation (Serial, 60-90s)
**What:** Cross-agent verification + adversarial attacks
- Collect all 4 proofs
- Verify Ed25519 signatures
- Check Merkle roots match
- Run 3 adversarial attacks:
  - Timeout injection (test if detection works)
  - Latency attack (test clock jitter detection)
  - Proof tampering (test if tampering detected)
- Determinism check: run Gates 1-3 again with same nonce, verify identical output
- **Output:** TriangulationResult (all 4 agents valid)

### Gate 5: Final Attestation (Serial, 30s)
**What:** Sign Merkle root with KMS key + immutable proof creation
- Compute Merkle root of all 4 agent proofs
- Sign root with Ed25519 (KMS-backed in production)
- Append to AP2 ledger
- Generate signed JSON readiness report
- **Output:** test_results.json + .sig + merkle_proof.json + ap2_entry.json

---

## KEY INNOVATIONS

### 1. Nonce-Based Commitment
```
Gate 0: Generate nonce_seed = SHA256(time || repo_hash)
Gate 3: Sign proof with Ed25519(result || nonce_seed)
Gate 4: Verify signature — nonce mismatch = FAILED
Gate 5: Final signature includes nonce

Result: Cannot retroactively modify test results without breaking signature.
```

### 2. Triangular Verification (Code + Proof + Behavior)
```
Traditional QA:
  Run test → Pass/Fail → Report → Done
  (Single point of truth, no external verification)

SMAOS QA:
  Run code (agent) → Measure behavior → Sign proof → Verify signature → Check Merkle root
  (3 independent verification layers)
```

### 3. Adversarial Tests Built-In
```
Instead of hoping tests work:
  1. Timeout attack: Inject 30s delay, verify detection works
  2. Latency attack: Measure clock jitter, verify we detect anomalies
  3. Proof tampering: Flip one bit in hash, verify signature fails

If adversarial attacks don't fail as expected → Pipeline fails.
```

### 4. Determinism Verification
```
Gate 4 checks:
  Run Gates 1-3 again with same nonce_seed
  Compare outputs: tests_passed, memory_peak, latency_p99
  Difference > threshold? → Flaky test detected → FAIL

Ensures same input always produces same output.
```

### 5. Temporal Durability (48-Hour Recovery)
```
All outputs written to disk immediately:
  - Gate 0 nonce → .qa-nonce file
  - Gate 1-3 results → .qa-artifacts/
  - Gate 4 proof → AP2 ledger (immutable)
  - Gate 5 attestation → .qa-artifacts/readiness_report.sig

If pipeline dies after Gate 3:
  - Restart from Gate 4
  - Ledger entries are append-only (can recover)
  - Can prove tests ran, even if attestation incomplete
```

---

## WALL-CLOCK TIMING

**Best Case (no retries, parallel execution):**
```
Gate 0:              5s (serial, all agents wait)
Gates 1-3 (parallel): max(7s + 60s + 5s) = 72s (all 4 agents run simultaneously)
Gate 4:             60s (serial, triangulation + adversarial)
Gate 5:             30s (serial, final signing)
─────────────────────────────
TOTAL:            ~2m 47s
```

**Worst Case (1 retry, adversarial failures):**
```
Gate 0:                    5s
Gates 1-3 (1st attempt):  72s
Gates 1-3 (retry Agent 2): 72s (only Agent 2, others cached)
Gate 4 (with investigations): 120s (adversarial attacks take longer to diagnose)
Gate 5:                    30s
─────────────────────────────
TOTAL:                ~3m 30s
```

**Target SLA:** <3m 30s P99

---

## CRYPTOGRAPHIC PROOF STRUCTURE

### Merkle Tree (Gate 5)

```
                    ROOT_HASH
                  (64 chars hex)
                        │
        ┌───────────────┼───────────────┐
        │               │               │
   AGENT1_HASH    AGENT2_HASH    AGENT3_HASH    AGENT4_HASH
   (64 chars)     (64 chars)     (64 chars)     (64 chars)
        │               │               │               │
   Gate 1-3      Gate 1-3      Gate 1-3      Gate 1-3
   Results      Results       Results       Results
   + Ed25519     + Ed25519     + Ed25519     + Ed25519
   Signature     Signature     Signature     Signature
        │               │               │               │
    (27 tests)    (32 tests)    (28 tests)    (50 tests)
    (1.2GB mem)   (900MB mem)   (1.5GB mem)   (RAGAS 89%)
```

**Tampering Detection:**
- Modify any result (e.g., Agent 1 tests: 27 → 28)
- Hash changes
- Merkle root changes
- Signature no longer verifies
- **Attack fails**

### AP2 Ledger Entry (Immutable)

```json
{
  "type": "qa_pipeline_attestation",
  "timestamp": "2026-09-01T12:30:45.123Z",
  "root_hash": "abc123def456...",
  "signature": "ed25519_signature_here",
  "agent_count": 4,
  "consensus": {"passing": 4, "total": 4},
  "nonce_seed": "gate0_nonce_seed_here",
  "gate_4_duration_ms": 67340
}
```

**Why immutable?**
- Append-only ledger (blockchain-like)
- Timestamp is part of hash (can't change without breaking hash)
- Entry is cryptographically signed
- To fake proof, attacker must:
  1. Modify all test results
  2. Recompute all Merkle hashes
  3. Resign root with Ed25519 key (requires KMS access)
  4. Create new AP2 ledger entry with matching timestamp
  5. All while Gate 4 determinism check runs

**Effectively impossible.**

---

## INTEGRATION WITH PHASE 1

### Existing Infrastructure (Already Built)

| Component | Status | Used By |
|-----------|--------|---------|
| L1-L8 harness | Complete (204 tests, 6000+ lines) | Gates 1-3 |
| Ed25519 signing (agentacct) | Complete | Gate 3 |
| AP2 ledger | Complete (Merkle chain) | Gate 3 + 5 |
| RAGAS evaluation (50Q) | Complete | Gate 2D (L7 tests) |
| Intent commitment | Complete | Gate 2B (L3-L4 tests) |
| Egress controls | Complete | Gate 2B (L5-L6 tests) |

### New Components (2-3 weeks to implement)

| Gate | New Code | Dependencies |
|------|----------|--------------|
| Gate 0 | ~200 lines (Rust) | git CLI, cargo |
| Gates 1-3 | ~800 lines (Rust) | cargo test, pytest, L1-L8 |
| Gate 4 | ~600 lines (Rust) | sha2, ed25519-dalek, custom harness |
| Gate 5 | ~400 lines (Rust) | AWS KMS (optional), AP2 client |

**Total new code:** ~2000 lines (Rust + Python tests)

---

## FAILURE MODES & RECOVERY

### Severity 1 (CRITICAL) — Pipeline Halts

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Agent 1 tests fail | Red test output | Re-run Agent 1 only |
| Gate 3 signing fails | KMS error | Retry with exponential backoff |
| Gate 4: Merkle mismatch | Proof validation fails | Isolate agent, run adversarial test |
| Gate 5: Signature invalid | Verification fails | Check KMS key access, retry |

**Recovery:** Retry up to 3 times, then escalate to human.

### Severity 2 (HIGH) — Log & Continue

| Failure | Detection | Action |
|---------|-----------|--------|
| Agent 2 memory spike (>4GB) | Behavioral metric | Retry; if persists, warn |
| Timeout attack not detected | Gate 4 adversarial fails | Log as "attack detection broken" |
| Latency p99 >100ms | Gate 2 threshold | Log regression, continue |

**Action:** Increment failure counter, log to AP2, continue pipeline.

### Severity 3 (LOW) — Log & Ignore

| Failure | Detection | Action |
|---------|-----------|--------|
| RAGAS baseline <87% | Gate 1D fails | Log, continue (not blocking) |
| RPS <100 (expected >100) | Gate 2C metric | Log, continue |

**Action:** Record in metrics, don't fail pipeline.

---

## DEPLOYMENT CHECKLIST

### Week 1: Design & Setup
- [ ] Review QA_PIPELINE_DESIGN_SMAOS.md
- [ ] Review QA_PIPELINE_TECHNICAL_REFERENCE.md
- [ ] Set up Rust crate: `cargo new --lib crates/smaos-qa`
- [ ] Configure Ed25519 keys (local for dev, KMS for prod)
- [ ] Set up AP2 ledger client connection

### Week 2: Implement Gates 0-3
- [ ] Gate 0 (pre-flight + nonce): ~200 lines, 5 tests
- [ ] Gate 1-3 agent runner: ~800 lines, 10 tests
- [ ] Integration with L1-L8 layer harness
- [ ] Test on single agent first (Agent 1)

### Week 3: Implement Gates 4-5
- [ ] Gate 4 (triangulation + adversarial): ~600 lines, 8 tests
- [ ] Gate 5 (final attestation): ~400 lines, 5 tests
- [ ] Merkle tree validation
- [ ] Readiness report generation

### Week 4: Integration & E2E Testing
- [ ] 4-agent orchestrator: ~500 lines
- [ ] E2E pipeline test (all gates)
- [ ] Stress testing (concurrent agents)
- [ ] Adversarial attack simulation
- [ ] Recovery testing (pause/resume)

### Week 5-6: Production Hardening
- [ ] KMS integration (AWS KMS or HashiCorp Vault)
- [ ] AP2 ledger synchronization
- [ ] Monitoring & alerting hooks
- [ ] Documentation & runbook
- [ ] Sign-off with QA team

---

## SUCCESS CRITERIA (Definition of Done)

### Functional
- [ ] All 5 gates implement and pass tests
- [ ] 4 agents run in parallel
- [ ] Total execution time <3m 30s
- [ ] Consensus: 4/4 agents must pass (no quorum logic)
- [ ] Merkle tree validates correctly
- [ ] Ed25519 signatures verify on spot check
- [ ] AP2 ledger entries appended successfully

### Security
- [ ] Nonce commitment prevents retroactive modification
- [ ] Timeout attack is detected and fails pipeline
- [ ] Latency attack is detected and fails pipeline
- [ ] Proof tampering is detected and fails pipeline
- [ ] Determinism check verifies consistency

### Operational
- [ ] Readiness report generated as JSON + PDF
- [ ] Artifacts stored in `.qa-artifacts/` with .sig files
- [ ] All outputs cryptographically signed
- [ ] Pipeline can restart from any gate (48-hour durability)
- [ ] Runbook exists for operators

### Performance
- [ ] Gate 0: <10s
- [ ] Gates 1-3: <80s (parallel)
- [ ] Gate 4: <100s
- [ ] Gate 5: <40s
- [ ] Total: <3m 30s P99

---

## INVESTMENT SUMMARY

### Engineering Effort
- **Time:** 5-6 weeks (1 engineer)
- **Code:** ~2000 lines (Rust + Python)
- **Tests:** 30+ test cases
- **Documentation:** 3 documents (Design, Technical, Runbook)

### Cost
- **Engineer:** 5-6 weeks @ $10k/week = $50-60k
- **Infrastructure:** AWS KMS (~$1/month), local testing free
- **Contingency:** 20% buffer = $10-12k

**Total Investment: $60-72k CZK (≈ 1.5-2% of Phase 2 budget)**

### ROI
- Prevents test gaming (infinite value in compliance)
- Cryptographic proof for regulators + investors (Series A credibility)
- Reusable pattern for future agentic QA
- Competitive differentiator (no other agentic AI system has this)

---

## NEXT STEPS

1. **Review & Approve** (Sep 1-2)
   - Engineering team reviews QA_PIPELINE_DESIGN_SMAOS.md
   - Stakeholders approve timeline + investment
   - Go/no-go decision

2. **Setup Phase** (Sep 3-5, 0.5 weeks)
   - Create Rust crate
   - Configure keys + ledger access
   - Create feature branch for implementation

3. **Implementation** (Sep 6-30, 4 weeks)
   - Weekly checkins (Monday)
   - Code reviews (Wednesday)
   - Integration testing (Friday)

4. **Hardening & Sign-Off** (Oct 1-7, 1 week)
   - KMS integration
   - Production readiness review
   - Operator runbook sign-off

5. **Phase 2-3 Delivery** (Oct 8 onwards)
   - All SMAOS pilots use QA pipeline
   - Readiness reports part of release process
   - AP2 ledger entries persist proof trail

---

## RISK MITIGATION

### Risk 1: Timeline Slips
**Mitigation:** Break into weekly milestones with clear deliverables. If any gate slips >2 days, pull in additional resource.

### Risk 2: KMS Integration Fails
**Mitigation:** Implement local Ed25519 signing first (working weeks 1-4); defer KMS to week 5 (optional for production).

### Risk 3: Adversarial Tests Too Strict
**Mitigation:** Parameterize thresholds (e.g., timeout_budget_ms). If tests fail, tune before shipping.

### Risk 4: AP2 Ledger Unavailable
**Mitigation:** Implement fallback (write to local file) + eventual consistency (sync once ledger returns).

---

## APPENDIX: TOOL STACK

### Primary (Rust)
```
tokio              1.40   (async runtime)
sha2               0.10   (Merkle hashing)
ed25519-dalek      2.1    (Ed25519 signing)
serde_json         1.0    (JSON serialization)
chrono             0.4    (timestamps)
```

### Secondary (Python)
```
pytest             7.0+   (unit testing)
hypothesis         6.0+   (property testing)
pytest-timeout     2.1+   (timeout enforcement)
pytest-benchmark   4.0+   (latency measurement)
```

### Optional (Production)
```
aws-sdk-kms        0.27   (AWS KMS for signing)
hashicorp-vault    ?      (Vault integration, if preferred)
prometheus         ?      (metrics + alerting)
```

---

## DOCUMENT REFERENCES

1. **QA_PIPELINE_DESIGN_SMAOS.md** (15 pages)
   - Strategic architecture
   - Gate ordering & timing
   - Failure modes
   - Merkle tree structure
   - Deployment diagram

2. **QA_PIPELINE_TECHNICAL_REFERENCE.md** (25 pages)
   - Rust code for all gates
   - Integration patterns
   - Test cases
   - Build instructions

3. **QA_PIPELINE_EXECUTIVE_SUMMARY.md** (this document)
   - Problem statement
   - Solution overview
   - Timeline & checklist
   - Risk mitigation

---

## QUESTIONS?

For technical deep dives, see **QA_PIPELINE_TECHNICAL_REFERENCE.md** (code examples, architecture patterns, build steps).

For strategic decisions, see **QA_PIPELINE_DESIGN_SMAOS.md** (risk assessment, tool recommendations, metrics).

For project planning, refer to this **Executive Summary** (timeline, success criteria, investment ROI).
