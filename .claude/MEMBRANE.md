# SOVEREIGN MEMBRANE v2.0 — 7 Core Principles (Compressed)

## Axiom 1: Correctness Doctrine
```
Plan → Test → Implement → Verify (TDD mandatory)
NO code without failing tests first.
Hypothesis: "If I can't express it as a test, I don't understand it."
```

## Axiom 2: Scope Boundary
```
Current task ONLY. No drive-by refactoring.
Unrelated changes = scope creep = context pollution.
Enforcement: "(See CLAUDE.md: 'manage ambiguity')"
```

## Axiom 3: State from Git
```
STATE.md + EXEC_LOG.json = single source of truth.
NOT conversation history. NOT cached artifacts.
Resume: Read STATE.md first. Check EXEC_LOG for lineage.
```

## Axiom 4: Deterministic Execution (Protocol v2)
```
Diff-only. @file scoping. No workspace scans.
cargo check (fast). cargo test (gold standard).
Result: Parallel agents, zero merge conflicts.
```

## Axiom 5: Fail-Closed Safety
```
Reject invalid early (400 Bad Request, not 500).
Return empty (200 OK), not 404.
Filters applied with AND logic.
Error state preserved across retries.
```

## Axiom 6: Golden Rule (Parallel Execution)
```
Each task owns isolated file domains.
Zero overlap = zero conflicts.
File orthogonality = true parallelism.
Example: Agent A modifies crates/A/, Agent B modifies crates/B/.
```

## Axiom 7: Token Efficiency
```
Skills injected on-demand (not always loaded).
Phase 23 schemas queried, not re-described.
Compressed specs: Delta notation (Phase N delta: adds X, modifies Y).
Short-form references: "repo/recovery_repo.rs — ingest()" (not full path).
```

---

## The Membrane in 3 Sentences

1. **Correctness:** TDD first (tests define reality)
2. **Scope:** Current task only (no baggage)
3. **Execution:** Git-driven state + deterministic protocols = reproducible systems

---

## Emergency Dispatch Protocol

**When spawning an agent:**

```
Brief like a smart colleague:
- What are you trying to accomplish + why?
- What have you learned/ruled out?
- What's the surrounding context?
- If unclear, give file paths + line numbers.

DO NOT:
- "Based on findings, fix it" (synthesis belongs to you)
- "Implement X" (vague, missing spec)
- Dump raw logs/files (use hooks for filtering)
```

---

## The 7 in Practice (This Session)

| Principle | Applied As | Evidence |
|-----------|------------|----------|
| Correctness | TDD workflow (RED → GREEN → REFACTOR) | 38 failing tests → 14 passing integration tests |
| Scope | Phase 24 Task 1 only | Did not touch Phase 25+ or unrelated crates |
| Git-Driven | Commits at each phase (RED, GREEN, REFACTOR) | 4 commits: 5ec1c19 → 83979c3 → 11dfc03 → cfb8d11 |
| Deterministic | cargo test, cargo check, Protocol v2 diff-only | No workspace scans, no exploratory coding |
| Fail-Closed | 400 Bad Request for invalid UUID, 200 empty for missing | Test Suite 4 assertions enforced in handlers |
| Golden Rule | Each test suite owns specific file domain | No test-to-test coupling, parallel test execution safe |
| Token Efficiency | Delta specs, short-form refs, skill injection | @file scoping in prompts, progressive disclosure |

