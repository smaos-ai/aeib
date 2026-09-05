# Phase 3 Part 1: Architecture Design
## Enterprise Features & Advanced Consensus (Jun 2027 - Dec 2027)

**Author:** Architecture Review (Phase 3 Planning)  
**Status:** ARCHITECTURE DESIGN ONLY (No Code Implementation)  
**Timeline:** 2 weeks design review (Sep 5-22, 2026) → 6 months execution (Jun-Dec 2027)  
**Execution Context:** After Phase 1 delivery (May 31, 2027) and Phase 2 completion (Jun 1, 2027)  
**Dependencies:** Phase 1 & Phase 2 complete; no blocking dependencies within Phase 3  
**Risk Level:** MEDIUM (consensus protocols are complex; robotics integration requires hardware)

---

## Executive Summary

Phase 3 Part 1 extends SMAOS with enterprise-grade consensus, dynamic agent management, distributed observability, drift detection, and robotics control. This design builds on 104 existing SISS infrastructure crates, leveraging Phase 1's proof layer (L8) and Phase 2's agent swarm (L4).

**5 Core Subsystems:**
1. **PBFT 3-of-5 Agent Consensus** — Byzantine Fault Tolerant decision-making for critical operations
2. **Advanced Agent Pool Management** — Dynamic spawning, graceful shutdown, state migration
3. **Distributed Tracing & Observability** — OpenTelemetry integration, cross-agent trace propagation
4. **Chronicle Cognitive Drift Detection** — Rolling 100-decision analysis, RAGAS deviation signals
5. **Advanced Robotics Integration** — UR10e cobot control, safety boundary enforcement, MuJoCo simulation

**Deliverable:** 1,500-2,000 LOC per subsystem (7,500-10,000 LOC total) + comprehensive test suite

---

## 1. PBFT 3-of-5 Agent Consensus (L3 Enterprise)

### 1.1 Overview

Extend existing `siss-swarm-consensus` BFT engine to support 3-of-5 quorum voting for high-stakes decisions. Use Practical Byzantine Fault Tolerance (PBFT) with Merkle root commitments for cryptographic finality.

**Key Invariant:** Any 3 agents must agree on a decision before execution. Up to 2 agents can fail (crash or Byzantine).

### 1.2 Current State (Phase 2 Baseline)

`siss-swarm-consensus/src/bft_engine.rs`:
- ✅ Agent registration with Ed25519 public keys
- ✅ Vote registration and counting
- ✅ Quorum validation (f < n/3 model)
- ✅ Merkle root verification
- ❌ View change protocol (leader rotation on timeout)
- ❌ Multi-round PBFT (pre-prepare → prepare → commit)
- ❌ Crash recovery with checkpoints

### 1.3 Design: Extended PBFT Protocol

#### Phase 1: Pre-prepare (Leader Election)
```
Leader (agent 0):
1. Receives intent from L4 orchestration
2. Wraps in Proposal { id, view, content, digest }
3. Broadcasts Pre-prepare { proposal, leader_sig } to agents 1, 2, 3, 4
4. Logs to L8 proof ledger: "Leader proposed X"

Follower (agent i):
1. Validates proposal structure + leader signature
2. Checks digest against content hash
3. Accepts if no conflicting prepare in same view
4. Moves to Phase 2 (prepare)
```

#### Phase 2: Prepare
```
Follower (agent i):
1. Broadcasts Prepare { proposal_id, view, digest, sig } to all agents
2. Waits for 2f+1 = 3 prepares (including self)
3. On quorum: moves to Phase 3 (commit), logs: "Prepared X"

Leader (agent 0):
1. Collects 2f+1 prepares
2. Broadcasts Prepare-ack { proposal_id, view, digest, sig_count }
3. Signals "Prepared" to followers
```

#### Phase 3: Commit
```
All agents:
1. Once 2f+1 prepares seen, broadcast Commit { proposal_id, view, sig }
2. Wait for 2f+1 = 3 commits
3. On quorum: execute intent, write ledger entry, emit proof
4. Log: "Committed X" → immutable in L8 ledger

Finality: Once 3 agents have committed, decision is Byzantine-final.
No reversion possible (even if all other agents crash).
```

#### Phase 4: View Change (Leader Rotation)
```
Trigger: Leader timeout (>500ms without progress) OR leader detected Byzantine
Initiator: Any agent
Protocol:
1. Agent broadcasts ViewChange { new_view, proof_of_timeout, sig }
2. New leader = (view_number % 5)
3. New leader waits for 2f+1 = 3 ViewChange messages
4. Broadcasts NewView { proposals_to_commit, new_view, aggregate_sig }
5. Followers validate and apply commits from previous leader
6. Resume normal operation with new leader

Edge Case: If new leader also times out, trigger view_change again.
```

### 1.4 Merkle Checkpoint Design

Every 10 committed proposals (configurable):
```rust
struct Checkpoint {
    proposal_count: u64,
    merkle_root: [u8; 32],
    timestamp: i64,
    proving_agents: [Uuid; 3],  // 3 agents that signed proof
    aggregate_signature: [u8; 96],  // BLS aggregate
}
```

