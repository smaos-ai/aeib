/// Saliency scoring: pattern-first routing that detects task semantics before confidence scoring.
/// AP2 microtransactions and RAG fetches always route to SLM (Tier1RapidMLX).
/// Complex reasoning and high token count escalate to LLM (Tier3Opus).
use crate::confidence_scorer::{RoutingTier, SimpleScorer};
use crate::routing_engine::RoutingDecision;

pub const SALIENCY_COMPLEX_THRESHOLD: u32 = 200; // tokens
pub const REASONING_DEPTH_COMPLEX: u8 = 3; // steps

/// Features extracted from a task that determine saliency.
#[derive(Debug, Clone)]
pub struct SaliencyFeatures {
    pub estimated_tokens: u32,
    pub reasoning_depth: u8,  // 0 = single step, N = N-step reasoning chain
    pub is_ap2_microtx: bool, // AP2 micro-transaction pattern
    pub is_rag_fetch: bool,   // RAG fetch pattern
    pub description: String,  // task description for fallback confidence scoring
}

impl SaliencyFeatures {
    /// Detect AP2 and RAG patterns from task description.
    pub fn from_description(desc: &str) -> Self {
        let desc_lower = desc.to_lowercase();
        let is_ap2_microtx = desc_lower.contains("ap2")
            || desc_lower.contains("microtransaction")
            || desc_lower.contains("mandate");
        let is_rag_fetch = desc_lower.contains("fetch")
            || desc_lower.contains("retrieve")
            || desc_lower.contains("lookup")
            || desc_lower.contains("by id");

        SaliencyFeatures {
            estimated_tokens: 100, // default estimate
            reasoning_depth: 1,
            is_ap2_microtx,
            is_rag_fetch,
            description: desc.to_string(),
        }
    }
}

/// Saliency scorer: pattern-based routing with high confidence fallback.
pub struct SaliencyScorer;

impl SaliencyScorer {
    /// Score a task's saliency and return routing decision.
    /// Invariant 1: AP2 and RAG patterns override all other signals.
    pub fn score(features: &SaliencyFeatures) -> RoutingDecision {
        // PATTERN PRIORITY (highest wins)
        if features.is_ap2_microtx {
            return RoutingDecision {
                primary_tier: RoutingTier::Tier1RapidMLX,
                fallback_chain: vec![RoutingTier::Tier2Sonnet, RoutingTier::Tier3Opus],
                reason: "ap2_microtransaction".to_string(),
            };
        }

        if features.is_rag_fetch {
            return RoutingDecision {
                primary_tier: RoutingTier::Tier1RapidMLX,
                fallback_chain: vec![RoutingTier::Tier2Sonnet, RoutingTier::Tier3Opus],
                reason: "rag_fetch".to_string(),
            };
        }

        // TOKEN COUNT GATE
        if features.estimated_tokens > SALIENCY_COMPLEX_THRESHOLD {
            return RoutingDecision {
                primary_tier: RoutingTier::Tier3Opus,
                fallback_chain: vec![],
                reason: format!("high_token_count_{}", features.estimated_tokens),
            };
        }

        // REASONING DEPTH GATE
        if features.reasoning_depth >= REASONING_DEPTH_COMPLEX {
            return RoutingDecision {
                primary_tier: RoutingTier::Tier3Opus,
                fallback_chain: vec![],
                reason: format!("deep_reasoning_depth_{}", features.reasoning_depth),
            };
        }

        // DEFAULT: delegate to existing confidence-based routing
        let confidence = SimpleScorer::score_task(&features.description);
        crate::routing_engine::RoutingEngine::decide(&confidence, None).unwrap_or_else(|_| {
            RoutingDecision {
                primary_tier: RoutingTier::Tier1RapidMLX,
                fallback_chain: vec![RoutingTier::Tier2Sonnet, RoutingTier::Tier3Opus],
                reason: "fallback_default".to_string(),
            }
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ap2_pattern_detection() {
        let features = SaliencyFeatures::from_description("Process AP2 mandate approval");
        assert!(features.is_ap2_microtx);
    }

    #[test]
    fn test_rag_pattern_detection() {
        let features = SaliencyFeatures::from_description("Fetch user by id");
        assert!(features.is_rag_fetch);
    }
}
