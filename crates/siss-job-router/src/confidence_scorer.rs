use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfidenceScore {
    pub score: f64,
    pub estimated_tokens: u32,
    pub recommended_tier: RoutingTier,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum RoutingTier {
    Tier1RapidMLX,
    Tier2Sonnet,
    Tier3Opus,
}

pub struct SimpleScorer;

impl SimpleScorer {
    pub fn score_task(task_description: &str) -> ConfidenceScore {
        let confidence = Self::compute_confidence(task_description);
        let tokens = Self::estimate_tokens(task_description);
        let tier = Self::recommend_tier(confidence);

        ConfidenceScore {
            score: confidence,
            estimated_tokens: tokens,
            recommended_tier: tier,
        }
    }

    fn compute_confidence(task_description: &str) -> f64 {
        let lower = task_description.to_lowercase();

        let confidence: f64 = if lower.contains("fetch by id") || lower.contains("polling") {
            0.1
        } else if lower.contains("filter") && !lower.contains("correlate") {
            0.4
        } else if lower.contains("correlate") || lower.contains("analysis") {
            0.65
        } else if lower.contains("decide") || lower.contains("decision") {
            0.8
        } else if lower.contains("complex") {
            0.95
        } else {
            0.5
        };

        // Clamp to [0.0, 1.0]
        confidence.max(0.0).min(1.0)
    }

    fn estimate_tokens(task_description: &str) -> u32 {
        let base = 100;
        let len_factor = (task_description.len() / 10).min(50);
        (base + len_factor) as u32
    }

    fn recommend_tier(confidence: f64) -> RoutingTier {
        match confidence {
            c if c >= 0.75 => RoutingTier::Tier3Opus,
            c if c >= 0.3 => RoutingTier::Tier2Sonnet,
            _ => RoutingTier::Tier1RapidMLX,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_confidence_simple_polling() {
        let score = SimpleScorer::score_task("fetch by id");
        assert_eq!(score.score, 0.1);
        assert_eq!(score.recommended_tier, RoutingTier::Tier1RapidMLX);
    }

    #[test]
    fn test_confidence_filter_query() {
        let score = SimpleScorer::score_task("filter results by status");
        assert_eq!(score.score, 0.4);
        assert_eq!(score.recommended_tier, RoutingTier::Tier2Sonnet); // 0.4 >= 0.3, so Tier2
    }

    #[test]
    fn test_confidence_correlation_analysis() {
        let score = SimpleScorer::score_task("correlate anomaly patterns");
        assert_eq!(score.score, 0.65);
        assert_eq!(score.recommended_tier, RoutingTier::Tier2Sonnet);
    }

    #[test]
    fn test_confidence_decision_making() {
        let score = SimpleScorer::score_task("decide next action based on context");
        assert_eq!(score.score, 0.8);
        assert_eq!(score.recommended_tier, RoutingTier::Tier3Opus);
    }

    #[test]
    fn test_confidence_token_estimate_clamped() {
        let score = SimpleScorer::score_task("short");
        assert!(score.estimated_tokens > 0);
        assert!(score.estimated_tokens < 1000);
    }

    #[test]
    fn test_confidence_similarity_matching() {
        let score1 = SimpleScorer::score_task("polling data fetch by id");
        let score2 = SimpleScorer::score_task("fetch by id polling");
        assert_eq!(score1.score, score2.score);
    }
}
