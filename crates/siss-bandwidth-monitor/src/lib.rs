use uuid::Uuid;
use serde::{Serialize, Deserialize};
use std::time::SystemTime;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BandwidthSummary {
    pub agent_id: Uuid,
    pub sampling_window_secs: u32,
    pub bytes_sent: u64,
    pub bytes_received: u64,
    pub packets_sent: u32,
    pub packets_received: u32,
    pub connection_attempts_blocked: u32,
    pub anomaly_score: f64,
    pub timestamp: SystemTime,
    pub is_anomalous: bool,
    pub anomaly_reason: Option<String>,
}

pub struct BandwidthMonitor {
    anomaly_threshold: f64,
    egress_allowed: bool,
}

impl BandwidthMonitor {
    pub fn new(anomaly_threshold: f64, egress_allowed: bool) -> Self {
        BandwidthMonitor {
            anomaly_threshold,
            egress_allowed,
        }
    }

    pub fn analyze_bandwidth(
        &self,
        agent_id: Uuid,
        bytes_sent: u64,
        bytes_received: u64,
        packets_sent: u32,
        packets_received: u32,
        connection_attempts_blocked: u32,
    ) -> BandwidthSummary {
        let (anomaly_score, is_anomalous, anomaly_reason) =
            self.compute_anomaly_score(bytes_sent, connection_attempts_blocked);

        BandwidthSummary {
            agent_id,
            sampling_window_secs: 60,
            bytes_sent,
            bytes_received,
            packets_sent,
            packets_received,
            connection_attempts_blocked,
            anomaly_score,
            timestamp: SystemTime::now(),
            is_anomalous,
            anomaly_reason,
        }
    }

    fn compute_anomaly_score(
        &self,
        bytes_sent: u64,
        connection_attempts: u32,
    ) -> (f64, bool, Option<String>) {
        let mut score = 0.0;
        let mut reason = None;

        // Unexpected egress anomaly
        if !self.egress_allowed && bytes_sent > 0 {
            score += 0.9;
            reason = Some("Unexpected egress traffic detected".to_string());
        }

        // Connection attempt anomaly
        if connection_attempts > 0 {
            score += 0.7;
            if reason.is_none() {
                reason = Some(
                    format!(
                        "{} unauthorized connection attempts blocked",
                        connection_attempts
                    )
                );
            }
        }

        let is_anomalous = score > self.anomaly_threshold;

        (score, is_anomalous, if is_anomalous { reason } else { None })
    }

    pub fn is_critical_alert(&self, summary: &BandwidthSummary) -> bool {
        summary.is_anomalous && summary.anomaly_score > 0.8
    }

    pub fn trigger_alert(&self, summary: &BandwidthSummary) -> Result<String, String> {
        if self.is_critical_alert(summary) {
            Ok(format!(
                "CRITICAL: Agent {} anomaly_score {:.2}%: {}",
                summary.agent_id,
                summary.anomaly_score * 100.0,
                summary.anomaly_reason.as_ref().unwrap_or(&"Unknown".to_string())
            ))
        } else {
            Err("Alert threshold not met".to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sovereign(id: u64) -> Uuid {
        Uuid::from_u64_pair(id, 0)
    }

    #[test]
    fn test_bandwidth_summary_normal_traffic() {
        let monitor = BandwidthMonitor::new(0.5, false);
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            0,           // bytes_sent (no egress)
            4096,        // bytes_received (ingress only)
            0,           // packets_sent
            8,           // packets_received
            0,           // connection_attempts_blocked
        );

        assert!(!summary.is_anomalous);
        assert_eq!(summary.bytes_sent, 0);
        assert_eq!(summary.bytes_received, 4096);
    }

    #[test]
    fn test_bandwidth_unexpected_egress_anomaly() {
        let monitor = BandwidthMonitor::new(0.5, false); // egress not allowed
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            1024,        // bytes_sent (UNEXPECTED!)
            4096,        // bytes_received
            1,           // packets_sent
            8,           // packets_received
            0,           // connection_attempts_blocked
        );

        assert!(summary.is_anomalous, "Unexpected egress should trigger anomaly");
        assert!(summary.anomaly_score > 0.5);
        assert!(summary.anomaly_reason.is_some());
    }

    #[test]
    fn test_bandwidth_connection_attempt_blocked() {
        let monitor = BandwidthMonitor::new(0.5, true); // egress allowed
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            0,           // bytes_sent
            4096,        // bytes_received
            0,           // packets_sent
            8,           // packets_received
            3,           // connection_attempts_blocked (ANOMALY)
        );

        assert!(summary.is_anomalous, "Connection attempts should trigger anomaly");
        assert!(summary.connection_attempts_blocked == 3);
    }

