pub mod cycles;
/// Policy module: DAG-based policy composition with cycle detection.
///
/// Components:
/// - engine: PolicyEngine with three-phase evaluation
/// - cycles: CycleDetector using Tarjan's algorithm
pub mod engine;

#[cfg(test)]
mod tests;

pub use cycles::{CycleDetector, Graph, Node};
pub use engine::{PolicyComposer, PolicyEngine};
