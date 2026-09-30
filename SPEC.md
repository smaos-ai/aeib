# WAVE 4: ASYNC TASK ROUTER & LOAD BALANCER — Complete Specification

## Executive Summary

Wave 4 enables SovereignNexus to safely process 1,000+ concurrent tasks per minute while maintaining strict observability through Wave 3's telemetry layer. The architecture must guarantee:

1. **No silent failures** — Every task passes through ReBAC/AP2/Temporal firewall
2. **Bounded memory** — Backpressure prevents OOM crashes under sustained load
3. **PostgreSQL resilience** — Connection pooling prevents database exhaustion
4. **Trace propagation** — Every concurrent task emits complete OpenTelemetry spans
5. **Deterministic ordering** — Task execution order is predictable (FIFO with priority)

**Strategic Principle:** We scale the nervous system in parallel with the muscle. Observability is not a luxury—it is the prerequisite for correctness at scale.

---

## 1. Rust Worker Pool Architecture

### 1.1 Core Design: Tokio-Based Async Runtime

**Crate:** `siss-async-router` (new)

**Architecture Diagram:**
```
┌─────────────────────────────────────────────────────────────┐
│ TASK INGRESS (HTTP/gRPC endpoint)                           │
│ - Validates agent_id, intent, resource                      │
│ - Generates trace_id, assigns priority                      │
│ - Enqueues task into bounded MPSC channel                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ ASYNC ROUTER: Bounded MPSC Queue (max_capacity=10,000)     │
│ - Task struct: { trace_id, agent_id, intent, priority }    │
│ - Applies backpressure: Enqueue fails if queue > 80% full  │
│ - Returns HTTP 429 (Too Many Requests) to caller           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ WORKER POOL: 32 Tokio tasks (CPU count: 4x multiplier)    │
│ - Each worker: `async fn worker_loop(rx: Receiver<Task>)` │
│ - Polls bounded channel for tasks (never blocks)           │
│ - Acquires DB connection from pool                         │
│ - Calls MandateVerifier::evaluate()                        │
│ - Emits OTel span (trace_id propagated)                    │
│ - Returns result or error to caller via Sender<Result>    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ RESULT HANDLER                                              │
│ - Sends decision (Allow/Deny) to caller via async channel  │
│ - Logs OTel span to telemetry-router                       │
│ - Updates metrics (latency, throughput, error rate)        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Worker Pool Configuration

**Pool Sizing:**
```rust
pub struct AsyncRouter {
    // CPU count detection
    num_workers: usize = num_cpus::get() * 4,  // 4x oversubscription
    
    // Queue bounds
    max_queue_capacity: usize = 10_000,         // Hard limit
    backpressure_threshold: f64 = 0.8,          // Reject at 80% full
    
    // Channel bounds
    task_channel: bounded_channel(max_queue_capacity),
    result_channel: bounded_channel(num_workers),
    
