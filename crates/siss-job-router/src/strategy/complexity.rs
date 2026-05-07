use siss_graph_core::node::execution::{ComplexityClass, HardwareTarget};

use super::RoutingStrategy;

/// Routes tasks based purely on their complexity class.
/// Trivial/Simple/Moderate → LocalMlx
/// Complex → RemoteFrontier
/// Heavy → Hybrid
pub struct ComplexityBasedStrategy;

impl RoutingStrategy for ComplexityBasedStrategy {
    fn decide(&self, complexity: ComplexityClass) -> HardwareTarget {
        match complexity {
            ComplexityClass::Trivial => HardwareTarget::LocalMlx,
            ComplexityClass::Simple => HardwareTarget::LocalMlx,
            ComplexityClass::Moderate => HardwareTarget::LocalMlx,
            ComplexityClass::Complex => HardwareTarget::RemoteFrontier,
            ComplexityClass::Heavy => HardwareTarget::Hybrid,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trivial_routes_to_local_mlx() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Trivial), HardwareTarget::LocalMlx);
    }

    #[test]
    fn test_simple_routes_to_local_mlx() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Simple), HardwareTarget::LocalMlx);
    }

    #[test]
    fn test_moderate_routes_to_local_mlx() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Moderate), HardwareTarget::LocalMlx);
    }

    #[test]
    fn test_complex_routes_to_remote_frontier() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Complex), HardwareTarget::RemoteFrontier);
    }

    #[test]
    fn test_heavy_routes_to_hybrid() {
        let strategy = ComplexityBasedStrategy;
        assert_eq!(strategy.decide(ComplexityClass::Heavy), HardwareTarget::Hybrid);
    }
}
