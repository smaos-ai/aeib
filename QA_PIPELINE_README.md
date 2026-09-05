# SMAOS Hybrid QA Pipeline — Complete Design Package
**Phase 2-3 Integration | Sep 1, 2026**

---

## QUICK START (5 Minutes)

### The Problem
Traditional QA can be gamed: modify tests → re-run → swap artifacts. SMAOS needs cryptographically-backed proof.

### The Solution
5-gate pipeline:
1. **Gate 0** (5s): Nonce generation → determinism baseline
2. **Gates 1-3** (72s parallel): Unit tests + behavioral profiling + Ed25519 signing (4 agents)
3. **Gate 4** (60s): Merkle validation + 3 adversarial attacks + determinism check
4. **Gate 5** (30s): Root signature + AP2 ledger + readiness report

**Total:** 2m 47s - 3m 30s. **Output:** Cryptographically signed proof that all tests ran correctly.

### Key Features
- **Prevents test gaming:** Nonce commitment + immediate AP2 ledger entry (immutable)
- **Catches adversarial breaks:** Timeout injection, latency attacks, proof tampering all detected
- **48-hour durability:** All outputs on disk, can restart from any gate
- **Local-first:** No cloud dependency (KMS optional for final signing)
- **Signed reports:** JSON + PDF with Ed25519 + Merkle proof

---

## DOCUMENT ROADMAP

### 1. Executive Summary (START HERE)
**File:** `QA_PIPELINE_EXECUTIVE_SUMMARY.md` (14 KB, 20 pages)

**Audience:** Engineering leads, product managers, stakeholders

**Contains:**
- Problem statement (1 page)
- 5-gate solution overview (2 pages)
- Key innovations explained (3 pages)
- Wall-clock timing (1 page)
- Integration with Phase 1 (1 page)
- Deployment checklist (2 pages)
- Success criteria (1 page)
- Investment summary ($60-72k, 5-6 weeks)
- Risk mitigation (1 page)

**Read time:** 15 minutes

**Key sections:**
- The Problem (Why we need this)
- The Solution (5-gate architecture)
- Cryptographic Proof Structure (How tampering is prevented)
- Deployment Checklist (Week-by-week plan)
- Success Criteria (Definition of done)

**Next step:** After reading, go to Technical Reference if you need implementation details, or Design if you want strategic context.

---

### 2. Strategic Design (ARCHITECTURE & STRATEGY)
**File:** `QA_PIPELINE_DESIGN_SMAOS.md` (37 KB, 40 pages)

**Audience:** Architects, security engineers, infrastructure team

**Contains:**

#### Part A: Logical Gate Ordering
- ASCII diagram showing Gates 0-5 execution flow
- Parallel timing analysis (2m 47s best case)
- Serial vs. parallel phase breakdown

#### Part B: Integration Points
- Where each tool fits (cargo, pytest, semgrep, custom agents)
- Agent communication flow (MCP consensus protocol)
- Reuse of Phase 1 components (L1-L8, AP2 ledger, agentacct)

#### Part C: Failure Modes (TABLE)
- 20+ failure modes per gate
- Detection method for each
- Recovery strategy
- Severity levels

#### Part D: Merkle Tree Structure
- 4-layer tree for agent proofs
- Hash computation algorithm
- Tampering detection mechanism
- AP2 ledger entry structure (JSON)

#### Part E: Tool Recommendations
- Unit testing: `cargo test`, pytest, `pytest-timeout`
- Behavioral: perf, valgrind, custom hooks
- Proof: ed25519-dalek, sha2, AP2 client
- Triangulation: custom MCP server
- Attestation: KMS (AWS/Vault), Jinja2 templates

#### Part F: Deployment Architecture (ASCII)
- Full system diagram showing:
  - Orchestrator process (serial Gates 0, 4, 5)
  - 4 agent processes (parallel Gates 1-3)
  - Consensus queue (in-memory or Redis)
  - Output artifacts (.qa-artifacts/)
  - Temporal durability (48-hour recovery)

