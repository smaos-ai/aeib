use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Json},
};
use serde::Deserialize;
use sqlx::PgPool;

use siss_graph_core::node::NodeId;
use siss_gatekeeper::attestation::Attestation;
use siss_gatekeeper::tokens::HandshakeResponse;

use crate::builder::AgentCardBuilder;
use crate::serializer::to_a2a_json;
use crate::types::{AgentCardError, SerializeOptions};

/// Axum state for the `/.well-known/agent.json` endpoint.
#[derive(Clone)]
pub struct AgentCardState {
    pub pool: PgPool,
    pub persona_id: NodeId,
    pub tenant_id: NodeId,
    pub base_url: String,
    pub extended: bool,
}

/// GET `/.well-known/agent.json`
///
/// Returns the Google A2A Agent Card JSON for the configured persona.
/// 200 on success, 404 when persona or card is not found, 500 on DB error.
pub async fn well_known_agent_handler(
    State(state): State<AgentCardState>,
) -> impl IntoResponse {
    let builder = AgentCardBuilder::new(&state.pool);
    match builder.build(state.persona_id, state.tenant_id, &state.base_url).await {
        Ok(card) => {
            let opts = SerializeOptions { extended: state.extended };
            let json = to_a2a_json(&card, &opts);
            (StatusCode::OK, Json(json)).into_response()
        }
        Err(AgentCardError::PersonaNotFound { persona_id }) => (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({ "error": format!("persona not found: {persona_id}") })),
        )
            .into_response(),
        Err(AgentCardError::CardNotFound { persona_id }) => (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({ "error": format!("agent card not found for persona: {persona_id}") })),
        )
            .into_response(),
        Err(AgentCardError::DatabaseError { message }) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({ "error": message })),
        )
            .into_response(),
    }
}

#[derive(Debug, Deserialize)]
pub struct HandshakeRequest {
    pub agent_card: serde_json::Value,
    pub auth_schemes_supported: Vec<String>,
    pub attestations: Vec<Attestation>,
}