    // Resource limits
    db_connection_pool: PgPool {
        min_connections: 16,
        max_connections: 256,  // Reserve 4 connections per worker
        connection_timeout: Duration::from_secs(5),
    },
}
```

**Worker Loop Pseudocode:**
```rust
async fn worker_loop(
    worker_id: usize,
    mut rx: Receiver<Task>,
    result_tx: Sender<Result<Decision>>,
    db_pool: PgPool,
    otel_tracer: Arc<OTelTracer>,
) {
    loop {
        // Non-blocking receive (respects backpressure)
        match rx.recv().await {
            Some(task) => {
                // 1. Create OTel span with trace_id
                let span = otel_tracer.start_span(
                    "task_evaluation",
                    &task.trace_id,
                );
                
                // 2. Acquire database connection (respects pool limit)
                let db_conn = db_pool.acquire().await?;
                
                // 3. Evaluate mandate (ReBAC → AP2 → Temporal)
                let decision = evaluate_mandate(
                    &task,
                    db_conn,
                    &span,
                ).await;
                
                // 4. Emit OTel trace (latency automatically captured)
                otel_tracer.end_span(span, &decision);
                
                // 5. Send result to caller (never blocks)
                let _ = result_tx.send_timeout(
                    Ok(decision),
                    Duration::from_millis(100),
                );
            }
            None => break, // Router shutting down
        }
    }
}
```

### 1.3 Task Struct & Priority Queue

**Task Definition:**
```rust
#[derive(Debug, Clone)]
pub struct Task {
    pub trace_id: Uuid,
    pub agent_id: Uuid,
    pub task_id: Uuid,
    pub intent: PolicyAction,  // Spawn, Pause, Resume, etc.
    pub resource: PolicyResource,  // Agent, Task, Vault
    pub priority: Priority,  // Critical, High, Normal, Low
    pub created_at: SystemTime,
    pub timeout_ms: u32,  // Max 5000ms per task
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Priority {
    Critical = 3,  // Agent stop/emergency
    High = 2,      // Task spawn (blocking orchestrator)
    Normal = 1,    // Routine operations
    Low = 0,       // Background tasks
}
```

**Priority Ordering:**
```rust
impl PartialOrd for Task {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        self.priority.cmp(&other.priority)
            .then_with(|| self.created_at.cmp(&other.created_at))
    }
}
```
FIFO within priority level, strict ordering across levels.

---

## 2. Backpressure Strategy

### 2.1 Queue Saturation Detection

**Metrics:**
```rust
pub struct BackpressureMetrics {
    pub queue_size: Arc<AtomicUsize>,
    pub queue_capacity: usize,
    pub rejection_threshold: f64,  // 0.8 = reject when 80% full
    pub rejection_rate_per_sec: Arc<AtomicU32>,
}
```

**Threshold Logic:**
```rust
pub fn should_reject_task(&self) -> bool {
    let current_size = self.queue_size.load(Ordering::Relaxed);
    let saturation = current_size as f64 / self.queue_capacity as f64;
    
    if saturation > self.rejection_threshold {
        self.rejection_rate_per_sec.fetch_add(1, Ordering::Relaxed);
        return true;
    }
    false
}
```

**HTTP Response:**
```rust
// When queue > 80% full
HTTP/1.1 429 Too Many Requests
Retry-After: 5
Content-Type: application/json

{
  "error": "Task queue saturated",
  "queue_size": 8000,
  "max_capacity": 10000,
  "retry_after_ms": 5000,
  "recommendation": "Reduce task ingestion rate by 20%"
}
```

### 2.2 Connection Pool Backpressure

**PostgreSQL Connection Management:**
```rust
pub struct DbPoolMetrics {
    pub available_connections: Arc<AtomicU32>,
    pub reserved_per_worker: u32,  // 4 connections per worker (32 workers = 128)
    pub min_available_threshold: u32,  // Warn if < 16 available
}