Checkpoints stored in `l8-proof` ledger table: `consensus_checkpoints`

Purpose: Crash recovery. Agent rejoins → validates checkpoints → resumes from latest checkpoint.

### 1.5 Crash Recovery

```
1. Agent A crashes and restarts
2. Queries l8-proof.consensus_checkpoints, finds latest at proposal N
3. Fetches proposals N+1..M from other agents (via siss-a2a-dispatcher)
4. Validates each proposal's Merkle proof against checkpoint
5. Applies valid proposals to local state
6. Resumes normal protocol at proposal M+1
7. If recovery takes >2s, viewed as Byzantine → peers skip it for quorum
```

### 1.6 Integration Points

| Component | Interface | Pub/Sub |
|-----------|-----------|---------|
| `l4-orchestration` (LangGraph) | Submit intent → `submit_proposal(intent)` → returns ConsensusProof | Sync RPC |
| `l8-proof` (Merkle ledger) | Write checkpoints & committed proposals | SQL insert |
| `siss-a2a-dispatcher` | Fetch proposals from peer agents | MCP call |
| `siss-vault-integration` | Load/validate Ed25519 keys for signatures | Sync KMS |
| `siss-otel-tracer` | Emit spans: "pbft.pre_prepare", "pbft.prepare", "pbft.commit", "pbft.view_change" | OpenTelemetry |
| `siss-event-log` | Log Byzantine violations (e.g., agent votes for 2 different proposals) | Event queue |

### 1.7 Test Strategy

**Unit Tests (vitest):**
- Quorum calculation for 5, 7, 9, 11 agents (PBFT formula: 2f+1 for f failures)
- Merkle root verification (matching Phase 1 L8 ledger style)
- View change transitions
- Checkpoint creation and validation

**Integration Tests (Playwright):**
- Happy path: 5 agents → pre-prepare → prepare → commit (10s end-to-end)
- Leader timeout: Agent 0 silent for 1s → agents elect agent 1 → resume
- Byzantine agent: Agent 2 votes for 2 different proposals → quorum still reaches (skips agent 2)
- Crash recovery: Kill agent A during commit phase → restart → validate recovered state

**Load Test (siss-sla-monitor):**
- 100 concurrent proposals (agents process sequentially per view)
- Measure: commit latency (target <500ms), checkpoint overhead (<1%)
- Thermal monitoring: Merkle proof generation CPU cost

### 1.8 New Crate: `siss-consensus-extended`

```
crates/siss-consensus-extended/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── pbft_engine.rs (2-3-of-5 multi-round protocol, 400 LOC)
│   ├── view_change.rs (leader rotation, 200 LOC)
│   ├── checkpoint.rs (crash recovery, 200 LOC)
│   └── byzantine_detection.rs (misbehavior tracking, 150 LOC)
├── tests/
│   ├── test_consensus_happy_path.rs (100 LOC)
│   ├── test_view_change.rs (100 LOC)
│   └── test_crash_recovery.rs (150 LOC)
└── benches/
    └── consensus_latency.rs (100 LOC)
```

---

## 2. Advanced Agent Pool Management (L4 Enterprise)

### 2.1 Overview

Extend `siss-agent-shell` + `siss-swarm-coordinator` to dynamically spawn agents based on workload, migrate state between agents, and enforce graceful shutdown. Target: support 50-1,000 concurrent agents per machine.

### 2.2 Current State

`siss-agent-shell/src/lib.rs`:
- ✅ Agent lifecycle (spawn, register, metadata)
- ✅ Job routing (intent → agent assignment)
- ✅ Context cartography (scope tracking)
- ❌ Dynamic spawning based on CPU/memory
- ❌ State migration (draining agent → moving in-flight tasks to sibling)
- ❌ Graceful shutdown coordination

### 2.3 Design: Pool Architecture

#### Pool Composition
```rust
struct AgentPool {
    config: PoolConfig,  // min_agents=3, max_agents=1000, cpu_threshold=80%
    active_agents: Arc<DashMap<Uuid, AgentHandle>>,  // live agents
    waiting_queue: Arc<Mutex<VecDeque<Intent>>>,  // backlog
    drain_set: Arc<DashSet<Uuid>>,  // agents shutting down
    metrics: Arc<PoolMetrics>,
}

struct PoolConfig {
    min_agents: usize,  // minimum pool size
    max_agents: usize,
    cpu_threshold: u8,  // % CPU usage triggering spawn
    memory_threshold_mb: u64,
    drain_timeout_secs: u64,  // max wait for in-flight tasks before force-kill
    migration_batch_size: usize,  // tasks per drain cycle
}

struct PoolMetrics {
    agents_count: u64,
    avg_latency_ms: f64,
    pending_intents: u64,
    drain_in_progress: u64,
    spawn_errors: u64,
}
```

#### Spawn Decision Logic
```
Every 1 second:
1. Read CPU utilization from l6-infrastructure
2. Count pending intents in waiting_queue
3. If (cpu > cpu_threshold OR pending > 10 * active_agents) AND active_agents < max_agents:
   → Spawn 1 new agent
4. If (cpu < 50% AND pending < active_agents / 2) AND active_agents > min_agents:
   → Initiate drain of 1 agent
5. Emit metric: pool.agents_count

Decision trees logged to siss-event-log with timestamp.
```

