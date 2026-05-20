# Specification: Phase 31 — Real-Time Agent Observability (AG-UI Foundation)

## Goal

Enable operators to monitor 5 concurrent agents executing in parallel with live SSE streaming, real-time task status dashboards, and human-in-the-loop control (pause/resume/abort). This is the foundational observability layer that makes Advanced Worktree Orchestration (Phase 30) operationally viable.

## One Thing (Singular Focus)

**Stream live execution events from parallel agents to an operator cockpit dashboard, allowing human operators to see what agents are doing in real-time and intervene (pause/resume/abort) with <500ms latency.**

## Success Criteria

- [ ] SSE endpoint `/api/agents/stream` broadcasts all framework events (task assignment, tool calls, outputs, completions) in real-time
- [ ] Cockpit dashboard displays 5 concurrent agents with live status, task progress, and output streaming
- [ ] Operators can pause, resume, abort individual agents via UI buttons with <100ms response time
- [ ] Agent execution pauses reliably when operator clicks pause button; resumes from exact state on resume
- [ ] SSE stream handles agent disconnects gracefully with automatic reconnect and state reconstruction
- [ ] <500ms latency from agent event emission to UI display (measured end-to-end)
- [ ] All integration tests pass (TDD: tests first, then implementation)
- [ ] Zero type errors (cargo check passes)
- [ ] Zero new clippy warnings (cargo clippy --all)
- [ ] Cockpit handles 5 agents streaming output concurrently without losing events or UI lag

## Architecture

### Phase 31 Delta
Adds observable streaming layer to Phase 30 dispatcher. No changes to existing worktree orchestration logic; only adds monitoring infrastructure.

### New Modules
1. **`crates/siss-ag-ui/`** — AG-UI implementation (Agent-to-User Interface)
   - `event_stream.rs`: Translates Phase 30 task execution events into SSE-compatible event envelope
   - `event_types.rs`: Core types (TaskAssigned, ToolCallStarted, OutputStreamed, TaskCompleted, AgentPaused)
   - `encoder.rs`: Serialize events to SSE format (newline-delimited JSON)
   - Public API: `AgEventStreamBroadcaster { broadcast(event: AgEvent) }`

2. **`crates/siss-cockpit/`** — Operator dashboard (HTTP server)
   - `handlers/stream.rs`: SSE endpoint that broadcasts all live events
   - `handlers/control.rs`: Pause/resume/abort endpoints (send control signals back to agents)
   - `state.rs`: In-memory event log + agent status cache
   - `ui/index.html`: Single-page dashboard with live agent cards, streaming output panel, control buttons
   - Public API: `CockpitServer::run(port: u16)`

### Modified Modules
1. **`crates/siss-dispatcher/`** (Phase 30)
   - `executor.rs`: After `spawn`, initialize `AgEventStreamBroadcaster` and register agent
   - Hook execution events: on task assignment, tool call, output, task completion → emit to broadcaster
   - Listen for control signals from cockpit (pause/resume) and apply to running agents

2. **`crates/siss-agent-shell/`** (Phase 26 extension)
   - Hook SSE events into existing execution boundary
   - `shell.rs`: On each `spawn()` call, create event emitter for that agent
   - Emit: task start, tool call, streaming output, task completion, errors

### Dependencies
- `tokio`: Async runtime (already in workspace)
- `axum`: HTTP server for cockpit (add to `Cargo.toml`)
- `futures`: Event broadcasting (already in workspace)
- `serde_json`: Event serialization (already in workspace)

### Data Flow
```
Agent Execution → emit AgEvent → AgEventStreamBroadcaster
                                        ↓
                         Cockpit SSE endpoint /api/agents/stream
                                        ↓
                         UI (WebSocket equivalent via SSE)
                                        ↓
                         Operator clicks "Pause Agent 3"
                                        ↓
                         Control signal → Dispatcher → Agent 3
```

### Design Decisions

