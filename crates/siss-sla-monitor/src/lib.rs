use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::sqlite::SqlitePool;
use sqlx::Row;
use std::sync::Arc;
use uuid::Uuid;

/// SLA Thresholds
#[derive(Debug, Clone, Copy)]
pub struct SLAThresholds {
    pub uptime_percent: f64,      // e.g., 99.5
    pub p99_latency_us: u64,      // e.g., 100
    pub max_error_rate_percent: f64, // e.g., 0.1
    pub max_data_loss_count: i32,  // e.g., 0
}

impl Default for SLAThresholds {
    fn default() -> Self {
        SLAThresholds {
            uptime_percent: 99.5,
            p99_latency_us: 100,
            max_error_rate_percent: 0.1,
            max_data_loss_count: 0,
        }
    }
}

/// Represents a single metric data point
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricSnapshot {
    pub timestamp: DateTime<Utc>,
    pub uptime_percent: f64,
    pub p99_latency_us: u64,
    pub error_rate_percent: f64,
    pub data_loss_count: i32,
}

/// Alert types and severity
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AlertSeverity {
    Info,
    Warning,
    Critical,
}

impl std::fmt::Display for AlertSeverity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AlertSeverity::Info => write!(f, "info"),
            AlertSeverity::Warning => write!(f, "warning"),
            AlertSeverity::Critical => write!(f, "critical"),
        }
    }
}

/// Alert record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Alert {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub severity: AlertSeverity,
    pub alert_type: String,
    pub message: String,
    pub acknowledged: bool,
}

/// SLA status summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SLAStatus {
    pub status: String, // "green", "yellow", "red"
    pub uptime_percent: f64,
    pub p99_latency_us: u64,
    pub error_rate_percent: f64,
    pub data_loss_count: i32,
    pub active_alerts: usize,
}

/// Core SLA Monitor
pub struct SLAMonitor {
    db_pool: SqlitePool,
    thresholds: SLAThresholds,
    current_metrics: Arc<tokio::sync::Mutex<MetricSnapshot>>,
}

