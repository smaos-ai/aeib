use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Json},
};
use sqlx::PgPool;

use siss_graph_core::node::NodeId;

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

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::Body, routing::get, Router};
    use chrono::Utc;
    use http::{Request, StatusCode};
    use tower::ServiceExt; // for .oneshot()
    use testcontainers::{
        core::WaitFor,
        runners::AsyncRunner,
        GenericImage, ImageExt,
    };
    use uuid::Uuid;

    use crate::repo::insert_agent_card;
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
        insert_agent_card(&pool, &node).await.unwrap();

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
        insert_agent_card(&pool, &node).await.unwrap();

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
        insert_agent_card(&pool, &node).await.unwrap();

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
}