pub async fn acquire_with_timeout(
    pool: &PgPool,
    timeout_ms: u32,
) -> Result<PooledConnection, BackpressureError> {
    match tokio::time::timeout(
        Duration::from_millis(timeout_ms as u64),
        pool.acquire(),
    ).await {
        Ok(Ok(conn)) => Ok(conn),
        Ok(Err(e)) => Err(BackpressureError::AcquireFailed(e)),
        Err(_) => Err(BackpressureError::AcquireTimeout),
    }
}
```

**Backpressure Cascade:**
1. **Queue > 80%** → Reject new tasks (HTTP 429)
2. **DB pool < 16 available** → Slow down worker ingestion (add 100ms delay)
3. **DB pool < 4 available** → Pause all new task acceptance (circuit breaker)

---

## 3. MandateVerifier Multiplexing Across 1000+ Concurrent Tasks

### 3.1 Trace Context Propagation

**Challenge:** Each of the 1,000 concurrent tasks must emit its own OTel trace while sharing a single MandateVerifier instance.

**Solution: Async Trace Context Injection**

```rust
pub async fn evaluate_mandate_with_trace(
    task: &Task,
    db_conn: PgPoolConnection,
    otel_tracer: &Arc<OTelTracer>,
) -> Result<MandateDecision, DenyReason> {
    // 1. Create root span with task's trace_id
    let root_span = otel_tracer.start_root_span(
        "mandate_evaluation",
        &task.trace_id,
        &task.agent_id,
        &task.task_id,
    );
    
    // 2. Inject trace context into async task local storage
    let trace_context = TraceContext {
        trace_id: task.trace_id,
        root_span_id: root_span.span_id,
        agent_id: task.agent_id,
        task_id: task.task_id,
        intent_hash: compute_intent_hash(&task),
        start_time: Instant::now(),
    };
    
    // 3. Run mandate verifier with trace context (no locking)
    let decision = {
        // AsyncLocalData allows per-task context without mutexes
        task_local::set_trace_context(&trace_context);
        
        evaluate_mandate_phases(
            &task,
            db_conn,
            otel_tracer,  // Reads trace_context from task-local
        ).await
    };
    
    // 4. End span and emit to telemetry-router
    otel_tracer.end_span(root_span, &decision);
    
    Ok(decision)
}
```

**Per-Task Storage (Lock-Free):**
```rust
tokio::task_local! {
    static TRACE_CONTEXT: TraceContext = TraceContext::default();
}

