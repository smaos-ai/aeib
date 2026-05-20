# [SOVEREIGN ARTIFACT] Engineering Runbook: siss-agent-shell Membrane Implementation

## 1. Architectural Overview
The `siss-agent-shell` is the execution membrane (Operator Plane) that bridges your local terminal agent (Claude Code / OpenClaw) with the Axum API (Cognitive Plane) and Agent of Empires (AoE) orchestrator. 

This membrane enforces the **Correctness Doctrine** and the **Fail-Closed State** by acting as an interceptor. It uses Agent-User Interaction Protocol (AG-UI) to stream telemetry and leverages Claude Code's deterministic lifecycle hooks to enforce the $\delta^+$ (displacement) safety geometry.

## 2. Phase 26 Implementation Steps

### Step 1: The AG-UI SSE Streaming Loop (Rust / TypeScript Bridge)
The AG-UI protocol acts as a middleware that translates raw framework events into a standardized Server-Sent Events (SSE) stream. Your first task is to build the SSE consumer that listens to the Axum endpoints built in Phase 24/25.

**Requirements:**
*   Implement an asynchronous SSE listener connecting to `/api/graph/projections/actions` and `/api/graph/projections/anomalies`.
*   Maintain connection stability: use an `AbortController` to cancel stale fetch requests, and implement a 5-second polling fallback with exponential backoff if the SSE drops.
*   Route incoming `TEXT_MESSAGE_CONTENT` or `TOOL_CALL_START` events to the local Agent of Empires tmux status bar.

### Step 2: Deterministic Lifecycle Hooks (Security & Logging)
Agents must not execute tools blindly. You will implement explicit `PreToolUse` and `PostToolUse` hook scripts registered in `.claude/settings.json`.

**A. The $\delta^+$ Safety Gate (`PreToolUse`)**
Create `scripts/hooks/pre_tool_use_gate.ts`. This script intercepts every tool call before execution.
*   **Logic:** Parse the intended command. If it touches protected directories (e.g., `.git`, `.claude/skills`), requires AP2 cryptographic mandates, or attempts destructive actions (`rm -rf`, `drop table`), it must be intercepted.
*   **Execution:** The hook must output a JSON response. To block, it must return a strict denial. To allow safely, it can modify the inputs by returning `updatedInput` alongside `permissionDecision: "allow"` or `"ask"`.

**B. The Provenance Ledger (`PostToolUse`)**
Create `scripts/hooks/post_tool_use_logger.ts`. 
*   **Logic:** Capture the output, execution time, and `tool_use_id`. 
*   **Execution:** Push this data securely to the `siss-graph-db` (Axum API) via an HTTP POST request to ensure an immutable audit trail of the agent's actions in the KuzuDB/LadybugDB graph.

### Step 3: Agent of Empires (AoE) Integration
The shell must integrate cleanly with the Operator Plane. Agent of Empires runs each agent in its own isolated `tmux` session, meaning the agents keep running when the TUI is closed.
*   Configure the membrane to emit status detection flags (`running`, `waiting`, `idle`, `error`) directly to standard output so AoE can parse them for the Web Dashboard and TUI.
*   Ensure that if the `siss-agent-shell` receives a `Ctrl+B` backgrounding command or an interruption, it gracefully suspends the tool execution and logs the state change.

### Step 4: Verification (TDD Requirements)
Before passing the code back to the Reviewer agent, the Writer must prove the membrane works:
1.  **Mock a malicious tool call** and verify the `PreToolUse` hook successfully blocks it with an exit code 2 and a clean `stderr` message.
2.  **Simulate an SSE disconnect** and verify the `AbortController` cleanly tears down the connection without leaking memory.
3.  **Run in a mock tmux session** and verify the output formatting doesn't break the AoE UI parser.
