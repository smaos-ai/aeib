//! L5 MCP Server Communication Tests
//! Tests for Model Context Protocol server endpoints and reliability

use l5_communication::{McpRegistry, McpRequest, ServerType};
use serde_json::json;

#[test]
fn test_mcp_request_server_registration() {
    let mut registry = McpRegistry::new();
    let server = registry.register_server(
        ServerType::Request,
        "http://localhost:8000/request".to_string(),
    );

    assert_eq!(server.server_type, ServerType::Request);
    assert_eq!(server.status, "ready");
}

#[test]
fn test_mcp_policy_server_registration() {
    let mut registry = McpRegistry::new();
    let server = registry.register_server(
        ServerType::Policy,
        "http://localhost:8001/policy".to_string(),
    );

    assert_eq!(server.server_type, ServerType::Policy);
}

#[test]
fn test_mcp_audit_server_registration() {
    let mut registry = McpRegistry::new();
    let server = registry.register_server(
        ServerType::Audit,
        "http://localhost:8003/audit".to_string(),
    );

    assert_eq!(server.server_type, ServerType::Audit);
}

#[test]
fn test_mcp_feedback_server_registration() {
    let mut registry = McpRegistry::new();
    let server = registry.register_server(
        ServerType::Feedback,
        "http://localhost:8004/feedback".to_string(),
    );

    assert_eq!(server.server_type, ServerType::Feedback);
}

#[test]
fn test_mcp_multiple_servers_registration() {
    let mut registry = McpRegistry::new();

    let request_server = registry.register_server(
        ServerType::Request,
        "http://localhost:8000".to_string(),
    );
    let policy_server = registry.register_server(
        ServerType::Policy,
        "http://localhost:8001".to_string(),
    );
    let audit_server = registry.register_server(
        ServerType::Audit,
        "http://localhost:8003".to_string(),
    );

    let servers = registry.list_servers();
    assert_eq!(servers.len(), 3);
}

#[test]
fn test_mcp_get_specific_server() {
    let mut registry = McpRegistry::new();
    registry.register_server(ServerType::Policy, "http://localhost:8001".to_string());

    let policy_server = registry.get_server(ServerType::Policy);
    assert!(policy_server.is_some());
    assert_eq!(policy_server.unwrap().server_type, ServerType::Policy);
}

#[test]
fn test_mcp_missing_server() {
    let registry = McpRegistry::new();
    let server = registry.get_server(ServerType::Audit);

    assert!(server.is_none());
}

#[test]
fn test_mcp_request_handling() {
    let registry = McpRegistry::new();
    let request = McpRequest {
        request_id: uuid::Uuid::new_v4().to_string(),
        method: "get_policy".to_string(),
        params: json!({"article": "50"}),
    };

    let response = registry.handle_request(&request);
    assert!(response.is_ok());
}

#[test]
fn test_mcp_request_response_correlation() {
    let registry = McpRegistry::new();
    let request_id = uuid::Uuid::new_v4().to_string();
    let request = McpRequest {
        request_id: request_id.clone(),
        method: "verify_compliance".to_string(),
        params: json!({"entity": "glass_manufacturer"}),
    };

    let response = registry.handle_request(&request).unwrap();
    assert_eq!(response.request_id, request_id);
}

#[test]
fn test_mcp_bulk_registration() {
    let mut registry = McpRegistry::new();

    for _ in 0..5 {
        registry.register_server(
            ServerType::Request,
            "http://localhost:8000".to_string(),
        );
    }

    let servers = registry.list_servers();
    // All 5 registrations should succeed
    assert!(servers.len() >= 5);
}

#[test]
fn test_mcp_server_isolation() {
    let mut registry = McpRegistry::new();

    let _request_server = registry.register_server(
        ServerType::Request,
        "http://localhost:8000".to_string(),
    );
    let policy_server = registry.register_server(
        ServerType::Policy,
        "http://localhost:8001".to_string(),
    );

    // Should only retrieve the policy server, not request server
    let found_policy = registry.get_server(ServerType::Policy);
    let found_audit = registry.get_server(ServerType::Audit);

    assert!(found_policy.is_some());
    assert!(found_audit.is_none());
}

#[test]
fn test_mcp_endpoint_configuration() {
    let mut registry = McpRegistry::new();
    let server = registry.register_server(
        ServerType::Audit,
        "http://localhost:8003/audit".to_string(),
    );

    assert!(server.endpoint.contains("localhost:8003"));
}

