pub mod ws_agent_feed;

pub use ws_agent_feed::{AgentFeed, AgentFeedMessage, FeedStats};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_api_exports() {
        // Verify all public types are accessible
        let _feed = AgentFeed::new();
    }
}
