# Phase 36: Resumable Cognitive Execution — Human-in-the-Loop Agentic Orchestration

**Status:** SPECIFICATION (2026-05-15)  
**Tests:** 0/18 pending (to be written in Inversion Development)  
**Implementation:** Awaiting Inversion Development  
**Depends On:** Phase 34 (Signal Tier Promotion), Phase 35 (π+ Projections)

---

## Executive Summary

Phase 36 introduces **Resumable Cognitive Execution (RCE)**: a state machine framework that enables autonomous agents to safely pause when critical intelligence projections arrive, await explicit human approval, and then resume execution with preserved context.

**The Problem RCE Solves:**
- Agents either execute autonomously (runaway loops, no human control) or don't execute at all (zero automation)
- Intelligence projections (π+ operators) identify risks but have no mechanism to interrupt and redirect agent behavior
- Without checkpointing, partial execution leaves systems in inconsistent states

**The RCE Solution:**
- Agents enter `Perform` state, executing planned workflows
- When π+ projections flag critical conditions (e.g., blast radius > threshold), RCE transitions to `Paused`
- Human operator reviews intelligence projection in the Visible Field (π+ output)
- Operator approves, rejects, or modifies execution plan
- Agent resumes from checkpoint with updated context
- **Human remains the Strategic Orchestrator; agents are tactical executors**

---

## Core Concepts

### 1. The RCE State Machine

```
┌─────────┐
│  Idle   │  Initial state; no workflow active
└────┬────┘
     │ start_workflow(plan)
     ↓
┌─────────────────────────────────────────────────┐
│  Perform                                        │
│  Executing workflow steps; checkpointing state  │
│  (agents actively run, making progress)         │
└────┬────────────────────────────────────────────┘
     │
     │ interrupt(reason, projection_data) [from π+ projection]
     ↓
┌─────────────────────────────────────────────────┐
│  Paused                                         │
│  Checkpoint saved; awaiting human decision      │
│  (human reviews intelligence projection)        │
└────┬───────────────┬──────────────────┬─────────┘
     │               │                  │
     │ approve()     │ reject()         │ modify(new_plan)
     ↓               ↓                  ↓
┌─────────────────────────────────────────────────┐
│  Resumed                                        │
│  Load checkpoint; continue from interruption    │
│  (agents resume with human-approved context)    │
└────┬────────────────────────────────────────────┘
     │
     │ (execution completes or next interrupt)
     ↓
┌─────────┐
│ Idle    │  Workflow complete or abandoned
└─────────┘
```

### 2. Execution Model

**Workflow Structure:**
```
Workflow {
    id: Uuid,
    plan: Vec<Step>,          // Sequence of agentic actions
    state: ExecutionState,    // Current position in state machine
    checkpoint: Option<Checkpoint>,  // Saved state at pause point
    history: Vec<Event>,      // Complete execution audit trail
}

Step {
    id: Uuid,
    action: AgentAction,      // What agent will do (e.g., "isolate sovereign")
    preconditions: Vec<Signal>,    // Conditions that must be true
    postconditions: Vec<Signal>,   // Conditions guaranteed after execution
    timeout_ms: u64,          // Abort if step takes longer
    idempotent: bool,         // Safe to retry if interrupted?
}

Checkpoint {
    step_index: usize,        // Which step were we on when interrupted?
    state_snapshot: serde_json::Value,  // Serialized agent state
    timestamp: DateTime<Utc>, // When checkpoint was created
    reason: String,           // Why we paused (e.g., "threat_radius_high")
    intelligence_projection: ProjectionData,  // π+ data that triggered pause
}
```

### 3. Interrupt Mechanism

When a π+ projection detects a critical condition, it **raises an interrupt**:

