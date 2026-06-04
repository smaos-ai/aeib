# Vision API — Governance Decision Support Layer

## Overview

The Vision API provides fail-closed governance enforcement for application decision flows. It evaluates requests against Human Gate policies, classifying risk levels and requiring human approval for high-risk actions.

The implementation is in pure Python (`vision_api.py`) with FastAPI HTTP bindings (`vision_api_fastapi.py`).

**Key Properties:**
- Fail-closed: Unapproved high-risk requests → zero charge, error returned
- Cryptographic audit: Merkle proofs accumulate decision history
- AP2 integration: Approved requests include charge_amount for ledger
- Performance: p99 <100ms, 1K+ req/sec throughput

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI server
python3 -m uvicorn vision_api_fastapi:app --host 0.0.0.0 --port 8000

# Or use the deployment script
bash deploy_localhost.sh
```

## Module: `vision_api`

### Classes and Types

#### `RiskLevel` (Enum)

Risk classification for actions (0.0-1.0 blast radius).

**Values:**
- `RiskLevel.LOW` — blast_radius < 0.25 (auto-approved)
- `RiskLevel.MEDIUM` — 0.25 ≤ blast_radius < 0.5 (auto-approved)
- `RiskLevel.HIGH` — 0.5 ≤ blast_radius < 0.75 (requires approval)
- `RiskLevel.CRITICAL` — blast_radius ≥ 0.75 (requires approval)

**Methods:**

```python
RiskLevel.from_blast_radius(radius: float) -> RiskLevel
```
Convert blast radius (0.0-1.0) to RiskLevel enum.

```python
risk_level.requires_approval() -> bool
```
Check if human approval required for this risk level.

**Example:**
```python
from vision_api import RiskLevel

risk = RiskLevel.from_blast_radius(0.8)
print(risk)  # RiskLevel.HIGH
print(risk.requires_approval())  # True
```

#### `HumanGatePolicy` (@dataclass)

Defines approval requirements per risk level and system configuration.

**Fields:**
- `policy_id: str` — Unique policy identifier (default: "default-human-gate")
- `requires_approval_for: List[RiskLevel]` — Risk levels requiring approval (default: [HIGH, CRITICAL])
- `ap2_charge_enabled: bool` — Whether to charge AP2 ledger on approval (default: True)
- `psi_drift_threshold: float` — PSI threshold for auto-engaging gate (default: 0.25)
- `max_concurrent_approvals: int` — Max concurrent approval requests (default: 10)
- `approval_timeout_secs: int` — Approval request timeout in seconds (default: 3600)

**Methods:**
```python
policy.needs_approval(risk_level: RiskLevel) -> bool
```
Check if approval required for given risk level.

**Example:**
```python
from vision_api import HumanGatePolicy, RiskLevel

policy = HumanGatePolicy(ap2_charge_enabled=True)
print(policy.needs_approval(RiskLevel.HIGH))  # True
print(policy.needs_approval(RiskLevel.LOW))   # False
```

#### `GovernRequest` (@dataclass)

Request to check governance policy before execution.

**Fields:**
- `request_id: str` — Unique request identifier
- `action: str` — Action being evaluated (e.g., "read", "delete")
- `blast_radius: float` — Risk score (0.0-1.0)
- `user_id: str` — User identifier
- `app_id: str` — Application identifier
- `human_approved: bool` — Whether human explicitly approved
- `timestamp: str` — ISO8601 timestamp (auto-set if not provided)

**Example:**
```python
from vision_api import GovernRequest

req = GovernRequest(
    request_id="req-001",
    action="read_file",
    blast_radius=0.1,
    user_id="user-1",
    app_id="app-1",
    human_approved=False,
)
```

#### `HumanGateProof` (@dataclass)

Merkle proof + audit metadata returned when gate passes.

**Fields (read-only):**
- `merkle_root: str` — Accumulated Merkle hash of all gate decisions
- `timestamp: str` — ISO8601 approval timestamp
- `decision_id: str` — Reference to request
- `approved_by: Optional[str]` — Human approver ID (if human-approved)
- `auto_approved: bool` — Whether auto-approved due to low risk

**Example:**
```python
# Returned in PreExecuteCheckResult.proof
if result.proof:
    print(result.proof.merkle_root)
    print(result.proof.approved_by)
```

#### `PreExecuteCheckResult` (@dataclass)

Result of pre-execution governance check.

**Fields (read-only):**
- `allowed: bool` — Whether action is approved
- `charge_amount: int` — AP2 ledger charge (0 if blocked)
- `proof: Optional[HumanGateProof]` — Merkle proof if allowed
- `error: Optional[str]` — Error code if blocked (e.g., "HumanGateRequired")
- `reason: str` — Human-readable reason

**Example:**
```python
# Returned by VisionAPI.pre_execute_check()
if result.allowed:
    print(f"Approved, charge: {result.charge_amount}")
    print(f"Proof: {result.proof.merkle_root}")
else:
    print(f"Blocked: {result.error}")
    print(f"Reason: {result.reason}")
