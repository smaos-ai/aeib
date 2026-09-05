pub mod activecampaign;
pub mod amazon_live;
pub mod bluesky;
pub mod brevo;
pub mod convertkit;
pub mod discord;
pub mod farcaster;
pub mod flodesk;
pub mod funnelytics;
pub mod getresponse;
pub mod ghost;
pub mod gumroad;
pub mod hubspot;
pub mod kick;
pub mod leadpages;
pub mod lens;
pub mod line;
pub mod linkedin;
pub mod mailchimp;
pub mod mastodon;
pub mod medium;
pub mod mirror;
pub mod notion;
pub mod odysee;
pub mod patreon;
pub mod patreon_enterprise;
pub mod peertube;
pub mod pixelfed;
pub mod rumble;
pub mod signal;
pub mod slack;
pub mod strava;
pub mod substack;
pub mod telegram;
pub mod threads;
pub mod tiktok;
pub mod tiktok_shop;
pub mod twitch;
pub mod twitter;
pub mod unbounce;
pub mod viber;
pub mod wechat;
pub mod youtube;
pub mod zapier;

pub use activecampaign::ActiveCampaignAdapter;
pub use amazon_live::AmazonLiveAdapter;
pub use bluesky::BlueskyAdapter;
pub use brevo::BrevoAdapter;
pub use convertkit::ConvertKitAdapter;
pub use discord::DiscordAdapter;
pub use farcaster::FarcasterAdapter;
pub use flodesk::FlodeskAdapter;
pub use funnelytics::FunnelyticsAdapter;
pub use getresponse::GetResponseAdapter;
pub use ghost::GhostAdapter;
pub use gumroad::GumroadAdapter;
pub use hubspot::HubspotAdapter;
pub use kick::KickAdapter;
pub use leadpages::LeadpagesAdapter;
pub use lens::LensProtocolAdapter;
pub use line::LineAdapter;
pub use linkedin::LinkedinAdapter;
pub use mailchimp::MailchimpAdapter;
pub use mastodon::MastodonAdapter;
pub use medium::MediumAdapter;
pub use mirror::MirrorAdapter;
pub use notion::NotionAdapter;
pub use odysee::OdyseeAdapter;
pub use patreon::PatreonAdapter;
pub use patreon_enterprise::PatreonEnterpriseAdapter;
pub use peertube::PeertubeAdapter;
pub use pixelfed::PixelfedAdapter;
pub use rumble::RumbleAdapter;
pub use signal::SignalAdapter;
pub use slack::SlackAdapter;
pub use strava::StravaAdapter;
pub use substack::SubstackAdapter;
pub use telegram::TelegramAdapter;
pub use threads::ThreadsAdapter;
pub use tiktok::TiktokAdapter;
pub use tiktok_shop::TiktokShopAdapter;
pub use twitch::TwitchAdapter;
pub use twitter::TwitterAdapter;
pub use unbounce::UnbounceAdapter;
pub use viber::ViberAdapter;
pub use wechat::WechatAdapter;
pub use youtube::YoutubeAdapter;
pub use zapier::ZapierAdapter;

use crate::{ActionDefinition, ActionResult, PlatformAuth, Result};
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
