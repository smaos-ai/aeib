pub mod api;

pub use api::{AgentFeed, AgentFeedMessage, FeedStats};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_command_center_exports() {
        // Verify all public types are accessible
        let _feed = AgentFeed::new();
    }
}
