# CLAUDE.md — SISS v2.0 System Directives

## 1. The Correctness Doctrine (Spec-Driven Development)
Never engage in unstructured "vibe coding". Follow the Plan-Implement-Verify loop strictly:
1. **Plan:** Start complex tasks in Plan Mode (`Shift+Tab`) and produce a detailed implementation plan before touching code.
2. **Goal-Driven Execution:** Transform imperative tasks into verifiable goals (e.g., instead of "add validation", do "write tests for invalid inputs, then make them pass").
3. **Verify:** Run the test suite after every change. Fix all failures before calling the task done.

## 1a. Inversion Development — Test First, Always
Before writing any implementation code:
1. Create the test file (e.g., `crates/<name>/src/tests/`) with failing tests that define the expected behavior.
2. Confirm the tests fail (`cargo test` → red).
3. Only then write the implementation to make them pass (`cargo test` → green).

Never write implementation code for a feature that has no failing test. If a task cannot be expressed as a test, write a spec first (see `.claude/SPEC_TEMPLATE.md`).

## 2. Karpathy Coding Guidelines: Simplicity over Cleverness
- **No over-engineering.** Do not add abstractions or implement 1,000 lines when 100 will do.
- **No drive-by refactoring.** Only modify code directly related to the user's explicit request. Do not clean up adjacent code unless instructed.
- **Manage ambiguity.** If requirements are unclear, ask the user before writing code. Never make blind assumptions.

## 3. Tool & Execution Constraints
- Prefer the `Read` tool for specific files over broad shell `cat`/`grep` commands.
- Do not run commands that delete or truncate databases without explicit human approval.
- Always read a file before editing it.

## 3a. Git Branch / Worktree / Fork — Suggest Only
**Never auto-execute the following. Always propose the command and wait for explicit approval:**
- `git checkout -b` (new branch)
- `git branch` (create/delete branch)
- `git worktree add` (new worktree)
- `git fork` / any fork operation
- `git reset --hard` / `git clean` / any destructive git operation

**Format for suggestions:**
> I would run: `git checkout -b feat/my-feature`
> Shall I proceed?

This applies even when the user's request implies branching. State the intent, show the command, wait.

## 4. Core Commands (Rust/Cargo — this is a Cargo workspace)
- **Test:** `cargo test`
- **Lint:** `cargo clippy`
- **Format:** `cargo fmt`
- **Type-check (fast):** `cargo check`
- **Build:** `cargo build`

## 5. Workspace Structure
```
crates/
  siss-graph-core        # Core graph types and traits
  siss-graph-db          # Graph persistence layer
  siss-gatekeeper        # Access control and policy enforcement
  siss-job-router        # Job routing and complexity scoring
  siss-context-cartography  # Context mapping and analysis
  siss-behavioral-firewall  # Behavioral rule enforcement
  siss-feedback-router   # Feedback routing and aggregation
  siss-agent-shell       # Agent shell and execution environment
  siss-agent-card        # Agent identity cards and repo management
```

## 6. Model Routing (see .claude/MODEL_ROUTING.md for full detail)
- **Opus:** Architecture, cross-crate refactors, SISS spec decisions
- **Sonnet:** Code reviews, medium-complexity logic, `siss-behavioral-firewall`
- **Haiku:** Code writing, test generation, boilerplate — default for execution

## 7. Extended Context (load only when relevant)
- **Architecture:** `docs/architecture/`
- **Multi-Agent Setup:** `AGENTS.md`
- **Spec Template:** `.claude/SPEC_TEMPLATE.md` — fill before any feature
- **Model Routing:** `.claude/MODEL_ROUTING.md`
- **Wiki (semantic memory):** `docs/wiki/` — query this, not raw chat history
- **Custom Skills:** `.claude/skills/` *(not yet created)*
