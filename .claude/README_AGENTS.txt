APAC 6-AGENT DISPATCH — README FOR AGENTS
==========================================

You are Agent N (where N = 1-6) dispatched to execute a specific APAC expansion task.

QUICK START:
============

1. Find your task file: .claude/AGENT_TASK_N.md
2. Read it completely (10 min)
3. Follow TDD execution order:
   - Write tests first (they FAIL)
   - Implement code (tests PASS)
   - Run clippy (0 warnings)
   - Commit with provided message
4. Return summary (template in your task file)

FILE OWNERSHIP:
===============

Agent 1: Cargo.toml, src/lib.rs, root Cargo.toml
Agent 2: src/compliance/**, migrations/001_*, tests.rs (compliance_tests ONLY)
Agent 3: src/settlement/**, migrations/002_*, tests.rs (settlement_tests ONLY)
Agent 4: src/localization/**, migrations/003_*, tests.rs (localization_tests ONLY)
Agent 5: src/market_intelligence/**, migrations/004_*, tests.rs (market_intelligence_tests ONLY)
Agent 6: src/playbook/**, src/lib.rs (export only), tests/integration_test.rs, APAC_EXPANSION_SUMMARY.md, tests.rs (playbook_tests ONLY)

DO NOT TOUCH FILES OUTSIDE YOUR SECTION.
DO NOT EDIT OTHER AGENTS' TEST MODULES.

KEY RULES:
==========

✅ TDD-first: Write tests before implementation
✅ Zero file overlap: Each agent owns exclusive domains
✅ Parallel execution: Agents 2-5 work simultaneously after Agent 1 completes
✅ No blocking: Each agent independent
✅ Clippy clean: Zero warnings required
✅ One commit per agent: Clear, focused commit message
✅ Test-driven: All tests must pass before commit

TIMELINE:
=========

Agent 1: Jun 6-7 (1 day) — Scaffolding
Agents 2-5: Jun 7 - Jul 3 (parallel, staggered deadlines)
Agent 6: Jul 3-10 (7 days) — Playbook + Integration
Final: Jul 10 - Aug 1 (integration, fixes, launch prep)

SUPPORT:
========

Read AGENT_TASK_N.md for full instructions (N = your number)
Read APAC_AGENT_DISPATCH.md for coordination details
Read docs/superpowers/plans/2026-06-06-apac-expansion.md for technical specs

SUCCESS = All tests PASSING + Clippy CLEAN + One clear commit + Summary returned

GO!
===

Start with your AGENT_TASK_N.md file now.
