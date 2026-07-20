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
pub mod medium;
pub mod linkedin;
pub mod bluesky;
pub mod threads;
pub mod mastodon;
pub mod farcaster;
pub mod lens;
pub mod pixelfed;
pub mod peertube;
pub mod telegram;
pub mod signal;
pub mod wechat;
pub mod viber;
pub mod line;
pub mod kick;
pub mod rumble;
pub mod odysee;
pub mod amazon_live;
pub mod tiktok_shop;
pub mod activecampaign;
pub mod hubspot;
pub mod mailchimp;
pub mod brevo;
pub mod getresponse;
pub mod unbounce;
pub mod leadpages;
pub mod funnelytics;
pub mod strava;
pub mod patreon_enterprise;
pub mod convertkit;
pub mod flodesk;
pub mod gumroad;
pub mod ghost;
pub mod mirror;

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
pub use medium::MediumAdapter;
pub use linkedin::LinkedinAdapter;
pub use bluesky::BlueskyAdapter;
pub use threads::ThreadsAdapter;
pub use mastodon::MastodonAdapter;
pub use farcaster::FarcasterAdapter;
pub use lens::LensProtocolAdapter;
pub use pixelfed::PixelfedAdapter;
pub use peertube::PeertubeAdapter;
pub use telegram::TelegramAdapter;
pub use signal::SignalAdapter;
pub use wechat::WechatAdapter;
pub use viber::ViberAdapter;
pub use line::LineAdapter;
pub use kick::KickAdapter;
pub use rumble::RumbleAdapter;
pub use odysee::OdyseeAdapter;
pub use amazon_live::AmazonLiveAdapter;
pub use tiktok_shop::TiktokShopAdapter;
pub use activecampaign::ActiveCampaignAdapter;
pub use hubspot::HubspotAdapter;
pub use mailchimp::MailchimpAdapter;
pub use brevo::BrevoAdapter;
pub use getresponse::GetResponseAdapter;
pub use unbounce::UnbounceAdapter;
pub use leadpages::LeadpagesAdapter;
pub use funnelytics::FunnelyticsAdapter;
pub use strava::StravaAdapter;
pub use patreon_enterprise::PatreonEnterpriseAdapter;
pub use convertkit::ConvertKitAdapter;
pub use flodesk::FlodeskAdapter;
pub use gumroad::GumroadAdapter;
pub use ghost::GhostAdapter;
pub use mirror::MirrorAdapter;

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
