use crate::errors::{SafetyError, SafetyResult};
use crate::hazard::HazardLevel;
use crate::fmea::FmeaRecord;
use serde::{Deserialize, Serialize};
use std::time::Duration;

/// ISO 26262 ASIL Levels (A: lowest, D: highest safety integrity)
#[derive(Clone, Debug, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum AssilLevel {
    A,
    B,
    C,
    D,
}

impl AssilLevel {
    /// Get MTBF (Mean Time Between Failures) target in hours
    pub fn mtbf(&self) -> Duration {
        match self {
            AssilLevel::A => Duration::from_secs(10_000 * 3600),
            AssilLevel::B => Duration::from_secs(100_000 * 3600),
            AssilLevel::C => Duration::from_secs(500_000 * 3600),
            AssilLevel::D => Duration::from_secs(1_000_000 * 3600),
        }
    }

    /// Get maximum allowed hazard severity for this ASIL level
    pub fn max_hazard_severity(&self) -> HazardLevel {
        match self {
            AssilLevel::A => HazardLevel::Minor,
            AssilLevel::B => HazardLevel::Major,
            AssilLevel::C => HazardLevel::Major,
            AssilLevel::D => HazardLevel::Critical,
        }
    }

    /// Get required verification rigor (higher = more thorough)
    pub fn verification_rigor(&self) -> u8 {
        match self {
            AssilLevel::A => 1,
            AssilLevel::B => 2,
            AssilLevel::C => 3,
            AssilLevel::D => 4,
        }
    }
}

/// Validator for ISO 26262 ASIL-D compliance
#[derive(Clone, Debug)]
pub struct AssilValidator {
    level: AssilLevel,
    fmea_records: Vec<FmeaRecord>,
}

impl AssilValidator {
    /// Create a new ASIL validator
    pub fn new(level: AssilLevel) -> Self {
        Self {
            level,
            fmea_records: Vec::new(),
        }
    }

    /// Get the ASIL level
    pub fn level(&self) -> AssilLevel {
        self.level
    }

    /// Add FMEA record and validate against ASIL threshold
    pub fn add_fmea_record(&mut self, record: FmeaRecord) -> SafetyResult<()> {
        let max_severity = self.level.max_hazard_severity();

        if record.severity > max_severity {
            return Err(SafetyError::HazardExceedsThreshold(format!(
                "FMEA record severity {:?} exceeds ASIL {:?} limit {:?}",
                record.severity, self.level, max_severity
            )));
        }

        self.fmea_records.push(record);
        Ok(())
    }

    /// Validate that all recorded hazards are within ASIL limits
    pub fn validate_all_hazards(&self) -> SafetyResult<()> {
        let max_severity = self.level.max_hazard_severity();

        for record in &self.fmea_records {
            if record.severity > max_severity {
                return Err(SafetyError::AssilViolation(format!(
                    "Hazard {:?} exceeds ASIL {:?} limit",
                    record.id, self.level
                )));
            }
        }

        Ok(())
    }

    /// Get failure modes at critical severity
    pub fn critical_failure_modes(&self) -> Vec<FmeaRecord> {
        self.fmea_records
            .iter()
            .filter(|r| r.severity == HazardLevel::Critical)
            .cloned()
            .collect()
    }

    /// Get total FMEA records count
    pub fn fmea_count(&self) -> usize {
        self.fmea_records.len()
    }

    /// Downgrade ASIL level if hazards exceed current level
    pub fn auto_downgrade_if_needed(&mut self) -> AssilLevel {
        let max_severity = self
            .fmea_records
            .iter()
            .map(|r| r.severity)
            .max()
            .unwrap_or(HazardLevel::Negligible);

        if max_severity > self.level.max_hazard_severity() {
            // Find appropriate ASIL level for this hazard
            let new_level = match max_severity {
                HazardLevel::Minor => AssilLevel::A,
                HazardLevel::Major => AssilLevel::B,
                HazardLevel::Critical => AssilLevel::D,
                HazardLevel::Negligible => AssilLevel::A,
            };
            self.level = new_level;
        }

        self.level
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_asil_a_mtbf() {
        assert_eq!(AssilLevel::A.mtbf(), Duration::from_secs(10_000 * 3600));
    }

    #[test]
    fn test_asil_d_mtbf() {
        assert_eq!(
            AssilLevel::D.mtbf(),
            Duration::from_secs(1_000_000 * 3600)
        );
    }

    #[test]
    fn test_asil_d_max_hazard() {
        assert_eq!(
            AssilLevel::D.max_hazard_severity(),
            HazardLevel::Critical
        );
    }

    #[test]
    fn test_asil_a_max_hazard() {
        assert_eq!(AssilLevel::A.max_hazard_severity(), HazardLevel::Minor);
    }
}