impl SLAMonitor {
    /// Create a new SLA Monitor with in-memory SQLite
    pub async fn new() -> Result<Self, sqlx::Error> {
        let db_url = "sqlite::memory:";
        let pool = SqlitePool::connect(db_url).await?;

        // Initialize schema
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                severity TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                acknowledged BOOLEAN NOT NULL DEFAULT 0
            )"
        )
        .execute(&pool)
        .await?;

        let current_metrics = Arc::new(tokio::sync::Mutex::new(MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 100.0,
            p99_latency_us: 47,
            error_rate_percent: 0.0,
            data_loss_count: 0,
        }));

        Ok(SLAMonitor {
            db_pool: pool,
            thresholds: SLAThresholds::default(),
            current_metrics,
        })
    }

    /// Create with persistent SQLite file
    pub async fn with_db_file(db_path: &str) -> Result<Self, sqlx::Error> {
        let db_url = format!("sqlite://{}", db_path);
        let pool = SqlitePool::connect(&db_url).await?;

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                severity TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                acknowledged BOOLEAN NOT NULL DEFAULT 0
            )"
        )
        .execute(&pool)
        .await?;

        let current_metrics = Arc::new(tokio::sync::Mutex::new(MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 100.0,
            p99_latency_us: 47,
            error_rate_percent: 0.0,
            data_loss_count: 0,
        }));

        Ok(SLAMonitor {
            db_pool: pool,
            thresholds: SLAThresholds::default(),
            current_metrics,
        })
    }

    /// Set custom SLA thresholds
    pub fn set_thresholds(&mut self, thresholds: SLAThresholds) {
        self.thresholds = thresholds;
    }

    /// Record a metric snapshot and check for SLA violations
    pub async fn record_metrics(&self, snapshot: MetricSnapshot) -> Result<Vec<Alert>, sqlx::Error> {
        let mut metrics = self.current_metrics.lock().await;
        *metrics = snapshot.clone();
        drop(metrics);

        // Check thresholds and create alerts
        let mut alerts = Vec::new();

        if snapshot.uptime_percent < self.thresholds.uptime_percent {
            let alert = self.create_alert(
                AlertSeverity::Critical,
                "uptime_violation".to_string(),
                format!(
                    "Uptime dropped to {:.2}% (threshold: {:.2}%)",
                    snapshot.uptime_percent, self.thresholds.uptime_percent
                ),
            );
            self.store_alert(&alert).await?;
            alerts.push(alert);
        }

        if snapshot.p99_latency_us > self.thresholds.p99_latency_us {
            let alert = self.create_alert(
                AlertSeverity::Warning,
                "latency_violation".to_string(),
                format!(
                    "P99 latency {}µs exceeds threshold {}µs",
                    snapshot.p99_latency_us, self.thresholds.p99_latency_us
                ),
            );
            self.store_alert(&alert).await?;
            alerts.push(alert);
        }

        if snapshot.error_rate_percent > self.thresholds.max_error_rate_percent {
            let alert = self.create_alert(
                AlertSeverity::Warning,
                "error_rate_violation".to_string(),
                format!(
                    "Error rate {:.2}% exceeds threshold {:.2}%",
                    snapshot.error_rate_percent, self.thresholds.max_error_rate_percent
                ),
            );
            self.store_alert(&alert).await?;
            alerts.push(alert);
        }

        if snapshot.data_loss_count > self.thresholds.max_data_loss_count {
            let alert = self.create_alert(
                AlertSeverity::Critical,
                "data_loss_detected".to_string(),
                format!(
                    "Data loss detected: {} capsules lost",
                    snapshot.data_loss_count
                ),
            );
            self.store_alert(&alert).await?;
            alerts.push(alert);
        }

        Ok(alerts)
    }

    /// Get current SLA status
    pub async fn get_status(&self) -> SLAStatus {
        let metrics = self.current_metrics.lock().await;

        let status = if metrics.uptime_percent < 99.0
            || metrics.data_loss_count > 0
            || metrics.p99_latency_us > 150
        {
            "red"
        } else if metrics.uptime_percent < 99.5
            || metrics.p99_latency_us > 100
            || metrics.error_rate_percent > 0.1
        {
            "yellow"
        } else {
            "green"
        };

        SLAStatus {
            status: status.to_string(),
            uptime_percent: metrics.uptime_percent,
            p99_latency_us: metrics.p99_latency_us,
            error_rate_percent: metrics.error_rate_percent,
            data_loss_count: metrics.data_loss_count,
            active_alerts: 0, // will be populated from DB query
        }
    }

    /// Get alert history (last N alerts)
    pub async fn get_alert_history(&self, limit: i64) -> Result<Vec<Alert>, sqlx::Error> {
        let rows = sqlx::query(
            "SELECT id, timestamp, severity, alert_type, message, acknowledged
             FROM alerts
             ORDER BY timestamp DESC
             LIMIT ?"
        )
        .bind(limit)
        .fetch_all(&self.db_pool)
        .await?;

        let alerts = rows
            .iter()
            .map(|row| {
                let timestamp: i64 = row.get("timestamp");
                let severity_str: String = row.get("severity");
                let severity = match severity_str.as_str() {
                    "critical" => AlertSeverity::Critical,
                    "warning" => AlertSeverity::Warning,
                    _ => AlertSeverity::Info,
                };

                Alert {
                    id: row.get("id"),
                    timestamp: DateTime::<Utc>::from_timestamp(timestamp, 0)
                        .unwrap_or_else(|| Utc::now()),
                    severity,
                    alert_type: row.get("alert_type"),
                    message: row.get("message"),
                    acknowledged: row.get("acknowledged"),
                }
            })
            .collect();

        Ok(alerts)
    }

    /// Acknowledge an alert
    pub async fn acknowledge_alert(&self, alert_id: &str) -> Result<(), sqlx::Error> {
        sqlx::query("UPDATE alerts SET acknowledged = 1 WHERE id = ?")
            .bind(alert_id)
            .execute(&self.db_pool)
            .await?;
        Ok(())
    }

    // Helper to create an alert
    fn create_alert(&self, severity: AlertSeverity, alert_type: String, message: String) -> Alert {
        Alert {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            severity,
            alert_type,
            message,
            acknowledged: false,
        }
    }

    // Helper to store alert in database
    async fn store_alert(&self, alert: &Alert) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO alerts (id, timestamp, severity, alert_type, message, acknowledged)
             VALUES (?, ?, ?, ?, ?, ?)"
        )
        .bind(&alert.id)
        .bind(alert.timestamp.timestamp())
        .bind(alert.severity.to_string())
        .bind(&alert.alert_type)
        .bind(&alert.message)
        .bind(alert.acknowledged)
        .execute(&self.db_pool)
        .await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_uptime_threshold_violation() {
        let monitor = SLAMonitor::new().await.unwrap();
        let snapshot = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 98.0, // Below 99.5 threshold
            p99_latency_us: 50,
            error_rate_percent: 0.0,
            data_loss_count: 0,
        };

        let alerts = monitor.record_metrics(snapshot).await.unwrap();
        assert!(!alerts.is_empty());
        assert_eq!(alerts[0].severity, AlertSeverity::Critical);
        assert!(alerts[0].alert_type.contains("uptime"));
    }

    #[tokio::test]
    async fn test_latency_threshold_violation() {
        let monitor = SLAMonitor::new().await.unwrap();
        let snapshot = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 99.9,
            p99_latency_us: 150, // Above 100µs threshold
            error_rate_percent: 0.0,
            data_loss_count: 0,
        };

        let alerts = monitor.record_metrics(snapshot).await.unwrap();
        assert!(!alerts.is_empty());
        assert_eq!(alerts[0].severity, AlertSeverity::Warning);
        assert!(alerts[0].alert_type.contains("latency"));
    }

    #[tokio::test]
    async fn test_error_rate_threshold_violation() {
        let monitor = SLAMonitor::new().await.unwrap();
        let snapshot = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 99.9,
            p99_latency_us: 50,
            error_rate_percent: 0.5, // Above 0.1% threshold
            data_loss_count: 0,
        };

        let alerts = monitor.record_metrics(snapshot).await.unwrap();
        assert!(!alerts.is_empty());
        assert!(alerts[0].alert_type.contains("error_rate"));
    }

    #[tokio::test]
    async fn test_data_loss_detection() {
        let monitor = SLAMonitor::new().await.unwrap();
        let snapshot = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 100.0,
            p99_latency_us: 50,
            error_rate_percent: 0.0,
            data_loss_count: 5, // Data loss detected
        };

        let alerts = monitor.record_metrics(snapshot).await.unwrap();
        assert!(!alerts.is_empty());
        assert_eq!(alerts[0].severity, AlertSeverity::Critical);
        assert!(alerts[0].alert_type.contains("data_loss"));
    }

    #[tokio::test]
    async fn test_no_alerts_on_healthy_metrics() {
        let monitor = SLAMonitor::new().await.unwrap();
        let snapshot = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 99.95,
            p99_latency_us: 47,
            error_rate_percent: 0.01,
            data_loss_count: 0,
        };

        let alerts = monitor.record_metrics(snapshot).await.unwrap();
        assert_eq!(alerts.len(), 0);
    }

    #[tokio::test]
    async fn test_alert_history_persistence() {
        let monitor = SLAMonitor::new().await.unwrap();

        // Create first alert
        let snapshot1 = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 98.0,
            p99_latency_us: 50,
            error_rate_percent: 0.0,
            data_loss_count: 0,
        };
        monitor.record_metrics(snapshot1).await.unwrap();

        // Create second alert
        let snapshot2 = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 99.9,
            p99_latency_us: 150,
            error_rate_percent: 0.0,
            data_loss_count: 0,
        };
        monitor.record_metrics(snapshot2).await.unwrap();

        // Retrieve history
        let history = monitor.get_alert_history(30).await.unwrap();
        assert_eq!(history.len(), 2);
    }

    #[tokio::test]
    async fn test_alert_acknowledgment() {
        let monitor = SLAMonitor::new().await.unwrap();

        let snapshot = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 98.0,
            p99_latency_us: 50,
            error_rate_percent: 0.0,
            data_loss_count: 0,
        };

        let alerts = monitor.record_metrics(snapshot).await.unwrap();
        assert!(!alerts.is_empty());

        let alert_id = &alerts[0].id;
        monitor.acknowledge_alert(alert_id).await.unwrap();

        let history = monitor.get_alert_history(30).await.unwrap();
        let acknowledged = history.iter().find(|a| a.id == *alert_id);
        assert!(acknowledged.is_some());
        assert!(acknowledged.unwrap().acknowledged);
    }

    #[tokio::test]
    async fn test_sla_status_green() {
        let monitor = SLAMonitor::new().await.unwrap();
        let snapshot = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 99.95,
            p99_latency_us: 47,
            error_rate_percent: 0.01,
            data_loss_count: 0,
        };

        monitor.record_metrics(snapshot).await.unwrap();
        let status = monitor.get_status().await;
        assert_eq!(status.status, "green");
    }

    #[tokio::test]
    async fn test_sla_status_yellow() {
        let monitor = SLAMonitor::new().await.unwrap();
        let snapshot = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 99.4, // Just below 99.5
            p99_latency_us: 47,
            error_rate_percent: 0.01,
            data_loss_count: 0,
        };

        monitor.record_metrics(snapshot).await.unwrap();
        let status = monitor.get_status().await;
        assert_eq!(status.status, "yellow");
    }

    #[tokio::test]
    async fn test_sla_status_red() {
        let monitor = SLAMonitor::new().await.unwrap();
        let snapshot = MetricSnapshot {
            timestamp: Utc::now(),
            uptime_percent: 98.0, // Well below threshold
            p99_latency_us: 47,
            error_rate_percent: 0.01,
            data_loss_count: 0,
        };

        monitor.record_metrics(snapshot).await.unwrap();
        let status = monitor.get_status().await;
        assert_eq!(status.status, "red");
    }
}
