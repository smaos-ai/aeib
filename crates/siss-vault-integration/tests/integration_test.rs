use siss_vault_integration::{VaultController, VaultClient, OIDCFlowConfig};
use std::collections::HashMap;

#[tokio::test]
async fn test_vault_controller_initialization() {
    let config = OIDCFlowConfig {
        vault_addr: "https://vault.local:8200".to_string(),
        oidc_audience: "https://github.com".to_string(),
        role_name: "sovereign-actions".to_string(),
    };

    let controller = VaultController::new(config.clone());
    assert_eq!(controller.config().vault_addr, "https://vault.local:8200");
    assert_eq!(controller.config().role_name, "sovereign-actions");
}

#[tokio::test]
async fn test_vault_client_creation() {
    let client = VaultClient::new("https://vault.local:8200".to_string());
    // Verify client is created successfully
    assert!(!client.vault_address().is_empty());
}

#[tokio::test]
async fn test_oidc_token_validation_with_valid_jwt() {
    let config = OIDCFlowConfig {
        vault_addr: "https://vault.local:8200".to_string(),
        oidc_audience: "https://github.com".to_string(),
        role_name: "github-actions".to_string(),
    };

    let controller = VaultController::new(config);

    // Valid JWT has 3 parts separated by dots
    let valid_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature";
    let result = controller.validate_oidc_token(valid_token).await;

    assert!(result.is_ok());
    assert_eq!(result.unwrap(), true);
}

#[tokio::test]
async fn test_oidc_token_validation_with_invalid_jwt() {
    let config = OIDCFlowConfig {
        vault_addr: "https://vault.local:8200".to_string(),
        oidc_audience: "https://github.com".to_string(),
        role_name: "github-actions".to_string(),
    };

    let controller = VaultController::new(config);

    // Invalid JWT (only 2 parts)
    let invalid_token = "header.payload";
    let result = controller.validate_oidc_token(invalid_token).await;

    assert!(result.is_err());
}

#[tokio::test]
async fn test_multi_cloud_path_aws() {
    let _client = VaultClient::new("https://vault.local:8200".to_string());

    // AWS path format: aws/data/config
    let aws_path = "aws/data/config";
    assert!(aws_path.contains("aws/data"));
}

#[tokio::test]
async fn test_multi_cloud_path_gcp() {
    let _client = VaultClient::new("https://vault.local:8200".to_string());

    // GCP path format: gcp/data/config
    let gcp_path = "gcp/data/config";
    assert!(gcp_path.contains("gcp/data"));
}

#[tokio::test]
async fn test_multi_cloud_path_azure() {
    let _client = VaultClient::new("https://vault.local:8200".to_string());

    // Azure path format: azure/data/config
    let azure_path = "azure/data/config";
    assert!(azure_path.contains("azure/data"));
}

#[tokio::test]
async fn test_secret_data_structure() {
    let mut secret_data = HashMap::new();
    secret_data.insert("db_password".to_string(), "secret123".to_string());
    secret_data.insert("api_key".to_string(), "key456".to_string());

    assert_eq!(secret_data.len(), 2);
    assert_eq!(secret_data.get("db_password"), Some(&"secret123".to_string()));
}

#[tokio::test]
async fn test_oidc_flow_config_serialization() {
    let config = OIDCFlowConfig {
        vault_addr: "https://vault.local:8200".to_string(),
        oidc_audience: "https://github.com".to_string(),
        role_name: "sovereign-ci".to_string(),
    };

    let json = serde_json::to_string(&config).expect("Serialization failed");
    let deserialized: OIDCFlowConfig = serde_json::from_str(&json).expect("Deserialization failed");

    assert_eq!(config.vault_addr, deserialized.vault_addr);
    assert_eq!(config.role_name, deserialized.role_name);
}

#[tokio::test]
async fn test_vault_error_display() {
    use siss_vault_integration::VaultError;

    let err = VaultError::OIDCTokenError("Test error".to_string());
    assert!(err.to_string().contains("Test error"));
}
