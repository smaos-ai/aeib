use super::PlatformAdapter;
use crate::{PlatformAuth, ActionResult, ActionStatus, ActionDefinition, Result};
use async_trait::async_trait;

pub struct TwitchAdapter;

impl TwitchAdapter {
    pub fn new() -> Self {
        Self
    }

    pub fn new_test() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PlatformAdapter for TwitchAdapter {
    fn platform_name(&self) -> &str {
        "twitch"
    }

    async fn authenticate(&self, _auth_token: &str) -> Result<PlatformAuth> {
        Ok(PlatformAuth {
            platform: "twitch".to_string(),
            user_id: "user_123".to_string(),
            access_token: "token_123".to_string(),
            refresh_token: None,
            scope: vec!["moderation:read".to_string()],
            expires_at: None,
        })
    }

    async fn list_actions(&self, _platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>> {
        Ok(vec![
            ActionDefinition {
                name: "start_stream".to_string(),
                description: "Start streaming".to_string(),
                required_params: vec!["title".to_string()],
                optional_params: vec!["category".to_string()],
                requires_approval: false,
                estimated_blast_radius: 0.4,
            },
        ])
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
            response: serde_json::json!({"stream_id": "stream_123"}),
            latency_ms: 120.0,
        })
    }

    async fn extract_value_signal(&self, _action_result: &ActionResult) -> Result<f64> {
        Ok(5.0) // Base value for Twitch streams
    }
}
