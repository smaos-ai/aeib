use std::collections::HashMap;
use uuid::Uuid;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RiskWeightClass {
    Sovereign,
    Corporate,
    Retail,
    Equity,
    Operational,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StressTestRecord {
    pub scenario_name: String,
    pub capital_ratio_under_stress: f64,
    pub merkle_proof: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BiasDetectionRecord {
    pub protected_attributes: Vec<String>,
    pub disparity_ratios: HashMap<String, f64>,
    pub passed: bool,
}

pub struct TreasuryCapsule {
    capsule_id: Uuid,
    capital_requirement_basis: u64,
    capital_held: u64,
    stress_test_records: Vec<StressTestRecord>,
    bias_detection_results: Vec<BiasDetectionRecord>,
    merkle_root: String,
}

impl TreasuryCapsule {
    pub fn new() -> Self {
        Self {
            capsule_id: Uuid::new_v4(),
            capital_requirement_basis: 0,
            capital_held: 0,
            stress_test_records: vec![],
            bias_detection_results: vec![],
            merkle_root: String::new(),
        }
    }

    pub fn calculate_capital_requirement(&self) -> f64 {
        self.capital_requirement_basis as f64 * 0.08
    }

    pub fn meets_capital_requirement(&self) -> bool {
        self.capital_held as f64 >= self.calculate_capital_requirement()
    }

    pub fn add_stress_test(&mut self, scenario: String, outcome: f64) {
        self.stress_test_records.push(StressTestRecord {
            scenario_name: scenario,
            capital_ratio_under_stress: outcome,
            merkle_proof: String::new(),
        });
    }

    pub fn detect_proxy_bias(&mut self, protected_attrs: Vec<String>) -> BiasDetectionRecord {
        const SIMULATED_DISPARITY: f64 = 0.15;
        const BIAS_THRESHOLD: f64 = 0.10;

        let mut disparity_ratios = HashMap::new();
        for attr in &protected_attrs {
            disparity_ratios.insert(attr.clone(), SIMULATED_DISPARITY);
        }

        let passed = disparity_ratios
            .values()
            .all(|&ratio| ratio <= BIAS_THRESHOLD);

        let record = BiasDetectionRecord {
            protected_attributes: protected_attrs,
            disparity_ratios,
            passed,
        };
        self.bias_detection_results.push(record.clone());
        record
    }

    pub fn is_ready_for_execution(&self) -> Result<(), String> {
        if !self.meets_capital_requirement() {
            return Err(format!(
                "Capital requirement not met: held={}, required={:.0}",
                self.capital_held,
                self.calculate_capital_requirement()
            ));
        }

        if self.merkle_root.is_empty() {
            return Err("Merkle root not set".to_string());
        }

        Ok(())
    }

    pub fn set_capital(&mut self, basis: u64, held: u64) {
        self.capital_requirement_basis = basis;
        self.capital_held = held;
    }

    pub fn set_merkle_root(&mut self, root: String) {
        self.merkle_root = root;
    }
}

impl Default for TreasuryCapsule {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_capital_requirement_calc() {
        let mut capsule = TreasuryCapsule::new();
        capsule.set_capital(1_000_000_000, 80_000_000);
        let req = capsule.calculate_capital_requirement();
        assert!((req - 80_000_000.0).abs() < f64::EPSILON);
    }

    #[test]
    fn test_capital_below_minimum() {
        let mut capsule = TreasuryCapsule::new();
        capsule.set_capital(1_000_000_000, 50_000_000);
        assert!(!capsule.meets_capital_requirement());
    }

    #[test]
    fn test_stress_test_recording() {
        let mut capsule = TreasuryCapsule::new();
        assert_eq!(capsule.stress_test_records.len(), 0);
        capsule.add_stress_test("2008-crash".to_string(), 0.062);
        assert_eq!(capsule.stress_test_records.len(), 1);
    }

    #[test]
    fn test_bias_detection_triggers_on_disparity() {
        let mut capsule = TreasuryCapsule::new();
        let record = capsule.detect_proxy_bias(vec!["race".to_string(), "gender".to_string()]);
        assert!(!record.passed);
    }

    #[test]
    fn test_ready_requires_capital() {
        let mut capsule = TreasuryCapsule::new();
        capsule.set_capital(1_000_000_000, 50_000_000);
        assert!(capsule.is_ready_for_execution().is_err());
    }
}
