use super::PlatformAdapter;
use crate::{PlatformAuth, ActionResult, ActionStatus, ActionDefinition, Result};
use async_trait::async_trait;

pub struct MediumAdapter {
    platform_name: String,
}

impl Default for MediumAdapter {
    fn default() -> Self {
        Self {
            platform_name: "medium".to_string(),
        }
    }
}

impl MediumAdapter {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn new_test() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PlatformAdapter for MediumAdapter {
    fn platform_name(&self) -> &str {
        &self.platform_name
    }

    async fn authenticate(&self, _auth_token: &str) -> Result<PlatformAuth> {
        Ok(PlatformAuth {
            platform: self.platform_name.clone(),
            user_id: "user_medium_001".to_string(),
            access_token: "token_medium".to_string(),
            refresh_token: Some("refresh_medium".to_string()),
            scope: vec!["write_article".to_string()],
            expires_at: None,
        })
    }

    async fn list_actions(&self, _platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>> {
        Ok(vec![
            ActionDefinition {
                name: "publish_article".to_string(),
                description: "Publish an article to Medium".to_string(),
                required_params: vec!["content".to_string()],
                optional_params: vec!["title".to_string(), "tags".to_string()],
                requires_approval: false,
                estimated_blast_radius: 0.35,
            },
            ActionDefinition {
                name: "sync_earnings".to_string(),
                description: "Sync earnings from Member Program".to_string(),
                required_params: vec![],
                optional_params: vec![],
                requires_approval: false,
                estimated_blast_radius: 0.0,
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
                "article_id": "abc123",
                "claps": 2500,
                "estimated_earnings": 75.50,
                "member_earnings_pool_pct": 15.5
            }),
            latency_ms: 200.0,
        })
    }

    async fn extract_value_signal(&self, action_result: &ActionResult) -> Result<f64> {
        Ok(action_result
            .response
            .get("estimated_earnings")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0))
    }
}