```rust
pub struct InterruptSignal {
    workflow_id: Uuid,
    severity: RiskLevel,  // Low, Medium, High, Critical
    reason: InterruptReason,
    projection_data: ProjectionData,  // Root-cause, threat, or SWOT
    recommended_action: Option<String>,
    human_approval_required: bool,
}

pub enum InterruptReason {
    ThreatAnticipation {
        blast_radius: usize,
        tokens_at_risk: i64,
        affected_sovereigns: Vec<SovereignId>,
    },
    RootCauseDiscovered {
        anomaly_type: String,
        confidence: f64,
        causal_chain_depth: i32,
    },
    SWOTDegradation {
        diversity_index: f64,
        threat_count: usize,
        recommendation: String,
    },
    TimeoutExceeded {
        step_id: Uuid,
        elapsed_ms: u64,
        timeout_ms: u64,
    },
    ResourceExhaustion {
        resource_type: String,
        usage_percent: f64,
        threshold: f64,
    },
}
```

---

## State Transitions & Semantics

### Transition 1: `Idle` → `Perform`

```
start_workflow(plan: Vec<Step>, context: ExecutionContext) 
  → Result<Workflow, RCEError>

Preconditions:
  ✓ Current state == Idle
  ✓ Plan is non-empty
  ✓ All steps have valid preconditions

Actions:
  1. Create new Workflow{id, plan, state: Perform, checkpoint: None}
  2. Record Event{type: "workflow_started", ...}
  3. Execute Step[0]
  4. If Step[0] succeeds → increment step_index, continue
  5. If Step[0] fails → transition to Idle (workflow_failed event)
  6. If Step[0] raises interrupt → transition to Paused

Guarantees:
  ✓ Workflow ID is globally unique
  ✓ All steps are checkpointed before execution
  ✓ No step executes without recording intent
```

### Transition 2: `Perform` → `Paused`

```
interrupt(signal: InterruptSignal) 
  → Result<(), RCEError>

Triggered By:
  • π+_TA projection: blast_radius > threshold
  • π+_RC projection: confidence >= 0.95 (high certainty root cause)
  • π+_SWOT projection: diversity_index < 0.5 (critical isolation)
  • Agent timeout: step exceeded max_duration
  • Resource exhaustion: heap/memory exceeds limit

Actions:
  1. Checkpoint current state:
     - Serialize agent context (heap snapshot)
     - Record current step_index
     - Capture InterruptSignal data
  2. Transition to Paused
  3. Publish event: "workflow_paused" with projection_data
  4. (Operator sees π+ projection in Visible Field; makes decision)

Guarantees:
  ✓ Checkpoint is durable (persisted before returning)
  ✓ No partial state leaks; checkpoint is atomic
  ✓ Interrupt reason is fully auditable
  ✓ All previous steps' effects are committed
```

### Transition 3: `Paused` → `Resumed` (Approval Path)

```
resume_workflow(decision: HumanDecision) 
  → Result<(), RCEError>

Human Decisions:
  A) Approve → continue with existing plan
  B) Reject → abort workflow, rollback effects
  C) Modify(new_plan) → continue with revised plan

Action Path A (Approve):
  1. Load Checkpoint
  2. Validate checkpoint integrity (checksums, timestamps)
  3. Deserialize saved state into agent context
  4. Increment step_index
  5. Execute Step[step_index] with restored context
  6. Record event: "workflow_resumed" {decision: "approve"}

Action Path B (Reject):
  1. Load Checkpoint
  2. Execute rollback_handlers for all completed steps
  3. Record event: "workflow_rejected"
  4. Transition to Idle
  5. Clean up resources

Action Path C (Modify):
  1. Load Checkpoint
  2. Validate new_plan merges with checkpoint
  3. Update plan with modifications
  4. Execute next step with new context
  5. Record event: "workflow_resumed" {decision: "modify", delta: new_plan_diff}

Guarantees:
  ✓ Deserialization failure → abort + alert (prevents corrupted state)
  ✓ Rollback is idempotent (safe to retry)
  ✓ All state transitions are logged
  ✓ Human decision is immutable (audit trail)
```