#### Part G: Implementation Phases
- Phase 2A: Gates 0-3 (2 weeks, 400 lines)
- Phase 2B: Gate 4 (1 week, 300 lines)
- Phase 2C: Gate 5 (1 week, 250 lines)
- Phase 2D: Orchestration (1 week, 500 lines)

#### Part H: Verification Checklist
- Gate-by-gate acceptance criteria
- Metrics captured per run
- Risk mitigation strategies
- 48-hour recovery procedure

**Read time:** 45 minutes (skim), 90 minutes (detailed)

**Key sections:**
- Part A: Gate Ordering (get the big picture)
- Part C: Failure Modes (understand what can go wrong)
- Part D: Merkle Tree (how tampering is prevented)
- Part F: Deployment Architecture (what it looks like)

**Next step:** After reading, go to Technical Reference for code implementation, or Executive Summary for business context.

---

### 3. Technical Implementation (CODE & DETAILS)
**File:** `QA_PIPELINE_TECHNICAL_REFERENCE.md` (34 KB, 25 pages)

**Audience:** Backend engineers, DevOps, implementers

**Contains:**

#### Section 1: Gate 0 Pre-Flight Validation
- Rust code (~200 lines) for:
  - Git state checking
  - Cargo.lock validation
  - Cache clearing
  - Nonce generation (SHA256)
  - Baseline measurement
- Full implementation ready to copy-paste

#### Section 2: Gates 1-3 Agent Runner
- Rust code (~800 lines) for:
  - Parallel agent spawning
  - Unit test runner (cargo test + pytest)
  - Behavioral profiling (memory, latency, chaos)
  - Ed25519 signing
  - AP2 ledger appending
- Agent result structs and trait definitions

#### Section 3: Gate 4 Triangulation
- Rust code (~600 lines) for:
  - Consensus protocol (collect 4 proofs with timeout)
  - Ed25519 verification
  - Merkle root computation
  - Determinism check (2x run comparison)
  - 3 Adversarial attacks:
    - Timeout injection
    - Latency attack (jitter measurement)
    - Proof tampering detection

#### Section 4: Gate 5 Final Attestation
- Rust code (~400 lines) for:
  - Merkle root computation (all 4 agents)
  - Root signing (local Ed25519 + KMS integration)
  - AP2 ledger entry creation
  - Readiness report generation (JSON + PDF)
  - Artifact writing to disk

#### Section 5: Orchestrator Main Loop
- Rust code (~500 lines) for:
  - Gate 0 → Gates 1-3 (parallel) → Gate 4 → Gate 5 pipeline
  - Progress logging and status reporting
  - Error handling and recovery
  - CLI argument parsing
  - Output formatting

#### Section 6: Unit Tests
- Rust test code for:
  - Gate 0 nonce generation
  - Gate 3 proof signing
  - Gate 4 adversarial timeout
  - Gate 5 Merkle root computation
  - Full integration test

#### Section 7: Build & Run
- Cargo.toml configuration
- Dependency list (tokio, sha2, ed25519-dalek, etc.)
- Build commands
- Expected output (annotated)

**Read time:** 60 minutes (skim), 120+ minutes (detailed implementation)

**Key sections:**
- Section 1: Start here if implementing Gate 0
- Section 2: Start here if implementing Gates 1-3
- Section 3: Start here if implementing Gate 4 (most complex)
- Section 5: Start here if building orchestrator
- Section 7: Copy-paste Cargo.toml to get started

**Next step:** Start implementation from section 1, then 2, then 3, etc. Reference Design doc for failure mode handling.

---

## QUICK REFERENCE: DOCUMENT SELECTION

**If you want to...**

