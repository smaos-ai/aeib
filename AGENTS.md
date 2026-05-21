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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **SovereignNexus** (24632 symbols, 40041 relationships, 199 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/SovereignNexus/context` | Codebase overview, check index freshness |
| `gitnexus://repo/SovereignNexus/clusters` | All functional areas |
| `gitnexus://repo/SovereignNexus/processes` | All execution flows |
| `gitnexus://repo/SovereignNexus/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