### Transition 4: `Resumed` → `Idle` (Completion)

```
complete_workflow() 
  → Result<WorkflowSummary, RCEError>

Triggered By:
  • All steps executed successfully
  • Operator explicitly aborts workflow
  • Timeout on entire workflow exceeded

Actions:
  1. Finalize all pending effects
  2. Compute WorkflowSummary (steps completed, duration, decisions made)
  3. Archive Checkpoint + full history
  4. Record event: "workflow_completed"
  5. Transition to Idle

WorkflowSummary {
    workflow_id: Uuid,
    total_steps: usize,
    completed_steps: usize,
    interrupted_count: usize,
    human_approvals: usize,
    total_duration_ms: u64,
    final_status: WorkflowStatus,  // success | failed | rejected
}

Guarantees:
  ✓ Summary is immutable historical record
  ✓ No state is lost (full audit trail persisted)
  ✓ Resources are freed (heap, locks released)
```

---

## Effect Handlers & Idempotency

### Effect Handler Pattern

Each agent step must implement effect handlers:

```rust
pub trait StepEffect: Send + Sync {
    /// Execute the step's primary action
    async fn perform(&self, context: &ExecutionContext) 
        -> Result<StepOutput, StepError>;
    
    /// Save state before perform() (for checkpoint)
    fn checkpoint(&self, context: &ExecutionContext) 
        -> Result<Vec<u8>, StepError>;
    
    /// Restore state from checkpoint (for resume)
    fn restore(&mut self, checkpoint_data: &[u8], context: &ExecutionContext)
        -> Result<(), StepError>;
    
    /// Undo perform()'s effects (for rollback)
    async fn rollback(&self, context: &ExecutionContext) 
        -> Result<(), StepError>;
}
```

### Idempotency Guarantees

```
If step.idempotent == true:
  ✓ perform() is safe to call multiple times without side effects
  ✓ Multiple calls with same input → identical output
  ✓ resume() can safely retry without coordination
  
If step.idempotent == false:
  ✓ perform() must only execute once per workflow
  ✓ Resume from checkpoint must detect prior execution
  ✓ prevent_double_execution guard required
```

### Example: "Isolate Sovereign" Step

```rust
pub struct IsolateSovereignEffect {
    sovereign_id: Uuid,
    isolation_rules: IsolationPolicy,
}

#[async_trait]
impl StepEffect for IsolateSovereignEffect {
    async fn perform(&self, context: &ExecutionContext) -> Result<StepOutput, StepError> {
        // 1. Verify sovereign exists (precondition)
        let sovereign = context.graph_db.get_sovereign(self.sovereign_id).await?;
        
        // 2. Check if already isolated (idempotency)
        if sovereign.status == SovereignStatus::Isolated {
            return Ok(StepOutput { 
                status: "already_isolated",
                duration_ms: 0,
            });
        }
        
        // 3. Apply isolation policy (mutation point)
        context.graph_db.update_sovereign_status(
            self.sovereign_id,
            SovereignStatus::Isolated
        ).await?;
        
        // 4. Broadcast isolation event (audit)
        context.event_bus.publish(Event {
            type: "sovereign_isolated",
            sovereign_id: self.sovereign_id,
            timestamp: Utc::now(),
        }).await?;
        
        Ok(StepOutput { status: "isolated", duration_ms: elapsed })
    }
    
    fn checkpoint(&self, context: &ExecutionContext) -> Result<Vec<u8>, StepError> {
        // Save enough state to restore after resume
        let snapshot = json!({
            "sovereign_id": self.sovereign_id,
            "pre_isolation_status": context.graph_db.get_sovereign_status(self.sovereign_id).await?
        });
        Ok(serde_json::to_vec(&snapshot)?)
    }
    
    fn restore(&mut self, data: &[u8], _context: &ExecutionContext) -> Result<(), StepError> {
        let snapshot: serde_json::Value = serde_json::from_slice(data)?;
        // Validation: ensure sovereign hasn't changed between pause/resume
        let stored_id = Uuid::parse_str(snapshot["sovereign_id"].as_str()?)?;
        if stored_id != self.sovereign_id {
            return Err(StepError::CheckpointCorrupted("Sovereign ID mismatch".into()));
        }
        Ok(())
    }
    
    async fn rollback(&self, context: &ExecutionContext) -> Result<(), StepError> {
        // Restore pre-isolation status
        context.graph_db.update_sovereign_status(
            self.sovereign_id,
            SovereignStatus::Active
        ).await?;
        
        context.event_bus.publish(Event {
            type: "sovereign_isolation_rolled_back",
            sovereign_id: self.sovereign_id,
            timestamp: Utc::now(),
        }).await?;
        
        Ok(())
    }
}
```

