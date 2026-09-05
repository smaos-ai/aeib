use l6_infrastructure::{Benchmark, BenchmarkConfig};

#[test]
fn test_benchmark_creation() {
    let config = BenchmarkConfig::new(8, 39.3, 30_000);
    let benchmark = Benchmark::new(config);
    assert!(benchmark.is_ok());
}

#[test]
fn test_benchmark_config_defaults() {
    let config = BenchmarkConfig::new(8, 39.3, 30_000);
    assert_eq!(config.gpu_vram_gb, 8);
    assert!(config.target_tok_per_sec > 30.0);
    assert!(config.timeout_ms > 0);
}

#[test]
fn test_benchmark_invalid_config_negative_vram() {
    let config = BenchmarkConfig::new(-1, 39.3, 30_000);
    let benchmark = Benchmark::new(config);
    assert!(benchmark.is_err());
}

#[test]
fn test_benchmark_invalid_config_zero_throughput() {
    let config = BenchmarkConfig::new(8, 0.0, 30_000);
    let benchmark = Benchmark::new(config);
    assert!(benchmark.is_err());
}

#[test]
fn test_benchmark_invalid_config_zero_timeout() {
    let config = BenchmarkConfig::new(8, 39.3, 0);
    let benchmark = Benchmark::new(config);
    assert!(benchmark.is_err());
}

#[test]
fn test_benchmark_measure_throughput_minimum() {
    let config = BenchmarkConfig::new(8, 39.3, 30_000);
    let benchmark = Benchmark::new(config).unwrap();
    let result = benchmark.measure_throughput_estimate();
    assert!(result.is_ok());
    let throughput = result.unwrap();
    assert!(throughput > 0.0);
}

#[test]
fn test_benchmark_measure_throughput_within_tolerance() {
    let config = BenchmarkConfig::new(8, 39.3, 30_000);
    let benchmark = Benchmark::new(config).unwrap();
    let result = benchmark.measure_throughput_estimate();
    assert!(result.is_ok());
    let throughput = result.unwrap();
    assert!(throughput <= 50.0);
}

#[test]
fn test_benchmark_meets_target_tolerance() {
    let config = BenchmarkConfig::new(8, 39.3, 30_000);
    let benchmark = Benchmark::new(config).unwrap();
    let meets_target = benchmark.meets_target_within_tolerance(39.0, 5.0);
    assert!(meets_target.is_ok());
    assert!(meets_target.unwrap());
}

#[test]
fn test_benchmark_fails_target_below_minimum() {
    let config = BenchmarkConfig::new(8, 39.3, 30_000);
    let benchmark = Benchmark::new(config).unwrap();
    let meets_target = benchmark.meets_target_within_tolerance(10.0, 5.0);
    assert!(meets_target.is_ok());
    assert!(!meets_target.unwrap());
}

#[test]
fn test_benchmark_audit_trail() {
    let config = BenchmarkConfig::new(8, 39.3, 30_000);
    let benchmark = Benchmark::new(config).unwrap();
    benchmark.measure_throughput_estimate().ok();
    let audit = benchmark.get_audit_trail();
    assert!(!audit.is_empty());
}
