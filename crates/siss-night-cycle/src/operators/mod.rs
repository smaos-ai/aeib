use serde::{Serialize, Deserialize};
use serde_json::Value;

pub mod phi;
pub mod phi_pruner;
pub mod delta;
pub mod gamma;

#[cfg(test)]
mod tests;

pub use phi::PhiOperator;
pub use phi_pruner::SafePruningPhiOperator;
pub use delta::DeltaOperator;
pub use gamma::GammaOperator;

/// OntologyEntity: core unit for night cycle operators
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OntologyEntity {
    pub id: String,
    pub timestamp: i64,
    pub confidence: f64,
    pub data: Value,
}

/// OntologyState: mutable state passed through operator chain
#[derive(Debug)]
pub struct OntologyState {
    pub entities: Vec<OntologyEntity>,
    pub confidence_threshold: f64,
}

/// OperatorResult: metrics from operator execution
#[derive(Debug, Clone)]
pub struct OperatorResult {
    pub entities_processed: usize,
    pub entities_changed: usize,
    pub operator_name: &'static str,
}

/// NightCycleOperator: trait for φ/δ/γ operators
pub trait NightCycleOperator {
    fn apply(&self, state: &mut OntologyState) -> OperatorResult;
}
