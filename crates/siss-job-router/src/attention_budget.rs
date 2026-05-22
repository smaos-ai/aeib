/// Attention Budget Enforcement: σ⁺ operator that enforces hard token caps and ϕ⁺ simplification.
/// SLM path capped at 2048 tokens; LLM path capped at 4096 tokens.
/// Oversize context is greedily trimmed by priority.

use crate::confidence_scorer::RoutingTier;
use thiserror::Error;

pub const SLM_TOKEN_CAP: i64 = 2048;
pub const LLM_TOKEN_CAP: i64 = 4096;
pub const TOKENS_PER_CHAR: f64 = 0.25;   // 1 token ≈ 4 chars

/// Local context entry (no dependency on siss-context-cartography).
#[derive(Debug, Clone)]
pub struct ContextEntry {
    pub content: String,         // raw text chunk
    pub priority: u8,            // 0 = drop first, 255 = keep last (ϕ⁺ uses this for greedy trim)
}

impl ContextEntry {
    /// Estimate token count for this entry.
    pub fn estimate_tokens(&self) -> i64 {
        (self.content.len() as f64 * TOKENS_PER_CHAR).ceil() as i64
    }
}

/// Context after budget enforcement (possibly simplified).
#[derive(Debug)]
pub struct EnforcedContext {
    pub entries: Vec<ContextEntry>,
    pub tokens_used: i64,
    pub simplification_applied: bool,
}

/// Error type for budget enforcement.
#[derive(Debug, Error, PartialEq, Eq)]
#[error("context exhausted after simplification: {tokens} > {cap}")]
pub struct BudgetError {
    pub tokens: i64,
    pub cap: i64,
}

/// Attention Budget Enforcer: σ⁺ operator with ϕ⁺ simplification fallback.
pub struct AttentionBudgetEnforcer;

impl AttentionBudgetEnforcer {
    /// Enforce hard token cap for the given routing tier.
    /// Invariant 2: Within cap → return unchanged. Over cap → apply ϕ⁺ trim. Still over → error.
    pub fn enforce(
        mut entries: Vec<ContextEntry>,
        tier: &RoutingTier,
    ) -> Result<EnforcedContext, BudgetError> {
        let cap = Self::cap_for_tier(tier);
        let mut total_tokens = entries.iter().map(|e| e.estimate_tokens()).sum::<i64>();

        if total_tokens <= cap {
            return Ok(EnforcedContext {
                entries,
                tokens_used: total_tokens,
                simplification_applied: false,
            });
        }

        // ϕ⁺ SIMPLIFICATION: greedy priority-descending trim
        // Sort by priority ascending (lowest priority first to drop)
        entries.sort_by_key(|e| e.priority);

        // Greedily drop entries from lowest priority until we fit
        while !entries.is_empty() {
            total_tokens = entries.iter().map(|e| e.estimate_tokens()).sum::<i64>();
            if total_tokens <= cap {
                return Ok(EnforcedContext {
                    entries,
                    tokens_used: total_tokens,
                    simplification_applied: true,
                });
            }
            entries.remove(0);  // drop the lowest-priority entry
        }

        // Exhausted all entries and still over cap (only if all entries were huge)
        Err(BudgetError {
            tokens: total_tokens,
            cap,
        })
    }

    /// Return the hard token cap for a given tier.
    pub fn cap_for_tier(tier: &RoutingTier) -> i64 {
        match tier {
            RoutingTier::Tier1RapidMLX => SLM_TOKEN_CAP,
            _ => LLM_TOKEN_CAP,  // Tier2Sonnet and Tier3Opus both use 4096
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_estimate_tokens() {
        let entry = ContextEntry {
            content: "x".repeat(1000),
            priority: 100,
        };
        let tokens = entry.estimate_tokens();
        assert_eq!(tokens, 250, "1000 chars at 0.25 token/char = 250 tokens");
    }

    #[test]
    fn test_cap_for_tier_slm() {
        assert_eq!(
            AttentionBudgetEnforcer::cap_for_tier(&RoutingTier::Tier1RapidMLX),
            2048
        );
    }

    #[test]
    fn test_cap_for_tier_llm() {
        assert_eq!(
            AttentionBudgetEnforcer::cap_for_tier(&RoutingTier::Tier3Opus),
            4096
        );
    }
}
