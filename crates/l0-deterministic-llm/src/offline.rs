use crate::types::OfflineFallbackTemplate;
use dashmap::DashMap;
use std::sync::Arc;

/// Rule-based offline fallback system
pub struct OfflineFallback {
    templates: Arc<DashMap<String, OfflineFallbackTemplate>>,
}

impl OfflineFallback {
    pub fn new() -> Self {
        Self {
            templates: Arc::new(DashMap::new()),
        }
    }

    /// Register a fallback template
    pub fn register_template(&self, template: OfflineFallbackTemplate) -> Result<(), String> {
        self.templates.insert(template.domain.clone(), template);
        Ok(())
    }

    /// Get fallback response for a prompt
    pub fn get_fallback(&self, prompt: &str) -> Option<String> {
        for entry in self.templates.iter() {
            if entry.value().matches(prompt) {
                return Some(entry.value().fallback_response.clone());
            }
        }
        None
    }

    /// Check if template exists for domain
    pub fn has_template(&self, domain: &str) -> bool {
        self.templates.contains_key(domain)
    }

    /// Get all registered domains
    pub fn domains(&self) -> Vec<String> {
        self.templates.iter().map(|e| e.key().clone()).collect()
    }

    /// Clear all templates
    pub fn clear(&self) {
        self.templates.clear();
    }

    /// Get template count
    pub fn count(&self) -> usize {
        self.templates.len()
    }
}

impl Default for OfflineFallback {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_and_retrieve_template() {
        let fallback = OfflineFallback::new();
        let template = OfflineFallbackTemplate::new(
            "hotel".to_string(),
            "credit".to_string(),
            "Hotel credit scoring unavailable. Default risk: medium.".to_string(),
        );

        fallback.register_template(template).unwrap();
        assert!(fallback.has_template("hotel"));
    }

    #[test]
    fn test_fallback_response_matching() {
        let fallback = OfflineFallback::new();
        let template = OfflineFallbackTemplate::new(
            "hotel".to_string(),
            "credit scoring".to_string(),
            "Default credit score: 650".to_string(),
        );

        fallback.register_template(template).unwrap();
        let result = fallback.get_fallback("What is the credit scoring?");

        assert!(result.is_some());
        assert_eq!(result.unwrap(), "Default credit score: 650");
    }

    #[test]
    fn test_no_matching_template() {
        let fallback = OfflineFallback::new();
        let result = fallback.get_fallback("Some random question");
        assert!(result.is_none());
    }

    #[test]
    fn test_case_insensitive_matching() {
        let fallback = OfflineFallback::new();
        let template = OfflineFallbackTemplate::new(
            "test".to_string(),
            "PATTERN".to_string(),
            "Matched!".to_string(),
        );

        fallback.register_template(template).unwrap();
        let result = fallback.get_fallback("This has pattern in it");

        assert!(result.is_some());
    }

    #[test]
    fn test_clear_templates() {
        let fallback = OfflineFallback::new();
        let template = OfflineFallbackTemplate::new(
            "test".to_string(),
            "pattern".to_string(),
            "response".to_string(),
        );

        fallback.register_template(template).unwrap();
        assert_eq!(fallback.count(), 1);

        fallback.clear();
        assert_eq!(fallback.count(), 0);
    }

    #[test]
    fn test_multiple_templates() {
        let fallback = OfflineFallback::new();

        let t1 = OfflineFallbackTemplate::new(
            "domain1".to_string(),
            "pattern1".to_string(),
            "response1".to_string(),
        );
        let t2 = OfflineFallbackTemplate::new(
            "domain2".to_string(),
            "pattern2".to_string(),
            "response2".to_string(),
        );

        fallback.register_template(t1).unwrap();
        fallback.register_template(t2).unwrap();

        assert_eq!(fallback.count(), 2);
        assert!(fallback.has_template("domain1"));
        assert!(fallback.has_template("domain2"));
    }
}
