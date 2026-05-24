use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

#[derive(Debug, Clone, sqlx::FromRow)]
pub struct AgentInfo {
    pub id: Uuid,
    pub agent_id: String,
    pub sovereign_id: Uuid,
    pub agent_type: String,
    pub capabilities: Vec<String>,
    pub endpoint_url: Option<String>,
    pub registered_at: DateTime<Utc>,
    pub status: String,
}

/// Register a new agent in the cross-sovereign agent registry.
pub async fn register_agent(
    pool: &PgPool,
    sovereign_id: Uuid,
    agent_id: &str,
    agent_type: &str,
    capabilities: Vec<String>,
    endpoint_url: Option<String>,
) -> Result<Uuid, sqlx::Error> {
    let id: Uuid = sqlx::query_scalar(
        r#"
        INSERT INTO cross_sovereign_agent_registry
        (sovereign_id, agent_id, agent_type, capabilities, endpoint_url)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (agent_id, sovereign_id) DO UPDATE
        SET last_seen_at = NOW()
        RETURNING id
        "#,
    )
    .bind(sovereign_id)
    .bind(agent_id)
    .bind(agent_type)
    .bind(&capabilities)
    .bind(endpoint_url)
    .fetch_one(pool)
    .await?;

    Ok(id)
}

/// Discover agents in a sovereign, optionally filtered by capability.
pub async fn discover_agents(
    pool: &PgPool,
    sovereign_id: Uuid,
    capability_filter: Option<&str>,
) -> Result<Vec<AgentInfo>, sqlx::Error> {
    let agents = if let Some(cap) = capability_filter {
        sqlx::query_as::<_, AgentInfo>(
            r#"
            SELECT id, agent_id, sovereign_id, agent_type, capabilities,
                   endpoint_url, registered_at, status
            FROM cross_sovereign_agent_registry
            WHERE sovereign_id = $1
              AND status = 'active'
              AND $2 = ANY(capabilities)
            ORDER BY registered_at DESC
            "#,
        )
        .bind(sovereign_id)
        .bind(cap)
        .fetch_all(pool)
        .await?
    } else {
        sqlx::query_as::<_, AgentInfo>(
            r#"
            SELECT id, agent_id, sovereign_id, agent_type, capabilities,
                   endpoint_url, registered_at, status
            FROM cross_sovereign_agent_registry
            WHERE sovereign_id = $1
              AND status = 'active'
            ORDER BY registered_at DESC
            "#,
        )
        .bind(sovereign_id)
        .fetch_all(pool)
        .await?
    };

    Ok(agents)
}

/// Discover agents across federation boundaries from a source sovereign.
pub async fn discover_agents_cross_sovereign(
    pool: &PgPool,
    source_sovereign_id: Uuid,
    capability_filter: Option<&str>,
) -> Result<Vec<AgentInfo>, sqlx::Error> {
    // Get federation peers
    let peer_sovereigns: Vec<Uuid> = sqlx::query_scalar(
        r#"
        SELECT sovereign_b_id
        FROM federation_peers
        WHERE sovereign_a_id = $1 AND status = 'active'
        "#,
    )
    .bind(source_sovereign_id)
    .fetch_all(pool)
    .await?;

    let mut all_agents = Vec::new();

    // Get agents from source sovereign
    let local_agents = discover_agents(pool, source_sovereign_id, capability_filter).await?;
    all_agents.extend(local_agents);

    // Get agents from each peer
    for peer_id in peer_sovereigns {
        let peer_agents = discover_agents(pool, peer_id, capability_filter).await?;
        all_agents.extend(peer_agents);
    }

    Ok(all_agents)
}

/// Update agent status (e.g., 'active' to 'inactive').
pub async fn update_agent_status(
    pool: &PgPool,
    agent_id: &str,
    sovereign_id: Uuid,
    status: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        r#"
        UPDATE cross_sovereign_agent_registry
        SET status = $1, last_seen_at = NOW()
        WHERE agent_id = $2 AND sovereign_id = $3
        "#,
    )
    .bind(status)
    .bind(agent_id)
    .bind(sovereign_id)
    .execute(pool)
    .await?;

    Ok(())
}
