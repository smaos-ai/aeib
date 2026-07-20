# STREAM 1: BaselineCapsule + HarnessCapsule v1 — Quick Reference

**Status:** Architecture & Implementation Plan COMPLETE. Ready for coding execution.  
**Timeline:** Aug 1-30, 2026 (5 weeks)  
**Blockers:** None (all dependencies already available)

---

## What Is STREAM 1?

STREAM 1 is the **foundation layer** for SovereignNexus's governance system. It wraps ReBAC policy enforcement (AP2) + tool authorization (Merkle proofs) + execution isolation + audit logging into a single, low-latency capsule that works with LangChain, Ollama, and AutoGPT.

### Why Now?
STREAM 2 (VisionAPI SDK) depends on STREAM 1. We need this foundation **by Aug 1** to unblock Streams 2-8.

---

## What Gets Built?

### 1. **siss-capsule** (NEW CRATE)
A unified governance capsule API that:
- Verifies policies in <5ms (ReBAC via AP2)
- Authorizes tools in <1ms (Merkle proofs)
- Creates execution contexts in <10ms (state snapshots)
- Logs to audit trail in <2ms
- **Total cold path: <20ms**

### 2. **HarnessCapsule v1** (3 ADAPTERS)
- **LangChain:** Intercepts `tool_use` events, enforces policies, returns certified decisions (<500ms roundtrip incl. LLM)
- **Ollama:** Local-first inference with GPU acceleration (Qwen/Gemma, <100ms per token)
- **AutoGPT:** Maps plugin schema to ReBAC policies, returns certified decisions

### 3. **JSON-LD OUTPUT**
Standardized capsule format with:
- Creator licensing metadata
- Merkle-DAG audit proof
- Execution trace (all 4 phases)
- Confidence score (γ-operator)

---

## Key Numbers

| Metric | Target | Why |
|--------|--------|-----|
| Cold path latency | <20ms | Sub-100ms total SLA requires this |
| Warm path latency | <10ms | With caching |
| LangChain roundtrip | <500ms | Matches production agentic SLA |
| Ollama token latency | <100ms | Real-time inference requirement |
| Test coverage | 20+ tests | Complete acceptance criteria coverage |
| Implementation time | 5 weeks | Realistic with TDD discipline |

---

## Files You Need to Read

1. **STREAM_1_ARCHITECTURE_SPEC.md** (738 lines)
   - System design overview
   - 4 module specifications
   - 20+ test cases (RED → GREEN format)
   - JSON-LD schema
   - Latency budgets
   - Approval gates

2. **STREAM_1_IMPLEMENTATION_PLAN.md** (866 lines)
   - Week-by-week breakdown (5 weeks)
   - 15 concrete subtasks
   - Acceptance criteria for every task
   - Risk mitigation
   - Checkpoint checklists
   - Handoff to Stream 2

---

## Implementation Start Checklist

**Before Aug 1:**
- [ ] Read ARCHITECTURE_SPEC.md (understand system design)
- [ ] Read IMPLEMENTATION_PLAN.md (understand phases)
- [ ] Confirm timeline: 5 weeks (Aug 1-30)
- [ ] Verify all dependencies available (siss-behavioral-firewall, siss-gatekeeper, siss-audit-archiver)

**Aug 1 (Day 1):**
- [ ] Create `crates/siss-capsule/` directory
- [ ] Create `Cargo.toml` with workspace dependencies
- [ ] Create module skeleton (`src/lib.rs`, `src/types.rs`, etc.)
- [ ] Verify `cargo build` succeeds

---

## Phase Overview

### Week 1: Core Infrastructure (Jul 30 - Aug 3)
- Create siss-capsule crate
- Implement BaselineCapsuleExecutor (4-phase execution)
- Write 6 core tests (RED → GREEN)
- **Checkpoint:** All tests GREEN, cold path latency measured

### Week 2: Isolation + JSON-LD (Aug 5 - Aug 9)
- Implement StateSnapshot (commit/rollback)
- Implement JSON-LD export with @context
- Write 13 additional tests (policy, tool auth, isolation, JSON-LD)
- **Checkpoint:** 18 tests GREEN, latency budget verified

### Week 3: Adapter Implementation (Aug 12 - Aug 16)
- Implement LangChain adapter
- Implement Ollama wrapper
- Implement AutoGPT shim
- Write 6 integration tests
- **Checkpoint:** 24 tests GREEN, all adapters working

