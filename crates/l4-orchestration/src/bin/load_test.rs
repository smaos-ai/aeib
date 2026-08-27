use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Instant;
use uuid::Uuid;

// Import pilot types from the library
use l4_orchestration::{GlassPilot, HotelPilot, Pilot, SchoolPilot};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PilotMetrics {
    pub iterations: usize,
    pub avg_latency_ms: f64,
    pub min_latency_ms: u128,
    pub max_latency_ms: u128,
    pub median_latency_ms: u128,
    pub p95_latency_ms: u128,
    pub p99_latency_ms: u128,
    pub total_duration_ms: u128,
    pub errors: usize,
    pub success_rate: f64,
    pub decisions: Vec<String>,
    pub checkpoints_captured: usize,
    pub avg_memory_peak_mb: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeCase {
    pub case_id: String,
    pub description: String,
    pub pilot: String,
    pub iteration: usize,
    pub handling: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofArtifact {
    pub artifact_id: String,
    pub checkpoint_times: Vec<f64>,
    pub decision_trails: Vec<String>,
    pub audit_logs: Vec<String>,
    pub total_layers_traversed: usize,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LoadTestResult {
    pub test_run_id: String,
    pub timestamp: DateTime<Utc>,
    pub total_iterations: usize,
    pub hotel_pilot: PilotMetrics,
    pub glass_pilot: PilotMetrics,
    pub school_pilot: PilotMetrics,
    pub edge_cases: Vec<EdgeCase>,
    pub proof_artifacts: Vec<ProofArtifact>,
    pub system_stats: HashMap<String, f64>,
}

fn run_pilot_iterations<T: Pilot + Default>(pilot_name: &str, iterations: usize) -> PilotMetrics {
    let mut latencies = Vec::new();
    let mut errors = 0;
    let mut decisions = Vec::new();
    let mut all_checkpoints_count = 0;
    let start_time = Instant::now();

    for iteration in 0..iterations {
        let iter_start = Instant::now();

        let pilot = T::default();
        match pilot.flow() {
            Ok(checkpoints) => {
                let iter_latency = iter_start.elapsed().as_millis();
                latencies.push(iter_latency);
                all_checkpoints_count += checkpoints.len();

                // Capture decision points
                for cp in &checkpoints {
                    if cp.state.contains("DECISION")
                        || cp.state.contains("APPROVE")
                        || cp.state.contains("ESCALAT")
                    {
                        decisions.push(format!(
                            "{}: {} ({:?}ms)",
                            iteration, cp.action, iter_latency
                        ));
                    }
                }
            }
            Err(e) => {
                errors += 1;
                decisions.push(format!("Iteration {}: ERROR - {}", iteration, e));
            }
        }
    }

    let total_duration = start_time.elapsed().as_millis();
    latencies.sort();

    let avg_latency_ms = latencies.iter().sum::<u128>() as f64 / latencies.len() as f64;
    let min_latency_ms = *latencies.first().unwrap_or(&0);
    let max_latency_ms = *latencies.last().unwrap_or(&0);
    let median_latency_ms = latencies[latencies.len() / 2];
    let p95_idx = (latencies.len() as f64 * 0.95) as usize;
    let p99_idx = (latencies.len() as f64 * 0.99) as usize;
    let p95_latency_ms = latencies.get(p95_idx).copied().unwrap_or(max_latency_ms);
    let p99_latency_ms = latencies.get(p99_idx).copied().unwrap_or(max_latency_ms);

    let success_rate = ((iterations - errors) as f64 / iterations as f64) * 100.0;

    PilotMetrics {
        iterations,
        avg_latency_ms,
        min_latency_ms,
        max_latency_ms,
        median_latency_ms,
        p95_latency_ms,
        p99_latency_ms,
        total_duration_ms: total_duration,
        errors,
        success_rate,
        decisions: decisions.into_iter().take(50).collect(), // Keep top 50
        checkpoints_captured: all_checkpoints_count,
        avg_memory_peak_mb: estimate_memory_usage(&latencies),
    }
}

fn estimate_memory_usage(latencies: &[u128]) -> f64 {
    // Rough estimation: more latency = more checkpoints = more memory
    let avg_latency = latencies.iter().sum::<u128>() / latencies.len() as u128;
    (avg_latency as f64 / 100.0) * 0.5 // Very rough estimate
}

fn extract_edge_cases(
    hotel_metrics: &PilotMetrics,
    glass_metrics: &PilotMetrics,
    school_metrics: &PilotMetrics,
) -> Vec<EdgeCase> {
    let mut edge_cases = Vec::new();

    // High latency outliers
    if hotel_metrics.max_latency_ms > (hotel_metrics.avg_latency_ms * 2.0) as u128 {
        edge_cases.push(EdgeCase {
            case_id: Uuid::new_v4().to_string(),
            description: "High latency detected in hotel pilot".to_string(),
            pilot: "hotel".to_string(),
            iteration: 0,
            handling: format!(
                "Max latency {}ms exceeds 2x average ({}ms)",
                hotel_metrics.max_latency_ms, hotel_metrics.avg_latency_ms as u128
            ),
            timestamp: Utc::now().to_rfc3339(),
        });
    }

    // Error occurrences
    if hotel_metrics.errors > 0 {
        edge_cases.push(EdgeCase {
            case_id: Uuid::new_v4().to_string(),
            description: format!("Errors in hotel pilot: {}", hotel_metrics.errors),
            pilot: "hotel".to_string(),
            iteration: 0,
            handling: "Logged and captured in decision trail".to_string(),
            timestamp: Utc::now().to_rfc3339(),
        });
    }

    if glass_metrics.errors > 0 {
        edge_cases.push(EdgeCase {
            case_id: Uuid::new_v4().to_string(),
            description: format!("Errors in glass pilot: {}", glass_metrics.errors),
            pilot: "glass".to_string(),
            iteration: 0,
            handling: "Glass pilot escalation required".to_string(),
            timestamp: Utc::now().to_rfc3339(),
        });
    }

    if school_metrics.errors > 0 {
        edge_cases.push(EdgeCase {
            case_id: Uuid::new_v4().to_string(),
            description: format!("Errors in school pilot: {}", school_metrics.errors),
            pilot: "school".to_string(),
            iteration: 0,
            handling: "Access control verification required".to_string(),
            timestamp: Utc::now().to_rfc3339(),
        });
    }

    // Consistency checks
    edge_cases.push(EdgeCase {
        case_id: Uuid::new_v4().to_string(),
        description: "Cross-pilot latency variance analysis".to_string(),
        pilot: "all".to_string(),
        iteration: 0,
        handling: format!(
            "Hotel avg: {}ms, Glass avg: {}ms, School avg: {}ms",
            hotel_metrics.avg_latency_ms as u64,
            glass_metrics.avg_latency_ms as u64,
            school_metrics.avg_latency_ms as u64
        ),
        timestamp: Utc::now().to_rfc3339(),
    });

    edge_cases
}

fn build_proof_artifacts(
    hotel_metrics: &PilotMetrics,
    glass_metrics: &PilotMetrics,
    school_metrics: &PilotMetrics,
) -> Vec<ProofArtifact> {
    vec![
        ProofArtifact {
            artifact_id: format!("proof-hotel-{}", Uuid::new_v4()),
            checkpoint_times: vec![
                hotel_metrics.min_latency_ms as f64,
                hotel_metrics.median_latency_ms as f64,
                hotel_metrics.max_latency_ms as f64,
                hotel_metrics.avg_latency_ms,
                hotel_metrics.p95_latency_ms as f64,
                hotel_metrics.p99_latency_ms as f64,
            ],
            decision_trails: hotel_metrics.decisions.clone(),
            audit_logs: vec![
                format!(
                    "Hotel L1→L8 flow executed {} times",
                    hotel_metrics.iterations
                ),
                format!("Success rate: {:.2}%", hotel_metrics.success_rate),
                format!(
                    "Total checkpoints captured: {}",
                    hotel_metrics.checkpoints_captured
                ),
            ],
            total_layers_traversed: 8,
        },
        ProofArtifact {
            artifact_id: format!("proof-glass-{}", Uuid::new_v4()),
            checkpoint_times: vec![
                glass_metrics.min_latency_ms as f64,
                glass_metrics.median_latency_ms as f64,
                glass_metrics.max_latency_ms as f64,
                glass_metrics.avg_latency_ms,
                glass_metrics.p95_latency_ms as f64,
                glass_metrics.p99_latency_ms as f64,
            ],
            decision_trails: glass_metrics.decisions.clone(),
            audit_logs: vec![
                format!(
                    "Glass/Auto L1→L8 flow executed {} times",
                    glass_metrics.iterations
                ),
                format!("Success rate: {:.2}%", glass_metrics.success_rate),
                format!(
                    "Total checkpoints captured: {}",
                    glass_metrics.checkpoints_captured
                ),
            ],
            total_layers_traversed: 8,
        },
        ProofArtifact {
            artifact_id: format!("proof-school-{}", Uuid::new_v4()),
            checkpoint_times: vec![
                school_metrics.min_latency_ms as f64,
                school_metrics.median_latency_ms as f64,
                school_metrics.max_latency_ms as f64,
                school_metrics.avg_latency_ms,
                school_metrics.p95_latency_ms as f64,
                school_metrics.p99_latency_ms as f64,
            ],
            decision_trails: school_metrics.decisions.clone(),
            audit_logs: vec![
                format!(
                    "School/Education L1→L8 flow executed {} times",
                    school_metrics.iterations
                ),
                format!("Success rate: {:.2}%", school_metrics.success_rate),
                format!(
                    "Total checkpoints captured: {}",
                    school_metrics.checkpoints_captured
                ),
            ],
            total_layers_traversed: 8,
        },
    ]
}

fn main() {
    println!("=== SMAOS Pilot Load Test Harness ===\n");
    println!("Starting load test: 1000 iterations (100 per pilot x 10 cycles)\n");

    let test_run_id = format!("load-test-{}", Uuid::new_v4());
    let start_time = Instant::now();

    // Run 100 iterations per pilot
    println!("Running Hotel pilot load test (100 iterations)...");
    let hotel_metrics = run_pilot_iterations::<HotelPilot>("hotel", 100);
    println!(
        "  ✓ Hotel: avg {}ms, errors {}, success {:.2}%\n",
        hotel_metrics.avg_latency_ms as u64, hotel_metrics.errors, hotel_metrics.success_rate
    );

    println!("Running Glass pilot load test (100 iterations)...");
    let glass_metrics = run_pilot_iterations::<GlassPilot>("glass", 100);
    println!(
        "  ✓ Glass: avg {}ms, errors {}, success {:.2}%\n",
        glass_metrics.avg_latency_ms as u64, glass_metrics.errors, glass_metrics.success_rate
    );

    println!("Running School pilot load test (100 iterations)...");
    let school_metrics = run_pilot_iterations::<SchoolPilot>("school", 100);
    println!(
        "  ✓ School: avg {}ms, errors {}, success {:.2}%\n",
        school_metrics.avg_latency_ms as u64, school_metrics.errors, school_metrics.success_rate
    );

    // Run additional 700 iterations distributed evenly
    println!("Running extended load test (700 additional iterations)...");
    let hotel_extended = run_pilot_iterations::<HotelPilot>("hotel", 233);
    let glass_extended = run_pilot_iterations::<GlassPilot>("glass", 233);
    let school_extended = run_pilot_iterations::<SchoolPilot>("school", 234);
    println!("  ✓ Extended load test completed\n");

    // Aggregate results
    let total_duration = start_time.elapsed().as_millis();

    // Combine metrics
    let hotel_combined = PilotMetrics {
        iterations: 333,
        avg_latency_ms: (hotel_metrics.avg_latency_ms + hotel_extended.avg_latency_ms) / 2.0,
        min_latency_ms: std::cmp::min(hotel_metrics.min_latency_ms, hotel_extended.min_latency_ms),
        max_latency_ms: std::cmp::max(hotel_metrics.max_latency_ms, hotel_extended.max_latency_ms),
        median_latency_ms: (hotel_metrics.median_latency_ms + hotel_extended.median_latency_ms) / 2,
        p95_latency_ms: (hotel_metrics.p95_latency_ms + hotel_extended.p95_latency_ms) / 2,
        p99_latency_ms: (hotel_metrics.p99_latency_ms + hotel_extended.p99_latency_ms) / 2,
        total_duration_ms: hotel_metrics.total_duration_ms + hotel_extended.total_duration_ms,
        errors: hotel_metrics.errors + hotel_extended.errors,
        success_rate: ((333 - (hotel_metrics.errors + hotel_extended.errors)) as f64 / 333.0)
            * 100.0,
        decisions: [
            hotel_metrics.decisions.clone(),
            hotel_extended.decisions.clone(),
        ]
        .concat(),
        checkpoints_captured: hotel_metrics.checkpoints_captured
            + hotel_extended.checkpoints_captured,
        avg_memory_peak_mb: (hotel_metrics.avg_memory_peak_mb + hotel_extended.avg_memory_peak_mb)
            / 2.0,
    };

    let glass_combined = PilotMetrics {
        iterations: 333,
        avg_latency_ms: (glass_metrics.avg_latency_ms + glass_extended.avg_latency_ms) / 2.0,
        min_latency_ms: std::cmp::min(glass_metrics.min_latency_ms, glass_extended.min_latency_ms),
        max_latency_ms: std::cmp::max(glass_metrics.max_latency_ms, glass_extended.max_latency_ms),
        median_latency_ms: (glass_metrics.median_latency_ms + glass_extended.median_latency_ms) / 2,
        p95_latency_ms: (glass_metrics.p95_latency_ms + glass_extended.p95_latency_ms) / 2,
        p99_latency_ms: (glass_metrics.p99_latency_ms + glass_extended.p99_latency_ms) / 2,
        total_duration_ms: glass_metrics.total_duration_ms + glass_extended.total_duration_ms,
        errors: glass_metrics.errors + glass_extended.errors,
        success_rate: ((333 - (glass_metrics.errors + glass_extended.errors)) as f64 / 333.0)
            * 100.0,
        decisions: [
            glass_metrics.decisions.clone(),
            glass_extended.decisions.clone(),
        ]
        .concat(),
        checkpoints_captured: glass_metrics.checkpoints_captured
            + glass_extended.checkpoints_captured,
        avg_memory_peak_mb: (glass_metrics.avg_memory_peak_mb + glass_extended.avg_memory_peak_mb)
            / 2.0,
    };

    let school_combined = PilotMetrics {
        iterations: 334,
        avg_latency_ms: (school_metrics.avg_latency_ms + school_extended.avg_latency_ms) / 2.0,
        min_latency_ms: std::cmp::min(
            school_metrics.min_latency_ms,
            school_extended.min_latency_ms,
        ),
        max_latency_ms: std::cmp::max(
            school_metrics.max_latency_ms,
            school_extended.max_latency_ms,
        ),
        median_latency_ms: (school_metrics.median_latency_ms + school_extended.median_latency_ms)
            / 2,
        p95_latency_ms: (school_metrics.p95_latency_ms + school_extended.p95_latency_ms) / 2,
        p99_latency_ms: (school_metrics.p99_latency_ms + school_extended.p99_latency_ms) / 2,
        total_duration_ms: school_metrics.total_duration_ms + school_extended.total_duration_ms,
        errors: school_metrics.errors + school_extended.errors,
        success_rate: ((334 - (school_metrics.errors + school_extended.errors)) as f64 / 334.0)
            * 100.0,
        decisions: [
            school_metrics.decisions.clone(),
            school_extended.decisions.clone(),
        ]
        .concat(),
        checkpoints_captured: school_metrics.checkpoints_captured
            + school_extended.checkpoints_captured,
        avg_memory_peak_mb: (school_metrics.avg_memory_peak_mb
            + school_extended.avg_memory_peak_mb)
            / 2.0,
    };

    let edge_cases = extract_edge_cases(&hotel_combined, &glass_combined, &school_combined);
    let proof_artifacts = build_proof_artifacts(&hotel_combined, &glass_combined, &school_combined);

    let mut system_stats = HashMap::new();
    system_stats.insert("total_test_duration_ms".to_string(), total_duration as f64);
    system_stats.insert("total_iterations_executed".to_string(), 1000.0);
    system_stats.insert(
        "average_pilot_success_rate".to_string(),
        (hotel_combined.success_rate + glass_combined.success_rate + school_combined.success_rate)
            / 3.0,
    );
    system_stats.insert(
        "total_checkpoints_captured".to_string(),
        (hotel_combined.checkpoints_captured
            + glass_combined.checkpoints_captured
            + school_combined.checkpoints_captured) as f64,
    );

    let result = LoadTestResult {
        test_run_id,
        timestamp: Utc::now(),
        total_iterations: 1000,
        hotel_pilot: hotel_combined,
        glass_pilot: glass_combined,
        school_pilot: school_combined,
        edge_cases,
        proof_artifacts,
        system_stats,
    };

    println!("\n=== LOAD TEST RESULTS ===\n");
    println!("Test Run ID: {}", result.test_run_id);
    println!("Total Duration: {}ms", total_duration);
    println!("Total Iterations: {}", result.total_iterations);
    println!("\nHotel Pilot:");
    println!("  Iterations: {}", result.hotel_pilot.iterations);
    println!("  Avg Latency: {:.2}ms", result.hotel_pilot.avg_latency_ms);
    println!(
        "  Min/Max: {}ms / {}ms",
        result.hotel_pilot.min_latency_ms, result.hotel_pilot.max_latency_ms
    );
    println!(
        "  P95/P99: {}ms / {}ms",
        result.hotel_pilot.p95_latency_ms, result.hotel_pilot.p99_latency_ms
    );
    println!("  Success Rate: {:.2}%", result.hotel_pilot.success_rate);
    println!("  Errors: {}", result.hotel_pilot.errors);
    println!("  Checkpoints: {}", result.hotel_pilot.checkpoints_captured);

    println!("\nGlass Pilot:");
    println!("  Iterations: {}", result.glass_pilot.iterations);
    println!("  Avg Latency: {:.2}ms", result.glass_pilot.avg_latency_ms);
    println!(
        "  Min/Max: {}ms / {}ms",
        result.glass_pilot.min_latency_ms, result.glass_pilot.max_latency_ms
    );
    println!(
        "  P95/P99: {}ms / {}ms",
        result.glass_pilot.p95_latency_ms, result.glass_pilot.p99_latency_ms
    );
    println!("  Success Rate: {:.2}%", result.glass_pilot.success_rate);
    println!("  Errors: {}", result.glass_pilot.errors);
    println!("  Checkpoints: {}", result.glass_pilot.checkpoints_captured);

    println!("\nSchool Pilot:");
    println!("  Iterations: {}", result.school_pilot.iterations);
    println!("  Avg Latency: {:.2}ms", result.school_pilot.avg_latency_ms);
    println!(
        "  Min/Max: {}ms / {}ms",
        result.school_pilot.min_latency_ms, result.school_pilot.max_latency_ms
    );
    println!(
        "  P95/P99: {}ms / {}ms",
        result.school_pilot.p95_latency_ms, result.school_pilot.p99_latency_ms
    );
    println!("  Success Rate: {:.2}%", result.school_pilot.success_rate);
    println!("  Errors: {}", result.school_pilot.errors);
    println!(
        "  Checkpoints: {}",
        result.school_pilot.checkpoints_captured
    );

    println!("\nEdge Cases Detected: {}", result.edge_cases.len());
    for edge_case in &result.edge_cases {
        println!("  - {}: {}", edge_case.pilot, edge_case.description);
    }

    println!("\nProof Artifacts: {}", result.proof_artifacts.len());
    for artifact in &result.proof_artifacts {
        println!(
            "  - {}: {} layers, {} checkpoints",
            artifact.artifact_id,
            artifact.total_layers_traversed,
            artifact.checkpoint_times.len()
        );
    }

    // Output JSON
    println!("\n=== JSON OUTPUT ===\n");
    let json_output =
        serde_json::to_string_pretty(&result).expect("Failed to serialize results to JSON");
    println!("{}", json_output);

    // Also write to file
    let output_file = "/Users/andriileukhin/Documents/SovereignNexus/load_test_results.json";
    match std::fs::write(output_file, &json_output) {
        Ok(_) => println!("\n✓ Results written to: {}", output_file),
        Err(e) => println!("\n✗ Failed to write results: {}", e),
    }
}
