use super::PlatformAdapter;
use crate::{PlatformAuth, ActionResult, ActionStatus, ActionDefinition, Result};
use async_trait::async_trait;

pub struct LeadpagesAdapter {
    platform_name: String,
}

impl Default for LeadpagesAdapter {
    fn default() -> Self {
        Self {
            platform_name: "leadpages".to_string(),
        }
    }
}

impl LeadpagesAdapter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn new_test() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PlatformAdapter for LeadpagesAdapter {
    fn platform_name(&self) -> &str {
        &self.platform_name
    }

    async fn authenticate(&self, _auth_token: &str) -> Result<PlatformAuth> {
        Ok(PlatformAuth {
            platform: self.platform_name.clone(),
            user_id: format!("user_{}_001", self.platform_name),
            access_token: format!("token_{}", self.platform_name),
            refresh_token: Some(format!("refresh_{}", self.platform_name)),
            scope: vec!["write".to_string()],
            expires_at: None,
        })
    }

    async fn list_actions(&self, _platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>> {
        Ok(vec![ActionDefinition {
            name: "publish".to_string(),
            description: format!("Publish content to {}", self.platform_name),
            required_params: vec!["content".to_string()],
            optional_params: vec![],
            requires_approval: false,
            estimated_blast_radius: 0.25,
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
            response: serde_json::json!({
                "platform": self.platform_name,
                "estimated_value": 50.0
            }),
            latency_ms: 150.0,
        })
    }

    async fn extract_value_signal(&self, action_result: &ActionResult) -> Result<f64> {
        Ok(action_result
            .response
            .get("estimated_value")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0))
    }
}
