use chrono::{DateTime, Utc};
use hex;
use rand::Rng;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::Arc;
use thiserror::Error;
use tokio::sync::RwLock;
use uuid::Uuid;

use crate::ZeroTrustConfig;

#[derive(Debug, Clone)]
pub struct SessionKey {
    pub id: String,
    pub nonce: Vec<u8>,
    pub created_at: DateTime<Utc>,
}

impl SessionKey {
    pub fn is_valid(&self) -> bool {
        !self.id.is_empty() && !self.nonce.is_empty()
    }
}

#[derive(Debug, Clone)]
pub struct SessionToken {
    pub token: String,
    pub session_key_id: String,
    pub nonce: Vec<u8>,
    pub created_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
}

#[derive(Debug, Error)]
pub enum SessionError {
    #[error("Session generation failed: {0}")]
    GenerationFailed(String),
    #[error("Token validation failed: {0}")]
    ValidationFailed(String),
    #[error("Session expired")]
    SessionExpired,
}

struct SessionEntry {
    key: SessionKey,
    #[allow(dead_code)]
    used_nonces: Vec<Vec<u8>>,
}

pub struct SessionManager {
    config: ZeroTrustConfig,
    active_sessions: Arc<RwLock<HashMap<String, SessionEntry>>>,
    nonce_cache: Arc<RwLock<Vec<Vec<u8>>>>,
}

impl SessionManager {
    pub fn new(config: ZeroTrustConfig) -> Self {
        Self {
            config,
            active_sessions: Arc::new(RwLock::new(HashMap::new())),
            nonce_cache: Arc::new(RwLock::new(Vec::new())),
        }
    }

    pub async fn generate_session_key(&self) -> Result<SessionKey, SessionError> {
        let id = Uuid::new_v4().to_string();
        let mut rng = rand::thread_rng();
        let nonce: Vec<u8> = (0..32).map(|_| rng.r#gen()).collect();

        let key = SessionKey {
            id: id.clone(),
            nonce: nonce.clone(),
            created_at: Utc::now(),
        };

        let mut sessions = self.active_sessions.write().await;
        sessions.insert(
            id,
            SessionEntry {
                key: key.clone(),
                used_nonces: vec![],
            },
        );

        Ok(key)
    }

    pub async fn create_token(&self, session_key: &SessionKey) -> Result<String, SessionError> {
        let mut hasher = Sha256::new();
        hasher.update(&session_key.nonce);
        hasher.update(session_key.created_at.to_rfc3339().as_bytes());

        let hash = hasher.finalize();
        let token = format!("token_{}", hex::encode(hash));

        Ok(token)
    }

    pub async fn validate_token(&self, token: &str) -> Result<bool, SessionError> {
        if token.is_empty() {
            return Err(SessionError::ValidationFailed("Empty token".to_string()));
        }

        // Check if token exists and hasn't expired
        let sessions = self.active_sessions.read().await;

        // Find session containing this token
        for (_, entry) in sessions.iter() {
            // Recreate token hash to verify
            let mut hasher = Sha256::new();
            hasher.update(&entry.key.nonce);
            hasher.update(entry.key.created_at.to_rfc3339().as_bytes());

            let hash = hasher.finalize();
            let expected_token = format!("token_{}", hex::encode(hash));

            if token == &expected_token {
                // Record this token in the replay cache
                let mut nonce_cache = self.nonce_cache.write().await;
                let mut hasher = Sha256::new();
                hasher.update(token.as_bytes());
                let token_hash = hex::encode(hasher.finalize());
                let token_bytes = token_hash.as_bytes().to_vec();

                if !nonce_cache.contains(&token_bytes) {
                    nonce_cache.push(token_bytes);
                }

                return Ok(true);
            }
        }

        Err(SessionError::ValidationFailed(
            "Token not found in active sessions".to_string(),
        ))
    }

    pub async fn is_replay_attack(&self, token: &str) -> Result<bool, SessionError> {
        let mut nonce_cache = self.nonce_cache.write().await;

        // Use full token as replay detection key via SHA256
        let mut hasher = Sha256::new();
        hasher.update(token.as_bytes());
        let token_hash = hex::encode(hasher.finalize());
        let token_bytes = token_hash.as_bytes().to_vec();

        if nonce_cache.contains(&token_bytes) {
            return Ok(true); // Replay detected
        }

        nonce_cache.push(token_bytes);

        // Keep cache size bounded
        if nonce_cache.len() > 10000 {
            nonce_cache.remove(0);
        }

        Ok(false)
    }

    pub async fn is_expired(&self, token: &str) -> Result<bool, SessionError> {
        let sessions = self.active_sessions.read().await;

        for (_, entry) in sessions.iter() {
            let mut hasher = Sha256::new();
            hasher.update(&entry.key.nonce);
            hasher.update(entry.key.created_at.to_rfc3339().as_bytes());

            let hash = hasher.finalize();
            let expected_token = format!("token_{}", hex::encode(hash));

            if token == &expected_token {
                let now = Utc::now();
                let expiry = entry.key.created_at
                    + chrono::Duration::seconds(self.config.session_timeout_secs as i64);

                return Ok(now > expiry);
            }
        }

        Err(SessionError::ValidationFailed(
            "Token not found".to_string(),
        ))
    }
}