### Week 4: Optimization & Benchmarking (Aug 19 - Aug 23)
- Benchmark all phases (measure latency)
- Full integration test with real LLM
- Documentation + examples
- **Checkpoint:** All latencies verified, docs complete

### Week 5: Polish & Release (Aug 26 - Aug 30)
- Code review + bug fixes
- Final verification
- Tag v1.0
- **Checkpoint:** Production-ready, ready for Stream 2 dependency

---

## Existing Infrastructure (DON'T REINVENT)

✓ **BaselineCapsule** (siss-gatekeeper/baseline_capsule.rs)
  - Personal truth recording with SHA-256 proofs
  - Already compiles and has 6 passing tests

✓ **ToolCallCapsule** (siss-gatekeeper/capsules/tool_call.rs)
  - Tool authorization with Merkle proofs
  - Fail-closed gate (unauthorized tools rejected)
  - Already passes concurrency tests

✓ **AP2 Policies** (siss-behavioral-firewall/ap2.rs)
  - ReBAC engine with attribute predicates
  - Bounded cache (1024 entries, 5-min TTL)
  - Ready to use

✓ **AuditArchiver** (siss-audit-archiver/lib.rs)
  - Hot/cold storage with S3 archival
  - 30-day default TTL
  - Ready to use

✓ **CovenantFirewall** (siss-behavioral-firewall/covenant_firewall.rs)
  - Behavioral rule enforcement
  - Ready for integration

**NO modifications to existing crates required. STREAM 1 only wraps and aggregates.**

---

## Success Criteria (TDD Style)

**You're done when:**
1. All 20+ tests GREEN (no flakes)
2. `cargo clippy -- -D warnings` → 0 warnings
3. Cold path latency <20ms (verified by benchmarks)
4. LangChain roundtrip <500ms (verified by integration tests)
5. Ollama tokens <100ms per token (verified by streaming test)
6. JSON-LD output valid (verified by schema test)
7. Documentation complete (API ref + examples)
8. v1.0 tagged (ready for Stream 2 dependency)

---

## Dependency Mapping (For Stream 2)

Stream 2 will import:
```toml
siss-capsule = "0.1.0"
```

And use:
```rust
use siss_capsule::{BaselineCapsuleExecutor, CapsuleResult, ExecutionContext};
```

Stream 2 needs to know:
- Public API contract (types + methods)
- Latency SLA (cold path <20ms, roundtrip <500ms)
- JSON-LD @context format
- Audit trail format

**All documented in ARCHITECTURE_SPEC.md Section 10.**

---

## Risk Mitigation Summary

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Latency budget exceeded | Medium | High | Benchmark early (Week 1), optimize Week 4 |
| LangChain API changes | Low | Medium | Use stable v0.1.x, wrap event structure |
| Ollama not available | Medium | Low | Skip integration test if unavailable |
| Test flakiness | Medium | Medium | Use tokio::test + seed, document flaky tests |

---

## Questions? Read These Sections

**Architecture question?** → STREAM_1_ARCHITECTURE_SPEC.md Sections 2-3  
**Timeline question?** → STREAM_1_IMPLEMENTATION_PLAN.md Section 2  
**Latency question?** → Both specs Section 6 (ARCHITECTURE) / Section 5 (PLAN)  
**Test question?** → ARCHITECTURE_SPEC.md Section 4  
**Approval question?** → ARCHITECTURE_SPEC.md Section 10 (Decision Log)  
**Stream 2 handoff?** → IMPLEMENTATION_PLAN.md Section 9

---

## Next Steps

1. **User reads both specs** (30 min)
2. **User approves timeline** ("I approve STREAM 1 execution Aug 1-30")
3. **Agent creates siss-capsule crate** (30 min)
4. **Agent writes 6 tests (RED)** (2 hours)
5. **Agent implements BaselineCapsuleExecutor** (4 hours)
6. **Agent runs `cargo test --lib`** → All 6 GREEN
7. **Repeat for Weeks 2-5** (follow IMPLEMENTATION_PLAN.md exactly)

---

## Approval Gate

**Before implementation begins, user must confirm:**

- [ ] Architecture spec is acceptable
- [ ] Implementation plan is realistic
- [ ] Timeline (Aug 1-30) is locked
- [ ] Test suite (20+ tests) is complete
- [ ] No modifications to existing crates required (additive only)
- [ ] Stream 2 dependencies are clear
- [ ] Ready to proceed with TDD discipline

**Status:** READY FOR APPROVAL

---

**Last Updated:** July 18, 2026  
**Author:** Architecture team  
**Approval Status:** Awaiting user sign-off

