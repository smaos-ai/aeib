use serde::{Deserialize, Serialize};

/// Safety hazard severity levels per ISO 26262
#[derive(Clone, Debug, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum HazardLevel {
    /// No impact on safety
    Negligible = 0,
    /// Minor impact; requires remediation
    Minor = 1,
    /// Major impact; dangerous situation
    Major = 2,
    /// Critical impact; loss of life or vehicle control
    Critical = 3,
}

impl HazardLevel {
    /// Convert to numeric severity (0-3)
    pub fn as_numeric(&self) -> u8 {
        *self as u8
    }

    /// Check if this hazard exceeds a threshold
    pub fn exceeds(&self, threshold: HazardLevel) -> bool {
        self > &threshold
    }

    /// Merge two hazards; return the worse one
    pub fn merge(&self, other: HazardLevel) -> HazardLevel {
        if self > &other {
            *self
        } else {
            other
        }
    }
}

/// Hazard record for FMEA analysis
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Hazard {
    pub id: uuid::Uuid,
    pub description: String,
    pub severity: HazardLevel,
    pub affected_systems: Vec<String>,
    pub detection_capability: f64,  // 1-10 scale
    pub can_remediate: bool,
}

impl Hazard {
    /// Create a new hazard
    pub fn new(description: String, severity: HazardLevel) -> Self {
        Self {
            id: uuid::Uuid::new_v4(),
            description,
            severity,
            affected_systems: Vec::new(),
            detection_capability: 5.0,
            can_remediate: true,
        }
    }

    /// Determine if hazard requires immediate halt
    pub fn requires_halt(&self) -> bool {
        self.severity == HazardLevel::Critical
    }

    /// Determine if hazard requires remediation
    pub fn requires_remediation(&self) -> bool {
        self.severity >= HazardLevel::Major
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hazard_level_ordering() {
        assert!(HazardLevel::Critical > HazardLevel::Major);
        assert!(HazardLevel::Major > HazardLevel::Minor);
        assert!(HazardLevel::Minor > HazardLevel::Negligible);
    }

    #[test]
    fn test_hazard_exceeds() {
        assert!(HazardLevel::Critical.exceeds(HazardLevel::Major));
        assert!(!HazardLevel::Minor.exceeds(HazardLevel::Major));
    }

    #[test]
    fn test_hazard_merge() {
        let h1 = HazardLevel::Major;
        let h2 = HazardLevel::Minor;
        assert_eq!(h1.merge(h2), HazardLevel::Major);
    }

    #[test]
    fn test_hazard_requires_halt() {
        let critical = Hazard::new("Test".to_string(), HazardLevel::Critical);
        assert!(critical.requires_halt());

        let major = Hazard::new("Test".to_string(), HazardLevel::Major);
        assert!(!major.requires_halt());
    }
}
