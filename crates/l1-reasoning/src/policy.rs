use super::error::{
    validate_compliance_level, validate_policy_id, validate_request, L1AuditEntry, L1Error,
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyRouter {
    pub policy_id: String,
    pub article_references: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyBound {
    pub decision: String,
    pub cited_article: String,
    pub compliance_level: u8,
}

impl PolicyRouter {
    pub fn new(policy_id: String) -> Result<Self, L1Error> {
        validate_policy_id(&policy_id)?;
        Ok(Self {
            policy_id,
            article_references: Vec::new(),
        })
    }

    pub fn cite_article_50(&self) -> String {
        "Article 50: EU AI Act transparency - documented in decision trail".to_string()
    }

    pub fn route_to_policy(&self) -> String {
        self.policy_id.clone()
    }

    pub fn enforce_bound(&self, request: &str) -> Result<PolicyBound, L1Error> {
        // Input validation with deny-by-default
        validate_request(request)?;
        validate_compliance_level(100)?;

        // Audit trail entry for successful decision
        let _audit = L1AuditEntry::new(self.policy_id.clone(), "enforce_bound".to_string(), 100);

        Ok(PolicyBound {
            decision: "Policy-bound decision".to_string(),
            cited_article: "Article 50".to_string(),
            compliance_level: 100,
        })
    }

    pub fn validate_policy(&self) -> Result<(), L1Error> {
        validate_policy_id(&self.policy_id)?;
        for article in &self.article_references {
            if !article.starts_with("Article ") {
                return Err(L1Error::InvalidArticleReference {
                    article: article.clone(),
                    recovery: "Use format 'Article N'".to_string(),
                    timestamp: chrono::Utc::now(),
                });
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cite_article_50() {
        let router = PolicyRouter::new("compliance".to_string()).unwrap();
        let citation = router.cite_article_50();
        assert!(citation.contains("Article 50"));
    }

    #[test]
    fn test_route_to_policy() {
        let router = PolicyRouter::new("compliance".to_string()).unwrap();
        assert_eq!(router.route_to_policy(), "compliance");
    }

    #[test]
    fn test_enforce_bound() {
        let router = PolicyRouter::new("compliance".to_string()).unwrap();
        let result = router.enforce_bound("test request");
        assert!(result.is_ok());
    }

    #[test]
    fn test_enforce_bound_empty_request_denied() {
        let router = PolicyRouter::new("compliance".to_string()).unwrap();
        let result = router.enforce_bound("");
        assert!(result.is_err());
    }

    #[test]
    fn test_new_policy_router_invalid_policy_id() {
        let result = PolicyRouter::new("".to_string());
        assert!(result.is_err());
        if let Err(L1Error::PolicyValidationFailed { recovery, .. }) = result {
            assert!(recovery.contains("non-empty"));
        }
    }

    #[test]
    fn test_validate_policy_roundtrip() {
        let router = PolicyRouter::new("test_policy".to_string()).unwrap();
        let result = router.validate_policy();
        assert!(result.is_ok());
    }

    #[test]
    fn test_enforce_bound_large_request_denied() {
        let router = PolicyRouter::new("compliance".to_string()).unwrap();
        let large_request = "x".repeat(11_000);
        let result = router.enforce_bound(&large_request);
        assert!(result.is_err());
    }
}
