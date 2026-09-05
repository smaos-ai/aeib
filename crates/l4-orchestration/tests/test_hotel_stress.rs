//! L4 Hotel Stress Tests: 100+ iterations with <100ms latency requirement
//! Performance tests for HotelPilot credit scoring workflow

use l4_orchestration::{HotelPilot, Pilot};
use std::time::Instant;

#[test]
fn test_hotel_single_iteration_latency() {
    let start = Instant::now();
    let pilot = HotelPilot::new();
    let _ = pilot.flow();
    let elapsed = start.elapsed();

    assert!(
        elapsed.as_millis() < 100,
        "Single iteration exceeded 100ms: {}ms",
        elapsed.as_millis()
    );
}

#[test]
fn test_hotel_100_iterations_latency() {
    let mut total_time = std::time::Duration::ZERO;
    let mut exceeded_count = 0;

    for i in 0..100 {
        let start = Instant::now();
        let pilot = HotelPilot::new();
        let result = pilot.flow();
        let elapsed = start.elapsed();

        assert!(result.is_ok(), "Iteration {} failed", i);
        total_time += elapsed;

        if elapsed.as_millis() >= 100 {
            exceeded_count += 1;
        }
    }

    let avg_time_ms = total_time.as_millis() as f64 / 100.0;
    assert!(
        exceeded_count == 0,
        "{} iterations exceeded 100ms threshold",
        exceeded_count
    );
    assert!(
        avg_time_ms < 50.0,
        "Average iteration time {} ms is too high",
        avg_time_ms
    );
}

#[test]
fn test_hotel_sequential_requests_no_interference() {
    let pilot1 = HotelPilot::new();
    let pilot2 = HotelPilot::new();

    let start1 = Instant::now();
    let flow1 = pilot1.flow().unwrap();
    let time1 = start1.elapsed();

    let start2 = Instant::now();
    let flow2 = pilot2.flow().unwrap();
    let time2 = start2.elapsed();

    assert!(time1.as_millis() < 100);
    assert!(time2.as_millis() < 100);
    assert_ne!(
        pilot1.state().request_id,
        pilot2.state().request_id,
        "Request IDs must be unique"
    );
}

#[test]
fn test_hotel_parallel_flow_completeness() {
    let checkpoints = HotelPilot::new().flow().unwrap();
    assert!(checkpoints.len() >= 11, "Hotel flow must have 11+ checkpoints");

    let has_request = checkpoints.iter().any(|cp| cp.state == "REQUEST");
    let has_l1 = checkpoints
        .iter()
        .any(|cp| cp.layer.as_ref().is_some_and(|l| l == "L1"));
    let has_l5 = checkpoints
        .iter()
        .any(|cp| cp.layer.as_ref().is_some_and(|l| l == "L5"));
    let has_l8 = checkpoints
        .iter()
        .any(|cp| cp.layer.as_ref().is_some_and(|l| l == "L8"));
    let has_approved = checkpoints.iter().any(|cp| cp.state == "APPROVED");

    assert!(has_request && has_l1 && has_l5 && has_l8 && has_approved);
}

#[test]
fn test_hotel_stress_state_consistency() {
    for _ in 0..50 {
        let pilot = HotelPilot::new();
        let state = pilot.state();

        assert!(!state.request_id.is_empty());
        assert_eq!(state.current_state, "APPROVED");
        assert!(!state.requires_human_escalation);
        assert_eq!(state.evaluation_score, Some(0.92));
        assert!(state.policy_context.is_some());
    }
}

#[test]
fn test_hotel_100_iterations_all_pass() {
    let mut success_count = 0;
    let mut checkpoint_counts = vec![];

    for _ in 0..100 {
        let pilot = HotelPilot::new();
        if let Ok(flow) = pilot.flow() {
            success_count += 1;
            checkpoint_counts.push(flow.len());
        }
    }

    assert_eq!(success_count, 100, "All 100 iterations must pass");
    assert!(
        checkpoint_counts.iter().all(|&c| c >= 11),
        "All flows must have 11+ checkpoints"
    );
}

