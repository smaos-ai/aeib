# APAC 6-AGENT DISPATCH — START HERE
**Date:** 2026-06-06  
**Deadline:** 2026-08-01  
**Status:** ✅ READY FOR EXECUTION

---

## What Is This?

You are participating in a **6-agent parallel execution** to build complete APAC regional expansion infrastructure in 60 days.

**Goal:** 50+ tests passing, €480M TAM validated, 3-phase launch playbook ready by Aug 1.

**Model:** TDD-first, parallel execution, zero file overlap.

---

## You Are Agent N

Find your agent number (1-6) and open your task file:

- **Agent 1:** `.claude/AGENT_TASK_1.md` (Scaffolding, 1 day)
- **Agent 2:** `.claude/AGENT_TASK_2.md` (Compliance, 5 days)
- **Agent 3:** `.claude/AGENT_TASK_3.md` (Settlement, 7 days)
- **Agent 4:** `.claude/AGENT_TASK_4.md` (Localization, 7 days)
- **Agent 5:** `.claude/AGENT_TASK_5.md` (Market Intelligence, 7 days)
- **Agent 6:** `.claude/AGENT_TASK_6.md` (Playbook + Integration, 7 days)

**Your task file contains everything you need:** step-by-step instructions, code snippets, test cases, success criteria, return summary template.

---

## Quick Reference

| Doc | Purpose | Read Time |
|-----|---------|-----------|
| `AGENT_TASK_N.md` | Your specific task with complete instructions | 10-15 min |
| `README_AGENTS.txt` | Quick-start rules for all agents | 2 min |
| `APAC_AGENT_DISPATCH.md` | Full coordination guide (file ownership, timeline) | 5 min |
| `DISPATCH_NOW.md` | Quick dispatch manifest | 3 min |
| `DISPATCH_COMPLETE.md` | Setup verification (this dispatch is complete) | 5 min |

---

## Execution in 3 Steps

1. **Read your task file** (AGENT_TASK_N.md)
2. **TDD-first:**
   - Write tests (they will FAIL)
   - Implement code (tests PASS)
   - Run clippy (0 warnings)
3. **Commit + Return Summary**

That's it. Everything else is in your task file.

---

## Key Rules

✅ **TDD-first:** Tests before implementation  
✅ **Zero overlap:** Only touch files assigned to you  
✅ **Parallel:** Work independently (no blocking)  
✅ **Clippy clean:** Zero warnings required  
✅ **One commit:** Per agent, clear message  
✅ **Tests pass:** All tests must PASS before commit  

---

## Timeline

- **Agent 1:** Jun 6-7 (blocks others)
- **Agents 2-5:** Jun 7 - Jul 3 (parallel)
- **Agent 6:** Jul 3-10 (final assembly)
- **Wrap-up:** Jul 10 - Aug 1 (fixes, launch prep)

---

## File Ownership (ZERO OVERLAP)

```
Agent 1: Cargo.toml, src/lib.rs, root Cargo.toml
Agent 2: src/compliance/**, migrations/001_*, tests.rs (compliance_tests only)
Agent 3: src/settlement/**, migrations/002_*, tests.rs (settlement_tests only)
Agent 4: src/localization/**, migrations/003_*, tests.rs (localization_tests only)
Agent 5: src/market_intelligence/**, migrations/004_*, tests.rs (market_intelligence_tests only)
Agent 6: src/playbook/**, tests/integration_test.rs, APAC_EXPANSION_SUMMARY.md, src/lib.rs (export only)
```

**Critical:** Do NOT touch files outside your section.

---

## Success = Tests Passing + Clippy Clean + One Commit

For each agent:
- Write tests → implement → `cargo test -p siss-apac-expansion MODULE_tests` → all pass
- Run `cargo clippy -p siss-apac-expansion --all-targets` → 0 warnings
- Commit with message provided in your task file
- Return summary template (in your task file)

---

## Need Help?

- **For instructions:** Read your AGENT_TASK_N.md file (complete)
- **For rules:** Read README_AGENTS.txt (quick)
- **For coordination:** Read APAC_AGENT_DISPATCH.md (detailed)
- **For technical specs:** Read docs/superpowers/plans/2026-06-06-apac-expansion.md (reference only)

---

## Go!

**Agent 1:** Start with `.claude/AGENT_TASK_1.md` NOW.

**Agents 2-6:** Wait for Agent 1 to complete, then start your task.

---

**Status:** ✅ READY FOR EXECUTION  
**Model:** Parallel TDD-first agents  
**Outcome:** 50+ tests, €480M TAM, launch ready by Aug 1
