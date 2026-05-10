use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::NodeId;
use siss_graph_core::node::execution::HardwareTarget;

use crate::types::{AgentCardError, AgentCardNode};

// ── Helpers ───────────────────────────────────────────────────────────────────

fn hardware_target_str(h: HardwareTarget) -> &'static str {
    match h {
        HardwareTarget::LocalMlx => "local_mlx",
        HardwareTarget::RemoteFrontier => "remote_frontier",
        HardwareTarget::Hybrid => "hybrid",
    }
}

fn parse_hardware_target(s: &str) -> Result<HardwareTarget, AgentCardError> {
    match s {
        "local_mlx" => Ok(HardwareTarget::LocalMlx),
        "remote_frontier" => Ok(HardwareTarget::RemoteFrontier),
        "hybrid" => Ok(HardwareTarget::Hybrid),
        other => Err(AgentCardError::DatabaseError {
            message: format!("unknown hardware_affinity value: {other}"),
        }),
    }
}

// ── Public API ────────────────────────────────────────────────────────────────

/// Insert an AgentCardNode and a `has_agent_card` edge from persona → card,
/// in a single transaction. Returns the new card's UUID.
pub async fn insert_agent_card_node(
    pool: &PgPool,
    node: &AgentCardNode,
) -> Result<Uuid, AgentCardError> {
    let mut tx = pool.begin().await?;

    sqlx::query(
        "INSERT INTO agent_cards \
         (id, tenant_id, persona_id, name, description, version, url, hardware_affinity, budget_cap) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8::hardware_target, $9)"
    )
    .bind(node.id.0)
    .bind(node.tenant_id.0)
    .bind(node.persona_id.0)
    .bind(&node.name)
    .bind(&node.description)
    .bind(&node.version)
    .bind(&node.url)
    .bind(hardware_target_str(node.hardware_affinity))
    .bind(node.budget_cap)
    .execute(&mut *tx)
    .await?;

    let edge_id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO edges (id, source_id, target_id, edge_type, tenant_id, metadata) \
         VALUES ($1, $2, $3, 'has_agent_card'::edge_type, $4, '{}'::jsonb)"
    )
    .bind(edge_id)
    .bind(node.persona_id.0)
    .bind(node.id.0)
    .bind(node.tenant_id.0)
    .execute(&mut *tx)
    .await?;

    tx.commit().await?;
    Ok(node.id.0)
}

/// Fetch an AgentCardNode by persona_id.
/// Returns `allowed_tools: vec![]` — the builder populates tools from edges.
pub async fn fetch_agent_card_node(
    pool: &PgPool,
    persona_id: Uuid,
) -> Result<Option<AgentCardNode>, AgentCardError> {
    #[allow(clippy::type_complexity)]
    let row: Option<(Uuid, Uuid, Uuid, String, String, String, String, String, i64, chrono::DateTime<Utc>)> =
        sqlx::query_as(
            "SELECT id, tenant_id, persona_id, name, description, version, url, \
             hardware_affinity::text, budget_cap, created_at \
             FROM agent_cards WHERE persona_id = $1"
        )
        .bind(persona_id)
        .fetch_optional(pool)
        .await?;

    row.map(|(id, tenant_id, persona_id, name, description, version, url, hw, budget_cap, created_at)| {
        Ok(AgentCardNode {
            id: NodeId(id),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name,
            description,
            version,
            url,
            hardware_affinity: parse_hardware_target(&hw)?,
            budget_cap,
            allowed_tools: vec![],
            created_at,
        })
    })
    .transpose()
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::{
        core::WaitFor,
        runners::AsyncRunner,
        GenericImage, ImageExt,
    };

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

    async fn make_tenant_and_persona(pool: &PgPool) -> (Uuid, Uuid) {
        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(pool, "TestCorp")
            .await
            .expect("insert tenant");
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            pool, "Aria", "ai_agent", tenant_id,
        )
        .await
        .expect("insert persona");
        (tenant_id, persona_id)
    }

    fn make_node(tenant_id: Uuid, persona_id: Uuid) -> AgentCardNode {
        AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "Aria Agent".into(),
            description: "Test agent".into(),
            version: "0.1.0".into(),
            url: "https://example.com/agent".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 100_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        }
    }

    #[tokio::test]
    async fn test_insert_and_fetch_agent_card() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;
        let node = make_node(tenant_id, persona_id);
        let card_id = node.id.0;

        insert_agent_card_node(&pool, &node).await.expect("insert");

        let fetched = fetch_agent_card_node(&pool, persona_id)
            .await
            .expect("fetch")
            .expect("card exists");

        assert_eq!(fetched.id.0, card_id);
        assert_eq!(fetched.name, "Aria Agent");
        assert_eq!(fetched.hardware_affinity, HardwareTarget::LocalMlx);
        assert_eq!(fetched.budget_cap, 100_000);
        assert_eq!(fetched.allowed_tools, vec![]);
    }

    #[tokio::test]
    async fn test_fetch_returns_none_for_unknown_persona() {
        let (_container, pool) = start_postgres().await;
        let result = fetch_agent_card_node(&pool, Uuid::new_v4())
            .await
            .expect("fetch");
        assert!(result.is_none());
    }

    #[tokio::test]
    async fn test_insert_creates_has_agent_card_edge() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;
        let node = make_node(tenant_id, persona_id);
        let card_id = node.id.0;

        insert_agent_card_node(&pool, &node).await.expect("insert");

        let edges = siss_graph_db::repo::edge_repo::find_edges_from(
            &pool,
            persona_id,
            "has_agent_card",
            tenant_id,
        )
        .await
        .expect("find edges");

        assert_eq!(edges.len(), 1);
        assert_eq!(edges[0].2, card_id); // target_id
    }

    #[test]
    fn test_hardware_target_str_roundtrip() {
        for (variant, s) in [
            (HardwareTarget::LocalMlx, "local_mlx"),
            (HardwareTarget::RemoteFrontier, "remote_frontier"),
            (HardwareTarget::Hybrid, "hybrid"),
        ] {
            assert_eq!(hardware_target_str(variant), s);
            assert_eq!(parse_hardware_target(s).unwrap(), variant);
        }
    }
}
