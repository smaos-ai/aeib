# WAVE 3: Unified Observability Layer — Complete Specification

## Executive Summary

Wave 3 transforms the behavioral firewall from opaque to transparent. Every access decision, rate-limit trigger, and attribute evaluation now emits structured telemetry that flows directly into the A2UI cockpit via Server-Sent Events (SSE). The Strategic Orchestrator sees the exact failure trace in real-time, enabling diagnosis of silent denials and performance bottlenecks at scale.

**Strategic Principle:** We will not scale beyond 1,000 concurrent tasks/min without the nervous system connected. Observability is not optional; it is a prerequisite for Wave 4.

---

## 1. OpenTelemetry Tracing Architecture

### 1.1 Unified Trace Context

**Trace Identity:**
- `trace_id`: UUID generated at task entry point (propagated through all three phases)
- `span_id`: UUID per phase/module (ReBAC, AP2, Temporal)
- `parent_span_id`: Links child spans to their orchestrator parent

**Root Span Attributes (emitted by MandateVerifier):**
```json
{
  "trace_id": "uuid",
  "root_span_id": "uuid",
  "agent_id": "sovereign_identity.id",
  "intent_hash": "sha256(action + resource + context)",
  "task_id": "uuid",
  "timestamp": "ISO8601 UTC",
  "total_latency_ms": 42.5,
  "decision": "Allow | Deny",
  "decision_reason": "Deny: ReBAC denied (no Operator relationship)",
  "phase_outcomes": [
    { "phase": "ReBAC", "result": "Allow", "latency_ms": 2.1 },
    { "phase": "AP2", "result": "Allow", "latency_ms": 1.8 },
    { "phase": "Temporal", "result": "Deny", "latency_ms": 38.6 }
  ]
}
```

---

### 1.2 ReBAC Tracing (siss-behavioral-firewall::rebac)

**Span Name:** `rebac.verify_relationship`

**Emitted Events:**
1. **Relationship Query Start**
   ```json
   {
     "event": "rebac.query_start",
     "sovereign_id": "uuid",
     "resource_type": "Agent | Task | Vault",
     "action": "Spawn | Pause | Resume | ...",
     "timestamp": "ISO8601"
   }
   ```

2. **Graph Traversal (per hop in delegation chain)**
   ```json
   {
     "event": "rebac.delegation_hop",
     "hop_number": 1,
     "from_sovereign": "uuid",
     "to_sovereign": "uuid",
     "relationship_type": "Owner | Operator | Observer | Delegate | Participant | Initiator",
     "depth": 2,
     "max_depth_allowed": 3,
     "latency_ms": 0.8
   }
   ```

3. **Cycle Detection**
   ```json
   {
     "event": "rebac.cycle_detected",
     "cycle_sovereigns": ["uuid1", "uuid2", "uuid3"],
     "depth_exceeded": false,
     "action": "Deny"
   }
   ```

4. **Relationship Query Result**
   ```json
   {
     "event": "rebac.query_result",
     "result": "Allow | Deny",
     "reason": "Owner found in delegation chain" | "Cycle detected" | "Expired relationship" | "Unknown relationship",
     "total_hops": 2,
     "total_latency_ms": 3.5,
     "cache_hit": false,
     "postgres_queries": 4
   }
   ```

---

### 1.3 AP2 Tracing (siss-behavioral-firewall::ap2)

**Span Name:** `ap2.evaluate`

**Emitted Events:**
1. **Attribute Fetch**
   ```json
   {
     "event": "ap2.attribute_fetch",
     "sovereign_id": "uuid",
     "cache_status": "hit | miss | expired",
     "attributes": {
       "trust_level": 75,
       "reputation": 120,
       "joined_at": "ISO8601",
       "blacklisted": false,
       "certifications": ["cert1", "cert2"]
     },
     "latency_ms": 1.2
   }
   ```

2. **Policy Rule Evaluation (per rule)**
   ```json
   {
     "event": "ap2.rule_evaluation",
     "rule_id": "uuid",
     "rule_name": "high_trust_operator",
     "priority": 10,
     "applies_to": "Spawn",
     "predicate_type": "TrustLevel | ReputationScore | And | Or | Not",
     "predicate_value": 75,
     "required_value": 50,
     "result": true,
     "latency_ms": 0.3
   }
   ```

