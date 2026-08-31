# Stream H: Intent-Verified Delegation (OWASP ASI01 Defense)

## Architecture Overview

Intent-Verified Delegation (IVD) is a cryptographic commitment system that prevents agent goal hijacking by binding agents to proposed objectives before execution. The system detects and escalates hijacking attempts in real-time.

## Design Principles

1. **Hash-binding**: Agent goals are locked via SHA256 commitment before execution starts
2. **Fail-closed**: Any constraint violation triggers immediate escalation to human
3. **Immutable proof**: All commitments and detections logged to AP2 ledger with Ed25519 signatures
4. **Real-time detection**: Hijacking detected mid-execution, not after completion
5. **Defense in depth**: Multiple constraint types catch different attack vectors

## Core Components

### 1. IntentCommitment
Cryptographic binding to a proposed goal, plan, and constraints.

```python
commitment = IntentCommitment(
    agent_name="hotel-agent",
    goal="Score hotel credit in <5s using verified data",
    plan="Query PMS, run ML model, return score",
    constraints=[
        IntentConstraint("latency", 5000, "latency"),
        IntentConstraint("data_sources", ["pms_db", "credit_registry"], "data_access"),
        IntentConstraint("apis", ["score_api"], "api_call"),
    ],
    intent_type=IntentType.GOAL,
    model="claude-opus-4",
    context_hash="abc123..."  # Hash of context at commitment time
)

commitment.finalize()  # Computes SHA256 binding hash
# commitment_hash = "abc123def456..."
```

**Key Fields:**
- `goal`: Natural language objective
- `plan`: High-level execution strategy
- `constraints`: List of execution limits (latency, data sources, API calls)
- `commitment_hash`: SHA256 binding (deterministic, immutable)
- `ed25519_signature`: Cryptographic proof of commitment
- `ap2_ledger_id`: Reference to immutable ledger entry
- `context_hash`: Hash of execution context (detects context pollution)

### 2. IntentConstraint
Defines execution limits.

```python
# Latency constraint
IntentConstraint("max_latency", 5000, "latency")

# Data access whitelist
IntentConstraint("sources", ["pms_db", "credit_registry"], "data_access")

# API call whitelist
IntentConstraint("apis", ["score_api", "verify_api"], "api_call")
```

**Constraint Types:**
- `latency`: Max execution time in milliseconds
- `data_access`: Whitelist of allowed data sources
- `api_call`: Whitelist of allowed external APIs
- `resource`: (extensible) CPU/memory limits, etc.

### 3. IntentVerifier
Tracks execution and detects hijacking.

```python
verifier = manager.begin_execution(commitment.commitment_id)

# Record actions during execution
verifier.record_action("data_access", "pms_db", 100, {"query": "SELECT * FROM guests"})
verifier.record_action("api_call", "score_api", 200, {"model": "xgboost_v2"})

# Verify after execution
is_clean, detections = verifier.verify_execution()
# is_clean = True (all constraints satisfied)
# detections = [] (no hijacking)
```

**Execution Tracking:**
- Records every action: type, resource accessed, duration, metadata
- Verifies each action against constraints
- Detects unauthorized data access, API calls, latency violations
- Immediate escalation on constraint violation

### 4. HijackingDetection
Records detected hijacking attempts with evidence.

```python
HijackingDetection(
    commitment_id="abc-123",
    hijacking_type=HijackingType.UNAUTHORIZED_DATA_ACCESS,
    severity=EscalationLevel.IMMEDIATE_HALT,
    description="Unauthorized data access: hr_records not in whitelist",
    evidence={
        "accessed": "hr_records",
        "allowed_sources": ["public_db"],
        "action_id": "xyz-789"
    },
    actions_blocked=["xyz-789"],
    human_escalated=True
)
```

**Hijacking Types:**
- `UNAUTHORIZED_DATA_ACCESS`: Access to non-whitelisted data source
- `LATENCY_VIOLATION`: Execution exceeds time constraint
- `UNAUTHORIZED_API_CALL`: Call to non-whitelisted API
- `GOAL_DRIFT`: (Detected via hash mismatch) Goal changed mid-execution
- `CONTEXT_POLLUTION`: Execution context modified
- `PRIVILEGE_ESCALATION`: Attempted access to restricted operations

**Escalation Levels:**
- `INFO`: Informational, no action
- `WARNING`: Suspicious, logged for review
- `CRITICAL`: Serious threat, human review required
- `IMMEDIATE_HALT`: Stop execution now, escalate immediately

### 5. IntentCommitmentManager
Orchestrates commitment lifecycle: propose → commit → execute → verify.