---

## Integration with Phase 35 (π+ Projections)

### How Projections Trigger Interrupts

```
Phase 35 Projection Loop:
  1. query_threat_anticipation(sovereign_id) 
     → ThreatAnticipationResponse {affected_sovereigns: 3, tokens_at_risk: 600k}
  
  2. Evaluate interrupt conditions:
     if response.total_tokens_at_risk > RCE_THRESHOLD (e.g., 500k):
         raise InterruptSignal {
             severity: High,
             reason: ThreatAnticipation { ... },
             projection_data: response,
             human_approval_required: true,
         }
  
  3. RCE receives interrupt:
     if current_state == Perform:
         transition_to_paused(interrupt_signal)
         publish_to_operator_cockpit(interrupt_signal)  // Human sees π+ output
  
  4. Operator reviews projection + decides:
     - "Approve isolation of Sovereign-42"
     - "Modify: isolate only Sovereign-42, not Sovereign-15"
     - "Reject: these sovereigns are critical; find alternative"
  
  5. RCE resumes with human decision:
     resume_workflow(HumanDecision::Approve)
     → Continues isolation workflow
```

### Projection-to-RCE Data Flow

```
Phase 35 (π+ Projections)
    ↓
    Produces: RootCauseResponse, ThreatAnticipationResponse, SwotScenarioResponse
    ↓
Phase 36 (RCE Interrupt Mechanism)
    ↓
    Converts to: InterruptSignal
    ↓
RCE State Machine
    ↓
    Transitions: Perform → Paused → (human decides) → Resumed → Idle
    ↓
Agent Workflow
    ↓
    Executes: Effect handlers (perform, checkpoint, restore, rollback)
    ↓
Phase 34 (Signal Tier)
    ↓
    Records: Outcome signals (success, timeout, rollback) → feeds back for tier promotion
```

---

## Data Structures & Type Definitions

### Core Types

```rust
/// Resumable Cognitive Execution state machine
pub struct ResumableCognitiveExecution {
    workflow_id: Uuid,
    state: ExecutionState,
    plan: Vec<Step>,
    current_step_index: usize,
    checkpoint: Option<Checkpoint>,
    history: Vec<Event>,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ExecutionState {
    Idle,
    Perform,
    Paused,
    Resumed,
}

pub struct Step {
    pub id: Uuid,
    pub action: Box<dyn StepEffect>,
    pub preconditions: Vec<Signal>,
    pub postconditions: Vec<Signal>,
    pub timeout_ms: u64,
    pub idempotent: bool,
    pub max_retries: usize,
}

pub struct Checkpoint {
    pub step_index: usize,
    pub state_snapshot: Vec<u8>,  // Serialized ExecutionContext
    pub timestamp: DateTime<Utc>,
    pub interrupt_signal: InterruptSignal,
    pub checksum: String,  // SHA-256 for integrity verification
}

pub struct Event {
    pub id: Uuid,
    pub event_type: EventType,
    pub timestamp: DateTime<Utc>,
    pub step_id: Option<Uuid>,
    pub details: serde_json::Value,
}

#[derive(Debug, Clone)]
pub enum EventType {
    WorkflowStarted,
    WorkflowPaused { reason: String },
    WorkflowResumed { decision: String },
    WorkflowCompleted { status: String },
    StepExecuted { step_id: Uuid, duration_ms: u64 },
    StepFailed { step_id: Uuid, error: String },
    StepRolledBack { step_id: Uuid },
}

pub enum HumanDecision {
    Approve,
    Reject { reason: String },
    Modify { new_plan: Vec<Step> },
}

pub struct ExecutionContext {
    pub workflow_id: Uuid,
    pub graph_db: Arc<GraphDatabase>,
    pub event_bus: Arc<EventBus>,
    pub metrics: Arc<MetricsCollector>,
    pub timeout_ms: u64,
}
```

