use super::PlatformAdapter;
use crate::{ActionDefinition, ActionResult, ActionStatus, PlatformAuth, Result};
use async_trait::async_trait;

pub struct TwitterAdapter;

impl Default for TwitterAdapter {
    fn default() -> Self {
        Self
    }
}

impl TwitterAdapter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn new_test() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PlatformAdapter for TwitterAdapter {
    fn platform_name(&self) -> &str {
        "twitter"
    }

    async fn authenticate(&self, _auth_token: &str) -> Result<PlatformAuth> {
        Ok(PlatformAuth {
            platform: "twitter".to_string(),
            user_id: "user_123".to_string(),
            access_token: "token_123".to_string(),
            refresh_token: None,
            scope: vec!["tweet.write".to_string()],
            expires_at: None,
        })
    }

    async fn list_actions(&self, _platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>> {
        Ok(vec![ActionDefinition {
            name: "post_tweet".to_string(),
            description: "Post a tweet".to_string(),
            required_params: vec!["text".to_string()],
            optional_params: vec!["media".to_string()],
            requires_approval: false,
            estimated_blast_radius: 0.2,
        }])
    }

    async fn execute_action(
        &self,
        _platform_auth: &PlatformAuth,
        action: &str,
        _params: serde_json::Value,
        _vision_api: Option<&crate::VisionSDK>,
    ) -> Result<ActionResult> {
        Ok(ActionResult {
            action: action.to_string(),
            status: ActionStatus::Success,
            response: serde_json::json!({"tweet_id": "123456"}),
            latency_ms: 100.0,
        })
    }

    async fn extract_value_signal(&self, _action_result: &ActionResult) -> Result<f64> {
        Ok(2.0) // Base value for Twitter engagement
    }
}
