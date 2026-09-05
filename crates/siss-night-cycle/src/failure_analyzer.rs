use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    pub event: String,
    pub message: String,
    pub source: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FailurePattern {
    pub event_type: String,
    pub category: String,
    pub count: u32,
    pub messages: Vec<String>,
}

pub struct FailureAnalyzer {
    pub entries: Vec<LogEntry>,
    pub patterns: HashMap<String, FailurePattern>,
}

impl FailureAnalyzer {
    pub fn from_log_file(path: &Path) -> std::io::Result<Self> {
        let file = File::open(path)?;
        let reader = BufReader::new(file);
        let mut entries = Vec::new();

        for line in reader.lines() {
            let line = line?;
            if let Ok(entry) = serde_json::from_str::<LogEntry>(&line) {
                entries.push(entry);
            }
        }

        Ok(Self {
            entries,
            patterns: HashMap::new(),
        })
    }

    pub fn analyze(&mut self) {
        let mut patterns: HashMap<String, (u32, Vec<String>)> = HashMap::new();

        for entry in &self.entries {
            let key = format!("{}::{}", entry.event, self.categorize(&entry.message));
            let entry_data = patterns.entry(key).or_insert((0, Vec::new()));
            entry_data.0 += 1;
            entry_data.1.push(entry.message.clone());
        }

        for (key, (count, messages)) in patterns {
            let parts: Vec<&str> = key.split("::").collect();
            let event_type = parts[0].to_string();
            let category = parts[1].to_string();

            self.patterns.insert(
                key,
                FailurePattern {
                    event_type,
                    category,
                    count,
                    messages,
                },
            );
        }
    }

    fn categorize(&self, message: &str) -> &'static str {
        if message.contains("timeout") || message.contains("Timeout") {
            "timeout"
        } else if message.contains("connection") || message.contains("Connection") {
            "network"
        } else if message.contains("database") || message.contains("Database") {
            "database"
        } else if message.contains("retry") || message.contains("Retry") {
            "retry"
        } else if message.contains("max retries") {
            "max_retries_exceeded"
        } else if message.contains("passed") {
            "success"
        } else {
            "unknown"
        }
    }

    pub fn get_failure_rate(&self, event_type: &str) -> f64 {
        let total = self.entries.len() as f64;
        if total == 0.0 {
            return 0.0;
        }

        let failures = self
            .entries
            .iter()
            .filter(|e| e.event.contains(event_type))
            .count() as f64;

        failures / total
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_parse_log_entries() {
        let mut temp_file = NamedTempFile::new().unwrap();
        let entry1 = r#"{"event":"watchdog_alert","message":"Test failed (attempt 1/2)","source":"siss-night-cycle","timestamp":"2026-05-27T10:38:37.666775+00:00"}"#;
        let entry2 = r#"{"event":"watchdog","message":"Max retries reached. Halting for human review.","source":"siss-night-cycle","timestamp":"2026-05-27T10:38:37.823616+00:00"}"#;

        writeln!(temp_file, "{}", entry1).unwrap();
        writeln!(temp_file, "{}", entry2).unwrap();
        temp_file.flush().unwrap();

        let analyzer = FailureAnalyzer::from_log_file(temp_file.path()).unwrap();
        assert_eq!(analyzer.entries.len(), 2);
        assert_eq!(analyzer.entries[0].event, "watchdog_alert");
    }

    #[test]
    fn test_categorize_messages() {
        let mut analyzer = FailureAnalyzer {
            entries: vec![
                LogEntry {
                    event: "watchdog_alert".to_string(),
                    message: "connection timeout".to_string(),
                    source: "test".to_string(),
                    timestamp: "2026-05-27T00:00:00Z".to_string(),
                },
                LogEntry {
                    event: "watchdog_alert".to_string(),
                    message: "Database error".to_string(),
                    source: "test".to_string(),
                    timestamp: "2026-05-27T00:00:00Z".to_string(),
                },
            ],
            patterns: HashMap::new(),
        };

        analyzer.analyze();
        let timeout_pattern = analyzer.patterns.values().find(|p| p.category == "timeout");
        assert!(timeout_pattern.is_some());
    }
}
