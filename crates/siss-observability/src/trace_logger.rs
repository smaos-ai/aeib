use crate::{Result, ObservabilityError};
use dashmap::DashMap;
use std::sync::Arc;
use uuid::Uuid;
use std::time::SystemTime;

#[derive(Debug, Clone)]
pub struct LogEntry {
    pub id: Uuid,
    pub span_id: Uuid,
    pub level: LogLevel,
    pub message: String,
    pub timestamp: SystemTime,
    pub context: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LogLevel {
    Debug,
    Info,
    Warn,
    Error,
    Critical,
}

impl LogLevel {
    pub fn as_str(&self) -> &str {
        match self {
            LogLevel::Debug => "DEBUG",
            LogLevel::Info => "INFO",
            LogLevel::Warn => "WARN",
            LogLevel::Error => "ERROR",
            LogLevel::Critical => "CRITICAL",
        }
    }
}

pub struct TraceLogger {
    logs: Arc<DashMap<Uuid, Vec<LogEntry>>>,
    global_logs: Arc<parking_lot::Mutex<Vec<LogEntry>>>,
}

impl TraceLogger {
    pub fn new() -> Self {
        Self {
            logs: Arc::new(DashMap::new()),
            global_logs: Arc::new(parking_lot::Mutex::new(Vec::new())),
        }
    }

    pub fn log(
        &self,
        span_id: Uuid,
        level: LogLevel,
        message: String,
        context: Option<String>,
    ) -> Uuid {
        let entry_id = Uuid::new_v4();
        let entry = LogEntry {
            id: entry_id,
            span_id,
            level,
            message,
            timestamp: SystemTime::now(),
            context,
        };

        self.logs
            .entry(span_id)
            .or_insert_with(Vec::new)
            .push(entry.clone());

        self.global_logs.lock().push(entry);

        entry_id
    }

    pub fn debug(&self, span_id: Uuid, message: String) -> Uuid {
        self.log(span_id, LogLevel::Debug, message, None)
    }

    pub fn info(&self, span_id: Uuid, message: String, context: Option<String>) -> Uuid {
        self.log(span_id, LogLevel::Info, message, context)
    }

    pub fn warn(&self, span_id: Uuid, message: String, context: Option<String>) -> Uuid {
        self.log(span_id, LogLevel::Warn, message, context)
    }

    pub fn error(&self, span_id: Uuid, message: String, context: Option<String>) -> Uuid {
        self.log(span_id, LogLevel::Error, message, context)
    }

    pub fn critical(&self, span_id: Uuid, message: String, context: Option<String>) -> Uuid {
        self.log(span_id, LogLevel::Critical, message, context)
    }

    pub fn get_logs(&self, span_id: Uuid) -> Option<Vec<LogEntry>> {
        self.logs.get(&span_id).map(|logs| logs.clone())
    }

    pub fn get_global_logs(&self) -> Vec<LogEntry> {
        self.global_logs.lock().clone()
    }

    pub fn get_logs_by_level(&self, span_id: Uuid, level: LogLevel) -> Option<Vec<LogEntry>> {
        self.logs.get(&span_id).map(|logs| {
            logs.iter()
                .filter(|log| log.level == level)
                .cloned()
                .collect()
        })
    }

    pub fn get_global_logs_by_level(&self, level: LogLevel) -> Vec<LogEntry> {
        self.global_logs
            .lock()
            .iter()
            .filter(|log| log.level == level)
            .cloned()
            .collect()
    }

    pub fn clear_logs(&self, span_id: Uuid) {
        self.logs.remove(&span_id);
    }

    pub fn clear_global_logs(&self) {
        self.global_logs.lock().clear();
    }

    pub fn log_count(&self, span_id: Uuid) -> usize {
        self.logs.get(&span_id).map(|logs| logs.len()).unwrap_or(0)
    }

    pub fn global_log_count(&self) -> usize {
        self.global_logs.lock().len()
    }