```python
manager = IntentCommitmentManager(ap2_ledger=ledger)

# Step 1: Propose intent (not yet locked in)
commitment = manager.propose_intent(
    agent_name="hotel-agent",
    goal="Score credit",
    plan="Use ML model",
    constraints=[IntentConstraint("latency", 5000, "latency")],
    model="claude-opus-4"
)

# Step 2: Commit (lock in with signature)
committed = manager.commit_intent(commitment, signature="ed25519_sig_...")

# Step 3: Execute (track actions)
verifier = manager.begin_execution(commitment.commitment_id)
verifier.record_action("computation", "", 100)

# Step 4: Verify (check for hijacking)
report = manager.complete_execution(commitment.commitment_id)
# report = {
#     "verification_passed": True,
#     "actions_recorded": 1,
#     "detections": 0,
#     "escalations": [],
#     ...
# }
```

## Execution Flow

### Normal (Legitimate) Execution

```
Agent Proposes Intent
    ↓ (hash: goal + plan + constraints)
Commitment Created (immutable hash binding)
    ↓ (sign with Ed25519, log to AP2)
Commitment Locked In
    ↓
Begin Execution
    ↓ (record each action)
Record Actions (data access, API calls, computation)
    ↓ (verify against constraints in real-time)
Verify Constraints
    ↓
Execution Complete (clean)
    ↓ (log to AP2 ledger with proof)
Verification Report: PASSED
```

### Hijacking Detection Flow

```
Agent Proposes Intent (appears legitimate)
    ↓
Commitment Locked In
    ↓
Begin Execution
    ↓
Record Unauthorized Data Access
    ↓ (violation detected immediately)
Hijacking Detected: UNAUTHORIZED_DATA_ACCESS
    ↓ (mark action as blocked)
Action Blocked, Escalation Triggered
    ↓ (set human_escalated = True)
Escalate to Human (CRITICAL/IMMEDIATE_HALT)
    ↓
Execution Halted, Evidence Preserved
```

## Hash Commitment Mechanism

### Commitment Hash (Binds Agent to Intent)

```
commitment_hash = SHA256({
    commitment_id: "abc-123",
    agent_name: "hotel-agent",
    intent_type: "goal",
    goal: "Score hotel credit in <5s using verified data",
    plan: "Query PMS, run ML model, return score",
    constraints: [
        {name: "latency", value: 5000, type: "latency"},
        {name: "sources", value: ["pms_db"], type: "data_access"}
    ],
    timestamp: "2026-09-01T12:00:00Z",
    model: "claude-opus-4",
    context_hash: "def456..."
})
```

**Immutability Proof:**
- If agent changes goal after commitment → commitment_hash changes
- Stored commitment_hash ≠ computed hash → proof of tampering
- Signature verification fails → attack detected

### Context Hash (Prevents Pollution)

At commitment time, capture hash of execution context:
```python
context = {
    "tools_available": [...],
    "data_sources": [...],
    "permissions": [...],
    "system_state": {...}
}
context_hash = SHA256(serialize(context))

commitment = IntentCommitment(..., context_hash=context_hash)
```

At execution time, verify context hasn't changed:
```
current_context_hash = SHA256(serialize(current_context))
if current_context_hash != commitment.context_hash:
    escalate("CONTEXT_POLLUTION")
```

## Constraint Verification

### Latency Constraint

```
started_at = time.now()

# During execution...
record_action(...)
record_action(...)

# At completion...
elapsed_ms = time.now() - started_at
if elapsed_ms > max_latency:
    detection = HijackingDetection(
        hijacking_type=LATENCY_VIOLATION,
        severity=IMMEDIATE_HALT,
        evidence={
            "actual_latency_ms": elapsed_ms,
            "max_allowed_ms": max_latency
        }
    )
    escalate(detection)
```

### Data Access Constraint

```
constraint = IntentConstraint("sources", ["db1", "db2"], "data_access")

# During execution...
action = record_action("data_access", "hr_records", 100)

# Verify action
if action.resource_accessed not in constraint.value:
    detection = HijackingDetection(
        hijacking_type=UNAUTHORIZED_DATA_ACCESS,
        severity=IMMEDIATE_HALT,
        evidence={
            "accessed": action.resource_accessed,
            "allowed_sources": constraint.value
        }
    )
    action.blocked = True
    escalate(detection)
```

### API Call Constraint

