// Phase 26 Tier 2: Rule-Based Fallback
// Fallback strategies for deterministic executor

use dashmap::DashMap;
use std::sync::Arc;

#[derive(Clone, Debug)]
pub enum FallbackAction {
    RetryWithBackoff { max_retries: u32, backoff_ms: u64 },
    SwitchToFallback { model_name: String },
    ReturnCached { cache_key: String },
    FailClosed,
}

#[derive(Clone, Debug)]
pub struct FallbackRule {
    pub condition: String,
    pub action: FallbackAction,
    pub priority: u32,
}

/// Rule-based fallback for deterministic execution
pub struct RuleBasedFallback {
    rules: Arc<DashMap<u32, FallbackRule>>,
    rule_counter: Arc<std::sync::atomic::AtomicU32>,
}

impl RuleBasedFallback {
    /// Create new fallback manager
    pub fn new() -> Self {
        Self {
            rules: Arc::new(DashMap::new()),
            rule_counter: Arc::new(std::sync::atomic::AtomicU32::new(0)),
        }
    }

    /// Add a new fallback rule with priority
    pub fn add_rule(&self, condition: String, action: FallbackAction, priority: u32) {
        let id = self
            .rule_counter
            .fetch_add(1, std::sync::atomic::Ordering::SeqCst);

        self.rules.insert(
            id,
            FallbackRule {
                condition,
                action,
                priority,
            },
        );
    }

    /// Get number of rules
    pub fn rule_count(&self) -> usize {
        self.rules.len()
    }

    /// Evaluate rules in priority order and return first matching action
    pub fn evaluate(&self, _context: &str) -> Option<FallbackAction> {
        if self.rules.is_empty() {
            return None;
        }

        // Sort by priority and return first action
        let mut rules_vec: Vec<_> = self.rules.iter().map(|r| r.value().clone()).collect();
        rules_vec.sort_by_key(|r| r.priority);

        rules_vec.first().map(|r| r.action.clone())
    }
}

impl Default for RuleBasedFallback {
    fn default() -> Self {
        Self::new()
    }
}
