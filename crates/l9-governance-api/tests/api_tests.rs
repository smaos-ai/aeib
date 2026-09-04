use l9_governance_api::api::GovernanceApi;
use l9_governance_api::models::{CreatePolicyRequest, InitiateSettlementRequest, RegisterDIDRequest};
use serde_json::json;

#[tokio::test]
async fn test_register_tenant() {
    let api = GovernanceApi::new();
    let (tenant_id, api_key) = api
        .register_tenant("ACME Corp".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    assert!(!api_key.is_empty());
    assert!(api_key.starts_with("sk_"));
    assert_ne!(tenant_id.to_string(), "");
}

#[tokio::test]
async fn test_validate_api_key() {
    let api = GovernanceApi::new();
    let (_tenant_id, api_key) = api
        .register_tenant("Widget Inc".to_string(), "us-east".to_string())
        .await
        .unwrap();

    let validated = api.validate_request(&api_key).await;
    assert!(validated.is_ok());
}

#[tokio::test]
async fn test_invalid_api_key() {
    let api = GovernanceApi::new();
    let invalid_key = "sk_invalid_xxxxx";

    let result = api.validate_request(invalid_key).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_register_did() {
    let api = GovernanceApi::new();
    let (_tenant_id, api_key) = api
        .register_tenant("TestCorp".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    let req = RegisterDIDRequest {
        did_method: "sov".to_string(),
        identifier: "org-123".to_string(),
        controller: Some("controller-did".to_string()),
    };

    let response = api.register_did(&api_key, req).await.unwrap();
    assert!(response.success);
    assert!(response.data.is_some());

    let data = response.data.unwrap();
    assert!(data.did.starts_with("did:smaos:"));
}

#[tokio::test]
async fn test_register_did_invalid_key() {
    let api = GovernanceApi::new();

    let req = RegisterDIDRequest {
        did_method: "sov".to_string(),
        identifier: "org-123".to_string(),
        controller: None,
    };

    let result = api.register_did("invalid_key", req).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_create_policy() {
    let api = GovernanceApi::new();
    let (_tenant_id, api_key) = api
        .register_tenant("PolicyTest".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    let req = CreatePolicyRequest {
        category: "egress".to_string(),
        rules: json!({"max_requests": 100}),
        parent_policy_id: None,
    };

    let response = api.create_policy(&api_key, req).await.unwrap();
    assert!(response.success);
    assert!(response.data.is_some());

    let data = response.data.unwrap();
    assert_eq!(data.version, 1);
    assert!(!data.published);
}

#[tokio::test]
async fn test_create_policy_invalid_category() {
    let api = GovernanceApi::new();
    let (_tenant_id, api_key) = api
        .register_tenant("PolicyTest".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    let req = CreatePolicyRequest {
        category: "".to_string(),
        rules: json!({}),
        parent_policy_id: None,
    };

    let result = api.create_policy(&api_key, req).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_initiate_settlement() {
    let api = GovernanceApi::new();
    let (_tenant_id, api_key) = api
        .register_tenant("Settlement".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    let req = InitiateSettlementRequest {
        from_org_did: "did:smaos:org-a".to_string(),
        to_org_did: "did:smaos:org-b".to_string(),
        amount: "1000".to_string(),
        currency: "EUR".to_string(),
    };

    let response = api.initiate_settlement(&api_key, req).await.unwrap();
    assert!(response.success);
    assert!(response.data.is_some());

    let data = response.data.unwrap();
    assert_eq!(data.status, "initiated");
}

#[tokio::test]
async fn test_initiate_settlement_invalid_did() {
    let api = GovernanceApi::new();
    let (_tenant_id, api_key) = api
        .register_tenant("Settlement".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    let req = InitiateSettlementRequest {
        from_org_did: "invalid-did".to_string(),
        to_org_did: "did:smaos:org-b".to_string(),
        amount: "1000".to_string(),
        currency: "EUR".to_string(),
    };

    let result = api.initiate_settlement(&api_key, req).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_health_check() {
    let api = GovernanceApi::new();
    let response = api.health_check().await.unwrap();

    assert!(response.success);
    assert_eq!(response.data.unwrap().status, "healthy");
}

#[tokio::test]
async fn test_get_metrics() {
    let api = GovernanceApi::new();
    let (_tenant_id, api_key) = api
        .register_tenant("Metrics".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    // Create some activity
    let req = RegisterDIDRequest {
        did_method: "sov".to_string(),
        identifier: "test-123".to_string(),
        controller: None,
    };
    api.register_did(&api_key, req).await.ok();

    let response = api.get_metrics().await.unwrap();
    assert!(response.success);

    let metrics = response.data.unwrap();
    assert_eq!(metrics.total_dids, 1);
}

#[tokio::test]
async fn test_multi_tenant_isolation() {
    let api = GovernanceApi::new();

    let (_tenant_a, api_key_a) = api
        .register_tenant("TenantA".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    let (_tenant_b, api_key_b) = api
        .register_tenant("TenantB".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    let req_a = RegisterDIDRequest {
        did_method: "sov".to_string(),
        identifier: "org-a".to_string(),
        controller: None,
    };

    let req_b = RegisterDIDRequest {
        did_method: "sov".to_string(),
        identifier: "org-b".to_string(),
        controller: None,
    };

    let response_a = api.register_did(&api_key_a, req_a).await.unwrap();
    let response_b = api.register_did(&api_key_b, req_b).await.unwrap();

    let did_a = response_a.data.unwrap().did;
    let did_b = response_b.data.unwrap().did;

    // Different tenants should get different DIDs
    assert_ne!(did_a, did_b);
}

#[tokio::test]
async fn test_rate_limiting() {
    let api = GovernanceApi::new();
    let (_tenant_id, api_key) = api
        .register_tenant("RateTest".to_string(), "eu-central".to_string())
        .await
        .unwrap();

    // Check that rate limit exists and can be validated
    let tenant_id = api.validate_request(&api_key).await.unwrap();
    let result = api.check_rate_limit(tenant_id).await;
    assert!(result.is_ok());
}
