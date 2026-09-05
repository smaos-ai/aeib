use std::collections::HashMap;

/// Evidence for a single HIPAA Security Rule control
#[derive(Debug, Clone)]
pub struct HipaaControlEvidence {
    /// Section reference (e.g., "§164.312(a)(1)")
    pub section_ref: String,
    /// Implementation note
    pub implementation_ref: String,
}

/// Maps HIPAA Security Rule required implementation specifications.
/// 18 required safeguards per the Security Rule.
pub struct HipaaSecurityMapper {
    controls: HashMap<String, HipaaControlEvidence>,
}

impl HipaaSecurityMapper {
    /// Creates an empty mapper
    pub fn new() -> Self {
        Self {
            controls: HashMap::new(),
        }
    }

    /// Total number of HIPAA Security Rule required controls (18)
    pub fn required_controls() -> usize {
        18
    }

    /// Inserts or updates a control evidence record
    pub fn insert(&mut self, control_id: impl Into<String>, evidence: HipaaControlEvidence) {
        self.controls.insert(control_id.into(), evidence);
    }

    /// Returns fraction of the 18 required controls implemented (0.0 – 1.0)
    pub fn score(&self) -> f64 {
        let implemented = self.controls.len().min(Self::required_controls()) as f64;
        implemented / Self::required_controls() as f64
    }

    /// Returns the number of mapped controls
    pub fn len(&self) -> usize {
        self.controls.len()
    }

    /// Returns true if no controls are mapped
    pub fn is_empty(&self) -> bool {
        self.controls.is_empty()
    }
}

impl Default for HipaaSecurityMapper {
    fn default() -> Self {
        Self::new()
    }
}
