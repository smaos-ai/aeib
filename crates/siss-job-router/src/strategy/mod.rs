pub mod complexity;

use siss_graph_core::node::execution::{ComplexityClass, HardwareTarget};

/// Trait for deciding which hardware target to use for a given task complexity.
pub trait RoutingStrategy: Send + Sync {
    fn decide(&self, complexity: ComplexityClass) -> HardwareTarget;
}