3. **Deny Predicate (only emitted on deny)**
   ```json
   {
     "event": "ap2.deny_predicate",
     "rule_id": "uuid",
     "rule_name": "blacklist_check",
     "predicate": "NotBlacklisted",
     "reason": "Agent is blacklisted",
     "latency_ms": 0.5
   }
   ```

4. **Evaluation Result**
   ```json
   {
     "event": "ap2.evaluation_result",
     "result": "Allow | Deny",
     "rules_evaluated": 5,
     "rules_passed": 4,
     "deny_rule_id": "uuid",
     "deny_rule_name": "blacklist_check",
     "total_latency_ms": 2.8,
     "cache_freshness_secs": 45
   }
   ```

---

### 1.4 Temporal Tracing (siss-behavioral-firewall::temporal)

**Span Name:** `temporal.check`

**Emitted Events:**
1. **Rate Limit Check**
   ```json
   {
     "event": "temporal.rate_limit_check",
     "sovereign_id": "uuid",
     "requests_in_window": 59,
     "limit_per_minute": 60,
     "window_remaining_secs": 23.5,
     "result": "Allow",
     "latency_ms": 0.2
   }
   ```

2. **Rate Limit Exceeded**
   ```json
   {
     "event": "temporal.rate_limit_exceeded",
     "sovereign_id": "uuid",
     "requests_in_window": 61,
     "limit_per_minute": 60,
     "oldest_request_age_secs": 42.3,
     "newest_request_age_secs": 0.1,
     "action": "Deny"
   }
   ```

3. **Time Window Check**
   ```json
   {
     "event": "temporal.time_window_check",
     "action": "Spawn",
     "current_hour_utc": 14,
     "blackout_dates": [{"month": 12, "day": 25}],
     "allowed_hours": [[9, 17], [20, 22]],
     "is_blackout_date": false,
     "is_allowed_hour": true,
     "result": "Allow",
     "latency_ms": 0.1
   }
   ```

4. **Time Window Denied**
   ```json
   {
     "event": "temporal.time_window_denied",
     "action": "Spawn",
     "reason": "blackout_date | outside_allowed_hours",
     "current_utc": "2026-05-22T14:30:00Z",
     "blackout_match": {"month": 5, "day": 22},
     "latency_ms": 0.1
   }
   ```

5. **Composite Check Result**
   ```json
   {
     "event": "temporal.check_result",
     "rate_limit_result": "Allow",
     "time_window_result": "Allow",
     "composite_result": "Allow",
     "total_latency_ms": 0.3
   }
   ```

---

## 2. Network Observability (Bandwidth Integration)

### 2.1 Process-Level Bandwidth Monitoring

**Crate:** `siss-bandwidth-monitor` (new)

**Monitored Metrics per Sandboxed Agent:**
- `bytes_sent`: Egress traffic (should be zero except to orchestrator)
- `bytes_received`: Ingress traffic (should be zero except from orchestrator)
- `packets_sent`: Packet count (anomaly detection)
- `packets_received`: Packet count (anomaly detection)
- `connection_attempts`: Unauthorized external connections (dropped by eBPF filter)

**Emitted Event (per agent per minute):**
```json
{
  "event": "bandwidth.summary",
  "agent_id": "uuid",
  "sampling_window_secs": 60,
  "bytes_sent": 0,
  "bytes_received": 4096,
  "packets_sent": 0,
  "packets_received": 8,
  "connection_attempts_blocked": 0,
  "anomaly_score": 0.0,
  "timestamp": "ISO8601"
}
```

---

## 3. AG-UI Telemetry Stream (SSE Integration)

### 3.1 Event Router: OTel → SSE Payload

**Crate:** `siss-telemetry-router` (new)

**SSE Payload Schema (mandate denial):**
```json
{
  "event_type": "mandate_denial",
  "trace_id": "uuid",
  "agent_id": "sovereign_id.uuid",
  "task_id": "uuid",
  "timestamp": "ISO8601",
  "decision": "Deny",
  "deny_phase": "Temporal",
  "deny_reason": "Rate limit exceeded (61 req/min)",
  "phase_breakdown": [
    { "phase": "ReBAC", "result": "Allow", "latency_ms": 2.1 },
    { "phase": "AP2", "result": "Allow", "latency_ms": 1.8 },
    { "phase": "Temporal", "result": "Deny", "latency_ms": 38.6 }
  ],
  "total_evaluation_latency_ms": 42.5
}
```

