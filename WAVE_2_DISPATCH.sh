#!/bin/bash
# Phase 31 Wave 2 Parallel Dispatch
# 3 agents, zero file conflicts, locked contracts

set -e

echo "🚀 WAVE 2: Dispatching 3 parallel agents..."
echo "Each agent reads WAVE_ORCHESTRATOR.md and implements strictly against locked contracts."
echo ""

# Task 2: Dispatcher Event Integration (Agent A)
echo "📍 Task 2: Dispatcher Integration — starting in worktree task2-dispatcher"
echo "   Owns: crates/siss-dispatcher/src/executor.rs, Cargo.toml"
echo ""

# Task 3: Cockpit SSE Server (Agent B)
echo "📍 Task 3: Cockpit SSE Server — starting in worktree task3-cockpit-sse"
echo "   Owns: crates/siss-cockpit/src/{server,state,handlers}/"
echo ""

# Task 4: Dashboard UI (Agent C)
echo "📍 Task 4: Dashboard UI — starting in worktree task4-dashboard-ui"
echo "   Owns: crates/siss-cockpit/ui/{index.html,dashboard.js}"
echo ""

echo "⏱️  All agents will run in parallel. Use 'wait' to block until all complete."
echo "✅ Exit code 0 when all agents merge to main."
echo ""

