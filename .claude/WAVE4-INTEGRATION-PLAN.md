# WAVE 4 INTEGRATION PLAN — Final Architecture Synthesis

**Status:** LOCKED & READY FOR IMPLEMENTATION  
**Target:** Unified pipeline from task submission → mandate evaluation → cockpit streaming → S3 archival  
**Timeline:** 3 sequential phases (4-6 hours estimated)  
**Success Criteria:** All components wired, end-to-end tests passing, cockpit receives real-time SSE updates

---

## INTEGRATION OVERVIEW

**Current State:**
- ✓ Wave 4: Async Task Router (13/13 tests passing, merged to main)
- ✓ Wave 3: Observability Layer (40/40 tests passing, merged to main)
- ✓ Phase 25: Behavioral Firewall (76/76 tests passing, merged to main)

**Integration Goal:**
```
HTTP Request
    ↓
[Async Task Router] (bounded queue, 8 workers, 5-permit semaphore)
    ↓
[MandateVerifier] (ReBAC → AP2 → Temporal, Phase 25)
    ↓
[OTel Tracer] (trace_id binding, phase latencies)
    ↓
[Telemetry Router] (SSE payload transform, <100ms latency)
    ↓
[A2UI Cockpit] (real-time streaming via Server-Sent Events)
    ↓
[Audit Archiver] (PostgreSQL → S3, 90-day lifecycle)
```

---

## PHASE 1: BEHAVIORAL FIREWALL INTEGRATION (1.5 hours)

### Goal
Wire `siss-task-router` to consume and execute `siss-behavioral-firewall` MandateVerifier for every queued task.

### Files to Modify
1. **`crates/siss-task-router/src/lib.rs`**
   - Import: `use siss_gatekeeper::mandate_verifier::{MandateVerifier, EvaluationRequest};`
   - Extend `AsyncTaskRouter` struct: add `mandate_verifier: Arc<MandateVerifier>`
   - Extend `AsyncTaskRouter::new()`: inject MandateVerifier instance
   - Modify worker loop: before processing task, call `mandate_verifier.evaluate(request).await`
   - Handle denial: if Deny, return early with RequestTimeoutError (fail-closed)

2. **`crates/siss-gatekeeper/src/lib.rs`**
   - Extend `MandateVerifier::evaluate()` to accept `MandateTask` input
   - Return decision with phase breakdown (ReBAC latency, AP2 latency, Temporal latency)

### Critical Constraints
- **Database Connection Pool:** The 5-permit semaphore in AsyncTaskRouter MUST wrap the ReBAC/AP2/Temporal queries to prevent PostgreSQL saturation
- **Fail-Closed:** Any DB timeout or evaluation error → Deny (no partial decisions)
- **Trace Propagation:** MandateTask.trace_id must flow through MandateVerifier to decision output

### Testing
- Create integration test: submit 50 MandateTasks, verify all evaluated through behavioral firewall
- Assert: decision outcomes match Phase 25 semantics (Deny on blacklist, rate limit, etc.)

---

## PHASE 2: OBSERVABILITY & STREAMING (2 hours)

### Goal
Bind Wave 3 observability layer to task execution. Emit OTel traces → SSE → A2UI cockpit in real-time.

### Files to Modify
1. **`crates/siss-task-router/src/lib.rs`** (worker loop)
   - Import: `use siss_otel_tracer::{TraceContext, MandateDecision, PhaseOutcome};`
   - Create TraceContext at task intake: `let ctx = TraceContext { trace_id, root_span_id, agent_id, task_id, ... }`
   - Call: `mandate_verifier.evaluate_with_trace(request, ctx).await`
   - Collect MandateDecision with phase_outcomes
   - Return decision + full trace data to task result

2. **`crates/siss-telemetry-router/src/lib.rs`**
   - Import: `use siss_task_router::{MandateTask, RoutingResult};`
   - Create `transform_decision_to_sse()` function
   - Input: MandateDecision (from task router)
   - Output: SSEPayload (JSON, <100ms)
   - Enforce latency SLA: assert total_latency_ms + telemetry_overhead < 100ms

3. **`crates/siss-cockpit/src/handlers/task_router_integration.rs`** (NEW FILE)
   - Create HTTP endpoint: `POST /api/v1/mandate` accepts MandateTask
   - Call: `router.submit_task(task).await`
   - Await decision from telemetry router
   - Stream SSEPayload via response: `data: {...}\n\n`
   - Handle backpressure: if CapacityExhausted, return HTTP 429

### Critical Constraints
- **Latency Budget:** ReBAC + AP2 + Temporal + OTel instrumentation + SSE transform ≤ 100ms (p95)
- **Concurrent Trace Isolation:** 100 concurrent tasks = 100 distinct OTel traces, zero bleed
- **SSE Format:** Exact format `data: {json}\n\n` with proper charset headers

### Testing
- Integration test: Submit MandateTask, verify SSE event received at cockpit within 100ms
- Latency test: Measure end-to-end from submission to cockpit SSE with telemetry overhead

---

## PHASE 3: AUDIT ARCHIVAL LIFECYCLE (1.5 hours)

### Goal
Enable PostgreSQL audit_traces table monitoring and S3 cold storage archival.

### Files to Modify
1. **`crates/siss-audit-archiver/src/lib.rs`**
   - Create database migration: `audit_traces` table schema
     ```sql
     CREATE TABLE audit_traces (
         id BIGINT PRIMARY KEY,
         trace_id UUID,
         agent_id UUID,
         task_id UUID,
         event_type TEXT,
         decision TEXT,
         deny_reason TEXT,
         evaluation_latency_ms FLOAT,
         phase_outcomes JSONB,
         created_at TIMESTAMP,
         archived_at TIMESTAMP,
         s3_path TEXT,
         cryptographic_hash TEXT
     );
     CREATE INDEX idx_created_at ON audit_traces(created_at);
     CREATE INDEX idx_archived_at ON audit_traces(archived_at);
     ```