#### State Migration on Drain
```
Agent A marked for drain:
1. Stop accepting NEW intents (set drain flag)
2. Query l2-knowledge pgvector: in-flight tasks for agent A
3. For each task:
   a. Serialize task state: (intent, trace_so_far, next_checkpoint)
   b. Pick migration target: least-busy agent B (from active_agents)
   c. Send migration request via siss-a2a-dispatcher:
      MigrateTask { task_id, intent, trace, state_root }
   d. Agent B validates trace Merkle proof, accepts task
   e. Agent B resumes from checkpoint
4. On completion of all migrations (timeout: drain_timeout_secs):
   a. Send shutdown signal to agent A
   b. Agent A flushes L8 ledger, closes DB connections
   c. Agent A exits process, freeing resources

Edge case: Agent A never acks migration → mark agent A as Byzantine,
force-kill after timeout, retry migration to agent C.
```

#### Graceful Shutdown Sequence
```
External signal (SIGTERM) to pool orchestrator:
1. Set pool.shutdown = true
2. Stop accepting new intents
3. Initiate drain for ALL agents simultaneously (parallel)
4. Wait for all agents to complete in-flight tasks (with timeout)
5. Shutdown order:
   a. Flush all ledger entries to l8-proof (atomic batch write)
   b. Save pgvector checkpoints to l2-knowledge
   c. Emit final metrics to siss-metrics
   d. Signal siss-observability: "pool.shutdown_complete"
   e. Exit pool process

Total shutdown latency target: <5 seconds for clean pool, <30s with stragglers
```

### 2.4 Pool Observability

Every agent publishes metrics every 100ms:
```
siss-metrics schema:
├── agent.{agent_id}.latency_ms (gauge)
├── agent.{agent_id}.tasks_in_flight (gauge)
├── agent.{agent_id}.cpu_percent (gauge)
├── agent.{agent_id}.memory_mb (gauge)
└── agent.{agent_id}.state (enum: active | draining | shutdown)

Pool publishes every 1s:
├── pool.agents_active (gauge)
├── pool.agents_draining (gauge)
├── pool.pending_intents (gauge)
├── pool.spawn_rate_per_min (counter)
└── pool.migration_errors (counter)
```

Dashboard: OpenTelemetry consumer reads metrics → auto-scales pool

### 2.5 Integration Points

| Component | Interface | Direction |
|-----------|-----------|-----------|
| `l6-infrastructure` | `get_cpu_utilization()` | Read (1s polling) |
| `l2-knowledge` | Query in-flight task state | SQL read/write |
| `l4-orchestration` | `submit_intent(intent)` → enqueue | RPC |
| `l8-proof` | Write migration records, shutdown checkpoint | SQL insert |
| `siss-a2a-dispatcher` | Send MigrateTask, ReceiveMigratedTask | MCP |
| `siss-otel-tracer` | Emit pool.spawn, pool.drain, pool.migrate spans | OpenTelemetry |
| `siss-observability` | Read pool metrics for autoscale policy | SQL read |

### 2.6 New Crate: `siss-agent-pool`

```
crates/siss-agent-pool/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── pool.rs (main pool struct, spawn/drain logic, 500 LOC)
│   ├── migration.rs (state serialization & migration protocol, 300 LOC)
│   ├── metrics.rs (pool metrics aggregation, 200 LOC)
│   └── shutdown.rs (graceful shutdown orchestration, 200 LOC)
├── tests/
│   ├── test_spawn_and_drain.rs (150 LOC)
│   ├── test_migration.rs (200 LOC)
│   └── test_graceful_shutdown.rs (100 LOC)
└── benches/
    └── pool_throughput.rs (100 LOC)
```

---

## 3. Distributed Tracing & Observability (L5 Enterprise)

### 3.1 Overview

Integrate OpenTelemetry (OTEL) with existing `siss-otel-tracer` + `siss-observability`. Enable cross-agent trace propagation, distributed context correlation, and performance SLA enforcement.

### 3.2 Current State

`siss-otel-tracer/src/lib.rs`:
- ✅ Basic OTEL types (TraceId, SpanId, attributes)
- ✅ Span creation and end
- ❌ W3C Trace Context headers (for cross-process propagation)
- ❌ Sampled span exporting to backend
- ❌ Baggage propagation (correlation IDs)
- ❌ SLA gates (alert if p99 latency > threshold)

`siss-observability/src/lib.rs`:
- ✅ Merkle tracer (Merkle-signed proof of execution order)
- ✅ Trace logger (structured JSON logs)
- ✅ Metrics aggregator
- ❌ Real-time SLA dashboard
- ❌ Cross-agent trace stitching

### 3.3 Design: Distributed Tracing with OTEL

#### Trace Context Propagation

Every RPC call (via `siss-a2a-dispatcher`) includes W3C Trace Context header:
```
traceparent: 00-{trace_id}-{parent_span_id}-{trace_flags}
    Hex format: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
    (version-trace_id-parent_span_id-sampled)

tracestate: vendor=value,vendor2=value2
    Example: tracestate=siss=agent0,phase=prepare
```

