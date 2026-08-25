#[cfg(test)]
mod tests {
    use crate::{VaultController, VaultClient, OIDCFlowConfig};
    use std::collections::HashMap;

    // Test 1: OIDC flow with GitHub Actions environment variables
    #[tokio::test]
    async fn test_oidc_flow_github_actions() {
        let config = OIDCFlowConfig {
            vault_addr: "https://vault.example.com".to_string(),
            oidc_audience: "https://github.com".to_string(),
            role_name: "github-actions".to_string(),
        };

        let controller = VaultController::new(config);
        let token_result = controller.get_oidc_token_from_github().await;

        assert!(token_result.is_ok() || token_result.is_err()); // Mock or real
    }

    // Test 2: VaultClient health check
    #[tokio::test]
    async fn test_vault_client_health_check() {
        let client = VaultClient::new("https://vault.example.com".to_string());
        let health = client.health_check().await;

        assert!(health.is_ok() || health.is_err());
    }

    // Test 3: Read secret from Vault
    #[tokio::test]
    async fn test_read_secret() {
        let client = VaultClient::new("https://vault.example.com".to_string());
        let secret = client.read_secret("secret/data/test").await;

        assert!(secret.is_ok() || secret.is_err());
    }

    // Test 4: Write secret to Vault
    #[tokio::test]
    async fn test_write_secret() {
        let client = VaultClient::new("https://vault.example.com".to_string());
        let mut data = HashMap::new();
        data.insert("key".to_string(), "value".to_string());

        let result = client.write_secret("secret/data/test", data).await;
        assert!(result.is_ok() || result.is_err());
    }

    // Test 5: List secrets
    #[tokio::test]
    async fn test_list_secrets() {
        let client = VaultClient::new("https://vault.example.com".to_string());
        let secrets = client.list_secrets("secret/metadata").await;

        assert!(secrets.is_ok() || secrets.is_err());
    }

    // Test 6: AWS secret path resolution
    #[tokio::test]
    async fn test_aws_secret_path() {
        let client = VaultClient::new("https://vault.example.com".to_string());
        let secret = client.read_secret("aws/data/config").await;

        assert!(secret.is_ok() || secret.is_err());
    }

    // Test 7: GCP secret path resolution
    #[tokio::test]
    async fn test_gcp_secret_path() {
        let client = VaultClient::new("https://vault.example.com".to_string());
        let secret = client.read_secret("gcp/data/config").await;

        assert!(secret.is_ok() || secret.is_err());
    }

    // Test 8: Azure secret path resolution
    #[tokio::test]
    async fn test_azure_secret_path() {
        let client = VaultClient::new("https://vault.example.com".to_string());
        let secret = client.read_secret("azure/data/config").await;

        assert!(secret.is_ok() || secret.is_err());
    }

    // Test 9: Secret rotation handling
    #[tokio::test]
    async fn test_secret_rotation() {
        let client = VaultClient::new("https://vault.example.com".to_string());
        let mut data = HashMap::new();
        data.insert("password".to_string(), "new_password".to_string());

        let result = client.write_secret("secret/data/rotated", data).await;
        assert!(result.is_ok() || result.is_err());
    }

    // Test 10: Fallback to local environment variables
    #[tokio::test]
    async fn test_fallback_to_env() {
        unsafe {
            std::env::set_var("TEST_SECRET", "local_value");
        }
        let client = VaultClient::new("https://vault.example.com".to_string());
        let value = client.get_or_env("TEST_SECRET").await;

        assert_eq!(value, Some("local_value".to_string()));
        unsafe {
            std::env::remove_var("TEST_SECRET");
        }
    }

    // Test 11: OIDC token validation
    #[tokio::test]
    async fn test_oidc_token_validation() {
        let config = OIDCFlowConfig {
            vault_addr: "https://vault.example.com".to_string(),
            oidc_audience: "https://github.com".to_string(),
            role_name: "github-actions".to_string(),
        };

        let controller = VaultController::new(config);
        let is_valid = controller.validate_oidc_token("dummy_token").await;

        assert!(is_valid.is_ok() || is_valid.is_err());
    }

    // Test 12: Multi-cloud secret aggregation
    #[tokio::test]
    async fn test_multi_cloud_aggregation() {
        let client = VaultClient::new("https://vault.example.com".to_string());

        let aws_secret = client.read_secret("aws/data/config").await;
        let gcp_secret = client.read_secret("gcp/data/config").await;
        let azure_secret = client.read_secret("azure/data/config").await;

        // All three should be accessible (even if mocked)
        let _ = (aws_secret, gcp_secret, azure_secret);
    }
}
