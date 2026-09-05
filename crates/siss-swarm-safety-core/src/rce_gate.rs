//! RCE (Remote Code Execution) prevention gates

use crate::error::{Error, Result};
use crate::types::{RcePattern, RceSeverity};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

/// RCE gate configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RceGateConfig {
    pub block_critical: bool,
    pub block_high: bool,
    pub block_medium: bool,
    pub allow_whitelist: Vec<String>,
}

impl Default for RceGateConfig {
    fn default() -> Self {
        Self {
            block_critical: true,
            block_high: true,
            block_medium: false,
            allow_whitelist: Vec::new(),
        }
    }
}

/// RCE Gate: prevents Remote Code Execution attacks
pub struct RceGate {
    config: RceGateConfig,
    patterns: Arc<RwLock<Vec<RcePattern>>>,
    blocked_count: Arc<RwLock<u64>>,
    allowed_count: Arc<RwLock<u64>>,
}

impl RceGate {
    /// Create new RCE gate
    pub fn new(config: RceGateConfig) -> Self {
        let mut patterns = Vec::new();
        patterns.extend(Self::default_patterns());

        Self {
            config,
            patterns: Arc::new(RwLock::new(patterns)),
            blocked_count: Arc::new(RwLock::new(0)),
            allowed_count: Arc::new(RwLock::new(0)),
        }
    }

    /// Check if input violates RCE patterns
    pub fn check(&self, input: &str) -> Result<()> {
        let patterns = self.patterns.read();

        for pattern in patterns.iter() {
            if self.matches_pattern(input, &pattern.pattern) {
                let should_block = match pattern.severity {
                    RceSeverity::Critical => self.config.block_critical,
                    RceSeverity::High => self.config.block_high,
                    RceSeverity::Medium => self.config.block_medium,
                    RceSeverity::Low => false,
                };

                if should_block && !self.is_whitelisted(input) {
                    let mut blocked = self.blocked_count.write();
                    *blocked += 1;
                    return Err(Error::RceViolation(format!(
                        "Pattern '{}' matched with severity {:?}",
                        pattern.id, pattern.severity
                    )));
                }
            }
        }

        let mut allowed = self.allowed_count.write();
        *allowed += 1;
        Ok(())
    }

    /// Register custom RCE pattern
    pub fn register_pattern(&self, pattern: RcePattern) -> Result<()> {
        let mut patterns = self.patterns.write();
        patterns.push(pattern);
        Ok(())
    }

    /// Get pattern match statistics
    pub fn stats(&self) -> (u64, u64) {
        let blocked = *self.blocked_count.read();
        let allowed = *self.allowed_count.read();
        (blocked, allowed)
    }

    fn matches_pattern(&self, input: &str, pattern: &str) -> bool {
        // Simple pattern matching - can be extended with regex
        input.contains(pattern)
    }

    fn is_whitelisted(&self, input: &str) -> bool {
        self.config.allow_whitelist.iter().any(|w| input.contains(w))
    }

    fn default_patterns() -> Vec<RcePattern> {
        vec![
            RcePattern {
                id: "eval_injection".to_string(),
                pattern: "eval(".to_string(),
                severity: RceSeverity::Critical,
                block_by_default: true,
            },
            RcePattern {
                id: "exec_injection".to_string(),
                pattern: "exec(".to_string(),
                severity: RceSeverity::Critical,
                block_by_default: true,
            },
            RcePattern {
                id: "system_injection".to_string(),
                pattern: "system(".to_string(),
                severity: RceSeverity::High,
                block_by_default: true,
            },
            RcePattern {
                id: "shell_escape".to_string(),
                pattern: "bash -c".to_string(),
                severity: RceSeverity::High,
                block_by_default: true,
            },
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rce_gate_creation() {
        let gate = RceGate::new(RceGateConfig::default());
        let (blocked, allowed) = gate.stats();
        assert_eq!(blocked, 0);
        assert_eq!(allowed, 0);
    }

    #[test]
    fn test_rce_pattern_detection() {
        let gate = RceGate::new(RceGateConfig::default());
        let result = gate.check("eval(malicious_code)");
        assert!(result.is_err());

        let (blocked, allowed) = gate.stats();
        assert_eq!(blocked, 1);
        assert_eq!(allowed, 0);
    }

    #[test]
    fn test_safe_input_allowed() {
        let gate = RceGate::new(RceGateConfig::default());
        let result = gate.check("normal_function_call()");
        assert!(result.is_ok());

        let (blocked, allowed) = gate.stats();
        assert_eq!(blocked, 0);
        assert_eq!(allowed, 1);
    }

    #[test]
    fn test_whitelist_bypass() {
        let config = RceGateConfig {
            block_critical: true,
            block_high: true,
            block_medium: false,
            allow_whitelist: vec!["safe_eval".to_string()],
        };
        let gate = RceGate::new(config);
        let result = gate.check("safe_eval(trusted_code)");
        assert!(result.is_ok());
    }

    #[test]
    fn test_custom_pattern() {
        let gate = RceGate::new(RceGateConfig::default());
        let pattern = RcePattern {
            id: "custom_threat".to_string(),
            pattern: "dangerous_function".to_string(),
            severity: RceSeverity::Medium,
            block_by_default: false,
        };
        gate.register_pattern(pattern).unwrap();

        let result = gate.check("dangerous_function()");
        assert!(result.is_ok());
    }
}
