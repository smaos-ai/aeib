# Phase 37: Agent-User Interaction Protocol (AG-UI) — API Specification

OpenAPI 3.0 specification for RCE state machine exposure as real-time SSE stream + decision webhooks.

## Overview

Three core endpoints expose Phase 36 RCE to the AoE Cockpit:
1. **SSE Stream** (`GET /api/rce/stream`) — Real-time state transitions and interrupt signals
2. **Decision Webhook** (`POST /api/rce/decision`) — Human approval/rejection/modification handler
3. **Projection Resolvers** (`GET /api/rce/{workflow_id}/projection`) — π+ projection context for Visible Field

---

## 1. SSE Stream Endpoint

### Endpoint
```
GET /api/rce/stream
```

### Query Parameters
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `workflow_id` | UUID | No | Filter to specific workflow (default: all) |
| `severity_min` | string | No | Min severity to stream (Low, Medium, High, Critical) |

### Response

**Content-Type:** `text/event-stream`

**Connection:** Keep-alive, indefinite stream

**Timeout:** 30-second keep-alive ping if no events

### Event Types & Schemas

#### Event: `workflow_started`
Emitted when RCE transitions from Idle → Perform.

```json
{
  "event": "workflow_started",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-15T10:30:45.123Z",
  "data": {
    "step_count": 6,
    "plan": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "step_1",
        "timeout_ms": 1000,
        "idempotent": true
      }
    ]
  }
}
```

#### Event: `workflow_paused`
Emitted when RCE transitions from Perform → Paused (critical interrupt).

```json
{
  "event": "workflow_paused",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-15T10:30:50.456Z",
  "data": {
    "step_index": 2,
    "step_id": "550e8400-e29b-41d4-a716-446655440002",
    "step_name": "evaluate_threat_surface",
    "interrupt_reason": "threat_anticipation_blast_radius_high",
    "interrupt_severity": "High",
    "checkpoint_id": "ckpt_550e8400e29b41d4a716446655440000",
    "checkpoint_timestamp": "2026-05-15T10:30:50.456Z",
    "human_approval_required": true,
    "projection_context": {
      "type": "threat_anticipation",
      "tokens_at_risk": 600000,
      "threshold": 500000,
      "confidence": 0.92
    }
  }
}
```

#### Event: `workflow_resumed`
Emitted when RCE transitions from Paused → Resumed (after human decision).

```json
{
  "event": "workflow_resumed",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-15T10:31:00.789Z",
  "data": {
    "step_index": 2,
    "decision": "approve",
    "decision_reason": null,
    "decided_by": "operator@acme.com",
    "decision_timestamp": "2026-05-15T10:31:00.000Z"
  }
}
```

#### Event: `workflow_rejected`
Emitted when RCE transitions from Paused → Idle (reject path).

```json
{
  "event": "workflow_rejected",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-15T10:31:05.012Z",
  "data": {
    "reason": "operator_manual_override",
    "decided_by": "operator@acme.com",
    "decision_timestamp": "2026-05-15T10:31:05.000Z"
  }
}
```

#### Event: `workflow_completed`
Emitted when all steps executed successfully.

```json
{
  "event": "workflow_completed",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-05-15T10:35:00.345Z",
  "data": {
    "total_steps": 6,
    "execution_time_ms": 270000
  }
}
```

#### Event: `keep_alive`
Sent every 30 seconds if no other events.

```json
{
  "event": "keep_alive",
  "timestamp": "2026-05-15T10:30:60.000Z"
}
```

### SSE Serialization Format

```
event: workflow_paused
data: {"event":"workflow_paused","workflow_id":"550e8400-e29b-41d4-a716-446655440000",...}

event: keep_alive
data: {"event":"keep_alive","timestamp":"2026-05-15T10:30:60.000Z"}
```

### HTTP Status Codes
| Status | Condition |
|--------|-----------|
| 200 | Stream established |
| 400 | Invalid workflow_id or severity_min |
| 401 | Unauthorized (no bearer token) |
| 404 | Workflow not found |

### Example cURL
```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:3000/api/rce/stream?workflow_id=550e8400-e29b-41d4-a716-446655440000&severity_min=High"
```

---

## 2. Decision Webhook Endpoint

### Endpoint
```
POST /api/rce/decision
```

### Request Headers
```
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body

#### Approve Decision
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "Approve",
  "reason": null,
  "decided_by": "operator@acme.com"
}
```

#### Reject Decision
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "Reject",
  "reason": "operator_manual_override",
  "decided_by": "operator@acme.com"
}
```

#### Modify Decision
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "Modify",
  "new_plan": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440010",
      "name": "step_1_modified",
      "timeout_ms": 2000,
      "idempotent": true
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440011",
      "name": "step_2_new",
      "timeout_ms": 1500,
      "idempotent": true
    }
  ],
  "decided_by": "operator@acme.com"
}
```

### Request Schema Validation

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `workflow_id` | UUID | Yes | Must exist in RCE store |
| `decision` | enum | Yes | Must be "Approve", "Reject", or "Modify" |
| `reason` | string | No (required for Reject) | Max 1024 chars |
| `new_plan` | array | Required if decision="Modify" | Non-empty, valid Steps |
| `decided_by` | string | Yes | Email/identifier, max 256 chars |