| Goal | Read First | Then Read | Time |
|------|-----------|-----------|------|
| Understand overall approach | Executive Summary | Design | 45m |
| Implement Gates 0-5 | Technical Reference | Design (failure modes) | 180m |
| Present to executives | Executive Summary | None | 15m |
| Design testing strategy | Design (Part B) | Technical Reference | 90m |
| Review for security | Design (Parts C, D) | Technical Reference (Gate 4) | 60m |
| Plan timeline | Executive Summary + Design (Part G) | Technical Reference | 30m |
| Implement CI/CD pipeline | Technical Reference + Design (Part F) | None | 120m |
| Debug a failure | Design (Part C) | Technical Reference (relevant gate) | 30m |

---

## INTEGRATION WITH PHASE 1-2

### What Already Exists (Don't Reinvent)
- L1-L8 harness (204 tests, 6000+ lines)
- Ed25519 signing via agentacct
- AP2 ledger (Merkle chain, append-only)
- RAGAS evaluation (50Q golden set)
- Intent commitment (constraint enforcement)
- Egress controls (whitelist + DNS validation)

### What's New (2000 lines, 5-6 weeks)
- Gate 0: Pre-flight validator
- Gate 1-3 orchestration: Agent spawning + result collection
- Gate 4: Triangulation + adversarial tests
- Gate 5: Final attestation + report generation

### Integration Points
```
Phase 1 (Complete)
├── L1 Reasoning (routing tests)         → Gate 1A
├── L2 Knowledge (pgvector tests)        → Gate 1A
├── L3 Permit Gates (enforcement tests)  → Gate 1B
├── L4 Orchestration (LangGraph tests)   → Gate 1B
├── L5 Communication (MCP tests)         → Gate 1C
├── L6 Infrastructure (hardware tests)   → Gate 1C
├── L7 RAGAS (evaluation)                → Gate 1D
├── L8 Proof (agentacct, AP2)           → Gate 3 (reuse for signing)

Phase 2 (New)
├── Gate 0 Pre-flight               (new, ~200 lines)
├── Gate 1-3 Agent Orchestration    (new, ~800 lines)
├── Gate 4 Triangulation            (new, ~600 lines)
├── Gate 5 Final Attestation        (new, ~400 lines)
└── Tests & Tooling                 (new, 30+ test cases)
```

---

## SUCCESS METRICS (After Implementation)

### Functional
- [ ] 5 gates fully implemented (Gates 0-5)
- [ ] 4 agents execute in parallel
- [ ] Total time <3m 30s P99
- [ ] Consensus required: 4/4 agents passing
- [ ] Merkle tree validates correctly
- [ ] Ed25519 signatures verified
- [ ] AP2 ledger appends successful

### Security
- [ ] Nonce prevents retroactive modification
- [ ] Timeout attack detected
- [ ] Latency attack detected
- [ ] Proof tampering detected
- [ ] Determinism verified (2x runs match)

### Operational
- [ ] Readiness reports generated (JSON + PDF)
- [ ] Artifacts stored with .sig files
- [ ] All outputs cryptographically signed
- [ ] Pipeline restartable from any gate
- [ ] Operator runbook exists

### Performance
- Gate 0: <10s
- Gates 1-3: <80s (parallel)
- Gate 4: <100s
- Gate 5: <40s
- **Total: <3m 30s**

---

## INVESTMENT & TIMELINE

### Effort
- **Time:** 5-6 weeks (1 engineer)
- **Code:** ~2000 lines (Rust + Python tests)
- **Tests:** 30+ test cases
- **Documentation:** 3 comprehensive docs (this package)

### Cost
- **Engineering:** 5-6 weeks @ $10k/week = $50-60k
- **Infrastructure:** AWS KMS (~$1/month), local testing free
- **Contingency:** 20% = $10-12k
- **Total:** ~$60-72k CZK (≈ 1-2% of Phase 2 budget)

### Timeline
```
Sep 1-2: Review & approval
Sep 3-5: Setup (0.5 weeks)
Sep 6-30: Implementation (4 weeks)
  ├─ Week 1: Gates 0-1
  ├─ Week 2: Gates 2-3
  ├─ Week 3: Gate 4
  └─ Week 4: Gate 5 + orchestrator
Oct 1-7: Hardening + sign-off (1 week)
Oct 8+: Production deployment
```

---

