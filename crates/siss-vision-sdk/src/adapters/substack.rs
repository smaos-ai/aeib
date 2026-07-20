use super::PlatformAdapter;
use crate::{PlatformAuth, ActionResult, ActionStatus, ActionDefinition, Result};
use async_trait::async_trait;

pub struct SubstackAdapter {
    platform_name: String,
}

impl Default for SubstackAdapter {
    fn default() -> Self {
        Self {
            platform_name: "substack".to_string(),
        }
    }
}

impl SubstackAdapter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn new_test() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PlatformAdapter for SubstackAdapter {
    fn platform_name(&self) -> &str {
        &self.platform_name
    }

    async fn authenticate(&self, _auth_token: &str) -> Result<PlatformAuth> {
        Ok(PlatformAuth {
            platform: self.platform_name.clone(),
            user_id: "user_123".to_string(),
            access_token: "token_123".to_string(),
            refresh_token: None,
            scope: vec!["write:publication".to_string()],
            expires_at: None,
        })
    }

    async fn list_actions(&self, _platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>> {
        Ok(vec![
            ActionDefinition {
                name: "publish_newsletter".to_string(),
                description: "Publish a newsletter".to_string(),
                required_params: vec!["content".to_string()],
                optional_params: vec!["title".to_string()],
                requires_approval: false,
                estimated_blast_radius: 0.25,
            },
            ActionDefinition {
                name: "schedule_post".to_string(),
                description: "Schedule a future post".to_string(),
                required_params: vec!["content".to_string(), "publish_at".to_string()],
                optional_params: vec![],
                requires_approval: false,
                estimated_blast_radius: 0.15,
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
                "subscriber_count": 5000,
                "paid_subscribers": 500,
                "estimated_value": 50.0
            }),
            latency_ms: 150.0,
        })
    }

    async fn extract_value_signal(&self, action_result: &ActionResult) -> Result<f64> {
        let estimated_value = action_result
            .response
            .get("estimated_value")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        Ok(estimated_value)
    }
}