### Response: 200 OK
Returned when decision successfully applied.

```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "Approve",
  "state_after": "Resumed",
  "step_index": 2,
  "timestamp": "2026-05-15T10:31:00.789Z",
  "checkpoint_verified": true,
  "next_action": "continue_workflow"
}
```

### Response: 200 OK (Reject)
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "Reject",
  "state_after": "Idle",
  "step_index": 0,
  "timestamp": "2026-05-15T10:31:05.012Z",
  "checkpoint_cleared": true,
  "next_action": "idle"
}
```

### Response: 200 OK (Modify)
```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision": "Modify",
  "state_after": "Resumed",
  "step_index": 2,
  "new_step_count": 2,
  "timestamp": "2026-05-15T10:31:00.789Z",
  "checkpoint_verified": true,
  "next_action": "continue_workflow"
}
```

### Error Responses

#### 400 Bad Request
Missing or invalid fields.

```json
{
  "error": "invalid_request",
  "message": "Field 'reason' required when decision='Reject'",
  "code": "MISSING_REQUIRED_FIELD"
}
```

#### 409 Conflict
Workflow not in Paused state.

```json
{
  "error": "invalid_state",
  "message": "Workflow 550e8400-e29b-41d4-a716-446655440000 in state 'Perform', not 'Paused'",
  "code": "STATE_MISMATCH",
  "current_state": "Perform"
}
```

#### 422 Unprocessable Entity
Checkpoint integrity failed.

```json
{
  "error": "checkpoint_integrity_failure",
  "message": "Checkpoint checksum mismatch: data may be corrupted",
  "code": "CHECKPOINT_CORRUPTED"
}
```

#### 404 Not Found
Workflow does not exist.

```json
{
  "error": "not_found",
  "message": "Workflow 550e8400-e29b-41d4-a716-446655440000 not found",
  "code": "WORKFLOW_NOT_FOUND"
}
```

#### 401 Unauthorized
Missing or invalid token.

```json
{
  "error": "unauthorized",
  "message": "Missing Authorization header",
  "code": "NO_AUTH_TOKEN"
}
```

### HTTP Status Codes
| Status | Condition |
|--------|-----------|
| 200 | Decision applied successfully |
| 400 | Validation error (missing/invalid fields) |
| 401 | Unauthorized |
| 404 | Workflow not found |
| 409 | Workflow not in Paused state |
| 422 | Checkpoint integrity check failed |
| 500 | Internal server error |

---

## 3. Projection Resolvers Endpoints

### Endpoint: Get Full Projection Context
```
GET /api/rce/{workflow_id}/projection
```

### Response: 200 OK

Returns the projection context that triggered the pause (if paused).

```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "Paused",
  "step_index": 2,
  "interrupt_reason": "threat_anticipation_blast_radius_high",
  "timestamp": "2026-05-15T10:30:50.456Z",
  "projections": {
    "threat_anticipation": {
      "type": "threat_anticipation",
      "tokens_at_risk": 600000,
      "threshold": 500000,
      "confidence": 0.92,
      "affected_sovereigns": [
        {
          "sovereign_id": "sov_001",
          "risk_level": "critical",
          "tokens_affected": 400000
        },
        {
          "sovereign_id": "sov_002",
          "risk_level": "high",
          "tokens_affected": 200000
        }
      ]
    },
    "root_cause": null,
    "swot": null
  }
}
```

### Endpoint: Get Threat Anticipation (π+_TA)
```
GET /api/rce/{workflow_id}/projection/threat-anticipation
```

### Response: 200 OK

```json
{
  "type": "threat_anticipation",
  "tokens_at_risk": 600000,
  "threshold": 500000,
  "confidence": 0.92,
  "affected_sovereigns": [
    {
      "sovereign_id": "sov_001",
      "risk_level": "critical",
      "tokens_affected": 400000,
      "threat_vector": "contract_exploit"
    },
    {
      "sovereign_id": "sov_002",
      "risk_level": "high",
      "tokens_affected": 200000,
      "threat_vector": "front_running"
    }
  ],
  "timestamp": "2026-05-15T10:30:50.456Z"
}
```

### Endpoint: Get Root Cause (π+_RC)
```
GET /api/rce/{workflow_id}/projection/root-cause
```

### Response: 200 OK

```json
{
  "type": "root_cause",
  "confidence": 0.95,
  "threshold": 0.90,
  "root_cause_chain": [
    {
      "depth": 0,
      "entity_type": "behavior",
      "entity_id": "behav_001",
      "description": "Suspicious token transfer patterns",
      "confidence": 0.95
    },
    {
      "depth": 1,
      "entity_type": "signal",
      "entity_id": "signal_001",
      "description": "Unusual velocity spike in transfers",
      "confidence": 0.92
    },
    {
      "depth": 2,
      "entity_type": "sovereign",
      "entity_id": "sov_001",
      "description": "Account origin traced to flagged pool",
      "confidence": 0.88
    }
  ],
  "timestamp": "2026-05-15T10:30:48.234Z"
}
```

### Endpoint: Get SWOT (π+_SWOT)
```
GET /api/rce/{workflow_id}/projection/swot
```

### Response: 200 OK

```json
{
  "type": "swot",
  "diversity_index": 0.45,
  "threshold": 0.50,
  "scenarios": {
    "strengths": [
      {
        "id": "strength_001",
        "description": "Strong historical compliance record",
        "weight": 0.3
      }
    ],
    "weaknesses": [
      {
        "id": "weakness_001",
        "description": "Insufficient KYC depth",
        "weight": 0.4
      }
    ],
    "opportunities": [
      {
        "id": "opportunity_001",
        "description": "Behavioral pattern learning",
        "weight": 0.2
      }
    ],
    "threats": [
      {
        "id": "threat_001",
        "description": "Account compromise risk",
        "weight": 0.5
      }
    ]
  },
  "timestamp": "2026-05-15T10:30:49.123Z"
}
```

### Endpoint: Get Checkpoint Summary
```
GET /api/rce/{workflow_id}/checkpoint
```

### Response: 200 OK

```json
{
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "checkpoint_id": "ckpt_550e8400e29b41d4a716446655440000",
  "state_index": 2,
  "timestamp": "2026-05-15T10:30:50.456Z",
  "reason": "threat_anticipation_blast_radius_high",
  "version": 1,
  "checksum_valid": true,
  "can_resume": true
}
```

### HTTP Status Codes
| Status | Condition |
|--------|-----------|
| 200 | Projection retrieved |
| 400 | Invalid workflow_id |
| 401 | Unauthorized |
| 404 | Workflow not found or projection not available |
| 500 | Internal error |

---

## 4. Shared Schemas

### Step Schema
```json
{
  "id": "UUID",
  "name": "string (max 256)",
  "timeout_ms": "integer (>0)",
  "idempotent": "boolean"
}
```

### Checkpoint Schema (Response Only)
```json
{
  "id": "UUID",
  "step_index": "integer",
  "timestamp": "RFC3339 timestamp",
  "reason": "string",
  "version": "integer",
  "checksum_valid": "boolean"
}
```

### Error Schema
```json
{
  "error": "string (error code)",
  "message": "string (human-readable)",
  "code": "string (ALL_CAPS enum)",
  "details": "object (optional, context-dependent)"
}
```

---

## 5. Authentication

All endpoints require Bearer token authentication:

```
Authorization: Bearer <JWT or opaque token>
```

Token validation:
- Extract from `Authorization: Bearer {token}` header
- Validate against configured auth provider (Keycloak, OAuth2, etc.)
- Reject 401 if missing or invalid
- Include `decided_by` field in webhook requests to identify operator

---

## 6. Rate Limiting & Quotas

| Endpoint | Rate Limit | Burst | Window |
|----------|-----------|-------|--------|
| SSE Stream | 1 stream/workflow | N/A | Session |
| Decision Webhook | 10 req/min | 2 | 1 minute |
| Projection Resolvers | 60 req/min | 5 | 1 minute |

---

## 7. Example Workflow: SSE + Webhook Integration

### Client Subscribes to SSE
```bash
curl -H "Authorization: Bearer token123" \
  http://localhost:3000/api/rce/stream?workflow_id=550e8400-e29b-41d4-a716-446655440000
