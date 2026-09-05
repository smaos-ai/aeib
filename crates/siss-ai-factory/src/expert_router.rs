//! Expert routing for mixture-of-experts (MoE) domain-aware model selection.
//!
//! Provides deterministic routing logic to map domains (Hotel, Glass, Auto) to specific
//! large language models. Router maintains a registry of expert models per domain and
//! handles fallback to default model for unknown domains.

use std::collections::HashMap;

/// Model identifier type (e.g., "qwen2.5-coder:14b")
pub type ModelId = String;

/// Domain variants for expert routing.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ExpertDomain {
    Hotel,
    Glass,
    Auto,
}

impl ExpertDomain {
    /// Convert domain to lowercase string representation.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Hotel => "hotel",
            Self::Glass => "glass",
            Self::Auto => "auto",
        }
    }

    /// Parse domain from string (case-insensitive).
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "hotel" => Some(Self::Hotel),
            "glass" => Some(Self::Glass),
            "auto" => Some(Self::Auto),
            _ => None,
        }
    }
}

impl std::fmt::Display for ExpertDomain {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

/// Expert router for mixture-of-experts domain-aware model selection.
#[derive(Debug, Clone)]
pub struct ExpertRouter {
    experts: HashMap<String, ModelId>,
}

impl ExpertRouter {
    /// Default model ID used as fallback.
    const DEFAULT_MODEL: &'static str = "qwen2.5-coder:14b";

    /// Create a new router with default expert mapping.
    /// Maps hotel, glass, auto to default model.
    pub fn new_default() -> Self {
        let mut experts = HashMap::new();
        experts.insert("hotel".to_string(), Self::DEFAULT_MODEL.to_string());
        experts.insert("glass".to_string(), Self::DEFAULT_MODEL.to_string());
        experts.insert("auto".to_string(), Self::DEFAULT_MODEL.to_string());
        Self { experts }
    }

    /// Create a router with custom expert mapping.
    pub fn with_expert_map(experts: HashMap<String, ModelId>) -> Self {
        Self { experts }
    }

    /// Route a domain to its assigned model ID (deterministic).
    pub fn route(&self, domain: ExpertDomain) -> ModelId {
        self.experts
            .get(domain.as_str())
            .cloned()
            .unwrap_or_else(|| Self::DEFAULT_MODEL.to_string())
    }

    /// Route by string domain name (case-insensitive).
    /// Returns None if domain string cannot be parsed.
    pub fn route_by_string(&self, domain_str: &str) -> Option<ModelId> {
        ExpertDomain::from_str(domain_str).map(|d| self.route(d))
    }

    /// Register or update an expert for a domain.
    pub fn register_expert(&mut self, domain: ExpertDomain, model_id: ModelId) {
        self.experts
            .insert(domain.as_str().to_string(), model_id);
    }

