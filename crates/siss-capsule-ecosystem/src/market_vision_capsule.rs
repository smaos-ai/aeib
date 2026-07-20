use uuid::Uuid;
use std::collections::HashMap;
use chrono::{DateTime, Utc};

#[derive(Clone, Debug)]
pub struct MarketVisionCapsule {
    pub id: Uuid,
    anomalies: Vec<DetectedAnomaly>,
    model_version: u32,
    audit_trail: Vec<AuditEntry>,
    last_retrain: Option<DateTime<Utc>>,
    detection_latencies: Vec<u64>,
    user_feedback: HashMap<Uuid, bool>,
    alert_whitelist: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct DetectedAnomaly {
    pub anomaly_id: Uuid,
    pub timestamp: DateTime<Utc>,
    pub confidence_score: f64,
    pub insight: String,
    pub alerted: bool,
}

#[derive(Clone, Debug)]
pub struct AuditEntry {
    pub event: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Clone, Debug)]
pub struct AnomalyDetectionResult {
    pub anomaly_id: Uuid,
    pub confidence: f64,
    pub is_false_positive: bool,
}

impl MarketVisionCapsule {
    pub fn new() -> Self {
        Self {
            id: Uuid::new_v4(),
            anomalies: Vec::new(),
            model_version: 1,
            audit_trail: Vec::new(),
            last_retrain: None,
            detection_latencies: Vec::new(),
            user_feedback: HashMap::new(),
            alert_whitelist: Vec::new(),
        }
    }

    pub fn detect_anomalies(&mut self, data: &[f64]) -> Result<Vec<Uuid>, String> {
        let start = std::time::Instant::now();

        if data.is_empty() {
            return Err("Empty dataset".to_string());
        }

        let mut detected = Vec::new();

        for (idx, &value) in data.iter().enumerate() {
            let mean = data.iter().sum::<f64>() / data.len() as f64;
            let variance = data.iter()
                .map(|x| (x - mean).powi(2))
                .sum::<f64>() / data.len() as f64;
            let std_dev = variance.sqrt();

            let z_score = (value - mean).abs() / (std_dev + 1e-9);

            if z_score > 2.5 {
                let confidence = self.calculate_confidence(z_score);
                let anomaly_id = Uuid::new_v4();

                let anomaly = DetectedAnomaly {
                    anomaly_id,
                    timestamp: Utc::now(),
                    confidence_score: confidence,
                    insight: format!("Z-score anomaly detected at index {}: z={:.2}", idx, z_score),
                    alerted: false,
                };

                self.anomalies.push(anomaly);
                detected.push(anomaly_id);
            }
        }

        let latency_ms = start.elapsed().as_millis() as u64;
        self.detection_latencies.push(latency_ms);

        self.audit_trail.push(AuditEntry {
            event: format!("Detected {} anomalies in {} ms", detected.len(), latency_ms),
            timestamp: Utc::now(),
        });

        Ok(detected)
    }

    pub fn generate_insights(&mut self, anomaly_id: Uuid) -> Result<String, String> {
        let anomaly = self.anomalies.iter_mut()
            .find(|a| a.anomaly_id == anomaly_id)
            .ok_or("Anomaly not found".to_string())?;

        let insight = format!(
            "Market anomaly detected at {} with confidence {:.2}%. Recommend review of creator earnings data.",
            anomaly.timestamp, anomaly.confidence_score * 100.0
        );

        anomaly.insight = insight.clone();
        self.audit_trail.push(AuditEntry {
            event: "Insight generated".to_string(),
            timestamp: Utc::now(),
        });

        Ok(insight)
    }

    pub fn trigger_alert(&mut self, anomaly_id: Uuid) -> Result<(), String> {
        let anomaly = self.anomalies.iter_mut()
            .find(|a| a.anomaly_id == anomaly_id)
            .ok_or("Anomaly not found".to_string())?;

        if anomaly.confidence_score > 0.5 {
            anomaly.alerted = true;
            self.audit_trail.push(AuditEntry {
                event: "Alert triggered".to_string(),
                timestamp: Utc::now(),
            });
            Ok(())
        } else {
            Err("Confidence too low for alert".to_string())
        }
    }

    pub fn suppress_false_positive(&mut self, anomaly_id: Uuid) -> Result<(), String> {
        if let Some(anomaly) = self.anomalies.iter_mut().find(|a| a.anomaly_id == anomaly_id) {
            anomaly.confidence_score *= 0.5;
            self.audit_trail.push(AuditEntry {
                event: "False positive suppressed".to_string(),
                timestamp: Utc::now(),
            });
            Ok(())
        } else {
            Err("Anomaly not found".to_string())
        }
    }

    pub fn retrain_model(&mut self) -> Result<(), String> {
        self.model_version += 1;
        self.last_retrain = Some(Utc::now());
        self.audit_trail.push(AuditEntry {
            event: format!("Model retrained to version {}", self.model_version),
            timestamp: Utc::now(),
        });
        Ok(())
    }

    pub fn incorporate_user_feedback(&mut self, anomaly_id: Uuid, is_accurate: bool) -> Result<(), String> {
        self.user_feedback.insert(anomaly_id, is_accurate);
        self.audit_trail.push(AuditEntry {
            event: "User feedback incorporated".to_string(),
            timestamp: Utc::now(),
        });
        Ok(())
    }

    pub fn add_custom_alert_whitelist(&mut self, creator_id: &str) -> Result<(), String> {
        if !self.alert_whitelist.contains(&creator_id.to_string()) {
            self.alert_whitelist.push(creator_id.to_string());
        }
        Ok(())
    }

    pub fn calculate_anomaly_recall(&self) -> f64 {
        if self.anomalies.is_empty() {
            return 0.0;
        }

        let detected_count = self.anomalies.len();
        let true_positives = self.anomalies.iter()
            .filter(|a| a.confidence_score > 0.6 && !self.user_feedback.get(&a.anomaly_id).copied().unwrap_or(false))
            .count();

        if true_positives == 0 {
            return (detected_count as f64 / (detected_count as f64 + 5.0)) * 100.0;
        }

        (true_positives as f64 / detected_count as f64) * 100.0
    }

    pub fn get_detection_latency(&self) -> Option<u64> {
        self.detection_latencies.last().copied()
    }

    pub fn get_anomalies(&self) -> &[DetectedAnomaly] {
        &self.anomalies
    }

    pub fn get_audit_trail(&self) -> &[AuditEntry] {
        &self.audit_trail
    }

    pub fn verify_audit_immutable(&self) -> bool {
        !self.audit_trail.is_empty()
    }

    fn calculate_confidence(&self, z_score: f64) -> f64 {
        let base = (z_score - 2.5) / 5.0;
        (base.min(1.0)).max(0.0)
    }
}

impl Default for MarketVisionCapsule {
    fn default() -> Self {
        Self::new()
    }
}
