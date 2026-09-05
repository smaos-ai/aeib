use siss_hardware_accel::{JetsonTarget, HardwareEmulator};

#[test]
fn test_jetson_thor_emulation_creation() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);
    assert_eq!(emulator.target().memory_gb, 128);
}

#[test]
fn test_hardware_emulation_m3_fallback() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);

    // On M3 Pro, should use M3 baseline
    let latency = emulator.benchmark_inference_latency(1000);
    assert!(latency > 0.0, "Latency should be positive");
}

#[test]
fn test_emulation_latency_scales_with_context() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);

    let latency_1k = emulator.benchmark_inference_latency(1000);
    let latency_10k = emulator.benchmark_inference_latency(10000);
    let latency_100k = emulator.benchmark_inference_latency(100000);

    // Latency should increase with context
    assert!(latency_1k < latency_10k, "1k context should be faster than 10k");
    assert!(latency_10k < latency_100k, "10k context should be faster than 100k");
}

#[test]
fn test_emulation_100k_token_target() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);

    let latency_100k = emulator.benchmark_inference_latency(100000);
    assert!(latency_100k < 500.0, "100k context should be <500ms (Phase 2C SLA)");
}

#[test]
fn test_quantization_config_applied() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);

    let config = emulator.target().quantization_config();
    assert!(config.supports_int8);
    assert!(config.supports_fp4);
    assert!(config.supports_bfloat16);
}

#[test]
fn test_kv_cache_allocation_limit() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);

    let max_cache = emulator.target().max_kv_cache_bytes();
    // 128GB - 10GB reserved = 118GB
    let expected = 118u64 * 1024 * 1024 * 1024;
    assert_eq!(max_cache, expected);
}

#[test]
fn test_hardware_detection_consistency() {
    let jetson1 = JetsonTarget::jetson_thor_or_emulated();
    let jetson2 = JetsonTarget::jetson_thor_or_emulated();

    // Detection should be consistent across calls
    assert_eq!(jetson1.available, jetson2.available);
}

#[test]
fn test_emulation_with_fp4_quantization() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);
    let config = emulator.quantization_config();

    assert!(config.supports_fp4, "FP4 should be available");

    // Latency with FP4 should be better than full precision
    let latency_full = emulator.benchmark_inference_latency(100000);
    let latency_fp4 = emulator.benchmark_inference_latency_with_quantization(100000, "fp4");

    assert!(latency_fp4 <= latency_full, "FP4 should be faster or equal");
}

#[test]
fn test_emulation_network_bandwidth() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);

    let bps = emulator.target().local_network_bandwidth_bps();
    assert_eq!(bps, 1_000_000_000, "Should be 1 Gbps");
}

#[test]
fn test_emulation_cache_size_recommendation() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);

    let cache_bytes = emulator.target().recommended_cache_size_bytes();
    let expected = 50u64 * 1024 * 1024 * 1024; // 50GB
    assert_eq!(cache_bytes, expected);
}

#[test]
fn test_emulation_thermal_status() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);

    let status = emulator.thermal_status();
    assert!(!status.is_empty(), "Should have thermal status");
}

#[test]
fn test_emulation_deterministic_metrics() {
    let jetson = JetsonTarget::jetson_thor_or_emulated();
    let emulator = HardwareEmulator::new(jetson);

    // Same input should give same output (deterministic)
    let latency1 = emulator.benchmark_inference_latency(50000);
    let latency2 = emulator.benchmark_inference_latency(50000);

    assert_eq!(latency1, latency2, "Emulation should be deterministic");
}
