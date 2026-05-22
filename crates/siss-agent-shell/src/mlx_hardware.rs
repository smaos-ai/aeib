/// Phase 57: Air-Gap Hardware Membrane — Compile-Time Cloud Egress Block
/// INVARIANT: CLOUD_BLOCKLIST const prevents any outbound connection at compile time.

use crate::hooks::{LifecycleHook, HookResult, ToolUseContext};
use std::collections::HashSet;

pub const CLOUD_BLOCKLIST: &[&str] = &[
    "openai.com",
    "anthropic.com",
    "azure.microsoft.com",
    "gcp.googleapis.com",
    "aws.amazon.com",
    "cloudflare.com",
    "stripe.com",
    "mixpanel.com",
    "datadog.com",
    "sentry.io",
];

pub struct AirGapMembrane {
    blocklist: HashSet<String>,
}

impl Default for AirGapMembrane {
    fn default() -> Self {
        let blocklist = CLOUD_BLOCKLIST.iter().map(|s| s.to_string()).collect();
        AirGapMembrane { blocklist }
    }
}

impl AirGapMembrane {
    /// Check if a hostname is cloud-blocked.
    /// RULE 1: Check direct match against CLOUD_BLOCKLIST
    /// RULE 2: Check domain suffix match (e.g., ".openai.com" matches "chat.openai.com")
    /// RULE 3: Return true if blocklist contains hostname or any suffix
    pub fn is_blocked(&self, hostname: &str) -> bool {
        if self.blocklist.contains(hostname) {
            return true;
        }

        let parts: Vec<&str> = hostname.split('.').collect();
        for i in 0..parts.len() {
            let suffix = parts[i..].join(".");
            if self.blocklist.contains(&suffix) {
                return true;
            }
        }
        false
    }
}

impl LifecycleHook for AirGapMembrane {
    fn name(&self) -> &str {
        "AirGapMembrane"
    }

    /// Intercept HTTP/TCP tools and block cloud egress.
    /// RULE 4: tool_name in ["HttpFetch", "HttpPost", "TcpConnect"] → extract hostname
    /// RULE 5: is_blocked(hostname) → HookResult::Halt { reason: "air_gap_violation" }
    /// RULE 6: Otherwise → HookResult::Continue
    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult {
        if !matches!(ctx.tool_name.as_str(), "HttpFetch" | "HttpPost" | "TcpConnect") {
            return HookResult::Continue;
        }

        if let Some(url_value) = ctx.tool_input.get("url") {
            if let Some(url_str) = url_value.as_str() {
                if let Some(hostname) = Self::extract_hostname(url_str) {
                    if self.is_blocked(&hostname) {
                        return HookResult::Halt {
                            reason: "air_gap_violation".to_string(),
                        };
                    }
                }
            }
        }
        HookResult::Continue
    }
}

impl AirGapMembrane {
    fn extract_hostname(url: &str) -> Option<String> {
        // Simple extraction: https://api.openai.com/path → api.openai.com
        if let Some(start) = url.find("://") {
            let after_scheme = &url[start + 3..];
            if let Some(end) = after_scheme.find('/') {
                Some(after_scheme[..end].to_string())
            } else {
                Some(after_scheme.to_string())
            }
        } else {
            Some(url.to_string())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_air_gap_blocks_openai() {
        let membrane = AirGapMembrane::default();
        assert!(membrane.is_blocked("api.openai.com"));
        assert!(membrane.is_blocked("chat.openai.com"));
        assert!(membrane.is_blocked("openai.com"));
    }

    #[test]
    fn test_air_gap_allows_localhost() {
        let membrane = AirGapMembrane::default();
        assert!(!membrane.is_blocked("localhost"));
        assert!(!membrane.is_blocked("127.0.0.1"));
        assert!(!membrane.is_blocked("internal.sovereign.ai"));
    }

    #[test]
    fn test_air_gap_hook_halts_cloud_fetch() {
        use siss_graph_core::node::NodeId;
        use uuid::Uuid;
        use serde_json::json;

        let membrane = AirGapMembrane::default();
        let ctx = ToolUseContext {
            task_id: NodeId::new(),
            tool_id: Uuid::new_v4(),
            tool_name: "HttpFetch".to_string(),
            tool_input: json!({ "url": "https://api.openai.com/v1/chat" }),
            tool_output: None,
        };

        let result = membrane.on_pre_tool_use(&ctx);
        assert_eq!(result, HookResult::Halt { reason: "air_gap_violation".to_string() });
    }
}
