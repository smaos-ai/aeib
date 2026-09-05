//! L1 → L2 Contract: Type-safe policy-bound output
//! Replaces implicit JSON with explicit trait boundaries

use crate::policy::PolicyBound;
use std::fmt;

/// Input contract for policy routing (what external code sends to L1)
pub trait L1Input: Send + Sync + fmt::Debug {
    fn request(&self) -> &str;
    fn user_id(&self) -> &str;
}

/// Output contract for L1 (what L1 sends to L2)
pub trait L1Output: Send + Sync + fmt::Debug {
    fn decision(&self) -> &str;
    fn article(&self) -> &str;
    fn compliance_level(&self) -> u8;
    fn request_id(&self) -> &str;
}

/// Concrete implementation of L1Input
#[derive(Debug, Clone)]
pub struct PolicyRequest {
    id: String,
    request: String,
    user_id: String,
}

impl PolicyRequest {
    pub fn new(request: String, user_id: String) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            request,
            user_id,
        }
    }

    pub fn id(&self) -> &str {
        &self.id
    }
}

impl L1Input for PolicyRequest {
    fn request(&self) -> &str {
        &self.request
    }

    fn user_id(&self) -> &str {
        &self.user_id
    }
}

/// Concrete output wrapper implementing L1Output
#[derive(Debug, Clone)]
pub struct PolicyDecision {
    bound: PolicyBound,
    request_id: String,
}

impl PolicyDecision {
    pub fn new(bound: PolicyBound, request_id: String) -> Self {
        Self { bound, request_id }
    }

    pub fn bound(&self) -> &PolicyBound {
        &self.bound
    }
}

impl L1Output for PolicyDecision {
    fn decision(&self) -> &str {
        &self.bound.decision
    }

    fn article(&self) -> &str {
        &self.bound.cited_article
    }

    fn compliance_level(&self) -> u8 {
        self.bound.compliance_level
    }

    fn request_id(&self) -> &str {
        &self.request_id
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_policy_request_creation() {
        let req = PolicyRequest::new("test".to_string(), "user123".to_string());
        assert_eq!(req.request(), "test");
        assert_eq!(req.user_id(), "user123");
        assert!(!req.id().is_empty());
    }

    #[test]
    fn test_policy_request_unique_ids() {
        let req1 = PolicyRequest::new("test".to_string(), "user".to_string());
        let req2 = PolicyRequest::new("test".to_string(), "user".to_string());
        assert_ne!(req1.id(), req2.id());
    }

    #[test]
    fn test_policy_decision_contract() {
        use crate::policy::PolicyBound;
        let bound = PolicyBound {
            decision: "approved".to_string(),
            cited_article: "Article 50".to_string(),
            compliance_level: 100,
        };
        let decision = PolicyDecision::new(bound, "req123".to_string());

        assert_eq!(decision.decision(), "approved");
        assert_eq!(decision.article(), "Article 50");
        assert_eq!(decision.compliance_level(), 100);
        assert_eq!(decision.request_id(), "req123");
    }

    #[test]
    fn test_l1_input_trait_object() {
        let req: Box<dyn L1Input> =
            Box::new(PolicyRequest::new("test".to_string(), "user".to_string()));
        assert_eq!(req.request(), "test");
    }

    #[test]
    fn test_l1_output_trait_object() {
        use crate::policy::PolicyBound;
        let bound = PolicyBound {
            decision: "blocked".to_string(),
            cited_article: "Article 6".to_string(),
            compliance_level: 0,
        };
        let decision = PolicyDecision::new(bound, "req456".to_string());
        let output: Box<dyn L1Output> = Box::new(decision);

        assert_eq!(output.decision(), "blocked");
        assert_eq!(output.compliance_level(), 0);
    }

    #[test]
    fn test_policy_request_empty_request_allowed() {
        // Empty requests are validated at L1 boundary, not here
        let req = PolicyRequest::new(String::new(), "user".to_string());
        assert_eq!(req.request(), "");
    }

    #[test]
    fn test_policy_decision_compliance_levels() {
        use crate::policy::PolicyBound;
        for level in &[0u8, 50, 100] {
            let bound = PolicyBound {
                decision: "test".to_string(),
                cited_article: "Article 50".to_string(),
                compliance_level: *level,
            };
            let decision = PolicyDecision::new(bound, "req".to_string());
            assert_eq!(decision.compliance_level(), *level);
        }
    }

    #[test]
    fn test_policy_request_clone() {
        let req1 = PolicyRequest::new("test".to_string(), "user".to_string());
        let req2 = req1.clone();
        assert_eq!(req1.request(), req2.request());
        assert_eq!(req1.id(), req2.id());
    }
}
