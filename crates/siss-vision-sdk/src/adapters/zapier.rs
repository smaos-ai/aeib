use super::PlatformAdapter;
use crate::{PlatformAuth, ActionResult, ActionStatus, ActionDefinition, Result};
use async_trait::async_trait;

pub struct ZapierAdapter;

impl ZapierAdapter {
    pub fn new() -> Self {
        Self
    }

    pub fn new_test() -> Self {
        Self::new()
    }
}

#[async_trait]
impl PlatformAdapter for ZapierAdapter {
    fn platform_name(&self) -> &str {
        "zapier"
    }

    async fn authenticate(&self, _auth_token: &str) -> Result<PlatformAuth> {
        Ok(PlatformAuth {
            platform: "zapier".to_string(),
            user_id: "user_123".to_string(),
            access_token: "token_123".to_string(),
            refresh_token: None,
            scope: vec!["zaps".to_string()],
            expires_at: None,
        })
    }

    async fn list_actions(&self, _platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>> {
        Ok(vec![
            ActionDefinition {
                name: "trigger_workflow".to_string(),
                description: "Execute automation workflow".to_string(),
                required_params: vec!["workflow_id".to_string()],
                optional_params: vec![],
                requires_approval: false,
                estimated_blast_radius: 0.3,
            },
            ActionDefinition {
                name: "create_workflow".to_string(),
                description: "Define new Zap".to_string(),
                required_params: vec!["trigger".to_string(), "action".to_string()],
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
                "task_count": 50,
                "executions": 10
            }),
            latency_ms: 200.0,
        })
    }

    async fn extract_value_signal(&self, action_result: &ActionResult) -> Result<f64> {
        let task_count = action_result
            .response
            .get("task_count")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        Ok(task_count * 0.1) // 10 cents per task
    }
}
