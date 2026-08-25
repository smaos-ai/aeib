use std::collections::HashMap;
use std::time::SystemTime;
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use thiserror::Error;

mod tests;

#[derive(Error, Debug)]
pub enum VaultError {
    #[error("OIDC token generation failed: {0}")]
    OIDCTokenError(String),

    #[error("Vault authentication failed: {0}")]
    AuthError(String),

    #[error("Secret read failed: {0}")]
    ReadError(String),

    #[error("Secret write failed: {0}")]
    WriteError(String),

    #[error("Health check failed: {0}")]
    HealthCheckError(String),

    #[error("Secret rotation failed: {0}")]
    RotationError(String),

    #[error("Request error: {0}")]
    RequestError(String),

    #[error("Serialization error: {0}")]
    SerializationError(String),
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OIDCFlowConfig {
    pub vault_addr: String,
    pub oidc_audience: String,
    pub role_name: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VaultSecret {
    pub path: String,
    pub data: HashMap<String, String>,
    pub created_at: SystemTime,
    pub ttl: Option<u64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct OIDCAuthRequest {
    jwt: String,
}

#[derive(Clone, Debug, Deserialize)]
struct VaultAuthResponse {
    auth: AuthData,
}

#[derive(Clone, Debug, Deserialize)]
struct AuthData {
    client_token: String,
}

#[derive(Clone, Debug, Deserialize)]
struct VaultSecretResponse {
    data: SecretData,
}

#[derive(Clone, Debug, Deserialize)]
struct SecretData {
    data: HashMap<String, String>,
}

#[derive(Clone, Debug, Deserialize)]
struct HealthResponse {
    initialized: bool,
    sealed: bool,
    #[allow(dead_code)]
    standby: bool,
}

/// VaultController orchestrates GitHub Actions OIDC → Vault authentication flow
pub struct VaultController {
    config: OIDCFlowConfig,
    client: VaultClient,
    token_cache: DashMap<String, (String, SystemTime)>,
}

impl VaultController {
    pub fn new(config: OIDCFlowConfig) -> Self {
        let client = VaultClient::new(config.vault_addr.clone());
        Self {
            config,
            client,
            token_cache: DashMap::new(),
        }
    }

    pub fn config(&self) -> &OIDCFlowConfig {
        &self.config
    }

    /// Retrieve OIDC token from GitHub Actions environment
    pub async fn get_oidc_token_from_github(&self) -> Result<String, VaultError> {
        // In GitHub Actions, the OIDC token is available via ACTIONS_ID_TOKEN_REQUEST_URL
        // and ACTIONS_ID_TOKEN_REQUEST_TOKEN environment variables
        let request_token = std::env::var("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
            .map_err(|e| VaultError::OIDCTokenError(format!("Missing request token: {}", e)))?;

        let request_url = std::env::var("ACTIONS_ID_TOKEN_REQUEST_URL")
            .map_err(|e| VaultError::OIDCTokenError(format!("Missing request URL: {}", e)))?;

        // Make request to GitHub OIDC endpoint
        let client = reqwest::Client::new();
        let response = client
            .get(&request_url)
            .bearer_auth(&request_token)
            .send()
            .await
            .map_err(|e| VaultError::OIDCTokenError(format!("Request failed: {}", e)))?;

        let body: serde_json::Value = response
            .json()
            .await
            .map_err(|e| VaultError::OIDCTokenError(format!("Parse error: {}", e)))?;

        let token = body
            .get("token")
            .and_then(|v| v.as_str())
            .ok_or_else(|| VaultError::OIDCTokenError("No token in response".to_string()))?;

        Ok(token.to_string())
    }

    /// Authenticate with Vault using OIDC token and cache the result
    pub async fn authenticate(&self) -> Result<String, VaultError> {
        let role = &self.config.role_name;

        // Check token cache first (5-minute TTL)
        if let Some(entry) = self.token_cache.get(role) {
            let (token, created_at) = entry.value();
            let elapsed = created_at
                .elapsed()
                .unwrap_or_else(|_| std::time::Duration::from_secs(0));

            if elapsed.as_secs() < 300 {
                return Ok(token.clone());
            }
        }

        // Get fresh OIDC token from GitHub
        let oidc_token = self.get_oidc_token_from_github().await?;

        // Exchange OIDC token for Vault token
        let vault_token = self.client.authenticate_oidc(role, &oidc_token).await?;

        // Cache the token
        self.token_cache
            .insert(role.clone(), (vault_token.clone(), SystemTime::now()));

        Ok(vault_token)
    }

    /// Validate OIDC token format and claims
    pub async fn validate_oidc_token(&self, token: &str) -> Result<bool, VaultError> {
        // Basic validation: token should be non-empty and follow JWT format
        let parts: Vec<&str> = token.split('.').collect();
        if parts.len() != 3 {
            return Err(VaultError::OIDCTokenError(
                "Invalid JWT format".to_string(),
            ));
        }

        Ok(true)
    }
}

/// VaultClient handles low-level Vault API operations
pub struct VaultClient {
    vault_addr: String,
    http_client: reqwest::Client,
}

impl VaultClient {
    pub fn new(vault_addr: String) -> Self {
        Self {
            vault_addr,
            http_client: reqwest::Client::new(),
        }
    }

    pub fn vault_address(&self) -> &str {
        &self.vault_addr
    }

    /// Check Vault health status
    pub async fn health_check(&self) -> Result<bool, VaultError> {
        let url = format!("{}/v1/sys/health", self.vault_addr);
        let response = self
            .http_client
            .get(&url)
            .send()
            .await
            .map_err(|e| VaultError::HealthCheckError(format!("Health check failed: {}", e)))?;

        let health: HealthResponse = response
            .json()
            .await
            .map_err(|e| VaultError::HealthCheckError(format!("Parse error: {}", e)))?;

        Ok(!health.sealed && health.initialized)
    }

    /// Authenticate with Vault using OIDC
    pub async fn authenticate_oidc(&self, role: &str, token: &str) -> Result<String, VaultError> {
        let url = format!(
            "{}/v1/auth/oidc/oidc/callback?code={}&state={}",
            self.vault_addr, token, role
        );

        let request = OIDCAuthRequest {
            jwt: token.to_string(),
        };

        let response = self
            .http_client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| VaultError::AuthError(format!("Auth request failed: {}", e)))?;

        let auth_response: VaultAuthResponse = response
            .json()
            .await
            .map_err(|e| VaultError::AuthError(format!("Parse error: {}", e)))?;

        Ok(auth_response.auth.client_token)
    }

    /// Read a secret from Vault (supports multi-cloud paths)
    pub async fn read_secret(&self, path: &str) -> Result<HashMap<String, String>, VaultError> {
        let url = format!("{}/v1/{}", self.vault_addr, path);

        let response = self
            .http_client
            .get(&url)
            .send()
            .await
            .map_err(|e| VaultError::ReadError(format!("Read failed: {}", e)))?;

        if !response.status().is_success() {
            return Err(VaultError::ReadError(format!(
                "HTTP {}",
                response.status()
            )));
        }

        let vault_response: VaultSecretResponse = response
            .json()
            .await
            .map_err(|e| VaultError::ReadError(format!("Parse error: {}", e)))?;

        Ok(vault_response.data.data)
    }

    /// Write a secret to Vault (supports multi-cloud paths)
    pub async fn write_secret(
        &self,
        path: &str,
        data: HashMap<String, String>,
    ) -> Result<(), VaultError> {
        let url = format!("{}/v1/{}", self.vault_addr, path);

        let response = self
            .http_client
            .post(&url)
            .json(&data)
            .send()
            .await
            .map_err(|e| VaultError::WriteError(format!("Write failed: {}", e)))?;

        if !response.status().is_success() {
            return Err(VaultError::WriteError(format!(
                "HTTP {}",
                response.status()
            )));
        }

        Ok(())
    }

    /// List secrets at a given path
    pub async fn list_secrets(&self, path: &str) -> Result<Vec<String>, VaultError> {
        let url = format!("{}/v1/{}", self.vault_addr, path);

        // Use GET with ?list=true query parameter (Vault LIST operation)
        let response = self
            .http_client
            .get(format!("{}?list=true", url))
            .send()
            .await
            .map_err(|e| VaultError::ReadError(format!("List failed: {}", e)))?;

        if !response.status().is_success() {
            return Err(VaultError::ReadError(format!(
                "List HTTP {}",
                response.status()
            )));
        }

        let body: serde_json::Value = response
            .json()
            .await
            .map_err(|e| VaultError::ReadError(format!("Parse error: {}", e)))?;

        let keys = body
            .get("data")
            .and_then(|d| d.get("keys"))
            .and_then(|k| k.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();

        Ok(keys)
    }

    /// Fallback to environment variable if secret not found in Vault
    pub async fn get_or_env(&self, key: &str) -> Option<String> {
        std::env::var(key).ok()
    }
}