```

### Server Emits: workflow_paused
```
event: workflow_paused
data: {"event":"workflow_paused","workflow_id":"550e8400...","data":{"tokens_at_risk":600000,...}}
```

### Client Fetches Projection Context
```bash
curl -H "Authorization: Bearer token123" \
  http://localhost:3000/api/rce/550e8400-e29b-41d4-a716-446655440000/projection/threat-anticipation
```

### Client Posts Decision
```bash
curl -X POST -H "Authorization: Bearer token123" \
  -H "Content-Type: application/json" \
  -d '{"workflow_id":"550e8400...","decision":"Approve","decided_by":"op@acme.com"}' \
  http://localhost:3000/api/rce/decision
```

### Server Emits: workflow_resumed
```
event: workflow_resumed
data: {"event":"workflow_resumed","workflow_id":"550e8400...","data":{"decision":"approve",...}}
```

---

## 8. Implementation Notes for Rust/Axum

- Use `axum::extract::ws::WebSocketUpgrade` for SSE (or `tokio-stream`)
- RCE state machine is behind a `tokio::sync::RwLock<ResumableCognitiveExecution>` in shared state
- Decision webhook must load checkpoint from durable storage (Postgres), verify checksum, apply decision
- Projection payloads come from `projection_repo` (Phase 35) — fetch latest by workflow_id
- SSE events must include real timestamps; use `chrono::Utc::now()`
- Serialize all responses with `serde_json`
- Implement custom error type for consistent error responses (implement `axum::response::IntoResponse`)

---

## 9. OpenAPI / Swagger Metadata

Title: **Agent-User Interaction Protocol (AG-UI)**  
Version: **1.0.0**  
Base URL: `/api/rce`  
Schemes: `https` (production), `http` (dev)  
Security: `BearerAuth` (OAuth2 / JWT)
