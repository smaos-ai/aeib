# APAC 6-AGENT PARALLEL DISPATCH — EXECUTE NOW
**Date:** 2026-06-06  
**Deadline:** 2026-08-01  
**Model:** TDD-first, parallel execution, zero file overlap

---

## DISPATCH MANIFEST

6 independent agents, each owns exclusive file domain. No overlap, no blocking, full parallelization.

### Agent 1: Project Setup & Scaffolding
**Task File:** `.claude/AGENT_TASK_1.md`  
**Timeline:** Jun 6-7 (1 day)  
**Files:** Cargo.toml, src/lib.rs, src/tests.rs (empty), Root Cargo.toml  
**Outcome:** Crate scaffolded, 5 modules declared  
**Status:** Read AGENT_TASK_1.md → Execute → Return summary  

**Blocking Note:** Agents 2-6 wait for this. Must pass `cargo check`.

---

### Agent 2: Regional Compliance Framework
**Task File:** `.claude/AGENT_TASK_2.md`  
**Timeline:** Jun 7-12 (5 days, parallel with others after Agent 1)  
**Files:** src/compliance/**, migrations/001_*.sql, tests.rs (compliance_tests only)  
**Deliverable:** ComplianceRegistry covering 5 APAC countries  
**Tests:** 8 compliance_tests (MUST PASS)  
**Outcome:** Singapore PDPA, Australia Privacy Act, Japan APPI, Korea PIPA, India DPDP  
**Status:** Read AGENT_TASK_2.md → Write tests first → Implement → Pass all tests

---

### Agent 3: Multi-Currency Settlement
**Task File:** `.claude/AGENT_TASK_3.md`  
**Timeline:** Jun 12-19 (7 days, parallel)  
**Files:** src/settlement/**, migrations/002_*.sql, tests.rs (settlement_tests only)  
**Deliverable:** Stripe Connect for 8 markets with 1-3 day payouts  
**Tests:** 10 settlement_tests (MUST PASS)  
**Outcome:** SGD, AUD, JPY, KRW, INR, THB, VND, IDR settlement  
**Status:** Read AGENT_TASK_3.md → Write tests first → Implement → Pass all tests

---

### Agent 4: SDK Localization Framework
**Task File:** `.claude/AGENT_TASK_4.md`  
**Timeline:** Jun 19-26 (7 days, parallel)  
**Files:** src/localization/**, migrations/003_*.sql, tests.rs (localization_tests only)  
**Deliverable:** 5-language localization with region-specific onboarding  
**Tests:** 12 localization_tests (MUST PASS)  
**Languages:** Mandarin, Japanese, Korean, Hindi, Vietnamese  
**Status:** Read AGENT_TASK_4.md → Write tests first → Implement → Pass all tests

---

### Agent 5: Market Intelligence & TAM Calculator
**Task File:** `.claude/AGENT_TASK_5.md`  
**Timeline:** Jun 26-Jul 3 (7 days, parallel)  
**Files:** src/market_intelligence/**, migrations/004_*.sql, tests.rs (market_intelligence_tests only)  
**Deliverable:** TAM sizing (€480M) across 5 regions  
**Tests:** 12 market_intelligence_tests (MUST PASS)  
**TAM:** SG €50M, AU €80M, JP €200M, KR €120M, IN €30M  
**Status:** Read AGENT_TASK_5.md → Write tests first → Implement → Pass all tests

---

### Agent 6: Operational Playbook Generator + Integration
**Task File:** `.claude/AGENT_TASK_6.md`  
**Timeline:** Jul 3-10 (7 days)  
**Files:** src/playbook/**, src/lib.rs (export only), tests/integration_test.rs, APAC_EXPANSION_SUMMARY.md, tests.rs (playbook_tests only)  
**Deliverable:** Operational playbook synthesizing all 5 components  
**Tests:** 8 playbook_tests + 1 integration_test (MUST PASS)  
**Outcome:** 3-phase launch roadmap, 6 success metrics, 5 risk strategies, critical path  
**Status:** Read AGENT_TASK_6.md → Write tests first → Implement → Pass all tests → Create summary

---

## EXECUTION PROTOCOL

### For Each Agent (1-6)

1. **Read your task file** (AGENT_TASK_N.md)
2. **TDD First:**
   - Write all tests (copy from plan, they will FAIL)
   - Run `cargo test -p siss-apac-expansion [module]_tests` → confirm all fail
   - Implement code until tests PASS
3. **Quality Gates:**
   - Run `cargo clippy -p siss-apac-expansion --all-targets` → 0 warnings
   - Run `cargo test -p siss-apac-expansion [module]_tests` → 100% pass
4. **Commit:** One clear commit per agent
5. **Return Summary:** (provided in AGENT_TASK_N.md)

### Coordination

- **Agents 2-6 can work in parallel** (no file overlap)
- **Agent 1 completes FIRST** (blocks setup)
- **All commits push to stream/8-defense branch**
- **No force-push** — merge conflicts resolved via rebase

---

## FILE OWNERSHIP (ZERO OVERLAP)

```
Agent 1:
  ├─ crates/siss-apac-expansion/Cargo.toml
  ├─ src/lib.rs
  ├─ src/tests.rs (empty skeleton)
  └─ Root Cargo.toml (workspace member)

Agent 2:
  ├─ src/compliance/mod.rs
  ├─ src/compliance/rules.rs
  ├─ src/compliance/validator.rs
  ├─ migrations/001_compliance_registry.sql
  └─ src/tests.rs (ONLY: compliance_tests section)

Agent 3:
  ├─ src/settlement/mod.rs
  ├─ src/settlement/stripe_integration.rs
  ├─ src/settlement/payout_scheduler.rs
  ├─ migrations/002_settlement_tracking.sql
  └─ src/tests.rs (ONLY: settlement_tests section)

Agent 4:
  ├─ src/localization/mod.rs
  ├─ src/localization/translator.rs
  ├─ src/localization/onboarding_flows.rs
  ├─ migrations/003_localization_strings.sql
  └─ src/tests.rs (ONLY: localization_tests section)

Agent 5:
  ├─ src/market_intelligence/mod.rs
  ├─ src/market_intelligence/tam_calculator.rs
  ├─ src/market_intelligence/regional_data.rs
  ├─ migrations/004_market_data.sql
  └─ src/tests.rs (ONLY: market_intelligence_tests section)

Agent 6:
  ├─ src/playbook/mod.rs
  ├─ src/playbook/generator.rs
  ├─ src/lib.rs (EXPORT ONLY: add pub mod playbook)
  ├─ tests/integration_test.rs
  ├─ APAC_EXPANSION_SUMMARY.md
  └─ src/tests.rs (ONLY: playbook_tests section)
```

**CRITICAL:** Do not touch files outside your section. Do not edit other agents' test modules.

---

## SUCCESS METRICS

**Per Agent:**
- [x] All tests PASSING
- [x] Clippy CLEAN
- [x] One clear commit
- [x] Summary returned

**Final (Jul 10):**
- [x] 50+ tests passing total
- [x] Full integration test PASSING
- [x] Release build SUCCESS
- [x] Zero clippy warnings
- [x] All code formatted
- [x] Summary document complete

---

## TIMELINE

```
Jun 6-7:   Agent 1 scaffolds crate
Jun 7-12:  Agent 2 builds compliance (parallel with agents 3-5 ready)
Jun 12-19: Agent 3 builds settlement (parallel)
Jun 19-26: Agent 4 builds localization (parallel)
Jun 26-Jul 3: Agent 5 builds market intelligence (parallel)
Jul 3-10:  Agent 6 builds playbook + integration test
Jul 10-Aug 1: Fix any integration issues, prepare for launch
```

---

## DISPATCH COMMAND

Each agent should:

1. Open `.claude/AGENT_TASK_N.md` where N is your agent number
2. Follow TDD execution order exactly
3. DO NOT read other agents' tasks (focus only on yours)
4. DO NOT modify files outside your section
5. Commit with the exact message provided in your task
6. Return the summary template at the end

---

## NEXT STEP: AGENT 1 START NOW

Execute `.claude/AGENT_TASK_1.md` immediately.

Agents 2-6: Wait for Agent 1 to complete, then start your tasks.

---

**Prepared:** 2026-06-06  
**Status:** ✅ READY FOR IMMEDIATE DISPATCH  
**Model:** Parallel TDD-first execution with zero file overlap  
**Outcome:** 50+ tests passing, €480M TAM, 3-phase launch roadmap by Aug 1