## RISK MITIGATION

### Risk 1: Timeline Slips
**Mitigation:** Weekly milestones with clear deliverables. If gate slips >2 days, add resource.

### Risk 2: KMS Integration Fails
**Mitigation:** Implement local Ed25519 first (weeks 1-4), defer KMS to week 5 (optional).

### Risk 3: Adversarial Tests Too Strict
**Mitigation:** Parameterize thresholds, tune before shipping.

### Risk 4: AP2 Ledger Unavailable
**Mitigation:** Implement fallback (local file), eventual consistency (sync once ledger returns).

---

## NEXT STEPS

### For Approval (This Week)
1. Review **Executive Summary** (15 minutes)
2. Skim **Design** Part A (gate ordering) + Part D (Merkle structure) (15 minutes)
3. Confirm: Timeline (5-6 weeks)? Budget ($60-72k)? Team (1 engineer)?
4. Approve or request changes

### For Implementation (Week 1)
1. Create Rust crate: `cargo new --lib crates/smaos-qa`
2. Read **Technical Reference** section 1 (Gate 0)
3. Implement Gate 0 + tests
4. Verify with existing Phase 1 harness

### For Integration (Weeks 2-4)
1. Implement Gates 1-3 (Technical Reference sections 2-3)
2. Implement Gate 4 (Technical Reference section 4)
3. Implement Gate 5 + orchestrator (Technical Reference sections 5-6)
4. Run full E2E pipeline test

### For Production (Week 5-6)
1. KMS integration (AWS KMS or Vault)
2. AP2 ledger synchronization
3. Operator runbook
4. Sign-off with QA team

---

## DOCUMENT VERSIONS & UPDATES

**Version 1.0 — Sep 1, 2026**
- Initial strategic design
- 3-document package (Executive Summary, Design, Technical Reference)
- 85 KB total
- 85+ pages

**Future Updates (Phase 2-3+)**
- Implementation checklist (as work progresses)
- Performance benchmarks (after Gates 0-3 work)
- Operator runbook (after Week 4)
- Post-deployment metrics (after launch)

---

## CONTACTS & QUESTIONS

**For strategic questions:** See Executive Summary + Design doc

**For implementation questions:** See Technical Reference

**For timeline/resource questions:** See Deployment Checklist in Executive Summary

**For security/threat modeling:** See Design Part C (Failure Modes) + Part D (Merkle Structure)

---

## GLOSSARY

| Term | Definition |
|------|-----------|
| Gate | Sequential stage of QA pipeline (0-5) |
| Nonce | Unique seed (SHA256) generated at Gate 0, used to bind all proofs |
| Merkle Tree | Hierarchical hash structure proving 4 agents' outputs are consistent |
| Attestation | Cryptographic proof (Ed25519) that all gates passed |
| AP2 Ledger | Immutable append-only blockchain where proof entries are stored |
| Triangulation | Gate 4: cross-agent verification + adversarial attacks |
| Proof Tampering | Attempt to modify test results (detected by signature verification) |
| Adversarial Test | Intentional attack (timeout, latency, proof modification) to verify detection |
| Determinism | Property that same input (nonce) always produces same output |

---

## FINAL NOTES

This package provides **everything needed to implement** SMAOS's hybrid QA pipeline:

1. **Strategic context:** Why we need this, what problem it solves
2. **Architectural design:** How all pieces fit together, what can go wrong
3. **Technical implementation:** Rust code ready to copy-paste and adapt
4. **Project plan:** Timeline, resource needs, success criteria
5. **Risk analysis:** What can go wrong and how to mitigate

**The pipeline is designed to be:**
- **Tamper-proof:** Nonce commitment + immediate AP2 entry
- **Adversary-resistant:** 3 attack simulations built-in
- **Durable:** All outputs persisted, 48-hour recovery possible
- **Local-first:** No cloud dependency (KMS optional)
- **Auditable:** Full signed proof trail for regulators

**Start with Executive Summary (15 min), then jump to relevant section (Design for architecture, Technical for code).**