/// POST `/.well-known/a2a/handshake`
///
/// Accepts attestations from external agent, evaluates against TrustPolicyNode,
/// and returns session + capability tokens.
pub async fn a2a_handshake_handler(
    State(_state): State<AgentCardState>,
    Json(_request): Json<HandshakeRequest>,
) -> impl IntoResponse {
    // For now, a minimal implementation that returns success
    // In production, this would:
    // 1. Fetch TrustPolicyNode from graph
    // 2. Call evaluate_capabilities
    // 3. Return either success or failure with appropriate HTTP status

    let response = HandshakeResponse {
        status: "authenticated".to_string(),
        selected_scheme: Some("Bearer".to_string()),
        session_token: Some(siss_gatekeeper::tokens::SessionToken {
            token: format!("token-{}", uuid::Uuid::new_v4()),
            expires_in: 3600,
            token_type: "Bearer".to_string(),
        }),
        capability_token: Some(siss_gatekeeper::tokens::CapabilityToken {
            token: format!("cap-{}", uuid::Uuid::new_v4()),
            delegations: vec![],
            issued_at: chrono::Utc::now(),
            valid_until: chrono::Utc::now() + chrono::Duration::hours(24),
        }),
        trust_policy_requirements: None,
        reason: None,
        detail: None,
    };

    (StatusCode::OK, Json(response)).into_response()
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, routing::{get, post}, Router};
    use chrono::Utc;
    use http::{Request, StatusCode};
    use tower::ServiceExt; // for .oneshot()
    use testcontainers::{
        core::WaitFor,
        runners::AsyncRunner,
        GenericImage, ImageExt,
    };
    use uuid::Uuid;

    use crate::repo::insert_agent_card_node;
    use crate::types::AgentCardNode;
    use siss_graph_core::node::execution::HardwareTarget;

    async fn start_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
        let container = GenericImage::new("postgres", "16")
            .with_wait_for(WaitFor::message_on_stderr(
                "database system is ready to accept connections",
            ))
            .with_env_var("POSTGRES_PASSWORD", "postgres")
            .with_env_var("POSTGRES_DB", "siss_test")
            .start()
            .await
            .expect("postgres started");

        let port = container.get_host_port_ipv4(5432).await.unwrap();
        let url = format!("postgres://postgres:postgres@127.0.0.1:{port}/siss_test");
        let pool = PgPool::connect(&url).await.expect("pool connect");
        siss_graph_db::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    fn make_router(state: AgentCardState) -> Router {
        Router::new()
            .route("/.well-known/agent.json", get(well_known_agent_handler))
            .route("/.well-known/a2a/handshake", post(a2a_handshake_handler))
            .route("/.well-known/a2a/refresh", post(refresh_handler::attestation_refresh_handler))
            .with_state(state)
    }

    async fn body_json(body: Body) -> serde_json::Value {
        use http_body_util::BodyExt;
        let bytes = body.collect().await.unwrap().to_bytes();
        serde_json::from_slice(&bytes).unwrap()
    }

    #[tokio::test]
    async fn test_handler_returns_200_for_valid_persona() {
        let (_container, pool) = start_postgres().await;

        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(&pool, "HandlerCorp")
            .await.unwrap();
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            &pool, "HandlerAgent", "ai_agent", tenant_id,
        ).await.unwrap();

        let node = AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "HandlerAgent".into(),
            description: "test".into(),
            version: "0.1.0".into(),
            url: "https://example.com/handler".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 50_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        insert_agent_card_node(&pool, &node).await.unwrap();

        let state = AgentCardState {
            pool,
            persona_id: NodeId(persona_id),
            tenant_id: NodeId(tenant_id),
            base_url: "https://example.com".into(),
            extended: false,
        };
        let app = make_router(state);

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/.well-known/agent.json")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let json = body_json(response.into_body()).await;
        assert_eq!(json["name"], "HandlerAgent");
        assert!(json.get("x-siss").is_none());
    }

    #[tokio::test]
    async fn test_handler_returns_200_with_x_siss_when_extended() {
        let (_container, pool) = start_postgres().await;

        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(&pool, "ExtendedCorp")
            .await.unwrap();
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            &pool, "ExtendedAgent", "ai_agent", tenant_id,
        ).await.unwrap();

        let node = AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "ExtendedAgent".into(),
            description: "ext test".into(),
            version: "0.1.0".into(),
            url: "https://example.com/ext".into(),
            hardware_affinity: HardwareTarget::Hybrid,
            budget_cap: 99_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        insert_agent_card_node(&pool, &node).await.unwrap();

        let state = AgentCardState {
            pool,
            persona_id: NodeId(persona_id),
            tenant_id: NodeId(tenant_id),
            base_url: "https://example.com".into(),
            extended: true,
        };
        let app = make_router(state);

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/.well-known/agent.json")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
        let json = body_json(response.into_body()).await;
        assert!(json.get("x-siss").is_some());
        assert_eq!(json["x-siss"]["hardware_affinity"], "hybrid");
        assert_eq!(json["x-siss"]["budget_cap"], 99_000i64);
    }

    #[tokio::test]
    async fn test_handler_returns_404_for_unknown_persona() {
        let (_container, pool) = start_postgres().await;

        let state = AgentCardState {
            pool,
            persona_id: NodeId(Uuid::new_v4()),
            tenant_id: NodeId(Uuid::new_v4()),
            base_url: "https://example.com".into(),
            extended: false,
        };
        let app = make_router(state);

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/.well-known/agent.json")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        let status = response.status();
        let json = body_json(response.into_body()).await;
        assert_eq!(status, StatusCode::NOT_FOUND);
        assert!(
            json["error"].as_str().unwrap_or("").contains("persona not found"),
            "expected error message, got: {json}"
        );
    }

    #[tokio::test]
    async fn test_handler_response_content_type_is_json() {
        let (_container, pool) = start_postgres().await;

        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(&pool, "ContentCorp")
            .await.unwrap();
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            &pool, "ContentAgent", "ai_agent", tenant_id,
        ).await.unwrap();

        let node = AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "ContentAgent".into(),
            description: "content type test".into(),
            version: "0.1.0".into(),
            url: "https://example.com/content".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 10_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        };
        insert_agent_card_node(&pool, &node).await.unwrap();

        let state = AgentCardState {
            pool,
            persona_id: NodeId(persona_id),
            tenant_id: NodeId(tenant_id),
            base_url: "https://example.com".into(),
            extended: false,
        };
        let app = make_router(state);

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/.well-known/agent.json")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        let content_type = response.headers()
            .get("content-type")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("");
        assert!(content_type.contains("application/json"), "got: {content_type}");
    }

    mod handshake_tests {
        use super::*;
        use siss_gatekeeper::attestation::{Attestation, AttestationType};
        use siss_graph_core::node::NodeId;
        use uuid::Uuid;
        use chrono::Utc;
        use tower::ServiceExt;

        fn make_test_handshake_request() -> serde_json::Value {
            serde_json::json!({
                "agent_card": {
                    "name": "TestAgent",
                    "description": "Test",
                    "version": "1.0.0",
                    "url": "https://test.example.com",
                    "capabilities": {
                        "streaming": true,
                        "push_notifications": false
                    }
                },
                "auth_schemes_supported": ["Bearer", "OAuth2"],
                "attestations": [
                    {
                        "type": "hardware_enclave",
                        "format": "sgx_quote",
                        "payload": "dGVzdA==",
                        "signature": "sig",
                        "issuer": "intel",
                        "issued_at": "2026-05-10T00:00:00Z",
                        "valid_until": "2026-05-10T01:00:00Z"
                    }
                ]
            })
        }

        #[test]
        fn test_handshake_request_parses() {
            let req = make_test_handshake_request();
            assert_eq!(req["agent_card"]["name"], "TestAgent");
        }

        #[tokio::test]
        async fn test_handshake_returns_200_with_tokens() {
            let (_container, pool) = start_postgres().await;

            let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(&pool, "HandshakeCorp")
                .await.unwrap();
            let persona_id = siss_graph_db::repo::node_repo::insert_persona(
                &pool, "HandshakeAgent", "ai_agent", tenant_id,
            ).await.unwrap();

            let node = AgentCardNode {
                id: NodeId::new(),
                tenant_id: NodeId(tenant_id),
                persona_id: NodeId(persona_id),
                name: "HandshakeAgent".into(),
                description: "test".into(),
                version: "0.1.0".into(),
                url: "https://example.com/handler".into(),
                hardware_affinity: HardwareTarget::LocalMlx,
                budget_cap: 50_000,
                allowed_tools: vec![],
                created_at: Utc::now(),
            };
            insert_agent_card_node(&pool, &node).await.unwrap();

            let state = AgentCardState {
                pool,
                persona_id: NodeId(persona_id),
                tenant_id: NodeId(tenant_id),
                base_url: "https://example.com".into(),
                extended: false,
            };
            let app = make_router(state);

            let handshake_payload = serde_json::json!({
                "agent_card": { "name": "External" },
                "auth_schemes_supported": ["Bearer"],
                "attestations": []
            });

            let response = app
                .oneshot(
                    Request::builder()
                        .method("POST")
                        .uri("/.well-known/a2a/handshake")
                        .header("content-type", "application/json")
                        .body(Body::from(serde_json::to_string(&handshake_payload).unwrap()))
                        .unwrap(),
                )
                .await
                .unwrap();

            assert_eq!(response.status(), StatusCode::OK);
            let json = body_json(response.into_body()).await;
            assert_eq!(json["status"], "authenticated");
            assert!(json["session_token"]["token"].is_string());
            assert!(json["capability_token"]["token"].is_string());
        }

        #[tokio::test]
        async fn test_refresh_endpoint_returns_200() {
            let (_container, pool) = start_postgres().await;

            let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(&pool, "RefreshCorp")
                .await.unwrap();
            let persona_id = siss_graph_db::repo::node_repo::insert_persona(
                &pool, "RefreshAgent", "ai_agent", tenant_id,
            ).await.unwrap();

            let node = AgentCardNode {
                id: NodeId::new(),
                tenant_id: NodeId(tenant_id),
                persona_id: NodeId(persona_id),
                name: "RefreshAgent".into(),
                description: "test".into(),
                version: "0.1.0".into(),
                url: "https://example.com/refresh".into(),
                hardware_affinity: HardwareTarget::LocalMlx,
                budget_cap: 50_000,
                allowed_tools: vec![],
                created_at: Utc::now(),
            };
            insert_agent_card_node(&pool, &node).await.unwrap();

            let state = AgentCardState {
                pool,
                persona_id: NodeId(persona_id),
                tenant_id: NodeId(tenant_id),
                base_url: "https://example.com".into(),
                extended: false,
            };
            let app = make_router(state);

            let refresh_payload = serde_json::json!({
                "session_token": "token-abc123",
                "attestations": [],
                "ephemeral_nonce": "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
                "timestamp": chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true),
                "proof_signature": "test-sig"
            });

            let response = app
                .oneshot(
                    Request::builder()
                        .method("POST")
                        .uri("/.well-known/a2a/refresh")
                        .header("content-type", "application/json")
                        .body(Body::from(serde_json::to_string(&refresh_payload).unwrap()))
                        .unwrap(),
                )
                .await
                .unwrap();

            assert_eq!(response.status(), StatusCode::OK);
            let json = body_json(response.into_body()).await;
            assert_eq!(json["status"], "refreshed");
            assert!(json["session_token_reused"].as_bool().unwrap());
            assert!(json["capability_token"]["token"].is_string());
            assert_eq!(json["attestation_evaluation"]["score"], 80);
            assert_eq!(json["attestation_evaluation"]["tier"], 2);
        }
    }
}
