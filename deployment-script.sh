#!/bin/bash
# Night Shift Grid — host tmux + git worktrees + Claude /loop (no Docker)
set -euo pipefail

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
cd "$WORKDIR"
BASE_REF="${NIGHT_SHIFT_BASE_REF:-main}"
CLAUDE_FLAGS="${CLAUDE_FLAGS:---dangerously-skip-permissions --permission-mode acceptEdits}"

tmux start-server 2>/dev/null || true
command -v tmux >/dev/null || { echo "tmux required"; exit 1; }
command -v claude >/dev/null || { echo "claude CLI required"; exit 1; }

echo "=== NIGHT SHIFT GRID (HOST) ==="

echo "Phase 1: Purge"
for i in 1 2 3 4; do tmux kill-session -t "night-agent-$i" 2>/dev/null || true; done
git worktree remove .claude/worktrees/night-agent-1 -f 2>/dev/null || true
git worktree remove .claude/worktrees/night-agent-2 -f 2>/dev/null || true
git worktree remove .claude/worktrees/night-agent-3 -f 2>/dev/null || true
git worktree remove .claude/worktrees/night-agent-4 -f 2>/dev/null || true
git branch -D night/agent-1-multiregion night/agent-2-sla night/agent-3-integration night/agent-4-chaos 2>/dev/null || true

echo "Phase 2: Worktrees"
mkdir -p .claude/worktrees
git worktree add -b night/agent-1-multiregion .claude/worktrees/night-agent-1 "$BASE_REF"
git worktree add -b night/agent-2-sla .claude/worktrees/night-agent-2 "$BASE_REF"
git worktree add -b night/agent-3-integration .claude/worktrees/night-agent-3 "$BASE_REF"
git worktree add -b night/agent-4-chaos .claude/worktrees/night-agent-4 "$BASE_REF"

echo "Phase 3: Tmux + Claude"
tmux new-session -d -s night-agent-1 -c "$WORKDIR/.claude/worktrees/night-agent-1" "claude $CLAUDE_FLAGS"
tmux new-session -d -s night-agent-2 -c "$WORKDIR/.claude/worktrees/night-agent-2" "claude $CLAUDE_FLAGS"
tmux new-session -d -s night-agent-3 -c "$WORKDIR/.claude/worktrees/night-agent-3" "claude $CLAUDE_FLAGS"
tmux new-session -d -s night-agent-4 -c "$WORKDIR/.claude/worktrees/night-agent-4" "claude $CLAUDE_FLAGS"
sleep 15

echo "Phase 4: /loop injection"
tmux send-keys -t night-agent-1 "/loop 15m Run the 5 manual integration tests for the Prague-Frankfurt staging environment. Verify cross-region replication and simulate a health check failover scenario. Log all anomalies to MULTI_REGION_REPORT.md." Enter
tmux send-keys -t night-agent-2 "/loop 10m Monitor the port 9000 dashboard endpoint. Validate the alert triggering and acknowledgment flow. Attempt manual failover endpoints and log uptime status to SLA_REPORT.md." Enter
tmux send-keys -t night-agent-3 "/loop 30m Execute the end-to-end pilot workflow integration test. Simulate 1000 trade orders and 500 hypotheses. Verify the persistence, veto, metrics, and security layers are functioning cohesively. Log bottlenecks to INTEGRATION_REPORT.md." Enter
tmux send-keys -t night-agent-4 "/loop 45m Run the 12 failure scenarios from the siss-chaos-petri matrix. Inject infrastructure failures and resource constraints into the staging environment and measure system drift. Output results to CHAOS_REPORT.md." Enter

echo ""
echo "=== GRID ACTIVE ==="
git worktree list | grep night-agent
tmux list-sessions | grep night-agent
echo "Monitor: tmux attach-session -t night-agent-1"