2. **`crates/siss-task-router/src/lib.rs`** (worker loop final step)
   - After decision made, emit to audit archiver
   - Call: `audit_archiver.ingest_trace(MandateDecision).await`
   - This inserts to PostgreSQL audit_traces table with decision data

3. **`crates/siss-audit-archiver/src/lib.rs`** (background job)
   - Create background task: `archive_background_job(archiver, pool, interval)`
   - Runs every 1 hour:
     1. Query: `SELECT * FROM audit_traces WHERE archived_at IS NULL AND created_at < NOW() - interval '90 days'`
     2. For each trace: `archive_to_s3(&trace)`
     3. Update: `archived_at = NOW(), s3_path = ..., cryptographic_hash = ...`
     4. Delete: from PostgreSQL (move to cold storage)

### Critical Constraints
- **90-Day TTL:** Hot storage (PostgreSQL) exactly 90 days, not 89 or 91
- **Atomicity:** Trace must exist in PostgreSQL and S3 simultaneously during transition
- **Immutability:** Once in S3, cryptographic hash prevents tampering; delete from PostgreSQL only after verification
- **S3 Path Format:** `s3://bucket/audit_archive/YYYY/MM/{trace_id}.jsonl` (month-partitioned for query efficiency)

### Testing
- Integration test: Submit MandateTask, verify audit trace inserted to PostgreSQL within 100ms
- Lifecycle test: Manually age trace to 91 days, trigger archival, verify S3 path, verify PostgreSQL deletion

---

## INTEGRATION CHECKLIST

### Pre-Implementation
- [ ] All Wave 3 & Phase 25 tests passing (baseline)
- [ ] Wave 4 task router 13/13 passing (baseline)
- [ ] PostgreSQL dev instance running (for audit_traces table)
- [ ] S3 bucket created (for audit archival)

### Phase 1: Firewall Integration
- [ ] MandateVerifier accepts MandateTask input
- [ ] Worker loop calls mandate_verifier.evaluate()
- [ ] Deny decisions trigger fail-closed (RequestTimeoutError)
- [ ] Integration test: 50 tasks evaluated, decisions returned
- [ ] All behavioral firewall Phase 25 tests still passing

### Phase 2: Observability & Streaming
- [ ] TraceContext created at task intake
- [ ] OTel spans recorded with phase breakdown
- [ ] SSEPayload generated from MandateDecision
- [ ] Latency SLA verified: <100ms p95
- [ ] Cockpit HTTP endpoint receives SSE
- [ ] 100 concurrent tasks verified: 100 unique traces, zero bleed
- [ ] A2UI cockpit displays real-time updates

### Phase 3: Audit Archival
- [ ] PostgreSQL audit_traces table created
- [ ] Traces inserted on decision evaluation
- [ ] Background job runs hourly
- [ ] Traces aged >90 days archived to S3
- [ ] Cryptographic hash verified on retrieval
- [ ] PostgreSQL deletion triggered only after S3 verification
- [ ] Lifecycle test: trace → hot storage → cold storage

### Post-Integration
- [ ] End-to-end test: Submit request → evaluate → cockpit stream → archive
- [ ] Load test: 1000+ concurrent tasks, verify queue saturation, cockpit updates
- [ ] Failure injection: DB down, S3 down, worker panic → system survives
- [ ] All 200+ tests (Phase 25 + Wave 3 + Wave 4 + integration) passing

---

## RISK MITIGATION

### Database Saturation
- **Mitigation:** 5-permit semaphore in AsyncTaskRouter limits concurrent DB queries
- **Monitoring:** Track active_tasks counter, alert if >10 for >5sec (indicates DB slowness)

### Latency SLA Breach
- **Mitigation:** Timeout tasks if exceed 500ms total
- **Monitoring:** Prometheus histogram: task_latency_ms by phase (ReBAC, AP2, Temporal, telemetry)

### S3 Archival Failure
- **Mitigation:** Retry with exponential backoff; if fail after 5 retries, keep in PostgreSQL (manual review)
- **Monitoring:** Track archive_failures counter, alert if >10/hour

### Concurrency Bleed
- **Mitigation:** TaskContext isolation verified by test suite; tokio::spawn() guarantees isolation
- **Monitoring:** Assert 0 trace_id collisions in cockpit event stream

---

## SUCCESS CRITERIA (Wave 4 Complete)

✓ All 13 task router tests passing  
✓ All 40 Wave 3 observability tests passing  
✓ All 76 Phase 25 behavioral firewall tests passing  
✓ End-to-end integration test: request → cockpit SSE within 100ms  
✓ Audit archival working: traces → PostgreSQL → S3 with cryptographic verification  
✓ Load test: 1000+ tasks/min, p95 <10ms, zero cascading failures  
✓ Cockpit displaying real-time mandate decisions with phase breakdown  

**Once complete: Ready for Wave 5 Chaos Petri failure injection testing.**

---

## NEXT STEPS

1. User reviews and authorizes integration plan
2. Proceed to Phase 1 (Firewall Integration) with explicit orders
3. Upon Phase 1 completion, Phase 2 (Observability & Streaming)
4. Upon Phase 2 completion, Phase 3 (Audit Archival)
5. Upon all 3 phases, conduct end-to-end validation
6. Proceed to Wave 5: Chaos Petri matrix testing

**Standing by for authorization to begin Phase 1.**
