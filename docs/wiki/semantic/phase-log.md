# Phase Log — Chronological Decision Record

**Purpose:** Immutable log of phase-level decisions and their rationale.

**Last Updated:** 2026-05-11

---

## Phase 20: Graduated Reputation Recovery (2026-05-11)

### Decision: Recovery as Explicit Lifecycle State

**Date:** 2026-05-11  
**Decision:** Create `'recovering'` as a first-class status in `sovereigns.status` (alongside `'active'`, `'probation'`, `'quarantined'`)  
**Rationale:**
- Phases 15–16 established explicit lifecycle states (quarantine, probation)
- Phase 20 extends this pattern: recovery is not a transient mode, but a defined state
- Network-visible: other sovereigns can see a peer is in recovery (lower trust signal)
- Enables deterministic state machine enforcement

**Superseded Alternatives:**
- ~~Keep status='active' and track recovery via separate recovery_log~~ (implicit state, harder to enforce)
- ~~Use status='probation' with recovery flag~~ (conflates two distinct states)

---

### Decision: Graduated Score Curve (85→100 over 8 weeks)

**Date:** 2026-05-11  
**Decision:** `recovered_base_score(weeks) = 85 + (weeks/8)*15`, linear interpolation, no exponential acceleration  
**Rationale:**
- Linear is predictable: operator can forecast recovery completion
- 8 weeks is proportional: Phase 16 probation is 30 days; recovery adds graduated trust rebuild
- Week 1 = 85 (still in reduced trust), Week 8 = 100 (full restoration)
- Doesn't incentivize gaming (exponential wouldn't match Phase 19's determinism)

**Superseded Alternatives:**
- ~~Exponential curve (week 1 = 90, week 8 = 100)~~ (unpredictable, harder to operator forecast)
- ~~Flat score during recovery~~ (no positive reinforcement for clean behavior)

---

### Decision: Phase 19 Signals Apply During Recovery

**Date:** 2026-05-11  
**Decision:** Slash/anomaly penalties and settlement bonuses apply throughout recovery window  
**Rationale:**
- Consistent deterrence: violations hurt more when you're already on thin ice
- Closes feedback loops: Phase 19's signals inform peer selection during recovery
- Fairness: clean behavior gets settlement bonus help; misbehavior gets penalized
- Self-healing: 30-day windows mean old penalties age out naturally

**Superseded Alternatives:**
- ~~Signals-free recovery (shields from penalties)~~ (breaks signal chain, unfair to active sovereigns)
- ~~Only settlement bonus applies~~ (not symmetric, doesn't penalize misbehavior)

---

### Decision: Violation During Recovery → Immediate Re-Quarantine (No Appeal)

**Date:** 2026-05-11  
**Decision:** Probation violation during recovery = re-quarantine directly; skip appeal + consensus  
**Rationale:**
- Proportional escalation: quarantine is harsh, but sovereign got: appeal (phase 16) → probation → recovery
- Violating on third chance is willful disregard; re-quarantine is appropriate sanction
- Efficiency: avoids re-running appeal consensus for what is a deterministic state machine violation
- Phase 15 logic: probation violations already → quarantine; recovery is a higher tier, so same escalation applies

**Superseded Alternatives:**
- ~~Reset to probation (retry recovery)~~ (too lenient; recovery is designed to be final)
- ~~Keep in recovery despite violation~~ (fails fail-closed principle)

---

## SMAOS Infrastructure Decisions (2026-05-11)

### Decision: Minimal Viable SMAOS Foundation

**Date:** 2026-05-11  
**Decision:** Build only GitNexus + LightRAG + AG-UI + minimal AoE before Phase 20  
**Rationale:**
- Full 6-layer platform would delay Phase 20 indefinitely
- MVP gives immediate value: blast-radius protection + explainability + observability
- Phase 20 becomes the proof-of-concept for the full platform
- Can extend layers post-Phase 20 without rework

**Superseded Alternatives:**
- ~~Build all 6 layers first~~ (scope creep, delays Phase 20)
- ~~Implement Phase 20 without SMAOS~~ (loses safety + explainability wins)

---

### Decision: PostgreSQL + Apache AGE for Intelligence Graph (not LightRAG)

**Date:** 2026-05-11  
**Decision:** Use existing PostgreSQL + Apache AGE as graph backend for intelligence graph  
**Rationale:**
- Project already uses AGE (no new vendor lock-in)
- Sovereignty principle: all data stays in customer Postgres, not third-party service
- Simpler integration: no additional dependencies or setup
- Full control: can tune graph schema for SMAOS decision patterns

**Trade-off:** LightRAG-style entity extraction would need custom implementation (acceptable for MVP)

---

### Decision: GitNexus MCP Scaffolded Locally

**Date:** 2026-05-11  
**Decision:** Build minimal GitNexus MCP server (Rust, stdio-based) locally rather than search for external tool  
**Rationale:**
- No existing GitNexus MCP available in standard repositories
- Custom implementation is small (< 200 lines) and fits SMAOS philosophy
- Blast-radius tool is core to safe refactoring; better to own it than depend on external
- Can extend later with richer analysis (cargo dep graphs, cross-crate calls, etc.)

**Future:** Move to dedicated GitNexus server if complexity grows

---

## Version Control

| Phase | Date | Status | Next Phase |
|-------|------|--------|-----------|
| S0: GitNexus | 2026-05-11 | ✓ Complete | S1: Intelligence Graph |
| S1: LightRAG | 2026-05-11 | 🟡 In Progress | S2: AG-UI Streaming |
| S2: AG-UI | Pending | ⏳ Not Started | S3: AoE Cockpit |
| S3: AoE | Pending | ⏳ Not Started | P20: Phase 20 Tasks 87–92 |
| P20 | Pending | ⏳ Not Started | — |