When agent B receives RPC from agent A:
1. Extract traceparent header
2. Create new span under parent_span_id
3. Add span: "a2a_message_received" → parent={parent_span_id}
4. Execute work
5. Emit child spans: "consensus.prepare", "ledger.write"
6. Propagate trace_id + new span_id in response header

Result: Single trace tree spans across all 5 agents' execution paths.

#### Baggage (Correlation Context)

Request header:
```
baggage: trace_id=4bf92f3577b34da6a3ce929d0e0e4736, intent_id=uuid-123, user=treasury_officer
```

Propagated through all downstream calls. Baggage indexed in Jaeger/Tempo:
- Query: "all spans for intent_id=uuid-123" → see full multi-agent flow
- Filter: "all spans by user=treasury_officer" → audit trail

#### Sampled Export

Only 1% of traces exported (configurable sampler: `TraceSampleRate = 0.01`).

Export target: OpenTelemetry Collector (optional external service or local:4317)
```
Agent → OTEL SDK → local collector → optional Jaeger/Tempo backend
```

If collector unavailable: traces discarded (no blocking). Local Merkle tracer still records to ledger.

### 3.4 SLA Gates

```rust
struct SLAGate {
    name: &str,  // "consensus_commit_latency"
    p99_threshold_ms: f64,
    check_interval_secs: u64,
}

let gates = vec![
    SLAGate { name: "pbft_prepare", p99_threshold_ms: 100.0, check_interval_secs: 10 },
    SLAGate { name: "pbft_commit", p99_threshold_ms: 200.0, check_interval_secs: 10 },
    SLAGate { name: "a2a_handoff", p99_threshold_ms: 50.0, check_interval_secs: 10 },
    SLAGate { name: "pool_spawn", p99_threshold_ms: 500.0, check_interval_secs: 60 },
];
```

Every check_interval_secs:
1. Query siss-metrics: p99 latency for span "pbft_prepare" over past 10s
2. If p99 > threshold:
   a. Emit alert to siss-event-log: "SLA_BREACH: pbft_prepare p99=250ms > 100ms"
   b. Trigger optional escalation: call supervisor agent, trigger chaos test
3. If p99 recovering: emit "SLA_RECOVER" event

Ledger entry:
```
INSERT INTO l8-proof.sla_violations (
  span_name, threshold_ms, observed_p99_ms, timestamp, trigger_action
)
```

### 3.5 Trace Stitching for Merkle Audit

Goal: Prove that agent A → agent B → agent C executed in order, with cryptographic proof.

Each agent emits Merkle tracer span:
```
Agent A:
  span_start("consensus.pre_prepare", attributes={proposal_id, view})
  ... work ...
  span_end()  // merkle_tracer computes hash of span + children

Agent B (receives A's proposal via a2a-dispatcher):
  span_start("consensus.prepare", attributes={proposal_id, view, parent_agent=A})
  merkle_proof = fetch from l8-proof.merkle_spans where agent=A, span_id=parent
  validate merkle_proof(proposal_id) == expected_root
  ... work ...
  span_end()  // emit merkle root
```

Result: Unbroken Merkle chain from A → B → C → L8 ledger. Proves execution order.

### 3.6 Integration Points

| Component | Interface | Direction |
|-----------|-----------|-----------|
| `siss-otel-tracer` | Emit spans (extend with W3C headers) | Write |
| `siss-observability` | Query Merkle roots for audit | Read |
| `siss-metrics` | SLA gate thresholds + p99 latency | Read |
| `siss-a2a-dispatcher` | Inject/extract traceparent headers | Middleware |
| `l8-proof` | Write SLA violations + Merkle chains | SQL insert |
| `siss-event-log` | Alert on SLA breach | Event queue |
| OpenTelemetry Collector (optional) | gRPC export at :4317 | Network |

### 3.7 New Crate: `siss-otel-bridge`

```
crates/siss-otel-bridge/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── w3c_propagator.rs (extract/inject traceparent headers, 150 LOC)
│   ├── baggage_context.rs (correlation context, 150 LOC)
│   ├── sla_gates.rs (SLA threshold enforcement, 200 LOC)
│   ├── exporter.rs (OTEL Collector gRPC export, 150 LOC)
│   └── trace_stitcher.rs (multi-agent Merkle audit chain, 200 LOC)
├── tests/
│   ├── test_w3c_propagation.rs (100 LOC)
│   ├── test_sla_gates.rs (100 LOC)
│   └── test_trace_stitching.rs (150 LOC)
└── benches/
    └── propagation_overhead.rs (50 LOC)
```

---

## 4. Chronicle Cognitive Drift Detection (L7 Enterprise)

### 4.1 Overview

Analyze agent decision-making over rolling 100-decision window. Use RAGAS (Retrieval-Augmented Generation Assessment System) to detect when agents deviate from learned policies. Alert on unusual patterns.

### 4.2 Current State

