use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::SystemTime;
use uuid::Uuid;

#[derive(Clone, Debug, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum SensorType {
    Lidar,
    Radar,
    Camera,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SensorReading {
    pub id: Uuid,
    pub sensor_type: SensorType,
    pub object_id: String,
    pub distance_m: f64,
    pub confidence: f64,
    pub timestamp: SystemTime,
}

impl SensorReading {
    pub fn new(
        sensor_type: SensorType,
        object_id: &str,
        distance_m: f64,
        confidence: f64,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            sensor_type,
            object_id: object_id.to_string(),
            distance_m,
            confidence,
            timestamp: SystemTime::now(),
        }
    }
}

pub struct HallucinationDetector {
    pub expected_model: Arc<WorldModel>,
    pub observed_model: Arc<WorldModel>,
}

pub struct WorldModel {
    readings: Arc<DashMap<String, Vec<SensorReading>>>,
}

impl WorldModel {
    pub fn new() -> Self {
        Self {
            readings: Arc::new(DashMap::new()),
        }
    }

    pub fn add_reading(&self, reading: SensorReading) {
        let mut entries = self.readings.entry(reading.object_id.clone()).or_insert_with(Vec::new);
        entries.push(reading);
    }

    pub fn get_readings(&self, object_id: &str) -> Option<Vec<SensorReading>> {
        self.readings
            .get(object_id)
            .map(|entry| entry.clone())
    }

    pub fn clear(&self) {
        self.readings.clear();
    }
}

impl Default for WorldModel {
    fn default() -> Self {
        Self::new()
    }
}

pub struct WorldModelValidator {
    sensor_readings: Arc<DashMap<Uuid, SensorReading>>,
    #[allow(dead_code)]
    hallucination_detector: Arc<HallucinationDetector>,
    world_model: Arc<WorldModel>,
}

impl WorldModelValidator {
    pub fn new() -> Self {
        let detector = Arc::new(HallucinationDetector {
            expected_model: Arc::new(WorldModel::new()),
            observed_model: Arc::new(WorldModel::new()),
        });

        Self {
            sensor_readings: Arc::new(DashMap::new()),
            hallucination_detector: detector,
            world_model: Arc::new(WorldModel::new()),
        }
    }

    pub fn add_sensor_reading(&self, reading: SensorReading) {
        self.sensor_readings.insert(reading.id, reading.clone());
        self.world_model.add_reading(reading);
    }

    /// Cross-check lidar, radar, camera consistency, detect hallucinations
    pub async fn validate_sensor_fusion(&self) -> Result<SensorFusionProof, String> {
        // Collect all readings
        let mut readings_by_object: std::collections::HashMap<String, Vec<SensorReading>> =
            std::collections::HashMap::new();

        for entry in self.sensor_readings.iter() {
            let reading = entry.value().clone();
            readings_by_object
                .entry(reading.object_id.clone())
                .or_insert_with(Vec::new)
                .push(reading);
        }

        // Validate multi-sensor consensus
        for (object_id, readings) in readings_by_object.iter() {
            // Group by sensor type
            let mut by_sensor: std::collections::HashMap<SensorType, Vec<f64>> =
                std::collections::HashMap::new();

            for reading in readings {
                by_sensor
                    .entry(reading.sensor_type)
                    .or_insert_with(Vec::new)
                    .push(reading.distance_m);
            }

            // If we have readings from multiple sensors, check consistency
            if by_sensor.len() > 1 {
                let distances: Vec<f64> = readings
                    .iter()
                    .map(|r| r.distance_m)
                    .collect();

                if !distances.is_empty() {
                    let mean = distances.iter().sum::<f64>() / distances.len() as f64;
                    let std_dev = (distances
                        .iter()
                        .map(|d| (d - mean).powi(2))
                        .sum::<f64>()
                        / distances.len() as f64)
                        .sqrt();

                    // Reject if standard deviation > 1.0m (likely hallucination)
                    if std_dev > 1.0 {
                        return Err(format!(
                            "Sensor fusion inconsistency for {}: std_dev={:.2}m",
                            object_id, std_dev
                        ));
                    }
                }
            }
        }

        Ok(SensorFusionProof {
            valid: true,
            consensus_reached: true,
            reading_count: self.sensor_readings.len(),
        })
    }

