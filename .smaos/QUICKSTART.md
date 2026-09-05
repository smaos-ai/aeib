# ⚡ Quick Start — SovereignNexus Session Independence

## Session 1: NOW (You)

1. **Update shell alias** (one-time):
```bash
echo 'alias smaos="trap \"python3 .smaos/scripts/sync_kanban.py --mode session_end 2>/dev/null || true\" EXIT; claude"' >> ~/.zshrc
source ~/.zshrc
```

2. **Next session, instead of `claude`, type:**
```bash
smaos
```

3. **Board auto-loads.** Work as normal. Session end triggers sync automatically.

---

## Phase 25: When Ready

```bash
# Create isolated worktree
cd /Users/andriileukhin/Documents/SovereignNexus
git worktree add .claude/worktrees/phase25-wave1

# Enter worktree
cd .claude/worktrees/phase25-wave1

# Read the spec
cat ../../HANDOFF.md

# Start: Task 1 (ReBAC Foundation)
# TDD: write failing tests → implement → cargo test → clippy clean
```

**Estimated time:** 4-6 hours  
**Output:** 12+ tests passing, Schema locked, Ready for Wave 2 parallel agents

---

## Parallel Execution (Future)

When you spawn agents for Wave 2 (AP2 Evaluator, TemporalGuard, PolicyEngine):

```bash
# Each agent gets the plan
cat .claude/plans/pure-wondering-bentley.md  # Phase 25 details

# All agents share:
crates/siss-governance/           # DecisionStore trait
crates/siss-behavioral-firewall/  # Shared crate they extend
.smaos/KANBAN.md                  # Coordination board
.smaos/exec/EXEC_LOG.json         # Audit trail
```

---

## Verify Everything Works

```bash
# DECISION-DB tests
cargo test -q -p siss-governance

# Kanban sync script
python3 .smaos/scripts/sync_kanban.py --mode manual

# Check board
cat .smaos/KANBAN.md
cat .smaos/exec/EXEC_LOG.json
```

All green? You're good. Session independence confirmed.
