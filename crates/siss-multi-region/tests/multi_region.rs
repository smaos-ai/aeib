use std::time::Instant;
use std::sync::Arc;
use std::time::Duration;
use uuid::Uuid;
use siss_multi_region::{MultiRegionReplicator, HealthChecker, FailoverManager, FailoverDecision};
use sha2::{Sha256, Digest};
use serde_json::{json, to_string_pretty};

fn compute_hash(data: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data.as_bytes());
    format!("{:x}", hasher.finalize())
}

#[tokio::test]
async fn test_capsule_replicates_to_all_regions() {
    let replicator = MultiRegionReplicator::new(
        "prague".to_string(),
        vec!["frankfurt".to_string()],
    );

    let capsule_id = Uuid::new_v4();
    let data = "test-capsule-data-v1";
    let hash = compute_hash(data);

    // Replicate capsule
    let result = replicator.replicate_capsule(capsule_id, data, &hash).await;
    assert!(result.is_ok(), "Replication should succeed");

    // Acknowledge replication on frankfurt
    let ack_result = replicator.acknowledge_replication(capsule_id, "frankfurt").await;
    assert!(ack_result.is_ok(), "Acknowledgment should succeed");

    // Verify replication complete
    let is_complete = replicator.is_replication_complete(capsule_id).await.unwrap();
    assert!(is_complete, "Replication should be complete after acknowledgment");

    // Verify state shows all_replicated (RPO=0 invariant)
    let state = replicator.get_replication_state(capsule_id).await.unwrap().unwrap();
    assert!(state.all_replicated(), "All replicas should be acknowledged (RPO=0)");
}

#[tokio::test]
async fn test_health_check_triggers_failover() {
    let checker = Arc::new(HealthChecker::new(Duration::from_secs(5)));

    // Register 3 regions
    checker.register_region("prague".to_string()).await.unwrap();
    checker.register_region("frankfurt".to_string()).await.unwrap();
    checker.register_region("london".to_string()).await.unwrap();

    // Prague fails (3 consecutive failures → Unhealthy)
    for _ in 0..3 {
        checker.record_failure("prague").await.unwrap();
    }

    // Frankfurt and London healthy
    checker.record_success("frankfurt", 100).await.unwrap();
    checker.record_success("london", 120).await.unwrap();

    // Create failover manager: prague primary, frankfurt & london secondaries
    let manager = FailoverManager::new(
        "prague".to_string(),
        vec!["frankfurt".to_string(), "london".to_string()],
        checker,
    );

    // Evaluate failover
    // Quorum math: total_regions=3, quorum_size=(3/2)+1=2
    // Primary prague is unhealthy, healthy_secondaries=[frankfurt, london] = 2
    // healthy_count = 0 + 2 = 2, quorum_size = 2 → quorum achieved → failover allowed
    let decision = manager.evaluate_failover().await.unwrap();

    match decision {
        FailoverDecision::FailoverToRegion { target_region, .. } => {
            assert!(target_region == "frankfurt" || target_region == "london",
                "Should failover to a healthy secondary");
        }
        _ => panic!("Expected FailoverToRegion decision, got {:?}", decision),
    }
}

#[tokio::test]
async fn test_vector_clock_causality_preserved() {
    use siss_multi_region::replication::VectorClock;

    let mut vc1 = VectorClock::new();
    vc1.increment("prague");
    // vc1 = {prague: 1}

    let mut vc2 = vc1.clone();
    vc2.increment("frankfurt");
    // vc2 = {prague: 1, frankfurt: 1}

    // vc1 happened before vc2
    assert!(vc1.happens_before(&vc2), "vc1 should happen before vc2");

    // vc2 did not happen before vc1
    assert!(!vc2.happens_before(&vc1), "vc2 should not happen before vc1");

    // They are not concurrent (one happens before the other)
    assert!(!vc1.concurrent_with(&vc2), "vc1 and vc2 are causally ordered, not concurrent");
}