    /// Detect world-model drift (e.g., object suddenly appears)
    pub async fn detect_world_model_drift(&self) -> Result<ModelDriftReport, String> {
        let mut report = ModelDriftReport {
            hallucination_detected: false,
            should_auto_halt: false,
            drift_magnitude: 0.0,
            sensor_confidence_degraded: false,
            objects_without_consensus: vec![],
        };

        // Check for sensor readings without consensus (hallucinations)
        let mut readings_by_object: std::collections::HashMap<String, Vec<SensorReading>> =
            std::collections::HashMap::new();

        for entry in self.sensor_readings.iter() {
            let reading = entry.value().clone();
            readings_by_object
                .entry(reading.object_id.clone())
                .or_insert_with(Vec::new)
                .push(reading);
        }

        for (object_id, readings) in readings_by_object.iter() {
            let sensor_types: std::collections::HashSet<SensorType> =
                readings.iter().map(|r| r.sensor_type).collect();

            // Single-sensor detections are potential hallucinations
            if sensor_types.len() == 1 {
                report.hallucination_detected = true;
                report.objects_without_consensus.push(object_id.clone());
            }

            // Check confidence degradation
            let avg_confidence = readings.iter().map(|r| r.confidence).sum::<f64>()
                / readings.len() as f64;
            if avg_confidence < 0.70 {
                report.sensor_confidence_degraded = true;
            }

            // Check for sudden distance changes (drift)
            if readings.len() >= 2 {
                let mut sorted = readings.clone();
                sorted.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));

                for i in 1..sorted.len() {
                    let prev = &sorted[i - 1];
                    let curr = &sorted[i];
                    let drift = (curr.distance_m - prev.distance_m).abs();

                    if drift > 5.0 {
                        report.drift_magnitude = drift;
                        report.should_auto_halt = true;
                    }
                }
            }
        }

        Ok(report)
    }

    /// Check if an object has readings from multiple sensor types
    pub async fn has_multi_sensor_consensus(&self, object_id: &str) -> bool {
        let mut sensor_types: std::collections::HashSet<SensorType> =
            std::collections::HashSet::new();

        for entry in self.sensor_readings.iter() {
            let reading = entry.value();
            if reading.object_id == object_id {
                sensor_types.insert(reading.sensor_type);
            }
        }

        sensor_types.len() > 1
    }

    pub fn clear_readings(&self) {
        self.sensor_readings.clear();
    }

    pub fn get_reading_count(&self) -> usize {
        self.sensor_readings.len()
    }
}

impl Default for WorldModelValidator {
    fn default() -> Self {
        Self::new()
    }
}

pub struct SensorFusionProof {
    pub valid: bool,
    pub consensus_reached: bool,
    pub reading_count: usize,
}

pub struct ModelDriftReport {
    pub hallucination_detected: bool,
    pub should_auto_halt: bool,
    pub drift_magnitude: f64,
    pub sensor_confidence_degraded: bool,
    pub objects_without_consensus: Vec<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_world_model_validator_creation() {
        let validator = WorldModelValidator::new();
        assert_eq!(validator.get_reading_count(), 0);
    }

    #[tokio::test]
    async fn test_add_sensor_reading() {
        let validator = WorldModelValidator::new();
        let reading = SensorReading::new(SensorType::Lidar, "car_001", 10.0, 0.95);

        validator.add_sensor_reading(reading);
        assert_eq!(validator.get_reading_count(), 1);
    }

    #[tokio::test]
    async fn test_multi_sensor_consensus() {
        let validator = WorldModelValidator::new();

        let lidar = SensorReading::new(SensorType::Lidar, "car_001", 10.0, 0.95);
        let radar = SensorReading::new(SensorType::Radar, "car_001", 10.1, 0.90);

        validator.add_sensor_reading(lidar);
        validator.add_sensor_reading(radar);

        assert!(validator.has_multi_sensor_consensus("car_001").await);
    }

    #[tokio::test]
    async fn test_detect_hallucination_single_sensor() {
        let validator = WorldModelValidator::new();
        let reading = SensorReading::new(SensorType::Camera, "ghost_car", 5.0, 0.50);

        validator.add_sensor_reading(reading);

        let report = validator.detect_world_model_drift().await.unwrap();
        assert!(report.hallucination_detected);
        assert!(report.objects_without_consensus.contains(&"ghost_car".to_string()));
    }

    #[tokio::test]
    async fn test_sensor_fusion_valid() {
        let validator = WorldModelValidator::new();

        let lidar = SensorReading::new(SensorType::Lidar, "car_001", 10.0, 0.95);
        let radar = SensorReading::new(SensorType::Radar, "car_001", 10.1, 0.90);
        let camera = SensorReading::new(SensorType::Camera, "car_001", 9.9, 0.85);

        validator.add_sensor_reading(lidar);
        validator.add_sensor_reading(radar);
        validator.add_sensor_reading(camera);

        let proof = validator.validate_sensor_fusion().await.unwrap();
        assert!(proof.valid);
        assert!(proof.consensus_reached);
    }

    #[tokio::test]
    async fn test_confidence_degradation_detection() {
        let validator = WorldModelValidator::new();

        let reading1 = SensorReading::new(SensorType::Lidar, "car_001", 10.0, 0.40); // Low confidence
        let reading2 = SensorReading::new(SensorType::Radar, "car_001", 10.1, 0.30); // Low confidence

        validator.add_sensor_reading(reading1);
        validator.add_sensor_reading(reading2);

        let report = validator.detect_world_model_drift().await.unwrap();
        assert!(report.sensor_confidence_degraded);
    }

    #[test]
    fn test_sensor_reading_creation() {
        let reading = SensorReading::new(SensorType::Lidar, "car_001", 10.5, 0.95);
        assert_eq!(reading.sensor_type, SensorType::Lidar);
        assert_eq!(reading.object_id, "car_001");
        assert_eq!(reading.distance_m, 10.5);
        assert_eq!(reading.confidence, 0.95);
    }

    #[test]
    fn test_world_model_add_reading() {
        let model = WorldModel::new();
        let reading = SensorReading::new(SensorType::Lidar, "car_001", 10.0, 0.95);

        model.add_reading(reading.clone());

        let readings = model.get_readings("car_001").unwrap();
        assert_eq!(readings.len(), 1);
        assert_eq!(readings[0].object_id, "car_001");
    }
}
