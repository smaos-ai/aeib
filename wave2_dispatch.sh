#!/bin/bash
set -e

echo "🚀 PHASE 32 WAVE 2: Dispatching 3 Parallel Agents..."
echo ""
echo "Agent A: Task 2 (Validator) — spawning in task2-a2ui-validator"
echo "Agent B: Task 3 (SSE+Renderer) — spawning in task3-cockpit-sse-renderer"
echo "Agent C: Task 4 (Dashboard UI) — spawning in task4-dashboard-ui"
echo ""
echo "All 3 agents will run concurrently. Using 'wait' to block until completion."
echo ""

# Task 2: Agent-Side Validator (Agent A)
claude -p "Read @WAVE_ORCHESTRATOR.md and @HANDOFF-PHASE32.md. You are WAVE 2: TASK 2 (Agent Validator). Implement A2UIComponent::validate() in siss-agent-shell/src/a2ui/validator.rs. Validate all Form components (Input, Select, Checkbox, Radio) have non-empty id field. Return Result<(), ValidationError>. Exit criteria: cargo check -p siss-agent-shell passes. Commit and merge to main." --worktree task2-a2ui-validator &
AGENT_A_PID=$!

# Task 3: Cockpit SSE + Renderer (Agent B)
claude -p "Read @WAVE_ORCHESTRATOR.md and @HANDOFF-PHASE32.md. You are WAVE 2: TASK 3 (Cockpit SSE + Renderer). Implement real Axum handlers in siss-cockpit: CockpitState with broadcast::Sender + 1000-event buffer. GET /api/agents/stream (SSE). POST /api/agents/:id/{pause,resume,abort}. POST /api/agents/:id/form-submit. A2UIComponent renderer (all 18 types to HTML). Pattern: clone from siss-enclave/src/api/ag_ui.rs. Exit criteria: cargo check -p siss-cockpit passes. Commit and merge to main." --worktree task3-cockpit-sse-renderer &
AGENT_B_PID=$!

# Task 4: Dashboard UI Components (Agent C)
claude -p "Read @WAVE_ORCHESTRATOR.md and @HANDOFF-PHASE32.md. You are WAVE 2: TASK 4 (Dashboard UI). Implement components.js (renderComponent(comp) for all 18 types) and form-handler.js (form submit + SSE response routing). Vanilla JS, no framework. Exit criteria: opens in browser, renders all 18 components, no console errors. Commit and merge to main." --worktree task4-dashboard-ui &
AGENT_C_PID=$!

echo "Monitoring agents..."
echo "Agent A (Validator) PID: $AGENT_A_PID"
echo "Agent B (SSE+Renderer) PID: $AGENT_B_PID"
echo "Agent C (Dashboard UI) PID: $AGENT_C_PID"
echo ""

# Wait for all agents to complete
wait $AGENT_A_PID $AGENT_B_PID $AGENT_C_PID

echo ""
echo "✅ Wave 2 Complete. All 3 agents merged to main."