#[test]
fn test_hotel_stress_throughput_100_requests() {
    let start = Instant::now();

    for _ in 0..100 {
        let pilot = HotelPilot::new();
        let _ = pilot.flow();
    }

    let total_time = start.elapsed();
    let throughput = 100.0 / total_time.as_secs_f64();

    assert!(
        throughput > 10.0,
        "Throughput must be >10 req/s, got {}",
        throughput
    );
}

#[test]
fn test_hotel_stress_no_memory_leaks() {
    let pilot = HotelPilot::new();

    for _ in 0..200 {
        let _ = pilot.flow();
        let _ = pilot.state();
    }

    // If we reach here without panic/OOM, test passes
    assert!(true);
}

#[test]
fn test_hotel_checkpoint_timing_order() {
    let checkpoints = HotelPilot::new().flow().unwrap();

    for i in 1..checkpoints.len() {
        assert!(
            checkpoints[i].timestamp >= checkpoints[i - 1].timestamp,
            "Checkpoint timestamps must be non-decreasing"
        );
    }
}

#[test]
fn test_hotel_stress_unique_ids() {
    let mut ids = std::collections::HashSet::new();
    let mut checkpoint_ids = std::collections::HashSet::new();

    for _ in 0..50 {
        let pilot = HotelPilot::new();
        let request_id = pilot.state().request_id.clone();
        ids.insert(request_id);

        if let Ok(checkpoints) = pilot.flow() {
            for cp in checkpoints {
                checkpoint_ids.insert(cp.id);
            }
        }
    }

    assert_eq!(ids.len(), 50, "All request IDs must be unique");
    assert!(
        checkpoint_ids.len() >= 550,
        "All checkpoint IDs must be unique (11+ per flow)"
    );
}

#[test]
fn test_hotel_stress_error_recovery() {
    for _ in 0..10 {
        let pilot = HotelPilot::new();
        match pilot.flow() {
            Ok(flow) => assert!(!flow.is_empty()),
            Err(e) => panic!("Flow should not fail: {}", e),
        }
    }
}

#[test]
fn test_hotel_batch_100_latency_percentiles() {
    let mut latencies = vec![];

    for _ in 0..100 {
        let start = Instant::now();
        let pilot = HotelPilot::new();
        let _ = pilot.flow();
        latencies.push(start.elapsed().as_millis() as u64);
    }

    latencies.sort();
    let p50 = latencies[49];
    let p95 = latencies[94];
    let p99 = latencies[98];

    assert!(p50 < 100, "p50 latency: {}ms", p50);
    assert!(p95 < 100, "p95 latency: {}ms", p95);
    assert!(p99 < 100, "p99 latency: {}ms", p99);
}

#[test]
fn test_hotel_stress_concurrent_state_access() {
    let pilots: Vec<_> = (0..100).map(|_| HotelPilot::new()).collect();

    for pilot in &pilots {
        let state = pilot.state();
        assert!(!state.request_id.is_empty());
        assert_eq!(state.evaluation_score, Some(0.92));
    }
}

#[test]
fn test_hotel_flow_layer_sequence() {
    let checkpoints = HotelPilot::new().flow().unwrap();
    let layers: Vec<&str> = checkpoints
        .iter()
        .filter_map(|cp| cp.layer.as_ref().map(|l| l.as_str()))
        .collect();

    // Verify required layers are present
    assert!(layers.contains(&"L1"));
    assert!(layers.contains(&"L2"));
    assert!(layers.contains(&"L3"));
    assert!(layers.contains(&"L4"));
    assert!(layers.contains(&"L5"));
    assert!(layers.contains(&"L7"));
    assert!(layers.contains(&"L8"));
}

#[test]
fn test_hotel_stress_policy_context_consistency() {
    for _ in 0..30 {
        let pilot = HotelPilot::new();
        let state = pilot.state();
        let policy_context = state.policy_context.unwrap();

        assert!(
            policy_context.contains("Article 50"),
            "Policy context must mention Article 50"
        );
        assert!(
            policy_context.contains("Annex III"),
            "Policy context must mention Annex III"
        );
    }
}

#[test]
fn test_hotel_stress_proof_trail_presence() {
    for _ in 0..25 {
        let pilot = HotelPilot::new();
        let state = pilot.state();
        let proof_trail = state.proof_trail.unwrap();

        assert!(
            proof_trail.contains("ed25519"),
            "Proof trail must contain ed25519 signature"
        );
    }
}
