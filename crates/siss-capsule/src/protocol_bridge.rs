// Phase 26 Tier 3: Protocol v2 Bridge
// @file scoping + diff-only validation + test-gating

use dashmap::DashMap;
use std::sync::Arc;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ScopeError {
    #[error("Mutation outside allowed scope: {0}")]
    OutsideScope(String),

    #[error("Path is forbidden: {0}")]
    ForbiddenPath(String),

    #[error("Invalid diff format")]
    InvalidDiff,
}

pub type Result<T> = std::result::Result<T, ScopeError>;

#[derive(Clone, Debug)]
pub struct ScopeRule {
    pub pattern: String,
    pub allowed_mutations: Vec<String>,
    pub forbidden_paths: Vec<String>,
}

/// Protocol v2 Bridge enforces @file scoping and diff validation
pub struct ProtocolV2Bridge {
    scoping_rules: Arc<DashMap<String, ScopeRule>>,
}

impl ProtocolV2Bridge {
    /// Create new bridge
    pub fn new() -> Self {
        Self {
            scoping_rules: Arc::new(DashMap::new()),
        }
    }

    /// Add a scope rule
    pub fn add_scope_rule(
        &self,
        pattern: String,
        allowed_mutations: Vec<String>,
        forbidden_paths: Vec<String>,
    ) {
        self.scoping_rules.insert(
            pattern.clone(),
            ScopeRule {
                pattern,
                allowed_mutations,
                forbidden_paths,
            },
        );
    }

    /// Check if file path matches any scope rule patterns
    fn matches_pattern(pattern: &str, file_path: &str) -> bool {
        // Wildcard matching: @crates/siss-* matches crates/siss-anything/...
        if !pattern.starts_with('@') {
            return false;
        }

        let pattern_without_at = &pattern[1..]; // Remove @

        if pattern_without_at.ends_with('*') {
            // Pattern like "crates/siss-*" matches file starting with "crates/siss-"
            let prefix = pattern_without_at.strip_suffix('*').unwrap();
            return file_path.starts_with(prefix);
        }

        // Exact pattern match (no wildcard)
        file_path.starts_with(pattern_without_at)
    }

    /// Check if path is in allowed mutations list
    fn is_allowed_path(allowed: &[String], file_path: &str) -> bool {
        for allow_pattern in allowed {
            if allow_pattern == "**" {
                return true;
            }
            if allow_pattern.ends_with("/**") {
                let prefix = &allow_pattern[..allow_pattern.len() - 3];
                // Check if file_path contains the directory with proper separators
                if file_path.contains(&format!("/{}/", prefix))
                    || file_path.contains(&format!("{}/", prefix))
                {
                    return true;
                }
            } else if file_path == allow_pattern {
                return true;
            }
        }
        false
    }

    /// Check if path is forbidden
    fn is_forbidden_path(forbidden: &[String], file_path: &str) -> bool {
        forbidden.iter().any(|path| file_path == path)
    }

    /// Validate mutation against scope rules
    pub fn validate_mutation(&self, file_path: &str, _diff: &str) -> Result<()> {
        if self.scoping_rules.is_empty() {
            // No rules, allow mutation
            return Ok(());
        }

        // Check if file matches any rule
        for rule_ref in self.scoping_rules.iter() {
            let rule = rule_ref.value();

            if Self::matches_pattern(&rule.pattern, file_path) {
                // Check forbidden paths first
                if Self::is_forbidden_path(&rule.forbidden_paths, file_path) {
                    return Err(ScopeError::ForbiddenPath(file_path.to_string()));
                }

                // Check allowed mutations
                if !Self::is_allowed_path(&rule.allowed_mutations, file_path) {
                    return Err(ScopeError::OutsideScope(file_path.to_string()));
                }

                return Ok(());
            }
        }

        // File doesn't match any rule pattern
        Err(ScopeError::OutsideScope(file_path.to_string()))
    }

    /// Validate that diff is proper text (not binary)
    pub fn is_valid_diff(&self, old: &str, new: &str) -> bool {
        // Reject if either contains null bytes (binary detection)
        !old.contains('\0') && !new.contains('\0')
    }
}

impl Default for ProtocolV2Bridge {
    fn default() -> Self {
        Self::new()
    }
}