```

#### `VisionAPI` (Class)

Main governance decision engine.

**Constructor:**
```python
api = VisionAPI()
```

**Methods:**

```python
api.pre_execute_check(request: GovernRequest) -> PreExecuteCheckResult
```
Evaluate governance policy for a request. **Fail-closed**: returns zero charge + error if not approved.

**Flow:**
1. Classify risk level from blast_radius
2. Check if human approval is required
3. If required and not approved → block (return error, zero charge)
4. If approved or low-risk → generate Merkle proof + return charge authorization

**Returns:**
- `PreExecuteCheckResult` with allowed flag, charge_amount, and Merkle proof

**Example:**
```python
from vision_api import VisionAPI, GovernRequest

api = VisionAPI()

# Low-risk request (auto-approved)
req = GovernRequest(
    request_id="req-1",
    action="read",
    blast_radius=0.1,
    user_id="user-1",
    app_id="app-1",
    human_approved=False,
)
result = api.pre_execute_check(req)
print(result.allowed)  # True
print(result.charge_amount)  # 100

# High-risk request without approval (blocked)
req2 = GovernRequest(
    request_id="req-2",
    action="delete",
    blast_radius=0.9,
    user_id="user-2",
    app_id="app-2",
    human_approved=False,
)
result2 = api.pre_execute_check(req2)
print(result2.allowed)  # False
print(result2.charge_amount)  # 0
print(result2.error)  # "HumanGateRequired"
```

```python
api.check_drift_detection(baseline: List[float], current: List[float]) -> bool
```
Check if drift detection (PSI > threshold) should auto-engage human gate.

**Returns:** `True` if PSI > policy.psi_drift_threshold

**Example:**
```python
baseline = [100.0, 101.0, 99.0, 100.0, 101.0]
current = [80.0, 80.0, 80.0, 80.0, 80.0]  # 20% shift

if api.check_drift_detection(baseline, current):
    print("Significant drift detected, human approval required")
```

```python
api.compute_psi(baseline: List[float], current: List[float]) -> float
```
Compute Population Stability Index for drift detection.

**Returns:** PSI score (0.0-1.0)

**Example:**
```python
psi = api.compute_psi(baseline, current)
print(f"PSI: {psi:.3f}")
if psi > 0.25:
    print("High drift!")
```

## Error Codes

When `result.allowed == False`, `result.error` contains:

- `"HumanGateRequired"` — Human approval required for risk level
- `"DriftGateRequired"` — PSI drift detected, approval required

## Fail-Closed Guarantee

**The gate always fails closed:**
- If approval is required and not provided → `allowed = False`, `charge_amount = 0`
- No partial charges, no edge cases
- Zero-charge rejection ensures cost is borne by requester (incentive alignment)

## AP2 Ledger Integration

When `result.allowed == True`:
- `charge_amount = 100` (AP2 units)
- Client should charge user's AP2 ledger
- `proof` can be stored for audit/compliance

When `result.allowed == False`:
- `charge_amount = 0`
- No ledger charge (fail-closed)

## Performance (Target SLO)

- p99 latency: <100ms
- p95 latency: <50ms
- Throughput: 1,000+ req/sec per instance

## Testing

See `test_pyo3_integration.py` for comprehensive test examples.

```bash
cd services/planet-dashboard
pip install -r requirements.txt
pytest test_pyo3_integration.py -v
```

## API Endpoints (FastAPI)

### POST /v1/govern

Governance decision endpoint (fail-closed).

**Request:**
```json
{
  "request_id": "req-001",
  "action": "read_file",
  "blast_radius": 0.1,
  "user_id": "user-1",
  "app_id": "app-1",
  "human_approved": false
}
```

**Response (Approved):**
```json
{
  "approved": true,
  "charge_amount": 100,
  "merkle_proof": {
    "merkle_root": "abc123...",
    "timestamp": "2026-06-04T12:00:00Z",
    "decision_id": "req-001",
    "approved_by": null,
    "auto_approved": true
  },
  "error": null,
  "reason": "Approved (risk: LOW)",
  "request_id": "req-001",
  "timestamp": "2026-06-04T12:00:00.123Z"
}
```

**Response (Blocked):**
```json
{
  "approved": false,
  "charge_amount": 0,
  "merkle_proof": null,
  "error": "HumanGateRequired",
  "reason": "Request requires human approval for risk level HIGH",
  "request_id": "req-002",
  "timestamp": "2026-06-04T12:00:01.456Z"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "uptime_seconds": 123.45,
  "requests_processed": 4567
}
```

### GET /metrics

Performance metrics endpoint.

**Response:**
```json
{
  "uptime_seconds": 123.45,
  "requests_processed": 4567,
  "avg_request_time_ms": 27.1
}
```

## Implementation Notes

**Thread Safety:** `VisionAPI` is thread-safe (uses immutable computation).

**State:** The API maintains an internal merkle root accumulator for audit trails.

**Determinism:** Given the same request, the API returns the same decision (deterministic).