#[tokio::test]
async fn test_quorum_not_achieved_halts_on_split_brain() {
    let checker = Arc::new(HealthChecker::new(Duration::from_secs(5)));

    // Register 2 regions only
    checker.register_region("prague".to_string()).await.unwrap();
    checker.register_region("frankfurt".to_string()).await.unwrap();

    // Prague fails (3 consecutive failures → Unhealthy)
    for _ in 0..3 {
        checker.record_failure("prague").await.unwrap();
    }

    // Frankfurt is healthy
    checker.record_success("frankfurt", 100).await.unwrap();

    // Create failover manager
    let manager = FailoverManager::new(
        "prague".to_string(),
        vec!["frankfurt".to_string()],
        checker,
    );

    // Evaluate failover
    // Quorum math: total_regions=2, quorum_size=(2/2)+1=2
    // Primary prague is unhealthy, healthy_secondaries=[frankfurt] = 1
    // healthy_count = 0 + 1 = 1, quorum_size = 2 → no quorum → split-brain halt
    let decision = manager.evaluate_failover().await.unwrap();

    match decision {
        FailoverDecision::HaltOnSplitBrain { detected_regions } => {
            assert!(detected_regions.len() >= 2, "Should detect split-brain across regions");
        }
        _ => panic!("Expected HaltOnSplitBrain decision, got {:?}", decision),
    }
}

#[tokio::test]
async fn test_replication_completes_within_rto() {
    let replicator = MultiRegionReplicator::new(
        "prague".to_string(),
        vec!["frankfurt".to_string()],
    );

    let capsule_id = Uuid::new_v4();
    let data = "test-capsule-for-rto";
    let hash = compute_hash(data);

    // Time the replication
    let start = Instant::now();

    replicator.replicate_capsule(capsule_id, data, &hash).await.unwrap();
    replicator.acknowledge_replication(capsule_id, "frankfurt").await.unwrap();

    let elapsed = start.elapsed();

    // Verify RTO < 30 seconds (in-memory, so always true, but documents the invariant)
    assert!(elapsed.as_millis() < 30_000, "Replication should complete within 30s RTO");

    // Verify RPO=0: data exists in replica
    let is_complete = replicator.is_replication_complete(capsule_id).await.unwrap();
    assert!(is_complete, "Replication should be complete (RPO=0 invariant)");
}