Phase 1 already includes:
- ✅ L7 RAGAS: 87%+ accuracy on 50-question golden set
- ✅ `siss-telemetry-router`: routing events to destinations
- ✅ `siss-metrics`: KPI tracking
- ❌ Rolling decision window analysis
- ❌ Policy drift scoring (RAGAS)
- ❌ Multi-agent consensus on drift

### 4.3 Design: Drift Detection Pipeline

#### Decision Window

```rust
struct DecisionWindow {
    agent_id: Uuid,
    window_size: usize,  // 100 decisions
    decisions: VecDeque<Decision>,  // (proposal_id, choice, timestamp, latency)
    policy_checksum: [u8; 32],  // Merkle root of expected policy rules
}

struct Decision {
    proposal_id: Uuid,
    choice: String,  // "APPROVE", "VETO", "ABSTAIN"
    latency_ms: f64,
    timestamp: i64,
    context: DecisionContext,
}

struct DecisionContext {
    intent_type: String,  // "transfer", "withdrawal", "policy_change"
    amount: f64,
    risk_score: f64,
    precedent_count: i32,  // how many similar decisions before
}
```

Every decision written to L8 proof ledger:
```sql
INSERT INTO decisions_log (
  agent_id, decision_id, choice, context_json, timestamp, merkle_proof
)
```

#### Rolling Analysis Every 10 Decisions

When agent reaches 10, 20, 30, ..., 100 decisions:
1. **Extract decision pattern:**
   ```
   Last 100 decisions from decisions_log
   → Aggregate: approval_rate, avg_latency, veto_count, etc.
   ```

2. **Query policy via RAGAS:**
   ```
   Question: "For {intent_type} with {amount} and {risk_score}, 
             what is the expected decision?"
   
   RAGAS: Query l2-knowledge pgvector (policy embeddings)
   → Return: expected_decision, confidence_score
   ```

3. **Compute drift score:**
   ```
   drift_score = abs(observed_approval_rate - expected_approval_rate)
   
   Thresholds:
   - drift_score < 0.05 → GREEN (normal)
   - 0.05 ≤ drift_score < 0.15 → YELLOW (watch)
   - 0.15 ≤ drift_score < 0.25 → ORANGE (investigate)
   - drift_score ≥ 0.25 → RED (escalate)
   
   E.g., if expected approval=85% but observed=55% → drift_score=0.30 → RED
   ```

4. **Pattern analysis (optional):**
   ```
   Time-series smoothing: drift over last 3 windows
   - Trending up (worsening) → higher alert priority
   - Sudden spike → possible adversarial prompt
   
   Latency spike detection: avg_latency > expected + 2*stdev → overloaded?
   ```

5. **Emit event:**
   ```
   siss-event-log entry:
   {
     "type": "drift_detected",
     "agent_id": uuid,
     "drift_score": 0.30,
     "severity": "RED",
     "decisions_analyzed": 100,
     "recommendation": "Supervisor review required",
     "timestamp": 1719604800
   }
   ```

#### Multi-Agent Consensus on Drift

If any agent detects RED drift, trigger PBFT consensus among 3-of-5:
```
Agent A (detection): broadcasts DriftAlert { agent_id=X, drift_score=0.30 }
Agents B, C, D: validate drift score (re-compute if needed)
Consensus: "Agent X is drifting" → APPROVED
Action: Pause agent X, trigger human review, optionally rollback recent decisions
```

### 4.4 Statistical Model for Drift

Expected decision distribution for transfer intent:
```
Risk Score < 10:   90% approve, 5% veto, 5% abstain
Risk Score 10-50:  70% approve, 20% veto, 10% abstain
Risk Score > 50:   30% approve, 60% veto, 10% abstain
```

Observed (agent A, last 100):
```
Risk < 10:   100 decisions, 50 approve → 50% (expected 90%) → delta = 40%
Risk 10-50:  200 decisions, 100 approve → 50% (expected 70%) → delta = 20%
Risk > 50:   100 decisions, 80 approve → 80% (expected 30%) → delta = 50%

Weighted drift = (40% + 20% + 50%) / 3 = 36.7% → RED
```

### 4.5 Integration Points

| Component | Interface | Direction |
|-----------|-----------|-----------|
| `l8-proof` | Write/query decisions_log | SQL |
| `l2-knowledge` | Query policy via pgvector similarity | SQL read |
| `l7-ragas` | Compute drift via golden set accuracy | Sync call |
| `siss-telemetry-router` | Route drift alerts to supervisors | Event queue |
| `siss-metrics` | Track drift_score per agent | Time-series |
| `siss-pbft-engine` | Consensus on RED drift → action | RPC |
| `siss-event-log` | Log all drift events for audit | SQL insert |

### 4.6 New Crate: `siss-chronicle-drift`

```
crates/siss-chronicle-drift/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── decision_window.rs (rolling 100-decision buffer, 200 LOC)
│   ├── policy_query.rs (RAGAS integration for expected decisions, 200 LOC)
│   ├── drift_score.rs (statistical drift computation, 250 LOC)
│   ├── consensus_trigger.rs (escalate RED drift to PBFT, 150 LOC)
│   └── metrics.rs (export drift scores to siss-metrics, 100 LOC)
├── tests/
│   ├── test_drift_computation.rs (150 LOC)
│   ├── test_consensus_escalation.rs (100 LOC)
│   └── test_ragas_integration.rs (100 LOC)
└── benches/
    └── drift_analysis_perf.rs (50 LOC)
```

