/// Policy module: DAG-based policy composition with cycle detection.
///
/// Components:
/// - engine: PolicyEngine with three-phase evaluation
/// - cycles: CycleDetector using Tarjan's algorithm

pub mod engine;
pub mod cycles;

#[cfg(test)]
mod tests;

pub use engine::{PolicyEngine, PolicyComposer};
pub use cycles::{CycleDetector, Graph, Node};
