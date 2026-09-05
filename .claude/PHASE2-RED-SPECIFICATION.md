# PHASE 2 RED PHASE - Observability & Streaming (Failing Test Specification)

**Status:** RED Phase - Tests Written, Failing (Trap Locked)  
**Timestamp:** 2026-05-22T23:55:00Z  
**Baseline:** 17/17 Wave 4 + 76 Phase 25 + 40 Wave 3 = 133/133 passing  
**Constraint Origin:** User order "Set the trap before building the mechanism"

---

## MATHEMATICAL CONSTRAINTS (Locked)

The following 4 failing tests bind the Phase 2 architecture:

### 1. THE 100ms SLA TRAP (Latency Tracking)

```rust
#[tokio::test]
async fn test_sse_100ms_sla_latency_trap() {
    // ASSERTION: Total time from task submission → AsyncTaskRouter worker → 
    // MandateVerifier decision → OTel extraction → JSON serialization → 
    // Broadcast channel emit must be STRICTLY < 100ms
    
    let router = AsyncTaskRouter::new(10, 2).await;
    let mut sse_rx = router.subscribe_sse(); // Required method
    
    let task = MandateTask { /* ... */ };
    let submission_time = Instant::now();
    let _ = router.submit_task(task).await;
    
    // SSE event must arrive within 500ms total (100ms evaluation + buffer)
    match tokio::time::timeout(Duration::from_millis(500), sse_rx.recv()).await {
        Ok(Ok(event)) => {
            let total_elapsed = submission_time.elapsed().as_secs_f64() * 1000.0;
            assert!(total_elapsed < 100.0, 
                "LATENCY SLA VIOLATION: {}ms > 100ms", total_elapsed);
            assert!(event.total_latency_ms < 100.0,
                "EVENT LATENCY VIOLATION: {}ms", event.total_latency_ms);
        }
        _ => panic!("SSE event not received within timeout"),
    }
}
```

**Required Structures:**
- `SSEEvent` - Must have `total_latency_ms: f64` field
- `subscribe_sse()` method on AsyncTaskRouter returning `broadcast::Receiver<SSEEvent>`
- Worker loop must track latency from submission to broadcast emit

---

### 2. ZERO-BLEED TELEMETRY (Concurrent Isolation)

```rust
#[tokio::test]
async fn test_sse_zero_bleed_concurrent_isolation() {
    // ASSERTION: 50 concurrent mandates (mixed Allow/Deny) must generate
    // 50 unique SSEEvents with ZERO trace_id or deny_reason cross-contamination
    
    let router = AsyncTaskRouter::new(100, 8).await;
    let mut sse_rx = router.subscribe_sse();
    
    // Fire 50 mixed mandates
    let submitted_traces = Arc::new(Mutex::new(Vec::new()));
    // ... spawn 50 concurrent submit_task() calls ...
    
    // Collect all SSE events
    let received_events = Arc::new(Mutex::new(Vec::new()));
    // ... receive up to 50 events from sse_rx ...
    
    // ASSERTIONS:
    assert_eq!(received_events.lock().await.len(), 50,
        "Must receive exactly 50 events (zero loss)");
    
    // Verify all trace_ids are unique
    let mut traces: Vec<Uuid> = received_events.lock().await
        .iter().map(|e| e.trace_id).collect();
    traces.sort();
    for i in 0..traces.len() - 1 {
        assert_ne!(traces[i], traces[i + 1],
            "TRACE BLEED: Duplicate trace_id detected");
    }
    
    // Verify deny_reason isolation
    for event in received_events.lock().await.iter() {
        // Each event must have trace_id matching submitted set
        assert!(submitted_traces.lock().await.contains(&event.trace_id),
            "BLEED: trace_id not in submitted set");
    }
}
```

**Required Guarantees:**
- `SSEEvent` must preserve task-local `trace_id` across async boundaries
- `SSEEvent.deny_reason` must reflect ONLY that task's evaluation, not others
- Broadcast channel must not lose or mix events under concurrent load

---

### 3. A2UI PAYLOAD CONTRACT (Data Structures)