---

## 5. Advanced Robotics Integration (L6 Enterprise)

### 5.1 Overview

Extend `siss-hardware-accel` + `siss-chaos-petri` to control industrial cobots (UR10e) and mobile robots (Clearpath). Define safety boundaries, execute physics-verified trajectories, and integrate with MuJoCo simulation.

### 5.2 Current State

`siss-hardware-accel/src/lib.rs`:
- ✅ Metal GPU backend (inference acceleration)
- ✅ Neural engine (model serving)
- ✅ SIMD ops (proof generation)
- ❌ Cobot arm control interface
- ❌ Safety boundary enforcement
- ❌ Physics simulation integration

`siss-chaos-petri/src/lib.rs`:
- ✅ MuJoCo physics engine interface
- ✅ Trajectory recording
- ✅ Chaos testing (inject faults)
- ❌ Real-time cobot control loop
- ❌ Sensor feedback integration

### 5.3 Design: Robotics Control Stack

#### Cobot Control Interface

```rust
trait CobotController: Send + Sync {
    async fn execute_trajectory(&self, trajectory: &Trajectory) -> Result<ExecutionReport>;
    async fn read_joint_angles(&self) -> Result<[f64; 6]>;  // 6-DOF arm
    async fn read_end_effector_pose(&self) -> Result<Pose>;  // (x,y,z,rx,ry,rz)
    async fn enforce_boundary(&self, zone: &SafetyZone) -> Result<()>;
    async fn emergency_stop(&self) -> Result<()>;
}

// UR10e Implementation
pub struct UR10eController {
    ros_client: RosClient,  // ROS 2 bridge via siss-mcp-gateway
    safety_monitor: Arc<SafetyMonitor>,
    state: Arc<Mutex<RobotState>>,
}

// Clearpath Implementation
pub struct ClearpathDiffDriveController {
    mcp_gateway: Arc<MpcGateway>,
    sensor_fusion: Arc<SensorFusion>,
    navigation_stack: Arc<NavigationStack>,
}
```

#### Safety Boundary Enforcement

```rust
struct SafetyZone {
    zone_id: Uuid,
    workspace: Bounds3D,  // (x_min..x_max, y_min..y_max, z_min..z_max)
    velocity_limit_m_per_s: f64,
    force_limit_n: f64,
    emergency_zone: Bounds3D,  // If entered → E-stop
}

// On every control cycle (~10ms):
1. Predict next end-effector pose (100ms lookahead)
2. If predicted pose outside workspace:
   a. Decelerate trajectory (scale velocity by 0.5)
   b. Emit warning to siss-event-log
3. If current pose in emergency_zone:
   a. Trigger emergency_stop()
   b. Log incident to l8-proof
   c. Alert supervisor
4. Measure end-effector force (via joint torque)
5. If force > force_limit:
   a. Reduce velocity further
   b. Log force violation
```

#### Physics Simulation (MuJoCo Integration)

```rust
struct SimulationEnvironment {
    model: MuJoCoModel,  // UR10e kinematic chain + obstacles
    sim_time: f64,
    gravity: [f64; 3],  // 9.81 m/s²
    contact_dynamics: ContactDynamics,
}

// Offline trajectory validation (pre-execution):
1. Load trajectory into MuJoCo model
2. Simulate every control point (10ms steps)
3. Check constraints:
   - Joint limits: -180° to 180° per joint
   - Velocity limits: <1.5 rad/s per joint
   - Collision detection: no self-collisions, no obstacles
   - Reachability: inverse kinematics solution exists
4. If all constraints pass → trajectory safe, execute on real robot
5. If constraint violation detected:
   a. Reject trajectory, return error
   b. Suggest corrected trajectory (via trajectory planner)
```

#### Real-Time Sensor Feedback Loop

```
Every 10ms:
1. Read joint angles from UR10e via ROS
2. Compute forward kinematics → current pose
3. Compare to desired pose (from active trajectory)
4. If error > threshold (1cm or 5°):
   a. Adjust control input (PID feedback)
   b. Log tracking error
   c. If error > 10cm → E-stop (loss of control)
5. Read force/torque sensor
6. Validate against force_limit
7. Emit metrics: latency, error, force

Safety invariant: If any sensor read fails (timeout > 100ms):
→ Emergency stop (fail-safe)
```

#### Trajectory Execution Report

```rust
struct ExecutionReport {
    trajectory_id: Uuid,
    status: ExecutionStatus,  // SUCCESS, ABORTED, FAILED
    actual_path: Vec<Pose>,  // recorded trajectory
    execution_time_ms: f64,
    max_tracking_error_m: f64,
    max_force_n: f64,
    collisions_detected: u32,
    checksum: [u8; 32],  // Merkle proof of execution
}

Written to l8-proof:
INSERT INTO robotics_executions (
  robot_id, trajectory_id, status, max_error, max_force, merkle_proof, timestamp
)
```

### 5.4 Integration Points