---

## 4. Audit Archive TTL & Cold Storage

### 4.1 Hot Storage (PostgreSQL)

**Table:** `audit_traces`
```sql
CREATE TABLE audit_traces (
  id BIGSERIAL PRIMARY KEY,
  trace_id UUID NOT NULL,
  agent_id UUID NOT NULL,
  task_id UUID,
  event_type TEXT NOT NULL,
  decision TEXT NOT NULL,
  deny_reason TEXT,
  evaluation_latency_ms FLOAT NOT NULL,
  phase_outcomes JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ON (agent_id, created_at),
  INDEX ON (trace_id)
);
```

**Retention Policy:** 90 days of hot storage (indexed, queryable from cockpit)

### 4.2 Cold Storage (S3 Immutable Archive)

**Bucket:** `sovereign-nexus-audit-archive`
**Lifecycle Policy:** Retain indefinitely

**Partition Scheme:**
```
s3://sovereign-nexus-audit-archive/audit_archive/2026/05/{trace_id}.jsonl
```

---

## 5. Implementation Crates

### 5.1 Crate: `siss-otel-tracer`
**Purpose:** Unified OpenTelemetry SDK initialization and trace emission
**Responsibilities:**
- Instrument MandateVerifier (root span)
- Instrument ReBAC verify_relationship() (child spans)
- Instrument AP2Evaluator.evaluate() (child spans)
- Instrument TemporalGuard.check() (child spans)
- Export spans to OTLP receiver

### 5.2 Crate: `siss-telemetry-router`
**Purpose:** Route OTel → SSE for real-time cockpit updates
**Responsibilities:**
- Subscribe to OTLP receiver output
- Filter by decision type and agent_id
- Transform OTel span → AG-UI SSE payload
- Route to A2UI cockpit via ServerSentEventsStream

### 5.3 Crate: `siss-audit-archiver`
**Purpose:** Manage audit trace lifecycle (hot → cold storage)
**Responsibilities:**
- Daily job: query audit_traces older than 90 days
- Serialize to JSONL, upload to S3
- Delete from PostgreSQL

### 5.4 Crate: `siss-bandwidth-monitor`
**Purpose:** Track per-agent network I/O
**Responsibilities:**
- Hook into kernel-level packet inspection
- Emit bandwidth.summary events per agent per minute
- Detect anomalies (unexpected egress)
- Route to telemetry-router for cockpit display

---

## 6. Success Criteria

- Every mandate decision emits a complete trace with phase breakdown
- Mandate denials appear in A2UI cockpit within 100ms
- ReBAC graph queries include PostgreSQL query count and latency
- AP2 predicate evaluation shows which rule denied
- Temporal denials include rate-limit window snapshot
- Audit traces archive to S3 after 90 days without data loss
- Bandwidth anomalies trigger alerts
- Cold storage archive is immutable

---

## Testing Strategy (TDD)

### Phase 1: RED
Create comprehensive test suites for trace context propagation, OTel event emission, SSE payload transformation, S3 archive lifecycle, and bandwidth anomaly detection.

### Phase 2: GREEN
Implement TraceContext structs, OTel instrumentation hooks, telemetry router with SSE transforms, audit archiver with TTL enforcement, and bandwidth monitor.

### Phase 3: REFACTOR
Optimize trace filtering, tune archive scheduling, profile bandwidth monitoring overhead.

---

## Architectural Decisions (Locked)

1. **OpenTelemetry as Single Source of Truth:** All observability flows from OTel spans.
2. **Hot/Cold Split at 90 Days:** Real-time queryability + indefinite retention.
3. **SSE for Real-Time Cockpit Updates:** Leverages Phase 32 SSE infrastructure.
4. **Per-Agent Bandwidth Monitoring:** Catches unauthorized external calls at kernel level.
5. **Immutable S3 Archive:** Ensures cryptographic audit trail is legally defensible.

---

Ready for implementation. All telemetry contracts are finalized. Proceeding with TDD.