---

## Safety Boundaries & Failure Modes

### 1. Checkpoint Integrity

```
Failure Mode: Corrupted checkpoint
Prevention:
  ✓ Compute SHA-256 checksum of checkpoint data
  ✓ Verify checksum before deserialization
  ✓ If mismatch: abort restore, alert operator, rollback workflow

Failure Mode: Checkpoint stale (sovereign state changed during pause)
Prevention:
  ✓ Include version numbers in checkpoint
  ✓ On restore, verify preconditions still hold
  ✓ If preconditions violated: abort, request human decision
```

### 2. Timeout Protection

```
Failure Mode: Step executes forever (network hang, infinite loop)
Prevention:
  ✓ Each step has timeout_ms
  ✓ Use tokio::time::timeout() to enforce
  ✓ On timeout:
      - Trigger rollback of completed steps
      - Raise interrupt: TimeoutExceeded
      - Transition to Paused
      - Operator can decide: retry, skip, or abort

Failure Mode: Total workflow timeout exceeded
Prevention:
  ✓ Workflow-level timeout (e.g., 1 hour)
  ✓ On expiry: force abort, rollback all steps, alert operator
```

### 3. Resource Exhaustion

```
Failure Mode: Heap grows unbounded (leak in step effect)
Prevention:
  ✓ Monitor heap usage during execution
  ✓ If usage > 80% of limit:
      - Trigger checkpoint
      - Raise interrupt: ResourceExhaustion
      - Pause workflow
      - Operator can skip problematic step or abort

Failure Mode: Memory lock contention (deadlock)
Prevention:
  ✓ Acquire locks in consistent order (total order)
  ✓ Use try_lock() with timeout (fail-fast)
  ✓ If lock acquisition > 5s: abort step, rollback, interrupt
```

### 4. Idempotency Violations

```
Failure Mode: Non-idempotent step retried after resume
Prevention:
  ✓ Step.idempotent flag is explicit
  ✓ For non-idempotent steps, record execution marker in checkpoint
  ✓ On resume, check marker before re-executing
  ✓ If already executed: skip to next step

Example guard:
  if !step.idempotent {
      if checkpoint_contains(format!("step_{}_executed", step.id)) {
          log!("Step already executed; skipping");
          continue to next step;
      }
  }
```

---

## Test Cases & Validation Criteria

### Test Suite (18 tests)

**State Machine Tests (6):**
1. `test_workflow_start_transition_idle_to_perform` — Start correctly transitions state
2. `test_workflow_pause_saves_checkpoint` — Interrupt creates durable checkpoint
3. `test_workflow_resume_restores_state` — Resume correctly deserializes saved state
4. `test_workflow_reject_rolls_back_effects` — Reject undoes all step effects
5. `test_workflow_modify_applies_new_plan` — Modify merges new steps with checkpoint
6. `test_workflow_timeout_triggers_interrupt` — Step timeout raises TimeoutExceeded

**Interrupt Mechanism Tests (4):**
7. `test_interrupt_from_threat_anticipation` — π+_TA projection triggers pause
8. `test_interrupt_from_root_cause_discovery` — π+_RC projection triggers pause
9. `test_interrupt_from_swot_degradation` — π+_SWOT projection triggers pause
10. `test_interrupt_severity_levels_respected` — Critical > High > Medium > Low ordering

