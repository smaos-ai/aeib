use crate::hazard::HazardLevel;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Failure Mode and Effects Analysis (FMEA) Record
/// ISO 26262 requires comprehensive FMEA analysis for ASIL-D systems
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FmeaRecord {
    pub id: Uuid,
    pub failure_mode: String,
    pub severity: HazardLevel,
    /// Occurrence probability (1-10 scale, 10 = highest)
    pub occurrence_probability: u8,
    /// Detection capability (1-10 scale, 10 = highest)
    pub detection_capability: u8,
    /// Risk Priority Number = severity × occurrence × detection
    pub risk_priority_number: u32,
}

impl FmeaRecord {
    /// Create a new FMEA record and calculate RPN
    pub fn new(
        failure_mode: String,
        severity: HazardLevel,
        occurrence: u8,
        detection: u8,
    ) -> Self {
        let rpn = (severity.as_numeric() as u32) * (occurrence as u32) * (detection as u32);

        Self {
            id: Uuid::new_v4(),
            failure_mode,
            severity,
            occurrence_probability: occurrence.min(10),
            detection_capability: detection.min(10),
            risk_priority_number: rpn,
        }
    }

    /// Check if this failure mode requires corrective action
    pub fn requires_action(&self) -> bool {
        self.risk_priority_number > 100 || self.severity >= HazardLevel::Major
    }

    /// Severity index (0-27 scale)
    pub fn severity_index(&self) -> u8 {
        (self.severity.as_numeric() as u32
            * self.occurrence_probability as u32
            * self.detection_capability as u32) as u8
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fmea_record_creation() {
        let record = FmeaRecord::new(
            "sensor_failure".to_string(),
            HazardLevel::Critical,
            3,
            2,
        );
        assert_eq!(record.failure_mode, "sensor_failure");
        assert_eq!(record.severity, HazardLevel::Critical);
        assert_eq!(record.risk_priority_number, 3 * 3 * 2);
    }

    #[test]
    fn test_fmea_requires_action() {
        let critical = FmeaRecord::new(
            "critical_fail".to_string(),
            HazardLevel::Critical,
            5,
            5,
        );
        assert!(critical.requires_action());

        let minor = FmeaRecord::new(
            "minor_fail".to_string(),
            HazardLevel::Minor,
            1,
            1,
        );
        assert!(!minor.requires_action());
    }
}