| Component | Interface | Direction |
|-----------|-----------|-----------|
| `siss-hardware-accel` | GPU inference for trajectory generation | RPC |
| `siss-chaos-petri` | MuJoCo physics simulation + fault injection | Sync call |
| `siss-mcp-gateway` | ROS 2 bridge for UR10e control | MCP |
| `l6-infrastructure` | Record robot metrics (CPU, network, thermal) | Metrics |
| `l8-proof` | Write execution reports + safety incidents | SQL insert |
| `siss-event-log` | Alert on boundary violations, E-stop | Event queue |
| `siss-behavioral-firewall` | Enforce egress: only UR10e MAC address allowed | Network ACL |
| Sensor feedback | Joint angles, force/torque, camera | Network (ROS 2) |

### 5.5 New Crate: `siss-robotics-control`

```
crates/siss-robotics-control/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── cobot_interface.rs (trait + UR10e/Clearpath impl, 400 LOC)
│   ├── safety_enforcement.rs (boundary checks, E-stop logic, 300 LOC)
│   ├── physics_validator.rs (MuJoCo trajectory validation, 250 LOC)
│   ├── sensor_feedback.rs (real-time control loop, 250 LOC)
│   └── trajectory_manager.rs (execution planning, 200 LOC)
├── tests/
│   ├── test_trajectory_validation.rs (150 LOC)
│   ├── test_boundary_enforcement.rs (100 LOC)
│   ├── test_sensor_feedback.rs (100 LOC)
│   └── test_e_stop.rs (50 LOC)
└── benches/
    └── control_loop_latency.rs (100 LOC)
```

---

## 6. System Integration & Data Flow

### 6.1 End-to-End Scenario: Treasury Payment Authorization

```
1. USER SUBMITS INTENT
   Treasury Officer submits: "Approve $100M transfer to Supplier X"
   → l4-orchestration.submit_intent(intent)

2. INTENT ENTERS POOL
   siss-agent-pool: enqueues intent, spawns agent if needed
   Agent assigned: UUID-A

3. PBFT CONSENSUS
   Agent A initiates proposal (view=0)
   → siss-pbft-engine.submit_proposal()
   → Broadcast to agents B, C, D, E
   
   All agents: pre-prepare → prepare → commit (3-phase)
   Merkle proofs written to l8-proof
   
   Result: 3-of-5 agreed → decision is FINAL

4. DRIFT DETECTION (Async)
   siss-chronicle-drift: analyzing agent A's recent decisions
   → Decision 100: approved transfer (expected: 85% approve, observed: 100%)
   → Drift score = 0.15 → YELLOW (watch)
   → Logged to l8-proof

5. ROBOTICS ACTION (If applicable)
   Supervisor triggers: "Execute transfer via RPA bot"
   → siss-robotics-control.execute_trajectory()
   → MuJoCo validates trajectory (collision-free)
   → UR10e reads blueprint, executes workflow
   → Execution report written to l8-proof

6. DISTRIBUTED TRACING
   Entire flow traced via siss-otel-bridge:
   - traceparent: 00-4bf92f-00a1b2-01 (sampled=1% chance)
   - Spans: pbft.prepare, pbft.commit, robot.execute, drift.analyze
   - Exported to optional Jaeger backend (if connected)

7. SLA GATES
   siss-otel-bridge checks:
   - PBFT commit latency: 250ms (target: <200ms) → YELLOW alert
   - Robot execution: 5s (target: <10s) → GREEN
   - Overall intent latency: 6s (target: <30s) → GREEN

8. GRACEFUL SHUTDOWN (Later)
   Pool receives SIGTERM
   → siss-agent-pool: initiate drain for all agents
   → Migrate agent A's pending tasks to agent B
   → Flush l8-proof ledger (atomic batch)
   → Exit cleanly

Result: Immutable audit trail in l8-proof, all decisions Byzantine-final.
```

### 6.2 Crate Dependencies

```
Layer 3 (Consensus & Control):
  siss-pbft-engine → siss-consensus-extended
  siss-agent-pool → siss-agent-shell, siss-swarm-coordinator
  siss-robotics-control → siss-hardware-accel, siss-chaos-petri

Layer 5 (Observability):
  siss-otel-bridge → siss-otel-tracer, siss-observability
  siss-chronicle-drift → l7-ragas, l2-knowledge, l8-proof

Layer 8 (Ledger & Proofs):
  All above → l8-proof (merkle ledger write)
  All above → siss-event-log (audit trail)

Cross-cutting:
  All → siss-a2a-dispatcher (RPC)
  All → siss-metrics (metrics export)
  All → siss-behavioral-firewall (egress filtering)
```

---

## 7. Testing Strategy

### 7.1 Test Levels

**Level 0: Unit Tests (Vitest)**
- PBFT quorum math: 3-of-5 for f=2
- Drift score computation: expected vs observed
- Trajectory validation: collision detection

**Level 1: Integration Tests (Playwright + Tokio)**
- Happy path: 5-agent consensus → decision final
- Pool spawn/drain cycle → state preservation
- Cross-agent trace stitching → audit trail