    #[test]
    fn test_bandwidth_critical_alert_threshold() {
        let monitor = BandwidthMonitor::new(0.5, false);
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            5120,        // Significant unexpected egress
            4096,
            2,
            8,
            0,
        );

        let is_critical = monitor.is_critical_alert(&summary);
        assert!(is_critical, "High anomaly score should be critical");
    }

    #[test]
    fn test_bandwidth_alert_emission() {
        let monitor = BandwidthMonitor::new(0.5, false);
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            2048,        // Unexpected egress
            4096,
            1,
            8,
            0,
        );

        let alert = monitor.trigger_alert(&summary);
        assert!(alert.is_ok());
        let alert_msg = alert.unwrap();
        assert!(alert_msg.contains("CRITICAL"));
        assert!(alert_msg.contains(&agent_id.to_string()));
    }

    #[test]
    fn test_bandwidth_no_alert_threshold_not_met() {
        let monitor = BandwidthMonitor::new(0.95, false);
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            512,         // Small unexpected egress
            4096,
            0,
            8,
            0,
        );

        let alert = monitor.trigger_alert(&summary);
        assert!(alert.is_err(), "Low anomaly score should not trigger alert");
    }

    #[test]
    fn test_bandwidth_multiple_anomalies_cumulative() {
        let monitor = BandwidthMonitor::new(0.5, false);
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            1024,        // Unexpected egress
            4096,
            1,
            8,
            2,           // Multiple connection attempts
        );

        assert!(summary.is_anomalous);
        assert!(summary.anomaly_score > 0.7, "Multiple anomalies should compound");
    }

    #[test]
    fn test_bandwidth_summary_serialization() {
        let monitor = BandwidthMonitor::new(0.5, false);
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            0,
            4096,
            0,
            8,
            0,
        );

        let json = serde_json::to_string(&summary).expect("Serialization failed");
        assert!(json.contains("\"bytes_received\":4096"));
        assert!(json.contains("\"anomaly_score\""));
        assert!(json.contains("\"is_anomalous\":false"));
    }

    #[test]
    fn test_bandwidth_egress_allowed_mode() {
        let monitor = BandwidthMonitor::new(0.5, true); // egress IS allowed
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            1024,        // egress is normal now
            4096,
            1,
            8,
            0,
        );

        assert!(!summary.is_anomalous, "Egress allowed should not trigger anomaly");
    }

    #[test]
    fn test_bandwidth_zero_traffic() {
        let monitor = BandwidthMonitor::new(0.5, false);
        let agent_id = sovereign(1);

        let summary = monitor.analyze_bandwidth(
            agent_id,
            0, 0, 0, 0, 0,
        );

        assert!(!summary.is_anomalous);
        assert_eq!(summary.anomaly_score, 0.0);
    }

    #[test]
    fn test_bandwidth_sampling_window_constant() {
        let monitor = BandwidthMonitor::new(0.5, false);

        let summary = monitor.analyze_bandwidth(
            sovereign(1),
            0, 4096, 0, 8, 0,
        );

        assert_eq!(summary.sampling_window_secs, 60);
    }

    #[test]
    fn test_bandwidth_anomaly_reason_message() {
        let monitor = BandwidthMonitor::new(0.5, false);

        let summary = monitor.analyze_bandwidth(
            sovereign(1),
            2048,        // Unexpected egress
            4096,
            1,
            8,
            5,           // Multiple blocked attempts
        );

        assert!(summary.anomaly_reason.is_some());
        let reason = summary.anomaly_reason.unwrap();
        assert!(!reason.is_empty());
    }
}
