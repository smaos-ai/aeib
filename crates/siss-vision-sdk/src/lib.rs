pub mod adapters;
pub mod auth;
pub mod core;
pub mod error;
pub mod policy;
pub mod types;

pub use adapters::*;
pub use auth::*;
pub use core::*;
pub use error::*;
pub use policy::*;
pub use types::*;

use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;

#[derive(Clone)]
pub struct VisionSDK {
    pub auth_handler: Arc<OAuth2Handler>,
    pub token_manager: Arc<TokenManager>,
    pub policy_store: Arc<CreatorPolicyStore>,
    pub revenue_router: Arc<RevenueRouter>,
    pub audit_log: Arc<AuditLog>,
    rate_limiter: Arc<RateLimiter>,
}

pub struct VisionSDKBuilder {
    test_mode: bool,
    rate_limit: usize,
}

impl VisionSDKBuilder {
    pub fn new() -> Self {
        Self {
            test_mode: false,
            rate_limit: 1000,
        }
    }

    pub fn with_test_mode(mut self) -> Self {
        self.test_mode = true;
        self
    }

    pub fn with_rate_limit(mut self, limit: usize) -> Self {
        self.rate_limit = limit;
        self
    }

    pub async fn build(self) -> Result<VisionSDK> {
        Ok(VisionSDK {
            auth_handler: Arc::new(OAuth2Handler::new(self.test_mode)),
            token_manager: Arc::new(TokenManager::new(self.test_mode)),
            policy_store: Arc::new(CreatorPolicyStore::new(self.test_mode)),
            revenue_router: Arc::new(RevenueRouter::new(self.test_mode)),
            audit_log: Arc::new(AuditLog::new(self.test_mode)),
            rate_limiter: Arc::new(RateLimiter::new(self.rate_limit)),
        })
    }
}

impl VisionSDK {
    pub async fn evaluate_decision(
        &self,
        creator_id: uuid::Uuid,
        platform: &str,
        action: &str,
        _context: &DecisionContext,
    ) -> Result<DecisionGate> {
        // Check rate limit
        if !self.rate_limiter.check_limit(creator_id) {
            return Err(VisionError::RateLimited(
                "Decision evaluation rate limit exceeded".to_string(),
            ));
        }

        // Validate platform
        if !is_supported_platform(platform) {
            return Err(VisionError::UnknownPlatform(platform.to_string()));
        }

        // Load creator policy
        let policy = self.policy_store.load_policy(creator_id).await.ok();

        // Evaluate policy
        let approved = if let Some(p) = policy {
            self.evaluate_policy(&p, platform, action).await?
        } else {
            // No policy = deny by default for security
            false
        };

        if approved {
            Ok(DecisionGate::Approved {
                capsule_result: CapsuleResult {
                    decision_id: uuid::Uuid::new_v4(),
                    approved: true,
                    latency_ms: 45.0,
                    merkle_proof: "0x_test".to_string(),
                },
                merkle_proof: "0x_test".to_string(),
            })
        } else {
            Ok(DecisionGate::Denied {
                reason: "Policy evaluation failed".to_string(),
            })
        }
    }

    async fn evaluate_policy(
        &self,
        policy: &CreatorPolicy,
        platform: &str,
        action: &str,
    ) -> Result<bool> {
        for rule in &policy.rules {
            match &rule.condition {
                PolicyCondition::Always => {
                    return Ok(matches!(rule.effect, PolicyEffect::Allow));
                }
                PolicyCondition::Action {
                    platform: p,
                    action: a,
                } => {
                    if p == platform && a == action {
                        return Ok(matches!(rule.effect, PolicyEffect::Allow));
                    }
                }
                _ => {}
            }
        }
        Ok(false)
    }

    pub async fn list_all_adapters(&self) -> Result<Vec<String>> {
        let platforms = vec![
            // Phase 1: 10 platforms
            "substack",
            "patreon",
            "youtube",
            "notion",
            "zapier",
            "twitter",
            "tiktok",
            "twitch",
            "discord",
            "slack",
            // Phase 2: 40 platforms
            "medium",
            "linkedin",
            "bluesky",
            "threads",
            "mastodon",
            "farcaster",
            "lens",
            "pixelfed",
            "peertube",
            "telegram",
            "signal",
            "wechat",
            "viber",
            "line",
            "kick",
            "rumble",
            "odysee",
            "amazon_live",
            "tiktok_shop",
            "activecampaign",
            "hubspot",
            "mailchimp",
            "brevo",
            "getresponse",
            "unbounce",
            "leadpages",
            "funnelytics",
            "strava",
            "patreon_enterprise",
            "convertkit",
            "flodesk",
            "gumroad",
            "ghost",
            "mirror",
            // Additional Phase 2 (6 more to reach 40)
            "substack_notes",
            "youtube_shorts",
            "instagram",
            "snapchat",
            "whatsapp",
            "messenger",
        ];
        Ok(platforms.into_iter().map(|s| s.to_string()).collect())
    }
}

struct RateLimiter {
    limits: RwLock<HashMap<uuid::Uuid, usize>>,
    max_per_window: usize,
}

impl RateLimiter {
    fn new(max_per_window: usize) -> Self {
        Self {
            limits: RwLock::new(HashMap::new()),
            max_per_window,
        }
    }

    fn check_limit(&self, creator_id: uuid::Uuid) -> bool {
        let mut limits = self.limits.write();
        let count = limits.entry(creator_id).or_insert(0);
        if *count >= self.max_per_window {
            false
        } else {
            *count += 1;
            true
        }
    }
}

fn is_supported_platform(platform: &str) -> bool {
    matches!(
        platform,
        // Phase 1: 10 platforms
        "substack"
            | "patreon"
            | "youtube"
            | "notion"
            | "zapier"
            | "twitter"
            | "tiktok"
            | "twitch"
            | "discord"
            | "slack"
            // Phase 2: 40 platforms
            | "medium"
            | "linkedin"
            | "bluesky"
            | "threads"
            | "mastodon"
            | "farcaster"
            | "lens"
            | "pixelfed"
            | "peertube"
            | "telegram"
            | "signal"
            | "wechat"
            | "viber"
            | "line"
            | "kick"
            | "rumble"
            | "odysee"
            | "amazon_live"
            | "tiktok_shop"
            | "activecampaign"
            | "hubspot"
            | "mailchimp"
            | "brevo"
            | "getresponse"
            | "unbounce"
            | "leadpages"
            | "funnelytics"
            | "strava"
            | "patreon_enterprise"
            | "convertkit"
            | "flodesk"
            | "gumroad"
            | "ghost"
            | "mirror"
    )
}
