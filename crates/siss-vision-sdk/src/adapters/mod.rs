pub mod substack;
pub mod patreon;
pub mod youtube;
pub mod notion;
pub mod zapier;
pub mod twitter;
pub mod tiktok;
pub mod twitch;
pub mod discord;
pub mod slack;

pub use substack::SubstackAdapter;
pub use patreon::PatreonAdapter;
pub use youtube::YoutubeAdapter;
pub use notion::NotionAdapter;
pub use zapier::ZapierAdapter;
pub use twitter::TwitterAdapter;
pub use tiktok::TiktokAdapter;
pub use twitch::TwitchAdapter;
pub use discord::DiscordAdapter;
pub use slack::SlackAdapter;

use crate::{PlatformAuth, ActionResult, Result, ActionDefinition};
use async_trait::async_trait;

#[async_trait]
pub trait PlatformAdapter: Send + Sync {
    fn platform_name(&self) -> &str;

    async fn authenticate(&self, auth_token: &str) -> Result<PlatformAuth>;

    async fn list_actions(&self, platform_auth: &PlatformAuth) -> Result<Vec<ActionDefinition>>;

    async fn execute_action(
        &self,
        platform_auth: &PlatformAuth,
        action: &str,
        params: serde_json::Value,
        vision_api: Option<&crate::VisionSDK>,
    ) -> Result<ActionResult>;

    async fn extract_value_signal(&self, action_result: &ActionResult) -> Result<f64>;

    async fn handle_error(&self, _error: &str) -> Result<String> {
        Ok("Error handled gracefully".to_string())
    }
}