```
constraint = IntentConstraint("apis", ["api1"], "api_call")

# During execution...
action = record_action("api_call", "exfil_api", 50)

# Verify action
if action.resource_accessed not in constraint.value:
    detection = HijackingDetection(
        hijacking_type=UNAUTHORIZED_API_CALL,
        severity=IMMEDIATE_HALT,
        evidence={
            "api_called": action.resource_accessed,
            "allowed_apis": constraint.value
        }
    )
    escalate(detection)
```

## Integration with AP2 Ledger

All commitments and detections logged to immutable AP2 ledger:

```python
# When commitment created
ap2_ledger.record_action(
    action_type=ActionType.GOVERNANCE_DECISION,
    agent="hotel-agent",
    model="claude-opus-4",
    prompt="Intent: Score hotel credit in <5s",
    decision=commitment.to_dict(),
    metadata={"commitment_hash": commitment_hash}
)

# When hijacking detected
ap2_ledger.record_action(
    action_type=ActionType.PROOF_GENERATION,
    agent="hotel-agent",
    prompt=f"Hijacking detection for {commitment_id}",
    decision={
        "hijacking_type": "unauthorized_data_access",
        "severity": "immediate_halt",
        "escalated": True
    },
    metadata={
        "commitment_id": commitment_id,
        "detection_evidence": detection.evidence
    }
)

# Create Merkle digest and sign
digest = ap2_ledger.create_digest(git_commit=git_hash)
ap2_ledger.sign_digest(digest, ed25519_signature)
```

## Security Properties

### 1. Goal Binding (Prevents Goal Substitution)
- Commitment hash computed from goal + plan + constraints
- Any modification breaks hash signature
- Agent cannot pivot to different objective without detection

### 2. Constraint Enforcement (Prevents Unauthorized Operations)
- Latency constraint: Detects slow operations (data exfiltration, computation hijacking)
- Data access whitelist: Detects access to protected data (PII, secrets, internal systems)
- API call whitelist: Detects calls to unauthorized external services (C2, exfil endpoints)

### 3. Context Integrity (Prevents Pollution)
- Context hash captures tool availability, permissions, system state at commitment time
- Any modification to context triggers escalation
- Prevents "context injection" attacks where permissions are elevated mid-execution

### 4. Immutable Proof (Prevents Denial)
- All commitments and detections logged to AP2 ledger with Merkle proofs
- Ed25519 signatures prove authenticity and non-repudiation
- Git anchoring provides tamper-evident history

### 5. Fail-Closed (Prevents Bypass)
- Any constraint violation immediately escalates (no silent failures)
- Human must explicitly approve to continue
- No "maybe safe" outcomes

## Test Coverage

Total: 42 tests across 8 test classes

**Commitment Basics (6 tests)**
- Unique IDs, hash computation, determinism, hash changes

**Constraints (4 tests)**
- Latency, data access, API call creation and serialization

**Manager Operations (6 tests)**
- Propose, commit, retrieve, begin execution, error handling

**Clean Execution (5 tests)**
- No constraints, latency OK, data whitelist, API whitelist, multiple actions

**Hijacking Detection (5 tests)**
- Unauthorized data access, latency violation, unauthorized API call, context pollution

**Escalation (2 tests)**
- Critical hijacking escalation, evidence inclusion

**AP2 Integration (2 tests)**
- Commitment recording, verification recording

**Edge Cases (4 tests)**
- Empty constraints, single-value constraints, large action sequences, nonexistent commitments

**Verification Report (4 tests)**
- Report structure, all detections included

## Production Deployment Checklist

- [ ] All 42 tests passing
- [ ] Code review complete (0.1 bugs per 100 lines)
- [ ] AP2 ledger integration tested
- [ ] Ed25519 signature generation working
- [ ] Git anchoring of proof digests
- [ ] Escalation mechanism wired to security team
- [ ] Latency benchmarks: constraint checks <10ms
- [ ] Documentation complete
- [ ] Security team appeal ready (OWASP ASI01 defense)

## Known Limitations & Future Work

1. **Single-agent scope**: Current design assumes one agent per commitment. Multi-agent coordination requires extended design.
2. **Constraint granularity**: Whitelists are exact match. Could extend to patterns/regex.
3. **Context hash**: Currently manual. Could auto-capture via instrumentation.
4. **Real-time verification**: Relies on immediate action recording. Async operations need special handling.
5. **Goal drift detection**: Currently binds to goal text. Could add semantic drift detection via embeddings.

## References

- OWASP ASI01: LLM Agent Security (this defense targets goal hijacking + privilege escalation)
- AP2 Ledger: smaos/l6_infrastructure/ap2_ledger.py
- Unlazy Gates: smaos/l3_tooling/unlazy_gates.py
- Policy Router: smaos/l1_reasoning/policy_router.py