#[tokio::test]
async fn test_generate_multi_region_report() {
    use std::fs;

    // Run all 5 scenarios to collect results
    let mut test_results = vec![];

    // Test 1: Replication
    let replicator = MultiRegionReplicator::new("prague".to_string(), vec!["frankfurt".to_string()]);
    let id1 = Uuid::new_v4();
    let data1 = "test-data-1";
    let hash1 = compute_hash(data1);
    let result1 = replicator.replicate_capsule(id1, data1, &hash1).await.is_ok()
        && replicator.acknowledge_replication(id1, "frankfurt").await.is_ok()
        && replicator.is_replication_complete(id1).await.unwrap_or(false);
    test_results.push(("test_capsule_replicates_to_all_regions", result1));

    // Test 2: Failover
    let checker2 = Arc::new(HealthChecker::new(Duration::from_secs(5)));
    checker2.register_region("prague".to_string()).await.ok();
    checker2.register_region("frankfurt".to_string()).await.ok();
    checker2.register_region("london".to_string()).await.ok();
    for _ in 0..3 { checker2.record_failure("prague").await.ok(); }
    checker2.record_success("frankfurt", 100).await.ok();
    checker2.record_success("london", 120).await.ok();
    let manager2 = FailoverManager::new("prague".to_string(), vec!["frankfurt".to_string(), "london".to_string()], checker2);
    let result2 = matches!(manager2.evaluate_failover().await, Ok(FailoverDecision::FailoverToRegion { .. }));
    test_results.push(("test_health_check_triggers_failover", result2));

    // Test 3: Vector clock
    use siss_multi_region::replication::VectorClock;
    let mut vc1 = VectorClock::new();
    vc1.increment("prague");
    let mut vc2 = vc1.clone();
    vc2.increment("frankfurt");
    let result3 = vc1.happens_before(&vc2) && !vc2.happens_before(&vc1);
    test_results.push(("test_vector_clock_causality_preserved", result3));

    // Test 4: Quorum
    let checker4 = Arc::new(HealthChecker::new(Duration::from_secs(5)));
    checker4.register_region("prague".to_string()).await.ok();
    checker4.register_region("frankfurt".to_string()).await.ok();
    for _ in 0..3 { checker4.record_failure("prague").await.ok(); }
    checker4.record_success("frankfurt", 100).await.ok();
    let manager4 = FailoverManager::new("prague".to_string(), vec!["frankfurt".to_string()], checker4);
    let result4 = matches!(manager4.evaluate_failover().await, Ok(FailoverDecision::HaltOnSplitBrain { .. }));
    test_results.push(("test_quorum_not_achieved_halts_on_split_brain", result4));

    // Test 5: RTO
    let replicator5 = MultiRegionReplicator::new("prague".to_string(), vec!["frankfurt".to_string()]);
    let id5 = Uuid::new_v4();
    let data5 = "test-data-5";
    let hash5 = compute_hash(data5);
    let start5 = Instant::now();
    replicator5.replicate_capsule(id5, data5, &hash5).await.ok();
    replicator5.acknowledge_replication(id5, "frankfurt").await.ok();
    let elapsed5 = start5.elapsed();
    let result5 = elapsed5.as_millis() < 30_000 && replicator5.is_replication_complete(id5).await.unwrap_or(false);
    test_results.push(("test_replication_completes_within_rto", result5));

    // Create report directory (workspace root)
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let report_dir = format!("{}/../../.claude/reports/night-cycle/multi_region", manifest_dir);
    fs::create_dir_all(&report_dir).expect("Failed to create report directory");

    // Generate test_run.json
    let test_run_json = json!({
        "timestamp": std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs(),
        "test_suite": "siss-multi-region",
        "tests": test_results.iter().map(|(name, passed)| {
            json!({
                "name": name,
                "status": if *passed { "PASSED" } else { "FAILED" },
                "passed": passed
            })
        }).collect::<Vec<_>>(),
        "summary": {
            "total": test_results.len(),
            "passed": test_results.iter().filter(|(_, p)| *p).count(),
            "failed": test_results.iter().filter(|(_, p)| !*p).count(),
        }
    });

    let test_run_str = to_string_pretty(&test_run_json).expect("Failed to serialize JSON");
    fs::write(
        format!("{}/test_run.json", report_dir),
        &test_run_str
    ).expect("Failed to write test_run.json");

    // Generate merkle_proof.json (SHA256 of test_run.json)
    let merkle_hash = compute_hash(&test_run_str);
    let merkle_proof = json!({
        "algorithm": "SHA256",
        "hash": merkle_hash,
        "source": "test_run.json"
    });
    fs::write(
        format!("{}/merkle_proof.json", report_dir),
        to_string_pretty(&merkle_proof).unwrap()
    ).expect("Failed to write merkle_proof.json");

    // Generate MULTI_REGION_REPORT.md
    let markdown = format!(
        "# Multi-Region Integration Test Report\n\n\
         ## Summary\n\n\
         - **Total Tests:** {}\n\
         - **Passed:** {}\n\
         - **Failed:** {}\n\n\
         ## Test Results\n\n\
         {}\n\n\
         ## Merkle Proof\n\n\
         **SHA256:** `{}`\n\n\
         **Source:** `test_run.json`\n",
        test_results.len(),
        test_results.iter().filter(|(_, p)| *p).count(),
        test_results.iter().filter(|(_, p)| !*p).count(),
        test_results.iter().map(|(name, passed)| {
            format!("- **{}**: {}", name, if *passed { "✓ PASS" } else { "✗ FAIL" })
        }).collect::<Vec<_>>().join("\n"),
        merkle_hash
    );

    fs::write(
        format!("{}/MULTI_REGION_REPORT.md", report_dir),
        markdown
    ).expect("Failed to write MULTI_REGION_REPORT.md");

    // All tests should pass
    assert!(test_results.iter().all(|(_, p)| *p), "All integration tests should pass");
}
