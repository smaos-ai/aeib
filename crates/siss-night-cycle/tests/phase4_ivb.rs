use siss_night_cycle::{FailureAnalyzer, OfflineVerifier, ConfigEvolution, MetricsDb};
use std::io::Write;
use tempfile::NamedTempFile;

#[test]
fn test_ivb_full_pipeline() {
    let mut log_file = NamedTempFile::new().unwrap();
    let entries = vec![
        r#"{"event":"watchdog_alert","message":"Test failed (attempt 1/2)","source":"siss-night-cycle","timestamp":"2026-05-27T10:38:37.666775+00:00"}"#,
        r#"{"event":"watchdog_alert","message":"Test failed (attempt 2/2)","source":"siss-night-cycle","timestamp":"2026-05-27T10:38:37.743206+00:00"}"#,
        r#"{"event":"watchdog","message":"Max retries reached. Halting for human review.","source":"siss-night-cycle","timestamp":"2026-05-27T10:38:37.823616+00:00"}"#,
        r#"{"event":"watchdog","message":"test passed","source":"siss-night-cycle","timestamp":"2026-05-27T10:41:05.478108+00:00"}"#,
        r#"{"event":"watchdog_alert","message":"connection timeout occurred","source":"siss-night-cycle","timestamp":"2026-05-27T10:42:05.123456+00:00"}"#,
    ];

    for entry in entries {
        writeln!(log_file, "{}", entry).unwrap();
    }
    log_file.flush().unwrap();

    let mut analyzer = FailureAnalyzer::from_log_file(log_file.path()).unwrap();
    analyzer.analyze();

    assert_eq!(analyzer.entries.len(), 5);
    assert!(!analyzer.patterns.is_empty());

    let metrics_file = NamedTempFile::new().unwrap();
    let db = MetricsDb::new(Some(metrics_file.path().to_path_buf())).unwrap();
    db.record_run(2.5, 150.0, 250, 25, 0).unwrap();

    let verifier = OfflineVerifier::new(analyzer, db);
    let report = verifier.verify().unwrap();

    assert!(report.total_entries_analyzed > 0);
    assert!(report.suggestions.len() > 0 || report.next_actions.is_empty());

    let config_file = NamedTempFile::new().unwrap();
    let mut evolution = ConfigEvolution::new(config_file.path().to_path_buf()).unwrap();
    evolution
        .record_mutation("max_retries", "3", "4", "High failure rate detected")
        .unwrap();

    assert_eq!(evolution.get_mutations().len(), 1);
    evolution.apply_mutation(0).unwrap();
    assert!(evolution.get_mutations()[0].applied);

    let report_file = NamedTempFile::new().unwrap();
    verifier
        .write_report(&report, &report_file.path().to_path_buf())
        .unwrap();

    let report_content = std::fs::read_to_string(report_file.path()).unwrap();
    assert!(report_content.contains("total_entries_analyzed"));
}

#[test]
fn test_ivb_failure_pattern_detection() {
    let mut log_file = NamedTempFile::new().unwrap();
    let entries = vec![
        r#"{"event":"watchdog_alert","message":"Database connection timeout","source":"siss-night-cycle","timestamp":"2026-05-27T10:00:00.000000+00:00"}"#,
        r#"{"event":"watchdog_alert","message":"Network timeout waiting for response","source":"siss-night-cycle","timestamp":"2026-05-27T10:01:00.000000+00:00"}"#,
        r#"{"event":"watchdog_alert","message":"Socket timeout on accept","source":"siss-night-cycle","timestamp":"2026-05-27T10:02:00.000000+00:00"}"#,
    ];

    for entry in entries {
        writeln!(log_file, "{}", entry).unwrap();
    }
    log_file.flush().unwrap();

    let mut analyzer = FailureAnalyzer::from_log_file(log_file.path()).unwrap();
    analyzer.analyze();

    let timeout_patterns: Vec<_> = analyzer
        .patterns
        .values()
        .filter(|p| p.category == "timeout")
        .collect();

    assert!(!timeout_patterns.is_empty());
    assert!(timeout_patterns[0].count >= 3);
}

#[test]
fn test_ivb_configuration_mutation_tracking() {
    let config_file = NamedTempFile::new().unwrap();
    let mut evolution = ConfigEvolution::new(config_file.path().to_path_buf()).unwrap();

    evolution
        .record_mutation("max_retries", "3", "4", "Reason 1")
        .unwrap();
    evolution
        .record_mutation("backoff_base", "2s", "1.5s", "Reason 2")
        .unwrap();
    evolution
        .record_mutation("socket_timeout", "100ms", "250ms", "Reason 3")
        .unwrap();

    evolution.apply_mutation(0).unwrap();
    evolution.apply_mutation(2).unwrap();

    let unapplied = evolution.get_unapplied_mutations();
    assert_eq!(unapplied.len(), 1);
    assert_eq!(unapplied[0].parameter, "backoff_base");
}