    /// List all registered experts.
    pub fn list_experts(&self) -> Vec<(String, ModelId)> {
        self.experts
            .iter()
            .map(|(d, m)| (d.clone(), m.clone()))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_expert_domain_as_str() {
        assert_eq!(ExpertDomain::Hotel.as_str(), "hotel");
        assert_eq!(ExpertDomain::Glass.as_str(), "glass");
        assert_eq!(ExpertDomain::Auto.as_str(), "auto");
    }

    #[test]
    fn test_expert_domain_from_str() {
        assert_eq!(ExpertDomain::from_str("hotel"), Some(ExpertDomain::Hotel));
        assert_eq!(ExpertDomain::from_str("HOTEL"), Some(ExpertDomain::Hotel));
        assert_eq!(ExpertDomain::from_str("glass"), Some(ExpertDomain::Glass));
        assert_eq!(ExpertDomain::from_str("GLASS"), Some(ExpertDomain::Glass));
        assert_eq!(ExpertDomain::from_str("auto"), Some(ExpertDomain::Auto));
        assert_eq!(ExpertDomain::from_str("AUTO"), Some(ExpertDomain::Auto));
        assert_eq!(ExpertDomain::from_str("unknown"), None);
    }

    #[test]
    fn test_expert_domain_to_string() {
        assert_eq!(ExpertDomain::Hotel.to_string(), "hotel");
        assert_eq!(ExpertDomain::Glass.to_string(), "glass");
        assert_eq!(ExpertDomain::Auto.to_string(), "auto");
    }

    #[test]
    fn test_expert_router_new_default() {
        let router = ExpertRouter::new_default();
        assert_eq!(router.route(ExpertDomain::Hotel), "qwen2.5-coder:14b");
        assert_eq!(router.route(ExpertDomain::Glass), "qwen2.5-coder:14b");
        assert_eq!(router.route(ExpertDomain::Auto), "qwen2.5-coder:14b");
    }

    #[test]
    fn test_expert_router_route_hotel() {
        let router = ExpertRouter::new_default();
        let model_id = router.route(ExpertDomain::Hotel);
        assert_eq!(model_id, "qwen2.5-coder:14b");
    }

    #[test]
    fn test_expert_router_route_glass() {
        let router = ExpertRouter::new_default();
        let model_id = router.route(ExpertDomain::Glass);
        assert_eq!(model_id, "qwen2.5-coder:14b");
    }

    #[test]
    fn test_expert_router_route_auto() {
        let router = ExpertRouter::new_default();
        let model_id = router.route(ExpertDomain::Auto);
        assert_eq!(model_id, "qwen2.5-coder:14b");
    }

    #[test]
    fn test_expert_router_deterministic() {
        let router = ExpertRouter::new_default();
        let model1 = router.route(ExpertDomain::Hotel);
        let model2 = router.route(ExpertDomain::Hotel);
        assert_eq!(model1, model2);
    }

    #[test]
    fn test_expert_router_different_domains_same_default() {
        let router = ExpertRouter::new_default();
        assert_eq!(router.route(ExpertDomain::Hotel), router.route(ExpertDomain::Glass));
        assert_eq!(router.route(ExpertDomain::Glass), router.route(ExpertDomain::Auto));
    }

    #[test]
    fn test_expert_router_route_by_string() {
        let router = ExpertRouter::new_default();
        assert_eq!(router.route_by_string("hotel"), Some("qwen2.5-coder:14b".to_string()));
        assert_eq!(router.route_by_string("HOTEL"), Some("qwen2.5-coder:14b".to_string()));
        assert_eq!(router.route_by_string("glass"), Some("qwen2.5-coder:14b".to_string()));
        assert_eq!(router.route_by_string("unknown"), None);
    }

    #[test]
    fn test_expert_router_custom_models() {
        let mut experts = HashMap::new();
        experts.insert("hotel".to_string(), "claude-3-opus:200k".to_string());
        experts.insert("glass".to_string(), "gpt-4-turbo".to_string());
        experts.insert("auto".to_string(), "llama-2-70b".to_string());

        let router = ExpertRouter::with_expert_map(experts);
        assert_eq!(router.route(ExpertDomain::Hotel), "claude-3-opus:200k");
        assert_eq!(router.route(ExpertDomain::Glass), "gpt-4-turbo");
        assert_eq!(router.route(ExpertDomain::Auto), "llama-2-70b");
    }

    #[test]
    fn test_expert_router_register_expert() {
        let mut router = ExpertRouter::new_default();
        router.register_expert(ExpertDomain::Hotel, "new-model:v1".to_string());
        assert_eq!(router.route(ExpertDomain::Hotel), "new-model:v1");
        assert_eq!(router.route(ExpertDomain::Glass), "qwen2.5-coder:14b");
    }

    #[test]
    fn test_expert_router_list_experts() {
        let router = ExpertRouter::new_default();
        let experts = router.list_experts();
        assert_eq!(experts.len(), 3);
        assert!(experts.iter().any(|(d, _)| d == "hotel"));
        assert!(experts.iter().any(|(d, _)| d == "glass"));
        assert!(experts.iter().any(|(d, _)| d == "auto"));
    }

    #[test]
    fn test_expert_router_list_experts_custom() {
        let mut experts = HashMap::new();
        experts.insert("hotel".to_string(), "model-a".to_string());
        experts.insert("glass".to_string(), "model-b".to_string());

        let router = ExpertRouter::with_expert_map(experts);
        let listed = router.list_experts();
        assert_eq!(listed.len(), 2);
    }

    #[test]
    fn test_expert_router_fallback_unknown_domain() {
        let router = ExpertRouter::with_expert_map(HashMap::new());
        let model = router.route(ExpertDomain::Hotel);
        assert_eq!(model, ExpertRouter::DEFAULT_MODEL);
    }
}
