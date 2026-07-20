use crate::{OAuth2Token, VisionError, Result};
use uuid::Uuid;
use std::collections::HashMap;
use parking_lot::RwLock;
use chrono::{Duration, Utc};

pub struct OAuth2Handler {
    test_mode: bool,
    client_id: String,
    client_secret: String,
}

impl OAuth2Handler {
    pub fn new(test_mode: bool) -> Self {
        Self {
            test_mode,
            client_id: "test_client_id".to_string(),
            client_secret: "test_client_secret".to_string(),
        }
    }

    pub async fn acquire_token(
        &self,
        platform: &str,
        code: &str,
        _state: &str,
    ) -> Result<OAuth2Token> {
        if self.test_mode {
            return Ok(OAuth2Token {
                access_token: format!("access_{}", uuid::Uuid::new_v4()),
                refresh_token: Some(format!("refresh_{}", uuid::Uuid::new_v4())),
                platform: platform.to_string(),
                expires_at: Some(Utc::now() + Duration::hours(1)),
                scope: vec!["read".to_string(), "write".to_string()],
            });
        }

        // Real OAuth2 flow would go here
        Err(VisionError::AuthError("Not implemented in production yet".to_string()))
    }

    pub async fn refresh_token(&self, refresh_token: &str) -> Result<OAuth2Token> {
        if self.test_mode {
            return Ok(OAuth2Token {
                access_token: format!("access_{}", uuid::Uuid::new_v4()),
                refresh_token: Some(refresh_token.to_string()),
                platform: "test".to_string(),
                expires_at: Some(Utc::now() + Duration::hours(1)),
                scope: vec!["read".to_string()],
            });
        }

        Err(VisionError::AuthError(
            "Refresh token failed".to_string(),
        ))
    }
}

pub struct TokenManager {
    test_mode: bool,
    cache: RwLock<HashMap<String, OAuth2Token>>,
}

impl TokenManager {
    pub fn new(test_mode: bool) -> Self {
        Self {
            test_mode,
            cache: RwLock::new(HashMap::new()),
        }
    }

    pub async fn store_token(
        &self,
        creator_id: Uuid,
        platform: &str,
        token: &OAuth2Token,
    ) -> Result<()> {
        let key = format!("{}_{}", creator_id, platform);
        self.cache.write().insert(key, token.clone());
        Ok(())
    }

    pub async fn retrieve_token(
        &self,
        creator_id: Uuid,
        platform: &str,
    ) -> Result<OAuth2Token> {
        let key = format!("{}_{}", creator_id, platform);

        // Check cache
        {
            let cache = self.cache.read();
            if let Some(token) = cache.get(&key) {
                // Check if expired
                if let Some(expires_at) = token.expires_at {
                    if expires_at > Utc::now() {
                        return Ok(token.clone());
                    }
                }
            }
        }

        // If expired or missing, create a new test token
        if self.test_mode {
            let new_token = OAuth2Token {
                access_token: format!("access_{}", uuid::Uuid::new_v4()),
                refresh_token: Some(format!("refresh_{}", uuid::Uuid::new_v4())),
                platform: platform.to_string(),
                expires_at: Some(Utc::now() + Duration::hours(1)),
                scope: vec!["read".to_string()],
            };
            self.cache.write().insert(key, new_token.clone());
            Ok(new_token)
        } else {
            Err(VisionError::TokenError("Token not found".to_string()))
        }
    }

    pub async fn revoke_token(
        &self,
        creator_id: Uuid,
        platform: &str,
    ) -> Result<()> {
        let key = format!("{}_{}", creator_id, platform);
        self.cache.write().remove(&key);
        Ok(())
    }
}
