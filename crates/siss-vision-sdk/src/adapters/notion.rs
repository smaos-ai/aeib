use super::PlatformAdapter;
use crate::{PlatformAuth, ActionResult, ActionStatus, ActionDefinition, Result};
use async_trait::async_trait;

pub struct NotionAdapter;

impl NotionAdapter {
    pub fn new() -> Self {
        Self
    }

    pub fn new_test() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PlatformAdapter for NotionAdapter {
    fn platform_name(&self) -> &str {
        "notion"
    }

    async fn authenticate(&self, _auth_token: &str) -> Result<PlatformAuth> {
        Ok(PlatformAuth {
            platform: "notion".to_string(),
            user_id: "user_123".to_string(),
            access_token: "token_123".to_string(),
            refresh_token: None,
            scope: vec!["databases".to_string()],
            expires_at: None,
        })
    }

    async fn list_actions(&self, _platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>> {
        Ok(vec![
            ActionDefinition {
                name: "create_page".to_string(),
                description: "Create database entry".to_string(),
                required_params: vec!["title".to_string()],
                optional_params: vec!["properties".to_string()],
                requires_approval: false,
                estimated_blast_radius: 0.1,
            },
            ActionDefinition {
                name: "update_database".to_string(),
                description: "Modify entries".to_string(),
                required_params: vec!["page_id".to_string()],
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
                "page_id": "abc123",
                "database_size": 100
            }),
            latency_ms: 180.0,
        })
    }

    async fn extract_value_signal(&self, _action_result: &ActionResult) -> Result<f64> {
        Ok(1.0) // Base value for Notion operations
    }
}