#[test]
fn test_mcp_request_with_complex_params() {
    let registry = McpRegistry::new();
    let request = McpRequest {
        request_id: uuid::Uuid::new_v4().to_string(),
        method: "evaluate_compliance".to_string(),
        params: json!({
            "entity_id": "hotel_chain_123",
            "regulations": ["Article 50", "GDPR"],
            "jurisdictions": ["EU", "CZ"],
            "timeout_ms": 5000
        }),
    };

    let response = registry.handle_request(&request);
    assert!(response.is_ok());
}

#[test]
fn test_mcp_request_batch_processing() {
    let registry = McpRegistry::new();

    let mut results = vec![];
    for i in 0..10 {
        let request = McpRequest {
            request_id: uuid::Uuid::new_v4().to_string(),
            method: format!("method_{}", i),
            params: json!({"batch": i}),
        };

        let response = registry.handle_request(&request);
        results.push(response);
    }

    assert_eq!(
        results.len(),
        10,
        "All 10 requests should be processed"
    );
    assert!(results.iter().all(|r| r.is_ok()));
}

#[test]
fn test_mcp_server_status_tracking() {
    let mut registry = McpRegistry::new();
    let server = registry.register_server(
        ServerType::Policy,
        "http://localhost:8001".to_string(),
    );

    assert_eq!(server.status, "ready");
}

#[test]
fn test_mcp_concurrent_request_handling() {
    let registry = McpRegistry::new();

    for i in 0..20 {
        let request = McpRequest {
            request_id: uuid::Uuid::new_v4().to_string(),
            method: "concurrent_test".to_string(),
            params: json!({"concurrent_id": i}),
        };

        let response = registry.handle_request(&request);
        assert!(response.is_ok());
    }
}

#[test]
fn test_mcp_response_timestamp() {
    let registry = McpRegistry::new();
    let request = McpRequest {
        request_id: uuid::Uuid::new_v4().to_string(),
        method: "test".to_string(),
        params: json!({}),
    };

    let response = registry.handle_request(&request).unwrap();
    assert!(response.timestamp <= chrono::Utc::now());
}

#[test]
fn test_mcp_server_discovery() {
    let mut registry = McpRegistry::new();

    // Register all server types
    registry.register_server(ServerType::Request, "http://localhost:8000".to_string());
    registry.register_server(ServerType::Policy, "http://localhost:8001".to_string());
    registry.register_server(ServerType::Audit, "http://localhost:8003".to_string());
    registry.register_server(ServerType::Feedback, "http://localhost:8004".to_string());

    // Should be able to discover all
    assert!(registry.get_server(ServerType::Request).is_some());
    assert!(registry.get_server(ServerType::Policy).is_some());
    assert!(registry.get_server(ServerType::Audit).is_some());
    assert!(registry.get_server(ServerType::Feedback).is_some());
}

#[test]
fn test_mcp_100_concurrent_requests() {
    let registry = McpRegistry::new();

    let mut success_count = 0;
    for i in 0..100 {
        let request = McpRequest {
            request_id: uuid::Uuid::new_v4().to_string(),
            method: format!("stress_test_{}", i),
            params: json!({"iteration": i}),
        };

        if let Ok(_response) = registry.handle_request(&request) {
            success_count += 1;
        }
    }

    assert_eq!(success_count, 100, "All 100 concurrent requests should succeed");
}

#[test]
fn test_mcp_server_unique_ids() {
    let mut registry = McpRegistry::new();

    let server1 = registry.register_server(ServerType::Request, "http://localhost:8000".to_string());
    let server2 = registry.register_server(ServerType::Request, "http://localhost:8001".to_string());

    assert_ne!(server1.id, server2.id, "Server IDs must be unique");
}

#[test]
fn test_mcp_request_idempotency() {
    let registry = McpRegistry::new();
    let request_id = uuid::Uuid::new_v4().to_string();

    let request1 = McpRequest {
        request_id: request_id.clone(),
        method: "idempotent_op".to_string(),
        params: json!({"key": "value"}),
    };

    let request2 = McpRequest {
        request_id: request_id.clone(),
        method: "idempotent_op".to_string(),
        params: json!({"key": "value"}),
    };

    let response1 = registry.handle_request(&request1);
    let response2 = registry.handle_request(&request2);

    assert!(response1.is_ok());
    assert!(response2.is_ok());
    assert_eq!(response1.unwrap().request_id, response2.unwrap().request_id);
}