// In ReBAC/AP2/Temporal evaluators:
let trace_id = TRACE_CONTEXT.with(|ctx| ctx.trace_id);
let span_id = TRACE_CONTEXT.with(|ctx| ctx.root_span_id);
```

### 3.2 Phase Evaluation with Multiplexing

**ReBAC Phase (PostgreSQL Graph Query):**
```rust
pub async fn rebac_verify(
    agent_id: Uuid,
    resource: &PolicyResource,
    action: &PolicyAction,
    db_conn: &mut PgPoolConnection,
) -> Result<PhaseOutcome, DenyReason> {
    let start = Instant::now();
    
    // Query respects connection pool limits (already acquired by worker)
    let result = sqlx::query_as::<_, Relationship>(
        "SELECT * FROM relationships WHERE sovereign_id = $1 
         AND resource_type = $2 AND action = $3"
    )
    .bind(agent_id)
    .bind(resource.type_name())
    .bind(action.to_string())
    .fetch_optional(db_conn)
    .await?;
    
    let latency_ms = start.elapsed().as_secs_f64() * 1000.0;
    
    Ok(PhaseOutcome {
        phase: Phase::ReBAC,
        result: if result.is_some() { Decision::Allow } else { Decision::Deny },
        latency_ms,
        query_count: Some(1),
        deny_reason: if result.is_none() {
            Some("No relationship found".to_string())
        } else {
            None
        },
    })
}
```

**AP2 Phase (In-Memory Cache):**
```rust
pub async fn ap2_evaluate(
    agent_id: Uuid,
    rules: &Arc<Vec<PolicyRule>>,
    ap2_cache: &SovereignAttributeCache,
) -> Result<PhaseOutcome, DenyReason> {
    let start = Instant::now();
    
    // No await needed—cache is in-memory, lock-free (DashMap)
    let attrs = ap2_cache.get(agent_id)?;
    
    let mut evaluation_result = Decision::Allow;
    let mut deny_reason = None;
    
    for rule in rules.iter() {
        if !rule.enabled {
            continue;
        }
        
        if !ap2_evaluator.evaluate_predicate(&rule.predicate, &attrs)? {
            evaluation_result = Decision::Deny;
            deny_reason = Some(format!(
                "Rule '{}' denied: {}",
                rule.name, rule.predicate
            ));
            break;  // First deny wins
        }
    }
    
    let latency_ms = start.elapsed().as_secs_f64() * 1000.0;
    
    Ok(PhaseOutcome {
        phase: Phase::AP2,
        result: evaluation_result,
        latency_ms,
        query_count: None,
        deny_reason,
    })
}
```

**Temporal Phase (Rate Limiter):**
```rust
pub async fn temporal_check(
    agent_id: Uuid,
    action: &PolicyAction,
    temporal_guard: &Arc<TemporalGuard>,
) -> Result<PhaseOutcome, DenyReason> {
    let start = Instant::now();
    
    // No await needed—rate limiter is lock-free (DashMap)
    let result = temporal_guard.check(agent_id, *action);
    
    let latency_ms = start.elapsed().as_secs_f64() * 1000.0;
    
    let (decision, deny_reason) = match result {
        Ok(()) => (Decision::Allow, None),
        Err(e) => (
            Decision::Deny,
            Some(format!("Temporal violation: {}", e)),
        ),
    };
    
    Ok(PhaseOutcome {
        phase: Phase::Temporal,
        result: decision,
        latency_ms,
        query_count: None,
        deny_reason,
    })
}
```

**Serialized Phase Execution (No Parallelism Within Task):**
```rust
pub async fn evaluate_mandate_phases(
    task: &Task,
    db_conn: PgPoolConnection,
    otel_tracer: &Arc<OTelTracer>,
) -> MandateDecision {
    // Phase 1: ReBAC (PostgreSQL query)
    let rebac_outcome = rebac_verify(
        task.agent_id,
        &task.resource,
        &task.intent,
        &db_conn,
    ).await.unwrap_or_else(|e| {
        PhaseOutcome {
            phase: Phase::ReBAC,
            result: Decision::Deny,
            latency_ms: 0.0,
            query_count: None,
            deny_reason: Some(e.to_string()),
        }
    });
    
    if rebac_outcome.result == Decision::Deny {
        // Short-circuit: ReBAC denied, skip AP2/Temporal
        return MandateDecision {
            trace_id: task.trace_id,
            decision: Decision::Deny,
            phase_outcomes: vec![rebac_outcome],
            deny_phase: Some(Phase::ReBAC),
            deny_reason: rebac_outcome.deny_reason,
            total_latency_ms: rebac_outcome.latency_ms,
        };
    }
    
    // Phase 2: AP2 (In-memory cache)
    let ap2_outcome = ap2_evaluate(
        task.agent_id,
        &AP2_RULES,
        &AP2_CACHE,
    ).await.unwrap_or_else(|e| {
        PhaseOutcome {
            phase: Phase::AP2,
            result: Decision::Deny,
            latency_ms: 0.0,
            query_count: None,
            deny_reason: Some(e.to_string()),
        }
    });
    
    if ap2_outcome.result == Decision::Deny {
        let total_latency = rebac_outcome.latency_ms + ap2_outcome.latency_ms;
        return MandateDecision {
            trace_id: task.trace_id,
            decision: Decision::Deny,
            phase_outcomes: vec![rebac_outcome, ap2_outcome],
            deny_phase: Some(Phase::AP2),
            deny_reason: ap2_outcome.deny_reason,
            total_latency_ms: total_latency,
        };
    }
    
    // Phase 3: Temporal (Rate limiter)
    let temporal_outcome = temporal_check(
        task.agent_id,
        &task.intent,
        &TEMPORAL_GUARD,
    ).await.unwrap_or_else(|e| {
        PhaseOutcome {
            phase: Phase::Temporal,
            result: Decision::Deny,
            latency_ms: 0.0,
            query_count: None,
            deny_reason: Some(e.to_string()),
        }
    });
    
    let total_latency = rebac_outcome.latency_ms +
                       ap2_outcome.latency_ms +
                       temporal_outcome.latency_ms;
    
    let (final_decision, deny_phase, deny_reason) = match temporal_outcome.result {
        Decision::Allow => (Decision::Allow, None, None),
        Decision::Deny => (
            Decision::Deny,
            Some(Phase::Temporal),
            temporal_outcome.deny_reason,
        ),
    };
    
    MandateDecision {
        trace_id: task.trace_id,
        decision: final_decision,
        phase_outcomes: vec![rebac_outcome, ap2_outcome, temporal_outcome],
        deny_phase,
        deny_reason,
        total_latency_ms: total_latency,
    }
}
```

### 3.3 Lock-Free Shared State

**No Mutexes in Hot Path:**
- **ReBAC graph:** PostgreSQL handles concurrency (connection per worker)
- **AP2 attributes:** DashMap (lock-free, async-safe)
- **Temporal rate limiter:** DashMap (lock-free, per-agent)
- **OTel spans:** Atomic operations (no blocking)

**Memory Overhead per Concurrent Task:**
```
Baseline per task:
  Task struct: ~256 bytes
  OTel span context: ~128 bytes
  DB connection: ~4 KB (shared from pool)
  Stack per async task: ~64 KB (tokio overhead)
  
