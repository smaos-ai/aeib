# AGENTS.md — SISS Multi-Agent Session Patterns

## Writer / Reviewer Pattern (Agent-Pair Programming)

For any non-trivial feature, run two isolated sessions:

### Session A — Writer
- Works in a dedicated git worktree
- Implements from the spec (`.claude/SPEC_TEMPLATE.md`)
- Runs `cargo test` and `cargo clippy` until green
- Opens a PR / diff when done — does NOT merge

### Session B — Reviewer
- Fresh context window — reads only the diff and the spec
- Acts as a staff engineer: looks for edge cases, missing tests, abstraction leaks
- Does NOT have access to Session A's reasoning — only the output
- Verdict: Approve / Request Changes / Reject

**Start a writer session:**
```bash
# Suggest only — wait for approval before running
git worktree add ../siss-feat-<name> -b feat/<name>
cd ../siss-feat-<name>
claude  # or jcode
```

**Start a reviewer session:**
```bash
cd /path/to/main/SovereignNexus
git diff main..feat/<name> | claude "Review this diff as a staff engineer. Spec: .claude/SPEC_TEMPLATE.md"
```

---

## Shadow Mode Pattern

For risky changes (behavioral firewall, gatekeeper, federation):
1. Implement on a shadow branch
2. Run the full test suite in isolation
3. Compare output against main — no divergence allowed before merge

---

## Agent Roles

| Role | Model | Responsibility |
|------|-------|---------------|
| Architect | Opus | Spec authoring, cross-crate decisions |
| Writer | Haiku | Implementation, test writing |
| Reviewer | Sonnet | Diff review, edge case detection |
| Debugger | Opus | Root cause analysis on failures |
