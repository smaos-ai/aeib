pub mod registry;
pub mod router;

pub use registry::{RegistryError, SkillRegistry};
pub use router::{McpRouter, RouteDecision};

#[cfg(test)]
mod tests {
    use crate::registry::{RegistryError, SkillRegistry};
    use crate::router::{McpRouter, RouteDecision, RoutingRequest};

    #[test]
    fn test_unknown_tool_name_returns_not_found() {
        let registry = SkillRegistry::new();
        let result = registry.get_skill("nonexistent");
        assert!(matches!(result, Err(RegistryError::SkillNotFound(_))));
    }

    #[test]
    fn test_sigma_selection_defers_low_confidence_schema() {
        let router = McpRouter::new("test-router".to_string());
        let request = RoutingRequest {
            tool_name: "some_tool".to_string(),
            schema: serde_json::json!({}),
            confidence: 0.2,
        };
        let response = router.route(&request);
        assert_eq!(response.decision, RouteDecision::Defer);
    }

    #[test]
    fn test_skill_registry_loads_and_routes_valid_skill() {
        let mut registry = SkillRegistry::new();
        registry
            .register_skill("test_skill".to_string(), "1.0.0".to_string())
            .unwrap();

        let result = registry.get_skill("test_skill");
        assert!(result.is_ok());
        assert_eq!(result.unwrap().name, "test_skill");

        let router = McpRouter::new("test-router".to_string());
        let request = RoutingRequest {
            tool_name: "test_skill".to_string(),
            schema: serde_json::json!({}),
            confidence: 0.9,
        };
        let response = router.route(&request);
        assert_eq!(response.decision, RouteDecision::Allow);
    }
}
