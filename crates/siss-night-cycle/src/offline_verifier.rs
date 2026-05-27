use crate::failure_analyzer::FailureAnalyzer;
use crate::metrics::MetricsDb;
use serde::{Deserialize, Serialize};
use std::fs::File;
use std::io::Write;
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Suggestion {
    pub category: String,
    pub current_value: String,
    pub recommended_value: String,
    pub confidence: f64,
    pub rationale: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationReport {
    pub timestamp: String,
    pub total_entries_analyzed: usize,
    pub patterns_found: usize,
    pub suggestions: Vec<Suggestion>,
    pub next_actions: Vec<String>,
}

pub struct OfflineVerifier {
    analyzer: FailureAnalyzer,
    db: MetricsDb,
}

impl OfflineVerifier {
    pub fn new(analyzer: FailureAnalyzer, db: MetricsDb) -> Self {
        Self { analyzer, db }
    }

    pub fn verify(&self) -> std::io::Result<VerificationReport> {
        let timestamp = chrono::Utc::now().to_rfc3339();
        let patterns_found = self.analyzer.patterns.len();
        let total_entries = self.analyzer.entries.len();

        let mut suggestions = Vec::new();
        let mut next_actions = Vec::new();

        if let Ok((_, _, avg_duration)) = self.db.stats() {
            let max_retries_rate = self.analyzer.get_failure_rate("watchdog_alert");

            if max_retries_rate > 0.1 {
                suggestions.push(Suggestion {
                    category: "watchdog_max_retries".to_string(),
                    current_value: "3".to_string(),
                    recommended_value: "4".to_string(),
                    confidence: 0.85,
                    rationale: format!(
                        "Max retries exceeded in {:.1}% of runs. Increase retries.",
                        max_retries_rate * 100.0
                    ),
                });
                next_actions.push(
                    "Update watchdog.rs max_retries from 3 to 4 and re-test".to_string(),
                );
            }

            if avg_duration > 500.0 {
                suggestions.push(Suggestion {
                    category: "backoff_timing".to_string(),
                    current_value: "2s base".to_string(),
                    recommended_value: "1.5s base".to_string(),
                    confidence: 0.75,
                    rationale: format!(
                        "Avg test duration {:.0}ms. Reduce backoff to speed up retries.",
                        avg_duration
                    ),
                });
                next_actions.push("Monitor impact of reduced backoff on success rate".to_string());
            }
        }

        let timeout_pattern = self
            .analyzer
            .patterns
            .values()
            .find(|p| p.category == "timeout");
        if let Some(pattern) = timeout_pattern {
            if pattern.count > 5 {
                suggestions.push(Suggestion {
                    category: "socket_timeout".to_string(),
                    current_value: "100ms".to_string(),
                    recommended_value: "250ms".to_string(),
                    confidence: 0.80,
                    rationale: format!(
                        "Timeout failures observed {} times. Increase socket timeout.",
                        pattern.count
                    ),
                });
                next_actions.push("Increase TcpListener timeout threshold".to_string());
            }
        }

        Ok(VerificationReport {
            timestamp,
            total_entries_analyzed: total_entries,
            patterns_found,
            suggestions,
            next_actions,
        })
    }

    pub fn write_report(&self, report: &VerificationReport, path: &PathBuf) -> std::io::Result<()> {
        let json = serde_json::to_string_pretty(&report)?;
        let mut file = File::create(path)?;
        file.write_all(json.as_bytes())?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::failure_analyzer::LogEntry;
    use std::collections::HashMap;
    use tempfile::NamedTempFile;

    #[test]
    fn test_offline_verifier_suggestions() {
        let mut analyzer = FailureAnalyzer {
            entries: vec![
                LogEntry {
                    event: "watchdog_alert".to_string(),
                    message: "Test failed (attempt 1/2)".to_string(),
                    source: "test".to_string(),
                    timestamp: "2026-05-27T00:00:00Z".to_string(),
                },
                LogEntry {
                    event: "watchdog_alert".to_string(),
                    message: "Test failed (attempt 2/2)".to_string(),
                    source: "test".to_string(),
                    timestamp: "2026-05-27T00:00:01Z".to_string(),
                },
            ],
            patterns: HashMap::new(),
        };
        analyzer.analyze();

        let temp_file = NamedTempFile::new().unwrap();
        let db = MetricsDb::new(Some(temp_file.path().to_path_buf())).unwrap();
        let verifier = OfflineVerifier::new(analyzer, db);

        let report = verifier.verify().unwrap();
        assert!(report.total_entries_analyzed > 0);
    }

    #[test]
    fn test_write_verification_report() {
        let analyzer = FailureAnalyzer {
            entries: vec![],
            patterns: HashMap::new(),
        };

        let temp_db_file = NamedTempFile::new().unwrap();
        let db = MetricsDb::new(Some(temp_db_file.path().to_path_buf())).unwrap();
        let verifier = OfflineVerifier::new(analyzer, db);

        let report = VerificationReport {
            timestamp: "2026-05-27T12:00:00Z".to_string(),
            total_entries_analyzed: 10,
            patterns_found: 2,
            suggestions: vec![],
            next_actions: vec!["Test action".to_string()],
        };

        let temp_report_file = NamedTempFile::new().unwrap();
        verifier
            .write_report(&report, &temp_report_file.path().to_path_buf())
            .unwrap();

        let content = std::fs::read_to_string(temp_report_file.path()).unwrap();
        assert!(content.contains("total_entries_analyzed"));
    }
}