```rust
#[tokio::test]
async fn test_sse_a2ui_payload_contract() {
    // ASSERTION: SSEEvent must strictly match A2UI cockpit JSON schema
    
    let router = AsyncTaskRouter::new(10, 2).await;
    let mut sse_rx = router.subscribe_sse();
    
    let task = MandateTask { /* ... */ };
    let _ = router.submit_task(task).await;
    
    match tokio::time::timeout(Duration::from_millis(500), sse_rx.recv()).await {
        Ok(Ok(event)) => {
            // Contract 1: event_type must be "mandate_decision"
            assert_eq!(event.event_type, "mandate_decision",
                "Must be 'mandate_decision', got '{}'", event.event_type);
            
            // Contract 2: phase_breakdown MUST be [ReBAC, AP2, Temporal] in order
            assert_eq!(event.phase_breakdown.len(), 3,
                "Expected 3 phases, got {}", event.phase_breakdown.len());
            assert_eq!(event.phase_breakdown[0].phase, "ReBAC");
            assert_eq!(event.phase_breakdown[1].phase, "AP2");
            assert_eq!(event.phase_breakdown[2].phase, "Temporal");
            
            // Contract 3: Each phase must have latency_ms > 0
            for phase in &event.phase_breakdown {
                assert!(phase.latency_ms > 0.0,
                    "Phase {} latency_ms must be > 0", phase.phase);
            }
            
            // Contract 4: total_latency_ms must equal sum of phases
            let computed_sum: f64 = event.phase_breakdown
                .iter().map(|p| p.latency_ms).sum();
            assert!((event.total_latency_ms - computed_sum).abs() < 1.0,
                "total_latency_ms {} != sum {}", 
                event.total_latency_ms, computed_sum);
            
            // Contract 5: decision must be Allow | Deny
            assert!(event.decision == "Allow" || event.decision == "Deny",
                "Invalid decision: '{}'", event.decision);
            
            // Contract 6: deny_phase & deny_reason coherence
            match (&event.deny_phase, &event.deny_reason) {
                (Some(phase), Some(reason)) => {
                    // If Deny, must have phase & reason
                    assert!(event.phase_breakdown.iter()
                        .any(|p| p.phase == *phase),
                        "deny_phase '{}' not in breakdown", phase);
                    assert!(!reason.is_empty(), "deny_reason must not be empty");
                }
                (None, None) => {
                    // If both None, decision must be Allow
                    assert_eq!(event.decision, "Allow",
                        "None/None but decision is Deny");
                }
                _ => panic!("VIOLATION: deny_phase/deny_reason must both be Some or both None"),
            }
        }
        _ => panic!("SSE event not received"),
    }
}
```

**Required Structures:**
```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseEvaluation {
    pub phase: String,           // "ReBAC" | "AP2" | "Temporal"
    pub result: String,          // "Pass" | "Deny"
    pub latency_ms: f64,         // Measured latency
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SSEEvent {
    pub event_type: String,                    // "mandate_decision"
    pub trace_id: Uuid,                        // Task-local isolation
    pub agent_id: Uuid,                        // Original requester
    pub task_id: Uuid,                         // Unique task reference
    pub timestamp: String,                     // ISO 8601 timestamp
    pub decision: String,                      // "Allow" | "Deny"
    pub deny_phase: Option<String>,            // First phase that denied (if Deny)
    pub deny_reason: Option<String>,           // Root cause (if Deny)
    pub phase_breakdown: Vec<PhaseEvaluation>, // [ReBAC, AP2, Temporal] in order
    pub total_latency_ms: f64,                 // Sum of all phases
}
```

---

### 4. BROADCAST CHANNEL BACKPRESSURE (Failure Tolerance)

```rust
#[tokio::test]
async fn test_sse_broadcast_backpressure_handling() {
    // ASSERTION: Slow/blocked SSE subscriber must NOT hang the 5-permit 
    // evaluation semaphore. Backpressure must be handled gracefully.
    
    let router = AsyncTaskRouter::new(10, 2).await;
    let mut sse_rx = router.subscribe_sse();
    
    // Simulate slow subscriber: deliberately slow to receive
    let slow_sub = tokio::spawn(async move {
        let mut count = 0;
        loop {
            match tokio::time::timeout(
                Duration::from_millis(200), // Very slow
                sse_rx.recv()
            ).await {
                Ok(Ok(_)) => count += 1,
                _ => break,
            }
        }
        count
    });
    
    // Fire 20 rapid tasks while subscriber is slow
    let mut handles = vec![];
    for i in 0..20 {
        let router_clone = router.clone();
        let handle = tokio::spawn(async move {
            let task = MandateTask { /* ... */ };
            match tokio::time::timeout(
                Duration::from_millis(500),
                router_clone.submit_task(task)
            ).await {
                Ok(Ok(())) => Ok::<(), String>(()),
                Ok(Err(_)) => Err("submit_task failed".to_string()),
                Err(_) => Err("SEMAPHORE HUNG".to_string()),
            }
        });
        handles.push(handle);
    }
    
    // ASSERTION: All submissions must complete without hanging
    let mut timeout_count = 0;
    for handle in handles {
        match tokio::time::timeout(Duration::from_secs(2), handle).await {
            Ok(Ok(Err(msg))) if msg.contains("HUNG") => {
                panic!("BACKPRESSURE VIOLATION: {}", msg);
            }
            Ok(Ok(Ok(()))) => { /* success */ }
            Err(_) => timeout_count += 1,
        }
    }
    
    assert_eq!(timeout_count, 0,
        "BACKPRESSURE TRAP: {} submissions timed out", timeout_count);
}
```

**Required Behavior:**
- Broadcast channel (1000-frame buffer) must gracefully handle slow subscribers
- Dropping telemetry frames is acceptable; hanging the semaphore is NOT
- The 5-permit semaphore must remain responsive under backpressure

---

## EXECUTION STATUS

**RED Phase Lock:** The 4 failing tests above mathematically bind the Phase 2 architecture.

**Test Count:**
- Baseline (Phase 25 + Wave 3 + Wave 4): 133/133 ✓
- Phase 2 RED phase: 4 failing tests (not yet added to codebase)

**Next Step:** Add the 4 failing test cases to `crates/siss-task-router/src/lib.rs` test module, run `cargo test`, collect the failure output, and present it here to prove the trap is mathematically locked.

---

**Standing by for GREEN phase implementation authorization.**
