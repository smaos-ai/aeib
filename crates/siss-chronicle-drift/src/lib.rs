//! # SISS Chronicle Drift
//! Rolling 100-decision window with RAGAS-based drift scoring.
//! Detects anomalies in agent decision quality using sliding window analysis.
//!
//! Integration point for Phase 1 L7 (RAGAS baseline) - marked for Jun 2027.

pub mod decision;
pub mod drift;
pub mod scorer;
pub mod error;

pub use decision::Decision;
pub use drift::DriftMonitor;
pub use scorer::RAGASScorer;
pub use error::{DriftError, Result};

#[cfg(test)]
mod tests;

/// Drift level
#[derive(Clone, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum DriftLevel {
    Green,
    Yellow,
    Orange,
    Red,
}

impl std::fmt::Display for DriftLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DriftLevel::Green => write!(f, "GREEN"),
            DriftLevel::Yellow => write!(f, "YELLOW"),
            DriftLevel::Orange => write!(f, "ORANGE"),
            DriftLevel::Red => write!(f, "RED"),
        }
    }
}

/// Drift monitor configuration
#[derive(Clone, Debug)]
pub struct DriftConfig {
    /// Rolling window size
    pub window_size: u32,
    /// Green threshold (quality score)
    pub green_threshold: f64,
    /// Yellow threshold
    pub yellow_threshold: f64,
    /// Orange threshold
    pub orange_threshold: f64,
}

impl Default for DriftConfig {
    fn default() -> Self {
        Self {
            window_size: 100,
            green_threshold: 0.85,
            yellow_threshold: 0.75,
            orange_threshold: 0.65,
        }
    }
}

impl DriftConfig {
    /// Create new drift config
    pub fn new(window_size: u32) -> Result<Self> {
        if window_size == 0 {
            return Err(DriftError::InvalidConfig("window size must be > 0".into()));
        }
        Ok(Self {
            window_size,
            ..Default::default()
        })
    }

    /// Classify score to drift level
    pub fn classify(&self, score: f64) -> DriftLevel {
        if score >= self.green_threshold {
            DriftLevel::Green
        } else if score >= self.yellow_threshold {
            DriftLevel::Yellow
        } else if score >= self.orange_threshold {
            DriftLevel::Orange
        } else {
            DriftLevel::Red
        }
    }
}

#[cfg(test)]
mod config_tests {
    use super::*;

    #[test]
    fn test_drift_config_validation() {
        assert!(DriftConfig::new(0).is_err());
        assert!(DriftConfig::new(100).is_ok());
    }

    #[test]
    fn test_drift_level_classification() {
        let config = DriftConfig::default();
        assert_eq!(config.classify(0.9), DriftLevel::Green);
        assert_eq!(config.classify(0.8), DriftLevel::Yellow);
        assert_eq!(config.classify(0.7), DriftLevel::Orange);
        assert_eq!(config.classify(0.5), DriftLevel::Red);
    }
}