| Decision | Rationale | Alternative Rejected |
|----------|-----------|---------------------|
| SSE not WebSocket | SSE is simpler for server-push; operators don't need bidirectional interactive control yet | WebSocket adds complexity; SSE sufficient for MVP |
| In-memory event log | Fast, simple for MVP; no database dependency | Persistent storage adds operational overhead |
| Single dashboard process | Simplified architecture for Phase 31; scale to multiple dashboards in Phase 33 | Distributed dashboard adds complexity |
| Pause = task checkpoint, not kill | Allows resuming mid-execution; safer for long-running operations | Kill is simpler but loses progress |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Event Ordering** — Events arrive out-of-order at UI, confusing operators | HIGH | Assign monotonic event ID; UI sorts/filters by ID. Test with concurrent 5-agent scenario. |
| **SSE Connection Loss** — Operator disconnects; misses events; reconnects to stale state | HIGH | Maintain rolling 1000-event buffer; on reconnect, send buffered events before new ones. |
| **Performance Degradation** — 5 agents × 100 events/sec = 500 EPS; browser can't render fast | HIGH | Batch events (send every 100ms); aggregate stdout (don't stream every char). Rate-limit event broadcast. |
| **State Desynchronization** — UI says "paused" but agent is still running | MEDIUM | Pause signal is idempotent; agent acks pause before UI updates. Cockpit polls agent status every 500ms. |
| **Malformed Events** — Agent sends invalid JSON; SSE stream breaks | MEDIUM | Validate event in broadcaster before emit; log invalid events; continue. Fail gracefully (don't crash stream). |
| **Resource Leaks** — Each agent holds event broadcaster reference; not released on cleanup | MEDIUM | Explicit broadcaster.deregister(agent_id) on Phase 30 cleanup. Test for goroutine/task leaks. |

## Questions for User

1. **Scope for Phase 31:** Should we include A2UI (declarative UI components) in this phase, or defer to Phase 32? Recommendation: defer. Phase 31 focus is streaming + monitoring + pause/resume. A2UI is a separate subsystem.

2. **Pause semantics:** When operator pauses Agent 3, should it:
   - Option A: Pause after current tool completes (clean checkpoint)
   - Option B: Pause immediately mid-tool (may lose state)
   - Recommendation: Option A (safer, more predictable recovery)

3. **Cockpit hosting:** Should cockpit run:
   - Option A: Standalone HTTP server (recommended for simplicity)
   - Option B: Integrated into dispatcher (adds coupling)
   - Recommendation: Option A (separate concerns)

4. **Event retention:** How many events should cockpit buffer?
   - Option A: Last 100 events per agent
   - Option B: Last 1000 events across all agents
   - Recommendation: Option B (safer for reconnects)

## Testing Strategy (TDD First)

Tests in `crates/demo-app/tests/phase_31_ag_ui_integration_test.rs`:
1. `test_ag_ui_broadcaster_emits_event_on_task_assignment` → subscribe, assert event received
2. `test_cockpit_sse_stream_broadcasts_all_events` → agent emits 5 events, SSE stream has 5
3. `test_cockpit_pause_signal_pauses_agent_execution` → emit pause signal, agent stops mid-task
4. `test_cockpit_resume_signal_resumes_from_checkpoint` → pause, resume, verify task completes
5. `test_event_ordering_maintained_under_5_concurrent_agents` → 5 agents, 100 events each, verify order
6. `test_sse_connection_loss_and_reconnect_with_buffered_events` → disconnect, reconnect, verify all events received
7. `test_cockpit_ui_renders_5_agent_cards_with_live_status` → browser integration test (optional for MVP)
8. `test_agent_pause_acks_before_continuing` → pause idempotency test

## Non-Goals (Phase 32+)

- A2UI component system (Phase 32)
- Persistent event storage (Phase 34)
- Multi-cockpit coordination (Phase 33)
- Advanced anomaly visualization (Phase 34)
- Agent-to-agent communication (Phase 32)

## Files to Create/Modify

| File | Action | Lines |
|------|--------|-------|
| `crates/siss-ag-ui/Cargo.toml` | Create | 15 |
| `crates/siss-ag-ui/src/lib.rs` | Create | 5 |
| `crates/siss-ag-ui/src/event_stream.rs` | Create | 120 |
| `crates/siss-ag-ui/src/event_types.rs` | Create | 80 |
| `crates/siss-ag-ui/src/encoder.rs` | Create | 60 |
| `crates/siss-cockpit/Cargo.toml` | Create | 20 |
| `crates/siss-cockpit/src/lib.rs` | Create | 5 |
| `crates/siss-cockpit/src/server.rs` | Create | 150 |
| `crates/siss-cockpit/src/handlers/stream.rs` | Create | 100 |
| `crates/siss-cockpit/src/handlers/control.rs` | Create | 80 |
| `crates/siss-cockpit/src/state.rs` | Create | 90 |
| `crates/siss-cockpit/ui/index.html` | Create | 200 |
| `crates/siss-cockpit/ui/dashboard.js` | Create | 250 |
| `crates/siss-dispatcher/src/executor.rs` | Modify | +50 lines (AG-UI integration) |
| `crates/siss-agent-shell/src/shell.rs` | Modify | +30 lines (event emission) |
| `Cargo.toml` (workspace) | Modify | +2 members |
| `crates/demo-app/tests/phase_31_ag_ui_integration_test.rs` | Create | 400 |

**Total:** ~1,700 lines of new code + tests.

## Verification Checklist (for `/verify` phase)

- [ ] All 8 integration tests pass
- [ ] Cockpit server starts on port 8080 without errors
- [ ] SSE stream `/api/agents/stream` emits live events
- [ ] Pause/resume endpoints work with <100ms latency
- [ ] 5 agents can run concurrently; cockpit shows all 5 live
- [ ] Broadcaster deregisters agents on cleanup (no resource leaks)
- [ ] cargo check passes (zero type errors)
- [ ] cargo clippy --all passes (zero new warnings)
- [ ] All Phase 30 tests still pass (no regressions)

