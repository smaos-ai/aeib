use super::PlatformAdapter;
use crate::{ActionDefinition, ActionResult, ActionStatus, PlatformAuth, Result};
use async_trait::async_trait;

pub struct YoutubeAdapter;

impl Default for YoutubeAdapter {
    fn default() -> Self {
        Self
    }
}

impl YoutubeAdapter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn new_test() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PlatformAdapter for YoutubeAdapter {
    fn platform_name(&self) -> &str {
        "youtube"
    }

    async fn authenticate(&self, _auth_token: &str) -> Result<PlatformAuth> {
        Ok(PlatformAuth {
            platform: "youtube".to_string(),
            user_id: "channel_123".to_string(),
            access_token: "token_123".to_string(),
            refresh_token: None,
            scope: vec!["https://www.googleapis.com/auth/youtube".to_string()],
            expires_at: None,
        })
    }

    async fn list_actions(&self, _platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>> {
        Ok(vec![
            ActionDefinition {
                name: "publish_video".to_string(),
                description: "Publish video".to_string(),
                required_params: vec!["title".to_string(), "description".to_string()],
                optional_params: vec!["tags".to_string()],
                requires_approval: false,
                estimated_blast_radius: 0.4,
            },
            ActionDefinition {
                name: "enable_monetization".to_string(),
                description: "Configure ad settings".to_string(),
                required_params: vec![],
                optional_params: vec![],
                requires_approval: true,
                estimated_blast_radius: 0.5,
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
            response: serde_json::json!({
                "view_count": 10000,
                "watch_time_hours": 5000,
                "estimated_revenue": 50.0
            }),
            latency_ms: 250.0,
        })
    }

    async fn extract_value_signal(&self, action_result: &ActionResult) -> Result<f64> {
        let estimated_revenue = action_result
            .response
            .get("estimated_revenue")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        Ok(estimated_revenue)
    }
}