    pub fn export_logs_jsonl(&self, span_id: Uuid) -> Result<String> {
        let logs = self.logs
            .get(&span_id)
            .ok_or(ObservabilityError::TraceNotFound(span_id.to_string()))?;

        let jsonl = logs
            .iter()
            .map(|entry| {
                format!(
                    r#"{{"id":"{}","span_id":"{}","level":"{}","message":"{}","timestamp":{},"context":{}}}"#,
                    entry.id,
                    entry.span_id,
                    entry.level.as_str(),
                    entry.message.replace("\"", "\\\""),
                    entry
                        .timestamp
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_millis(),
                    entry
                        .context
                        .as_ref()
                        .map(|c| format!(r#""{}""#, c.replace("\"", "\\\"")))
                        .unwrap_or_else(|| "null".to_string())
                )
            })
            .collect::<Vec<_>>()
            .join("\n");

        Ok(jsonl)
    }

    pub fn get_error_logs(&self, span_id: Uuid) -> Option<Vec<LogEntry>> {
        self.logs.get(&span_id).map(|logs| {
            logs.iter()
                .filter(|log| matches!(log.level, LogLevel::Error | LogLevel::Critical))
                .cloned()
                .collect()
        })
    }

    pub fn get_global_error_logs(&self) -> Vec<LogEntry> {
        self.global_logs
            .lock()
            .iter()
            .filter(|log| matches!(log.level, LogLevel::Error | LogLevel::Critical))
            .cloned()
            .collect()
    }
}

impl Default for TraceLogger {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_debug_log() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        let entry_id = logger.debug(span_id, "Debug message".to_string());
        assert!(entry_id != Uuid::nil());
        assert_eq!(logger.log_count(span_id), 1);
    }

    #[test]
    fn test_info_log() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        logger.info(span_id, "Info message".to_string(), Some("context".to_string()));
        assert_eq!(logger.log_count(span_id), 1);
    }

    #[test]
    fn test_error_log() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        logger.error(span_id, "Error occurred".to_string(), Some("error context".to_string()));
        let logs = logger.get_error_logs(span_id).unwrap();
        assert_eq!(logs.len(), 1);
        assert_eq!(logs[0].level, LogLevel::Error);
    }

    #[test]
    fn test_critical_log() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        logger.critical(span_id, "Critical issue".to_string(), None);
        let logs = logger.get_error_logs(span_id).unwrap();
        assert_eq!(logs.len(), 1);
        assert_eq!(logs[0].level, LogLevel::Critical);
    }

    #[test]
    fn test_get_logs_by_level() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        logger.debug(span_id, "Debug".to_string());
        logger.info(span_id, "Info".to_string(), None);
        logger.warn(span_id, "Warn".to_string(), None);
        logger.error(span_id, "Error".to_string(), None);

        let debug_logs = logger.get_logs_by_level(span_id, LogLevel::Debug).unwrap();
        assert_eq!(debug_logs.len(), 1);

        let error_logs = logger.get_logs_by_level(span_id, LogLevel::Error).unwrap();
        assert_eq!(error_logs.len(), 1);
    }

    #[test]
    fn test_global_logs() {
        let logger = TraceLogger::new();

        let span1 = Uuid::new_v4();
        let span2 = Uuid::new_v4();

        logger.info(span1, "Span 1 log".to_string(), None);
        logger.info(span2, "Span 2 log".to_string(), None);

        assert_eq!(logger.global_log_count(), 2);
    }

    #[test]
    fn test_get_global_logs_by_level() {
        let logger = TraceLogger::new();

        let span1 = Uuid::new_v4();
        let span2 = Uuid::new_v4();

        logger.error(span1, "Error 1".to_string(), None);
        logger.error(span2, "Error 2".to_string(), None);
        logger.info(span1, "Info".to_string(), None);

        let global_errors = logger.get_global_logs_by_level(LogLevel::Error);
        assert_eq!(global_errors.len(), 2);
    }

    #[test]
    fn test_clear_logs() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        logger.info(span_id, "Message".to_string(), None);
        assert_eq!(logger.log_count(span_id), 1);

        logger.clear_logs(span_id);
        assert_eq!(logger.log_count(span_id), 0);
    }

    #[test]
    fn test_clear_global_logs() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        logger.info(span_id, "Message".to_string(), None);
        assert_eq!(logger.global_log_count(), 1);

        logger.clear_global_logs();
        assert_eq!(logger.global_log_count(), 0);
    }

    #[test]
    fn test_export_logs_jsonl() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        logger.info(span_id, "First message".to_string(), Some("ctx1".to_string()));
        logger.error(span_id, "Error message".to_string(), None);

        let jsonl = logger.export_logs_jsonl(span_id).unwrap();
        assert!(jsonl.contains("First message"));
        assert!(jsonl.contains("Error message"));
        assert!(jsonl.contains("INFO"));
        assert!(jsonl.contains("ERROR"));
    }

    #[test]
    fn test_log_with_context() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        logger.warn(span_id, "Warning".to_string(), Some("warning context".to_string()));
        let logs = logger.get_logs(span_id).unwrap();
        assert_eq!(logs.len(), 1);
        assert_eq!(logs[0].context, Some("warning context".to_string()));
    }

    #[test]
    fn test_get_logs_nonexistent_span() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        let logs = logger.get_logs(span_id);
        assert!(logs.is_none());
    }

    #[test]
    fn test_multiple_logs_same_span() {
        let logger = TraceLogger::new();
        let span_id = Uuid::new_v4();

        for i in 0..10 {
            logger.info(span_id, format!("Message {}", i), None);
        }

        assert_eq!(logger.log_count(span_id), 10);
    }
}