Total per 1000 concurrent tasks:
  1000 * (256 + 128 + 64,000) = ~64 MB resident memory
  + DB connection pool (256 conns * 4KB) = ~1 MB
  + AP2 attribute cache (depends on hot agents)
  
Conservative estimate: 128 MB total for 1000 concurrent tasks
```

---

## 4. Failure Handling & Recovery

### 4.1 Task Timeout

**Per-Task Timeout:**
```rust
pub async fn evaluate_with_timeout(
    task: &Task,
    db_pool: &PgPool,
) -> Result<MandateDecision, TimeoutError> {
    tokio::time::timeout(
        Duration::from_millis(task.timeout_ms as u64),
        evaluate_mandate_phases(task, db_pool),
    )
    .await
    .map_err(|_| TimeoutError {
        trace_id: task.trace_id,
        elapsed_ms: task.timeout_ms,
    })
}

// Default timeout: 5000 ms (5 seconds)
// Override per task: task.timeout_ms = 1000 for critical operations
```

**Timeout OTel Span:**
```rust
// Emit timeout trace before returning error
otel_tracer.end_span_with_error(
    span,
    "Mandate evaluation timeout",
    Duration::from_millis(task.timeout_ms as u64),
);
```

### 4.2 Database Connection Failure

**Retry Strategy:**
```rust
pub async fn get_db_connection_with_retry(
    pool: &PgPool,
    max_retries: u32,
) -> Result<PooledConnection, DbError> {
    for attempt in 0..max_retries {
        match pool.acquire().await {
            Ok(conn) => return Ok(conn),
            Err(e) if attempt < max_retries - 1 => {
                tokio::time::sleep(
                    Duration::from_millis(100 * (attempt as u64 + 1))
                ).await;
            }
            Err(e) => return Err(DbError::ExhaustedRetries {
                attempts: max_retries,
                last_error: e,
            }),
        }
    }
}
```

Exponential backoff: 100ms, 200ms, 300ms, 400ms, 500ms (max 5 attempts)

### 4.3 Circuit Breaker

**When DB Pool is Exhausted:**
```rust
pub struct CircuitBreaker {
    state: Arc<RwLock<CircuitState>>,
    failure_threshold: u32,  // 10 consecutive failures
    recovery_timeout: Duration,  // 30 seconds
}

enum CircuitState {
    Closed,      // Normal operation
    Open,        // Reject all new tasks (HTTP 503)
    HalfOpen,    // Allow single task to test recovery
}

pub async fn should_reject_by_circuit_breaker(&self) -> bool {
    let state = self.state.read().await;
    matches!(state, CircuitState::Open)
}
```

---

## 5. Metrics & Observability

### 5.1 Router Metrics

**Prometheus Counters:**
```rust
pub struct RouterMetrics {
    pub tasks_ingested: Counter,  // Total tasks received
    pub tasks_rejected: Counter,  // Queue saturation rejections
    pub tasks_completed: Counter,  // Successfully evaluated
    pub tasks_timed_out: Counter,  // Exceeded timeout
    pub tasks_failed: Counter,  // Error during evaluation
    
    pub queue_size: Gauge,  // Current queue depth
    pub worker_utilization: Gauge,  // Percentage of workers active
    pub db_connection_available: Gauge,  // Available connections
    
