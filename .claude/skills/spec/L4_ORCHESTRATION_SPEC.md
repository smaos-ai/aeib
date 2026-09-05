# Specification: L4 Orchestration — Deterministic LangGraph State Machine with Checkpoints & Human Escalation

## Goal
**The ONE Thing:** Build a fault-tolerant, deterministic state machine for LangGraph orchestration that enforces the complete intent-to-ledger workflow (CLASSIFY → EXECUTE → AUTHORIZE → PERSIST) with checkpoint recovery and human escalation gates for 3 pilots (hotel/glass/school).

## Current State Analysis
- ✅ ActionVelocityTracker: Per-pilot velocity constraints (prevents runaway)
- ✅ VelocityCheckedWorkflow: Sequential node execution with velocity hooks
- ✅ 15+ tests for velocity tracking
- ✅ 3 pilot implementations in L3 (hotel/glass/school) with intent + egress controls
- ❌ NO formal state machine (just sequential execution)
- ❌ NO checkpoint/resume capability
- ❌ NO human authorization gates
- ❌ NO ledger persistence

## Architecture Decisions

### 1. State Machine Design (Deterministic, Fail-Closed)
**States per workflow instance:**
```
INIT
  ↓ (accept intent)
INTENT_RECEIVED
  ↓ (validate intent constraints)
INTENT_VALIDATED
  ↓ (classify intent)
CLASSIFIED
  ↓ (execute action nodes)
EXECUTING
  ↓ (request human authorization)
AWAITING_AUTHORIZATION
  ↓ (human approves/denies)
AUTHORIZED or DENIED
  ↓ (persist result + signature)
LEDGER_WRITTEN
  ↓
COMPLETE
```

**Fail-closed semantics:** Default deny at authorization gate; explicit human approval required.

### 2. Checkpoint System
**Format:** JSON files in `/tmp/smaos_checkpoints/{workflow_id}.json`
```json
{
  "workflow_id": "wf_hotel_001",
  "pilot_name": "hotel",
  "state": "AWAITING_AUTHORIZATION",
  "timestamp": 1725000000.0,
  "context": {
    "intent": {...},
    "classification": {...},
    "execution_results": {...},
    "velocity_report": {...}
  },
  "escalation": {
    "escalation_id": "esc_001",
    "required_action": "human_review",
    "reason": "velocity_spike | high_risk_classification | manual_gate"
  },
  "checkpoint_hash": "sha256_digest"
}
```

**Why JSON files?** Local-first (CLAUDE.md constraint), immutable audit trail, human-readable, no external dependencies.

### 3. Human Escalation Routing
**Trigger points:**
1. **Velocity violation** (L4 ActionVelocityTracker)
2. **High-risk classification** (L1 policy router output)
3. **Manual authorization gate** (explicit before ledger write)

**Escalation state in workflow:**
- Pauses at AWAITING_AUTHORIZATION
- Writes checkpoint to disk
- Returns escalation_id to calling system
- Waits for human approval/denial via approve_escalation(escalation_id) or deny_escalation(escalation_id)
- Resumes workflow → LEDGER_WRITTEN → COMPLETE

### 4. Integration Points
| System | Integration | Method |
|--------|-------------|--------|
| L1 (Reasoning) | Intent classification | policy_router.classify(intent) |
| L3 (Tooling) | Egress validation + intent constraints | Call existing pilot executors |
| L4 (Velocity) | Prevent runaway agents | ActionVelocityTracker.record_action() |
| L6 (Infrastructure) | Ledger writing + KMS signing | ap2_ledger.write_entry(proof_data) |

### 5. Pilot-Specific Implementations
**Generic orchestrator** (reusable for all 3):
- State machine logic (same for hotel/glass/school)
- Checkpoint persistence (same)
- Escalation routing (same)

**Pilot-specific node executors:**
- hotel: fetch_pms → score_credit → check_sanctions → execute_decision
- glass: parse_cad → check_safety → execute_decision
- school: verify_student → check_eligibility → execute_decision

**Pattern:** Pilots provide a list of (node_name, executor_func), orchestrator runs them with state tracking.

## Success Criteria
- [ ] **State Machine Tests (50+ tests):** All state transitions verified with mocked inputs
  - Normal path (INIT → ... → COMPLETE)
  - Escalation path (INIT → ... → AWAITING_AUTHORIZATION → [APPROVED|DENIED] → COMPLETE)
  - Velocity violation (recorded action → escalation triggered)
  - Checkpoint recovery (save → crash → load → resume)
  
