use siss_os_sidecar::{FallbackMonitor, ResourceMonitor};
use std::sync::Arc;
use std::sync::atomic::AtomicU32;
use std::time::Duration;

#[tokio::test]
async fn test_fallback_monitor_produces_valid_resource_state() {
    let monitor = FallbackMonitor::for_test();
    let mut monitor = monitor;

    let state = monitor.sample().await.unwrap();

    assert!(
        state.unified_memory_pct >= 0.0 && state.unified_memory_pct <= 1.0,
        "Memory pct should be in [0.0, 1.0]"
    );

    assert!(
        state.per_core_load.len() > 0,
        "Should have at least one CPU core"
    );

    for load in &state.per_core_load {
        assert!(
            load >= &0.0 && load <= &1.0,
            "Core load should be in [0.0, 1.0], got {}",
            load
        );
    }

    assert_eq!(
        state.metal_queue_depth, 0,
        "FallbackMonitor should report metal_queue_depth=0"
    );
}

#[tokio::test]
async fn test_fallback_monitor_with_multiple_samples() {
    let mut monitor = FallbackMonitor::for_test();

    let state1 = monitor.sample().await.unwrap();
    assert!(state1.per_core_load.len() > 0);

    tokio::time::sleep(Duration::from_millis(250)).await;

    let state2 = monitor.sample().await.unwrap();
    assert!(state2.per_core_load.len() > 0);

    // Both samples should be valid, thermal slope should be computed (may be zero on idle)
    assert!(state2.thermal_slope >= -10.0 && state2.thermal_slope <= 10.0);
}

#[tokio::test]
async fn test_metal_queue_counter_propagates_to_resource_state() {
    let counter = Arc::new(AtomicU32::new(0));
    let mut monitor = FallbackMonitor::new(counter.clone());

    let state = monitor.sample().await.unwrap();
    assert_eq!(state.metal_queue_depth, 0);

    // Set the counter externally
    counter.store(64, std::sync::atomic::Ordering::Relaxed);

    let state = monitor.sample().await.unwrap();
    assert_eq!(
        state.metal_queue_depth, 64,
        "Should reflect external counter change"
    );
}

#[tokio::test]
async fn test_fallback_monitor_respects_poll_interval() {
    let monitor = FallbackMonitor::for_test();
    let interval = monitor.poll_interval();

    assert!(
        interval >= Duration::from_millis(400),
        "Poll interval should be >= 400ms (need 200ms for CPU gap)"
    );
}
