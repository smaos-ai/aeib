pub mod key_rotation;
pub mod session_manager;
pub mod trust_boundary;

pub use key_rotation::{KeyRotationEngine, RotationProof, RotationSchedule};
pub use session_manager::{SessionKey, SessionManager, SessionToken};
pub use trust_boundary::{AccessDecision, TrustBoundary, TrustContext};

#[derive(Debug, Clone)]
pub struct ZeroTrustConfig {
    pub key_rotation_interval_secs: u64,
    pub session_timeout_secs: u64,
    pub max_concurrent_sessions: usize,
    pub enable_replay_protection: bool,
}

impl Default for ZeroTrustConfig {
    fn default() -> Self {
        Self {
            key_rotation_interval_secs: 86400, // 24 hours
            session_timeout_secs: 3600,        // 1 hour
            max_concurrent_sessions: 1000,
            enable_replay_protection: true,
        }
    }
}