- [ ] **Checkpoint System Tests (20+ tests):**
  - Checkpoint written at each state transition
  - Checkpoint recovery works end-to-end
  - Checkpoint hash validation
  - Corrupt checkpoint detected
  
- [ ] **Escalation Tests (15+ tests):**
  - Escalation created at AWAITING_AUTHORIZATION
  - approve_escalation() → workflow resumes
  - deny_escalation() → workflow blocks
  - Escalation logged to audit trail
  
- [ ] **Integration Tests (20+ tests):**
  - Hotel pilot: intent → classify → execute → authorize → ledger (STAR test)
  - Glass pilot: same flow
  - School pilot: same flow
  
- [ ] **Code Quality:**
  - 600-800 lines of implementation code
  - <5 lines per function (tight, testable)
  - 0 critical linter warnings
  - >95% code coverage on hot paths
  
- [ ] **Manual Verification (MMV):**
  - Hotel: Submit intent (browser) → Page shows "Awaiting Authorization" → Click Approve → Ledger entry written (verified in console)
  - Glass: Same workflow
  - School: Same workflow

## Files to Create/Modify

### New Files
1. `/smaos/l4_orchestration/deterministic_state_machine.py` (400-500 LOC)
   - DeterministicWorkflow class
   - State enum
   - Checkpoint manager
   - Escalation router

2. `/smaos/l4_orchestration/test_l4_state_machine.py` (50+ tests)
3. `/smaos/l4_orchestration/test_l4_checkpoint_recovery.py` (20+ tests)
4. `/smaos/l4_orchestration/test_l4_escalation_routing.py` (15+ tests)
5. `/smaos/l4_orchestration/test_l4_pilot_integration.py` (20+ STAR tests)

### Modify Existing Files
1. `/smaos/l4_orchestration/l4_langgraph_integration.py`
   - Integrate DeterministicWorkflow into VelocityCheckedWorkflow
   - Add checkpoint hooks after each state transition
   
2. `/smaos/l4_orchestration/action_velocity.py`
   - Already exists, no changes needed (clean separation)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Checkpoint file corruption | Workflow stuck in AWAITING_AUTHORIZATION | Checkpoint hash validation; refuse corrupt checkpoints |
| Lost escalation approval | Human approval lost; workflow orphaned | Escalations logged to immutable JSON file; approvals signed |
| Velocity tracker not called | Runaway agent undetected | Unit tests verify velocity hook called in every state transition |
| Ledger write fails silently | Audit trail incomplete | Ledger write happens in final state; if it fails, stay in LEDGER_WRITE state (not COMPLETE) |
| Pilot-specific executor crashes | Entire workflow stops | Catch exceptions in node executor; escalate to AWAITING_AUTHORIZATION with error reason |

## Assumptions (Verify with User)

1. **Ledger Integration:** Should we call `ap2_ledger.write_entry()` from L6, or is that out of L4 scope?
   - **Assumption:** L4 prepares ledger data; L6/L7 handles signing + persistence. L4 just calls L6 APIs.

2. **Human Authorization UI:** Is there a browser UI component for approving escalations, or is it a backend-only system?
   - **Assumption:** Backend API; frontend will be built in L5 Communication phase.

3. **Checkpoint Recovery:** If a workflow crashes in EXECUTING state, should we auto-retry the failed node or escalate to human?
   - **Assumption:** Auto-retry once; if it fails twice, escalate to AWAITING_AUTHORIZATION with error reason.

4. **Pilot Customization:** Should each pilot override state machine behavior, or is the state machine rigid?
   - **Assumption:** Rigid state machine; pilots only customize node executors. No state machine overrides.

5. **High-Risk Classification:** Which classifications from L1 trigger escalation?
   - **Assumption:** Policy router returns {classification, risk_level}. risk_level='high' triggers automatic escalation.

## Open Questions
1. Should checkpoints include execution logs (verbose) or just state + escalation info (compact)?
2. Should we support parallel node execution or strictly sequential (per hotel/glass/school requirement)?
3. For checkpoint recovery: if a workflow was in EXECUTING and we load it, should we:
   - Replay all executed nodes (idempotent)?
   - Trust that they already ran (non-idempotent)?
   - Ask human to confirm (fail-safe)?
4. How long should an escalation wait for human approval before timing out?

## Next Steps (Implementation Phase)
1. Write failing tests for all 4 test suites (100+ total)
2. Implement DeterministicWorkflow class
3. Implement checkpoint manager
4. Integrate with ActionVelocityTracker
5. Manual verification (MMV) for 3 pilots in browser
