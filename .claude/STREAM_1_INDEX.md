# STREAM 1: Complete Specification Index

**Specification Date:** July 18, 2026  
**Implementation Start:** August 1, 2026  
**Duration:** 5 weeks (Aug 1-30, 2026)  
**Status:** Ready for approval and execution

---

## Document Map

### START HERE: STREAM_1_README.md (7.6 KB)
**Read time:** 5 minutes  
**Purpose:** Quick reference guide and overview

Contains:
- What is STREAM 1 (one paragraph summary)
- Key numbers (5 metrics that matter)
- Files you need to read (ordered by importance)
- Implementation start checklist
- Phase overview (1 paragraph each)
- Existing infrastructure (what we don't rebuild)
- Success criteria checklist
- Next steps and approval gate

**When to use:** First time understanding STREAM 1, refreshing your memory, explaining to others

**Key takeaways:**
- 5-week timeline (Aug 1-30)
- 20+ tests required
- <20ms cold path latency
- <500ms LangChain roundtrip
- Pure additive (no modifications to existing crates)

---

### CORE ARCHITECTURE: STREAM_1_ARCHITECTURE_SPEC.md (27 KB, 738 lines)
**Read time:** 30 minutes  
**Purpose:** Complete system design and specification

Sections:
1. Overview (goal, success criteria, existing infrastructure)
2. Architecture (ASCII diagram + high-level design)
3. Detailed Module Specification (4 modules with full API)
4. Test Suite Specification (20+ tests with RED→GREEN format)
5. JSON-LD Output Specification (schema with examples)
6. Latency Budget (all phases specified with verification method)
7. Implementation Plan (week-by-week overview)
8. Success Checkpoints (5 checkpoints with checklists)
9. Constraints & Assumptions
10. Decision Log (architecture choices explained)
11. Appendix (file structure)

**When to use:** Understanding what gets built, designing implementation approach, writing code

**Reference sections by module:**
- **siss-capsule:** Sections 3.1 (types), 3.2 (main API), 3.3 (isolation), 3.4 (JSON-LD)
- **LangChain adapter:** Section 3.5
- **Ollama wrapper:** Section 3.6
- **AutoGPT shim:** Section 3.7
- **Test cases:** Section 4 (organized by category)

---

### DETAILED IMPLEMENTATION: STREAM_1_IMPLEMENTATION_PLAN.md (24 KB, 866 lines)
**Read time:** 30 minutes  
**Purpose:** Week-by-week execution plan with subtasks

Sections:
1. Executive Summary (goal, deliverables, timeline)
2. Phase Breakdown (5 phases in detail)
   - Phase 1: Core Infrastructure (Week 1, 5 subtasks)
   - Phase 2: Isolation + JSON-LD (Week 2, 2 subtasks)
   - Phase 3: Adapter Implementation (Week 3, 3 subtasks)
   - Phase 4: Optimization & Benchmarking (Week 4, 4 subtasks)
   - Phase 5: Polish & Release (Week 5, 5 subtasks)
3. Success Metrics (code quality, latency, test coverage, documentation)
4. Risk Mitigation (4 risks with mitigation strategies)
5. Dependencies & Blockers
6. Team Assignments (single vs multi-agent execution)
7. Handoff to Stream 2 (what Stream 2 can depend on)
8. Approval Signatures
9. Day-by-Day Task Breakdown (detailed calendar for each week)

**When to use:** Starting implementation, tracking progress, understanding what comes next

**Key tracking information:**
- Checkpoint checklists (verify completion each week)
- Acceptance criteria (what makes a task "done")
- Day-by-day breakdown (what to do on specific dates)
- Risk assessment (what could go wrong, how to mitigate)

---

## Quick Reference Tables

### Module Breakdown
| Module | Location | Lines | Purpose | Tests |
|--------|----------|-------|---------|-------|
| **siss-capsule core** | src/lib.rs, types.rs | ~300 | Unified governance API | 6 |
| **BaselineCapsuleExecutor** | src/baseline_capsule_executor.rs | ~200 | 4-phase execution | 5+3 |
| **Isolation** | src/isolation.rs | ~100 | State snapshot + rollback | 3 |
| **JSON-LD** | src/jsonld_export.rs | ~80 | @context serialization | 2 |
| **LangChain adapter** | src/adapters/langchain.rs | ~150 | tool_use interception | 2 |
| **Ollama wrapper** | src/adapters/ollama.rs | ~200 | Local inference | 2 |
| **AutoGPT shim** | src/adapters/autogpt.rs | ~150 | Plugin compatibility | 2 |
| **Benchmarks** | benches/ | ~150 | Latency measurement | 2 |

### Test Categories (20+ total)
| Category | Count | Purpose | Files |
|----------|-------|---------|-------|
| BaselineCapsule | 6 | Truth recording + verification | baseline_capsule_tests.rs |
| Policy Verification | 5 | ReBAC enforcement | policy_verification_tests.rs |
| Tool Authorization | 3 | Merkle proof + concurrency | tool_authorization_tests.rs |
| Isolation & Rollback | 3 | State snapshot + commit/rollback | isolation_tests.rs |
| JSON-LD Output | 2 | Schema validation | jsonld_output_tests.rs |
| LangChain Integration | 2 | <500ms latency verified | langchain_integration_tests.rs |
| Ollama Inference | 2 | <100ms token latency | ollama_tests.rs |
| AutoGPT Compatibility | 2 | Schema mapping + execution | autogpt_tests.rs |

### Latency Budget
| Phase | Target | How Verified | Notes |
|-------|--------|--------------|-------|
| Policy Verification | <5ms | Cold path benchmark | ReBAC + AP2 cache hit |
| Tool Authorization | <1ms | Cold path benchmark | Hash-only, no DB |
| Isolation Context | <10ms | Cold path benchmark | State snapshot creation |
| Audit Logging | <2ms | Cold path benchmark | In-memory hot storage |
| **Cold Path Total** | **<20ms** | latency_bench.rs | All phases measured |
| **Warm Path Total** | **<10ms** | latency_bench.rs | With caching enabled |
| LangChain Roundtrip | <500ms | langchain_roundtrip_bench.rs | Incl. LLM inference |
| Ollama Token Latency | <100ms | ollama_tests.rs | GPU-accelerated |

### Week-by-Week Summary
| Week | Dates | Focus | Tests | Checkpoint |
|------|-------|-------|-------|-----------|
| 1 | Jul 30 - Aug 3 | Core infrastructure | 6 → 6 | Tests GREEN, build succeeds |
| 2 | Aug 5 - Aug 9 | Isolation + JSON-LD | 6 → 18 | Latency budget verified |
| 3 | Aug 12 - Aug 16 | Adapters | 18 → 24 | All adapters working |
| 4 | Aug 19 - Aug 23 | Optimization | 24 → 24 | All latencies verified |
| 5 | Aug 26 - Aug 30 | Polish + release | 24 → 24 | v1.0 tagged |

---

## How to Use These Specs

### Scenario 1: Getting Started (Day 1)
1. Read STREAM_1_README.md (5 min)
2. Skim STREAM_1_ARCHITECTURE_SPEC.md sections 1-3 (10 min)
3. Read STREAM_1_IMPLEMENTATION_PLAN.md section 1 (5 min)
4. Create siss-capsule crate structure
5. Come back to ARCHITECTURE_SPEC.md section 3 when coding

### Scenario 2: During Implementation (Weekly)
1. Start of week: Read IMPLEMENTATION_PLAN.md for that week (10 min)
2. Each day: Follow day-by-day breakdown (IMPLEMENTATION_PLAN.md Appendix)
3. During coding: Reference ARCHITECTURE_SPEC.md for module details
4. Before checkin: Verify all acceptance criteria in IMPLEMENTATION_PLAN.md

### Scenario 3: Debugging (When Stuck)
1. Check ARCHITECTURE_SPEC.md sections 9-10 (constraints & decision log)
2. Check IMPLEMENTATION_PLAN.md section 4 (risk mitigation)
3. Review test pattern in ARCHITECTURE_SPEC.md section 4
4. Verify latency budget assumptions in ARCHITECTURE_SPEC.md section 6

### Scenario 4: Code Review (End of Phase)
1. Verify checkpoint checklist (IMPLEMENTATION_PLAN.md Appendix)
2. Count tests: all required tests written and passing?
3. Verify latency: benchmarks show <targets?
4. Verify code quality: `cargo clippy -- -D warnings` shows 0 warnings?
5. Verify documentation: all public APIs have doc comments?

---

## Key Files in Project

### Specification Documents (in .claude/)
- **STREAM_1_README.md** — Quick reference (this is your bookmark)
- **STREAM_1_ARCHITECTURE_SPEC.md** — Complete design
- **STREAM_1_IMPLEMENTATION_PLAN.md** — Execution schedule
- **STREAM_1_INDEX.md** — This file (you are here)

### Related Project Files
- **/crates/siss-gatekeeper/src/baseline_capsule.rs** — Existing implementation (reference)
- **/crates/siss-gatekeeper/src/capsules/tool_call.rs** — Existing implementation (reference)
- **/crates/siss-behavioral-firewall/src/ap2.rs** — Existing implementation (reference)
- **/crates/siss-audit-archiver/src/lib.rs** — Existing implementation (reference)

### Will Be Created
- **/crates/siss-capsule/Cargo.toml** — Package manifest
- **/crates/siss-capsule/src/lib.rs** — Public API
- **/crates/siss-capsule/src/types.rs** — Data types
- **/crates/siss-capsule/src/baseline_capsule_executor.rs** — Main logic
- **/crates/siss-capsule/src/isolation.rs** — State management
- **/crates/siss-capsule/src/jsonld_export.rs** — Output format
- **/crates/siss-capsule/src/adapters/langchain.rs** — LangChain
- **/crates/siss-capsule/src/adapters/ollama.rs** — Ollama
- **/crates/siss-capsule/src/adapters/autogpt.rs** — AutoGPT
- **/crates/siss-capsule/src/tests/\*.rs** — 8 test files (20+ tests)
- **/crates/siss-capsule/benches/\*.rs** — 2 benchmark files

---

## Approval Checklist

**Before starting Phase 1, confirm:**

Architecture Level:
- [ ] System design (4 modules, 4 adapters) is acceptable
- [ ] Module API contracts are clear (ARCHITECTURE_SPEC section 3)
- [ ] Test suite (20+ tests, RED→GREEN) is complete
- [ ] Latency budgets (<20ms cold, <500ms roundtrip) are achievable

Implementation Level:
- [ ] Timeline (5 weeks, Aug 1-30) is locked
- [ ] Phase breakdown (5 phases) makes sense
- [ ] Checkpoint criteria are measurable (all tests GREEN, latencies verified)
- [ ] Risk mitigation is adequate (4 risks identified + mitigations)

Dependencies Level:
- [ ] No modifications to existing crates (purely additive)
- [ ] All dependencies available (siss-behavioral-firewall, siss-gatekeeper, siss-audit-archiver)
- [ ] Stream 2 handoff requirements understood (IMPLEMENTATION_PLAN section 9)
- [ ] No blockers identified (all prerequisites met)

Process Level:
- [ ] TDD discipline (RED → GREEN pattern) understood
- [ ] Acceptance criteria for each task are clear
- [ ] Code quality standards (zero clippy warnings, 100% API docs) are acceptable
- [ ] Ready to proceed with this exact plan (no deviations)

**Status:** All checkpoints ready. Awaiting user approval.

---

## Contact & Questions

**Need clarification on:** → Read this section first:
- Architecture/design → STREAM_1_ARCHITECTURE_SPEC.md (relevant section)
- Timeline/phases → STREAM_1_IMPLEMENTATION_PLAN.md (Week breakdown)
- Tests/acceptance → STREAM_1_ARCHITECTURE_SPEC.md section 4
- Latency/performance → Both specs section 6 (ARCHITECTURE) / section 5 (PLAN)
- Risk/mitigation → STREAM_1_IMPLEMENTATION_PLAN.md section 4
- Stream 2 handoff → STREAM_1_IMPLEMENTATION_PLAN.md section 9
- Code examples → STREAM_1_ARCHITECTURE_SPEC.md section 3 (module specs show code)

**If something is unclear:** Revision is welcome. This is pre-implementation specification, so now is the time to adjust.

---

## Version History

| Date | Version | Author | Status |
|------|---------|--------|--------|
| Jul 18, 2026 | 1.0 | Architecture Team | Ready for approval |

---

**NEXT:** User approves → Agent creates siss-capsule crate → Phase 1 begins