    pub latency_p50: Histogram,  // 50th percentile
    pub latency_p95: Histogram,  // 95th percentile
    pub latency_p99: Histogram,  // 99th percentile
}
```

**Scrape Interval:** 10 seconds
**Prometheus Retention:** 30 days (local) + long-term storage (Thanos/S3)

### 5.2 OTel Span Attributes

**Per-Task Span:**
```json
{
  "trace_id": "uuid",
  "span_id": "uuid",
  "span_name": "task_evaluation",
  "attributes": {
    "task.id": "uuid",
    "agent.id": "uuid",
    "intent": "Spawn",
    "priority": "High",
    "queue_wait_ms": 42.3,
    "rebac.latency_ms": 2.1,
    "rebac.query_count": 4,
    "ap2.latency_ms": 1.8,
    "temporal.latency_ms": 0.3,
    "total_evaluation_ms": 4.2,
    "decision": "Allow",
    "worker_id": 7
  }
}
```

---

## 6. Testing Strategy (TDD)

### RED Phase Tests
1. **Queue Saturation:** Task rejection at 80% capacity
2. **Connection Pool Exhaustion:** Backpressure when < 16 connections available
3. **Trace Propagation:** Each of 100 concurrent tasks emits unique trace_id
4. **Timeout Handling:** Task aborted after timeout_ms
5. **Circuit Breaker:** Reject all tasks when DB pool exhausted

### GREEN Phase Implementation
1. Bounded MPSC queue with backpressure metrics
2. Tokio worker pool with connection per worker
3. Task-local trace context (async-local storage)
4. Timeout enforcement per task
5. Circuit breaker state machine

### REFACTOR Phase
1. Optimize latency (target: p95 < 10ms per phase)
2. Tune worker pool size (profile CPU utilization)
3. Monitor memory growth (GC pressure)

---

## 7. Deployment Configuration

**Production Defaults:**
```rust
pub struct AsyncRouterConfig {
    num_workers: usize = 128,  // 4x CPU cores (32 cores on production hardware)
    max_queue_capacity: usize = 10_000,
    backpressure_threshold: f64 = 0.8,
    
    db_pool: DbPoolConfig {
        min_connections: 32,
        max_connections: 256,
        idle_timeout: Duration::from_secs(900),
    },
    
    per_task_timeout_ms: u32 = 5_000,
    circuit_breaker_threshold: u32 = 10,
    circuit_breaker_recovery_secs: u32 = 30,
}
```

**Target SLOs:**
- **Throughput:** 1,000+ tasks/min (16.7 tasks/sec)
- **Latency (p50):** < 5ms per task
- **Latency (p95):** < 10ms per task
- **Latency (p99):** < 50ms per task
- **Error Rate:** < 0.1% (99.9% success)
- **Availability:** 99.95% (max 22 minutes downtime/month)

---

## 8. Architectural Decisions (Locked)

1. **Bounded Queue:** Prevents unbounded memory growth; HTTP 429 backoff to caller
2. **Connection-Per-Worker:** Each worker holds max 1 DB connection; prevents pool starvation
3. **Task-Local Trace Context:** No mutexes in evaluation path; lock-free multiplexing
4. **Serial Phase Evaluation:** ReBAC → AP2 → Temporal (no parallelism within task); deterministic latency
5. **Short-Circuit on First Deny:** Saves latency & DB queries when early phase denies
6. **Circuit Breaker:** Graceful degradation under complete DB failure

---

## 9. Success Criteria

✅ 1,000 concurrent tasks/min processed without OOM crash
✅ Every task emits OpenTelemetry trace with unique trace_id
✅ p95 latency < 10ms per task (ReBAC + AP2 + Temporal)
✅ Backpressure prevents queue saturation (< 80% utilization)
✅ Database connection pool never exhausted
✅ Circuit breaker activates within 5 seconds of DB failure
✅ All mandate decisions (Allow/Deny) logged to audit trail
✅ Prometheus metrics available for operator monitoring

---

Ready for RED Phase. Awaiting test suite design & implementation orders.