**Checkpoint & Serialization Tests (4):**
11. `test_checkpoint_integrity_checksum_verified` — SHA-256 checksum validates
12. `test_checkpoint_corruption_detected_on_restore` — Corrupted checkpoint aborts
13. `test_checkpoint_version_mismatch_detected` — Stale checkpoint rejected
14. `test_serialization_roundtrip_preserves_context` — Serialize→Deserialize == Identity

**Idempotency & Safety Tests (4):**
15. `test_idempotent_step_safe_to_retry` — Step executes once despite retries
16. `test_non_idempotent_step_guards_prevent_double_execution` — Guard prevents duplicate
17. `test_resource_exhaustion_triggers_interrupt` — Heap monitoring works
18. `test_human_decision_immutable_in_audit_trail` — All decisions logged immutably

---

## Implementation Sequence (Inversion Development)

**Phase 36A (This Document):** ✅ Architecture Specification locked  
**Phase 36B (Next):** Inversion Development with 18 failing tests

```
Week 1: Core state machine
  - Write 6 state machine tests (FAIL)
  - Implement ExecutionState enum + transitions
  - Implement perform → pause → resume path (GREEN)

Week 2: Interrupt mechanism
  - Write 4 interrupt tests (FAIL)
  - Implement InterruptSignal + interrupt() handler
  - Wire to π+ projection output (GREEN)

Week 3: Checkpoint & serialization
  - Write 4 checkpoint tests (FAIL)
  - Implement Checkpoint struct + checksum validation
  - Implement serialize/deserialize (GREEN)

Week 4: Safety & idempotency
  - Write 4 safety tests (FAIL)
  - Implement idempotency guards + timeout enforcement
  - Implement resource monitoring (GREEN)
```

---

## Non-Goals (Phase 36)

- ❌ Distributed workflow coordination (multi-agent RCE; defer to Phase 37)
- ❌ Real-time streaming dashboards (UI for checkpoint visualization; defer to Phase 37)
- ❌ Machine learning-based decision recommendations (ML augmentation; defer to Phase 38)
- ❌ Automatic rollback triggers (fully autonomous remediation; defer to Phase 39)
- ❌ Time-travel debugging (execution replay; defer to Phase 40)

---

## Success Criteria

By end of Phase 36:

✅ Agents can execute workflows autonomously (Perform state)  
✅ π+ projections interrupt agents when critical conditions detected (Paused state)  
✅ Operators review intelligence and approve/reject/modify via cockpit (Human decision)  
✅ Agents resume with preserved context (Resumed state)  
✅ All state transitions are auditable (complete Event history)  
✅ Checkpoints are durable and verifiable (integrity checksums)  
✅ Rollback is safe and idempotent (no orphaned effects)  
✅ All 18 tests pass (correctness proven)  

---

## Appendix: Glossary

| Term | Definition |
|------|-----------|
| **RCE** | Resumable Cognitive Execution; state machine for human-controlled agentic workflows |
| **Checkpoint** | Snapshot of execution state at interrupt point; enables resume |
| **Interrupt** | Signal from π+ projection that triggers workflow pause |
| **Effect** | Agentic action with perform/rollback semantics |
| **Idempotent** | Safe to retry; multiple executions = single execution |
| **Human Decision** | Operator approval/rejection/modification of interrupted workflow |
| **Audit Trail** | Complete Event history of all state transitions |
| **Visible Field** | Human-actionable intelligence (π+ projection output) |
| **Gray Fog** | Stored graph memory (raw intelligence) |
| **LOTA** | "Living off the Agent"; autonomous execution without human control |

---

**Last Updated:** 2026-05-15  
**Next Phase:** 36B (Inversion Development with 18 failing tests)  
**Ownership:** Claude Haiku 4.5 + User Direction

