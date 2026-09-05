use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Decision record for drift monitoring
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Decision {
    pub id: Uuid,
    pub timestamp: i64,
    pub action: String,
    pub reasoning: String,
    /// Quality score (0.0-1.0)
    pub quality_score: f64,
    /// Optional: ground truth correctness
    pub is_correct: Option<bool>,
    /// Metadata for analysis
    pub metadata: std::collections::HashMap<String, String>,
}

impl Decision {
    /// Create new decision
    pub fn new(action: String, reasoning: String) -> Self {
        Self {
            id: Uuid::new_v4(),
            timestamp: chrono::Utc::now().timestamp(),
            action,
            reasoning,
            quality_score: 0.0,
            is_correct: None,
            metadata: std::collections::HashMap::new(),
        }
    }

    /// Set quality score
    pub fn with_quality_score(mut self, score: f64) -> Self {
        self.quality_score = score.max(0.0).min(1.0);
        self
    }

    /// Mark decision correctness
    pub fn with_correctness(mut self, is_correct: bool) -> Self {
        self.is_correct = Some(is_correct);
        self
    }

    /// Add metadata
    pub fn with_metadata(mut self, key: String, value: String) -> Self {
        self.metadata.insert(key, value);
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_decision_creation() {
        let decision = Decision::new(
            "approve".to_string(),
            "meets criteria".to_string(),
        );
        assert_eq!(decision.action, "approve");
        assert_eq!(decision.quality_score, 0.0);
    }

    #[test]
    fn test_decision_quality_clamping() {
        let decision = Decision::new("test".to_string(), "test".to_string())
            .with_quality_score(1.5);
        assert_eq!(decision.quality_score, 1.0);

        let decision = Decision::new("test".to_string(), "test".to_string())
            .with_quality_score(-0.5);
        assert_eq!(decision.quality_score, 0.0);
    }

    #[test]
    fn test_decision_chaining() {
        let decision = Decision::new("test".to_string(), "test".to_string())
            .with_quality_score(0.9)
            .with_correctness(true)
            .with_metadata("model".to_string(), "gpt4".to_string());

        assert_eq!(decision.quality_score, 0.9);
        assert_eq!(decision.is_correct, Some(true));
        assert!(decision.metadata.contains_key("model"));
    }
}