**Level 2: System Tests (Playwright + MuJoCo)**
- Treasury officer submits intent → PBFT → drift check → audit
- UR10e trajectory execution → safety enforcement → recorded
- Pool graceful shutdown → ledger flushed

**Level 3: Load Tests (Criterion + siss-chaos-petri)**
- 100 concurrent PBFT proposals → measure commit latency p99
- 500 agents in pool → spawn/drain under load
- MuJoCo sim 1000 trajectories → collision detection performance

**Level 4: Fault Injection (Chaos Testing)**
- Kill 2-of-5 consensus agents → recovery via view change
- Slow network (100ms latency) → view change triggered
- Robot sensor timeout → E-stop executed
- Database connection failure → graceful fallback

### 7.2 Acceptance Criteria

All subsystems must pass:
- ✅ Unit tests: >85% coverage
- ✅ Integration tests: 100% happy path + 3 sad paths
- ✅ Console clean (no errors, warnings documented)
- ✅ Merkle proofs verified end-to-end
- ✅ Latency targets met: PBFT commit <200ms, robot E-stop <50ms
- ✅ No data loss on graceful shutdown

---

## 8. Implementation Roadmap (Jun-Dec 2027)

### Week 1-2: PBFT Engine (siss-consensus-extended)
- Implement pre-prepare, prepare, commit phases
- View change protocol with leader rotation
- Checkpoint + crash recovery
- Tests: 150 LOC

### Week 3-4: Agent Pool Management (siss-agent-pool)
- Pool spawn/drain logic
- State migration protocol
- Graceful shutdown
- Tests: 150 LOC

### Week 5-6: OTEL Integration (siss-otel-bridge)
- W3C Trace Context propagation
- SLA gates + alerting
- Trace stitching (Merkle audit)
- Tests: 150 LOC

### Week 7-8: Drift Detection (siss-chronicle-drift)
- Rolling 100-decision window
- RAGAS policy query
- Drift scoring
- Tests: 100 LOC

### Week 9-10: Robotics Control (siss-robotics-control)
- UR10e interface (ROS 2 bridge)
- Safety boundary enforcement
- Physics validation (MuJoCo)
- Real-time feedback loop
- Tests: 100 LOC

### Week 11-12: Integration & Quality
- End-to-end tests (all 5 subsystems)
- Load testing + chaos injection
- Console hygiene + SLA gate validation
- Documentation + runbooks

### Week 13-15: Buffer & Demo
- Performance tuning
- User acceptance testing
- Recorded demo walkthrough

### Week 16-24: Production Hardening
- Bug fixes from testing
- Monitoring & alerting
- Disaster recovery testing
- Knowledge transfer

---

## 9. Risk Assessment & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| PBFT liveness failure (view change loop) | HIGH | Timeout tuning, view change backoff exponential |
| State migration data loss during drain | HIGH | Merkle proofs for every task state, verify on migration target |
| Robot safety boundary breach | CRITICAL | Hardware E-stop (always active), software SIL 3 rating |
| OTEL sampled spans lose context | MEDIUM | Baggage propagates even when span not sampled |
| Drift detection false positives | MEDIUM | Multi-agent consensus before escalation, manual review required |
| Pool spawn creates zombie agents | MEDIUM | Health checks every 10s, force-kill if unresponsive >30s |

---

## 10. Success Criteria (Dec 2027)

- ✅ All 5 subsystems implemented, tested, merged
- ✅ PBFT consensus: 5 agents, 3-of-5 quorum, <200ms commit latency
- ✅ Agent pool: 50-1,000 agents supported, graceful drain proven
- ✅ OTEL traces: 100% of cross-agent calls traced, 1% sampled, SLA gates alerting
- ✅ Drift detection: 100-decision windows analyzed, RED drift escalates via PBFT
- ✅ Robotics: UR10e trajectory execution recorded, safety boundaries enforced
- ✅ Zero console errors in production load tests
- ✅ Merkle audit chain verified end-to-end (intent → consensus → execution → ledger)
- ✅ Demo recorded: Treasury intent → PBFT consensus → drift check → robotics execution → immutable ledger

---

## Appendix A: Dependencies & Workspace

### New Crates (4 total)
- `siss-consensus-extended` (imports: `siss-swarm-consensus`, `l8-proof`, `siss-vault-integration`)
- `siss-agent-pool` (imports: `siss-agent-shell`, `siss-swarm-coordinator`, `l2-knowledge`)
- `siss-otel-bridge` (imports: `siss-otel-tracer`, `siss-observability`, `siss-metrics`)
- `siss-chronicle-drift` (imports: `l7-ragas`, `l2-knowledge`, `l8-proof`)
- `siss-robotics-control` (imports: `siss-hardware-accel`, `siss-chaos-petri`, `siss-mcp-gateway`)

### External Crates (Pre-installed)
- `opentelemetry` (already in workspace via Phase 1)
- `tokio` (async runtime)
- `dashmap` (concurrent maps)
- `serde` (serialization)

---

**Document Status:** ARCHITECTURE DESIGN COMPLETE  
**Next Phase:** Implementation (Jun 1, 2027)  
**Design Review:** Required before code commencement  
**Author:** Code Explorer (Phase 3 Architecture)
