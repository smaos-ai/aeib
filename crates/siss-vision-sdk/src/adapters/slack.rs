use super::PlatformAdapter;
use crate::{ActionDefinition, ActionResult, ActionStatus, PlatformAuth, Result};
use async_trait::async_trait;

pub struct SlackAdapter;

impl Default for SlackAdapter {
    fn default() -> Self {
        Self
    }
}

impl SlackAdapter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn new_test() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PlatformAdapter for SlackAdapter {
    fn platform_name(&self) -> &str {
        "slack"
    }

    async fn authenticate(&self, _auth_token: &str) -> Result<PlatformAuth> {
        Ok(PlatformAuth {
            platform: "slack".to_string(),
            user_id: "user_123".to_string(),
            access_token: "token_123".to_string(),
            refresh_token: None,
            scope: vec!["workflows.triggers:write".to_string()],
            expires_at: None,
        })
    }

    async fn list_actions(&self, _platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>> {
        Ok(vec![ActionDefinition {
            name: "post_message".to_string(),
            description: "Post message to channel".to_string(),
            required_params: vec!["channel".to_string(), "text".to_string()],
            optional_params: vec![],
            requires_approval: false,
            estimated_blast_radius: 0.1,
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
            response: serde_json::json!({"ts": "1234567890.000100"}),
            latency_ms: 90.0,
        })
    }

    async fn extract_value_signal(&self, _action_result: &ActionResult) -> Result<f64> {
        Ok(0.5) // Base value for Slack messages
    }
}
