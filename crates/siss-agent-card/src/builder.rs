use sqlx::PgPool;
use uuid::Uuid;

use siss_graph_core::node::NodeId;

use crate::repo::fetch_agent_card_node;
use crate::types::{AgentCard, AgentCardError, Authentication, Capability, Skill};

pub struct AgentCardBuilder<'a> {
    pool: &'a PgPool,
}

impl<'a> AgentCardBuilder<'a> {
    pub fn new(pool: &'a PgPool) -> Self {
        Self { pool }
    }

    /// Build a complete `AgentCard` from the Knowledge Graph.
    ///
    /// 1. Validates the persona exists and is not frozen.
    /// 2. Fetches the AgentCardNode (must be pre-inserted via `insert_agent_card`).
    /// 3. Enumerates tools via `can_execute` edges → builds skills.
    pub async fn build(
        &self,
        persona_id: NodeId,
        tenant_id: NodeId,
        _base_url: &str, // reserved: Phase 4 will use this to set node.url at runtime
    ) -> Result<AgentCard, AgentCardError> {
        // 1. Validate persona
        let persona_row = siss_graph_db::repo::node_repo::fetch_persona(self.pool, persona_id.0)
            .await?
            .ok_or(AgentCardError::PersonaNotFound { persona_id: persona_id.0 })?;

        let (_id, _tenant, _name, _kind, is_frozen) = persona_row;
        if is_frozen {
            return Err(AgentCardError::PersonaNotFound { persona_id: persona_id.0 });
        }

        // 2. Fetch AgentCardNode
        let mut node = fetch_agent_card_node(self.pool, persona_id.0)
            .await?
            .ok_or(AgentCardError::CardNotFound { persona_id: persona_id.0 })?;

        // 3. Enumerate tools from CAN_EXECUTE edges (persona → tool)
        let edges = siss_graph_db::repo::edge_repo::find_edges_from(
            self.pool,
            persona_id.0,
            "can_execute",
            tenant_id.0,
        )
        .await?;

        let tool_ids: Vec<Uuid> = edges.iter().map(|(_, _, target)| *target).collect();
        node.allowed_tools = tool_ids.iter().map(|&u| NodeId(u)).collect();

        // 4. Build skills from tool rows
        let mut skills = Vec::new();
        for tool_id in &tool_ids {
            let row: Option<(String, String, String)> = sqlx::query_as(
                "SELECT name, tool_uri, risk_class::text FROM tools WHERE id = $1"
            )
            .bind(tool_id)
            .fetch_optional(self.pool)
            .await?;

            if let Some((name, uri, risk_class)) = row {
                let id = name.to_lowercase().replace(['-', ' '], "_");
                skills.push(Skill {
                    id,
                    name,
                    description: uri,
                    tags: vec![risk_class],
                });
            }
        }

        Ok(AgentCard {
            node,
            skills,
            capabilities: Capability { streaming: true, push_notifications: false },
            authentication: Authentication { schemes: vec!["Bearer".into()] },
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::repo::insert_agent_card_node;
    use chrono::Utc;
    use testcontainers::{
        core::WaitFor,
        runners::AsyncRunner,
        GenericImage, ImageExt,
    };

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

    async fn make_tenant_and_persona(pool: &PgPool) -> (Uuid, Uuid) {
        let tenant_id = siss_graph_db::repo::node_repo::insert_tenant(pool, "BuilderCorp")
            .await
            .expect("insert tenant");
        let persona_id = siss_graph_db::repo::node_repo::insert_persona(
            pool, "Aria", "ai_agent", tenant_id,
        )
        .await
        .expect("insert persona");
        (tenant_id, persona_id)
    }

    fn make_card_node(tenant_id: Uuid, persona_id: Uuid) -> AgentCardNode {
        AgentCardNode {
            id: NodeId::new(),
            tenant_id: NodeId(tenant_id),
            persona_id: NodeId(persona_id),
            name: "Aria".into(),
            description: "A sovereign agent".into(),
            version: "0.1.0".into(),
            url: "https://example.com/agent".into(),
            hardware_affinity: HardwareTarget::LocalMlx,
            budget_cap: 100_000,
            allowed_tools: vec![],
            created_at: Utc::now(),
        }
    }

    #[tokio::test]
    async fn test_build_returns_card_with_no_tools() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;
        let node = make_card_node(tenant_id, persona_id);
        insert_agent_card_node(&pool, &node).await.expect("insert card");

        let builder = AgentCardBuilder::new(&pool);
        let card = builder
            .build(NodeId(persona_id), NodeId(tenant_id), "https://example.com")
            .await
            .expect("build");

        assert_eq!(card.node.name, "Aria");
        assert!(card.skills.is_empty());
        assert!(card.capabilities.streaming);
        assert!(!card.capabilities.push_notifications);
        assert_eq!(card.authentication.schemes, vec!["Bearer"]);
    }

    #[tokio::test]
    async fn test_build_returns_persona_not_found() {
        let (_container, pool) = start_postgres().await;
        let builder = AgentCardBuilder::new(&pool);
        let err = builder
            .build(NodeId(Uuid::new_v4()), NodeId(Uuid::new_v4()), "https://example.com")
            .await
            .unwrap_err();
        assert!(matches!(err, AgentCardError::PersonaNotFound { .. }));
    }

    #[tokio::test]
    async fn test_build_returns_persona_not_found_when_frozen() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;

        // Freeze the persona
        siss_graph_db::repo::node_repo::freeze_persona(&pool, persona_id)
            .await
            .expect("freeze persona");

        let builder = AgentCardBuilder::new(&pool);
        let err = builder
            .build(NodeId(persona_id), NodeId(tenant_id), "https://example.com")
            .await
            .unwrap_err();
        assert!(matches!(err, AgentCardError::PersonaNotFound { .. }));
    }

    #[tokio::test]
    async fn test_build_returns_card_not_found_when_no_card_inserted() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;
        let builder = AgentCardBuilder::new(&pool);
        let err = builder
            .build(NodeId(persona_id), NodeId(tenant_id), "https://example.com")
            .await
            .unwrap_err();
        assert!(matches!(err, AgentCardError::CardNotFound { .. }));
    }

    #[tokio::test]
    async fn test_build_populates_skills_from_can_execute_edges() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, persona_id) = make_tenant_and_persona(&pool).await;

        let tool_id = siss_graph_db::repo::node_repo::insert_tool(
            &pool, "mcp-filesystem", "mcp://localhost:3000/fs", "medium", tenant_id,
        )
        .await
        .expect("insert tool");

        siss_graph_db::repo::edge_repo::insert_edge(
            &pool,
            persona_id,
            tool_id,
            "can_execute",
            tenant_id,
            serde_json::Value::Null,
        )
        .await
        .expect("insert edge");

        let node = make_card_node(tenant_id, persona_id);
        insert_agent_card_node(&pool, &node).await.expect("insert card");

        let builder = AgentCardBuilder::new(&pool);
        let card = builder
            .build(NodeId(persona_id), NodeId(tenant_id), "https://example.com")
            .await
            .expect("build");

        assert_eq!(card.skills.len(), 1);
        assert_eq!(card.skills[0].id, "mcp_filesystem");
        assert_eq!(card.skills[0].name, "mcp-filesystem");
        assert_eq!(card.skills[0].tags, vec!["medium"]); // risk_class = "medium"
        assert_eq!(card.node.allowed_tools.len(), 1);
        assert_eq!(card.node.allowed_tools[0].0, tool_id);
    }
}
