use crate::asil::AssilLevel;
use crate::errors::{SafetyError, SafetyResult};
use crate::hazard::HazardLevel;
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::SystemTime;

/// Sensor type for SOTIF validation
#[derive(Clone, Debug, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum SensorType {
    Lidar,
    Radar,
    Camera,
    Ultrasonic,
}

/// Health status of a sensor
#[derive(Clone, Debug, Copy, Serialize, Deserialize)]
pub struct SensorHealth {
    pub operational: bool,
    pub confidence: f64,  // 0-1
    pub last_reading: SystemTime,
}

/// SOTIF (Safety of the Intended Functionality) Validator
/// Ensures malfunctions do not create unreasonable hazards
#[derive(Clone)]
pub struct SotifValidator {
    asil_level: AssilLevel,
    sensor_health: Arc<DashMap<SensorType, SensorHealth>>,
}

impl SotifValidator {
    /// Create new SOTIF validator
    pub fn new(asil_level: AssilLevel) -> Self {
        Self {
            asil_level,
            sensor_health: Arc::new(DashMap::new()),
        }
    }

    /// Register or update sensor health
    pub fn register_sensor_health(&self, sensor: SensorType, confidence: f64) {
        self.sensor_health.insert(
            sensor,
            SensorHealth {
                operational: confidence > 0.5,
                confidence: confidence.clamp(0.0, 1.0),
                last_reading: SystemTime::now(),
            },
        );
    }

    /// Validate that malfunction severity does not exceed ASIL limit
    pub fn validate_malfunction_severity(
        &self,
        severity: HazardLevel,
    ) -> SafetyResult<()> {
        let max_allowed = self.asil_level.max_hazard_severity();

        if severity > max_allowed {
            return Err(SafetyError::SotifValidationFailed(format!(
                "Malfunction severity {:?} exceeds ASIL {:?} limit {:?}",
                severity, self.asil_level, max_allowed
            )));
        }

        Ok(())
    }

    /// Check overall sensor health
    pub fn check_sensor_health(&self) -> SafetyResult<()> {
        let total = self.sensor_health.len();
        if total == 0 {
            return Ok(());
        }

        let healthy = self
            .sensor_health
            .iter()
            .filter(|entry| entry.confidence > 0.6)
            .count();

        let health_ratio = healthy as f64 / total as f64;

        if health_ratio < 0.5 {
            return Err(SafetyError::SensorDegradation(format!(
                "Only {}/{} sensors operational",
                healthy, total
            )));
        }

        Ok(())
    }

    /// Detect if system is degraded (fewer than 2 sensors operational)
    pub fn is_system_degraded(&self) -> bool {
        let operational = self
            .sensor_health
            .iter()
            .filter(|entry| entry.confidence > 0.5)
            .count();

        operational < 2
    }

    /// Get health status of specific sensor
    pub fn sensor_health(&self, sensor: SensorType) -> Option<SensorHealth> {
        self.sensor_health.get(&sensor).map(|entry| *entry.value())
    }

    /// Validate entire request safety
    pub fn validate_request(&self, hazard: HazardLevel) -> SafetyResult<()> {
        self.validate_malfunction_severity(hazard)?;
        self.check_sensor_health()?;

        if self.is_system_degraded() && hazard >= HazardLevel::Major {
            return Err(SafetyError::SotifValidationFailed(
                "System degraded and hazard severity too high".to_string(),
            ));
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sotif_validates_safe_request() {
        let validator = SotifValidator::new(AssilLevel::D);
        let result = validator.validate_malfunction_severity(HazardLevel::Major);
        assert!(result.is_ok());
    }

    #[test]
    fn test_sotif_rejects_critical_for_asil_a() {
        let validator = SotifValidator::new(AssilLevel::A);
        let result = validator.validate_malfunction_severity(HazardLevel::Critical);
        assert!(result.is_err());
    }

    #[test]
    fn test_sotif_sensor_health_tracking() {
        let validator = SotifValidator::new(AssilLevel::D);
        validator.register_sensor_health(SensorType::Lidar, 0.95);
        assert_eq!(
            validator.sensor_health(SensorType::Lidar).unwrap().confidence,
            0.95
        );
    }

    #[test]
    fn test_sotif_degradation_detection() {
        let validator = SotifValidator::new(AssilLevel::D);
        validator.register_sensor_health(SensorType::Lidar, 0.3);
        validator.register_sensor_health(SensorType::Radar, 0.2);
        assert!(validator.is_system_degraded());
    }
}
