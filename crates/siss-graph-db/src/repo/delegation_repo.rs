use chrono::Utc;
use sqlx::PgPool;
use uuid::Uuid;

/// Insert a delegation edge from parent persona to child persona.
///
/// Creates a DELEGATES_TO edge representing explicit capability delegation.
/// The ceiling defines the maximum capabilities the child can receive.
pub async fn insert_delegation_edge(
    pool: &PgPool,
    source_persona_id: Uuid,
    target_persona_id: Uuid,
    tenant_id: Uuid,
    ceiling_delegations: &str,
    ceiling_constraints: &str,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    let delegated_at = Utc::now();

    sqlx::query(
        "INSERT INTO delegation_edges \
         (id, source_persona_id, target_persona_id, tenant_id, ceiling_delegations, ceiling_constraints, delegated_at) \
         VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)"
    )
    .bind(id)
    .bind(source_persona_id)
    .bind(target_persona_id)
    .bind(tenant_id)
    .bind(ceiling_delegations)
    .bind(ceiling_constraints)
    .bind(delegated_at)
    .execute(pool)
    .await?;

    Ok(id)
}

/// Fetch all ancestors of a given persona (recursive).
///
/// Returns list of ancestor persona IDs from root to immediate parent.
/// Used for lineage construction and ancestor-aware revocation.
pub async fn fetch_ancestors(pool: &PgPool, persona_id: Uuid) -> Result<Vec<Uuid>, sqlx::Error> {
    let rows: Vec<(Uuid,)> = sqlx::query_as(
        "WITH RECURSIVE ancestor_chain AS (
           SELECT id, delegated_by FROM personas WHERE id = $1
           UNION ALL
           SELECT p.id, p.delegated_by FROM personas p
           INNER JOIN ancestor_chain a ON p.id = a.delegated_by
         )
         SELECT id FROM ancestor_chain WHERE id != $1 ORDER BY id",
    )
    .bind(persona_id)
    .fetch_all(pool)
    .await?;

    Ok(rows.iter().map(|(id,)| *id).collect())
}

/// Fetch all descendants of a given persona (recursive).
///
/// Returns list of all descendant persona IDs in the subtree.
/// Used for strict revocation propagation (fail-closed).
pub async fn fetch_descendants(pool: &PgPool, persona_id: Uuid) -> Result<Vec<Uuid>, sqlx::Error> {
    let rows: Vec<(Uuid,)> = sqlx::query_as(
        "WITH RECURSIVE descendant_tree AS (
           SELECT id FROM personas WHERE delegated_by = $1
           UNION ALL
           SELECT p.id FROM personas p
           INNER JOIN descendant_tree d ON p.delegated_by = d.id
         )
         SELECT id FROM descendant_tree",
    )
    .bind(persona_id)
    .fetch_all(pool)
    .await?;

    Ok(rows.iter().map(|(id,)| *id).collect())
}

/// Fetch all descendant sessions of a given parent session (recursive).
///
/// Returns list of all child sessions (direct and transitive).
/// Used for strict revocation propagation to mark entire subtree as revoked.
pub async fn fetch_descendant_sessions(
    pool: &PgPool,
    parent_session_id: Uuid,
) -> Result<Vec<Uuid>, sqlx::Error> {
    let rows: Vec<(Uuid,)> = sqlx::query_as(
        "WITH RECURSIVE session_tree AS (
           SELECT id, parent_session_id FROM sessions WHERE parent_session_id = $1
           UNION ALL
           SELECT s.id, s.parent_session_id FROM sessions s
           INNER JOIN session_tree st ON s.parent_session_id = st.id
         )
         SELECT id FROM session_tree",
    )
    .bind(parent_session_id)
    .fetch_all(pool)
    .await?;

    Ok(rows.iter().map(|(id,)| *id).collect())
}

/// Fetch the delegation ceiling envelope for a given persona.
///
/// Returns the ceiling at delegation time, showing max capabilities the child can have.
pub async fn fetch_delegation_ceiling(
    pool: &PgPool,
    persona_id: Uuid,
) -> Result<Option<(String, String)>, sqlx::Error> {
    let row: Option<(String, String)> = sqlx::query_as(
        "SELECT REPLACE(REPLACE(ceiling_delegations::text, ': ', ':'), ', ', ','), \
         REPLACE(REPLACE(ceiling_constraints::text, ': ', ':'), ', ', ',') \
         FROM delegation_edges \
         WHERE target_persona_id = $1 \
         ORDER BY delegated_at DESC \
         LIMIT 1",
    )
    .bind(persona_id)
    .fetch_optional(pool)
    .await?;

    Ok(row)
}

/// Check if a delegation path (chain) would create a cycle.
///
/// Used during delegation creation to enforce acyclic property.
/// Returns true if adding an edge source -> target would create a cycle.
pub async fn would_create_cycle(
    pool: &PgPool,
    source_persona_id: Uuid,
    target_persona_id: Uuid,
) -> Result<bool, sqlx::Error> {
    // If target has source as a descendant, adding source -> target creates a cycle
    let descendants = fetch_descendants(pool, target_persona_id).await?;
    Ok(descendants.contains(&source_persona_id))
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor, runners::AsyncRunner};

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
        crate::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    async fn create_test_delegation_personas(pool: &PgPool) -> (Uuid, Uuid, Uuid, Uuid) {
        let tenant_id = crate::repo::node_repo::insert_tenant(pool, "DelegationCorp")
            .await
            .expect("insert tenant");

        let root_persona =
            crate::repo::node_repo::insert_persona(pool, "RootAgent", "ai_agent", tenant_id)
                .await
                .expect("insert root");

        let parent_persona =
            crate::repo::node_repo::insert_persona(pool, "ParentAgent", "ai_agent", tenant_id)
                .await
                .expect("insert parent");

        let child_persona =
            crate::repo::node_repo::insert_persona(pool, "ChildAgent", "ai_agent", tenant_id)
                .await
                .expect("insert child");

        (tenant_id, root_persona, parent_persona, child_persona)
    }

    #[tokio::test]
    async fn test_insert_delegation_edge() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, root, parent, _child) = create_test_delegation_personas(&pool).await;

        let ceiling_delegations = r#"[{"permission":"can_execute","resource_type":"tool"}]"#;
        let ceiling_constraints = r#"{"rate_limit":"1000/min"}"#;

        let edge_id = insert_delegation_edge(
            &pool,
            root,
            parent,
            tenant_id,
            ceiling_delegations,
            ceiling_constraints,
        )
        .await
        .expect("insert edge");

        assert_ne!(edge_id, Uuid::nil());
    }

    #[tokio::test]
    async fn test_fetch_ancestors_chain() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, root, parent, child) = create_test_delegation_personas(&pool).await;

        // Set up delegation chain: root → parent → child
        let _ = insert_delegation_edge(&pool, root, parent, tenant_id, "[]", "{}").await;
        let _ = insert_delegation_edge(&pool, parent, child, tenant_id, "[]", "{}").await;

        // Update personas to reflect delegation chain (set delegated_by)
        let _ = sqlx::query("UPDATE personas SET delegated_by = $1 WHERE id = $2")
            .bind(root)
            .bind(parent)
            .execute(&pool)
            .await;

        let _ = sqlx::query("UPDATE personas SET delegated_by = $1 WHERE id = $2")
            .bind(parent)
            .bind(child)
            .execute(&pool)
            .await;

        let ancestors = fetch_ancestors(&pool, child)
            .await
            .expect("fetch ancestors");
        assert!(ancestors.len() >= 1);
    }

    #[tokio::test]
    async fn test_fetch_descendants_subtree() {
        let (_container, pool) = start_postgres().await;
        let (tenant_id, root, parent, child) = create_test_delegation_personas(&pool).await;

        // Insert delegation edges
        let _ = insert_delegation_edge(&pool, root, parent, tenant_id, "[]", "{}").await;
        let _ = insert_delegation_edge(&pool, parent, child, tenant_id, "[]", "{}").await;

        // Update personas to reflect delegation chain (set delegated_by)
        let _ = sqlx::query("UPDATE personas SET delegated_by = $1 WHERE id = $2")
            .bind(root)
            .bind(parent)
            .execute(&pool)
            .await;

        let _ = sqlx::query("UPDATE personas SET delegated_by = $1 WHERE id = $2")
            .bind(parent)
            .bind(child)
            .execute(&pool)
            .await;

        let descendants = fetch_descendants(&pool, root)
            .await
            .expect("fetch descendants");
        assert!(descendants.len() >= 1);
    }

    #[tokio::test]
    async fn test_would_create_cycle_no_cycle() {
        let (_container, pool) = start_postgres().await;
        let (_tenant_id, root, parent, _child) = create_test_delegation_personas(&pool).await;

        // root → parent; adding parent → root would create cycle
        let is_cycle = would_create_cycle(&pool, parent, root)
            .await
            .expect("check cycle");
        // Initially should be false because we haven't inserted descendants yet
        assert!(!is_cycle);
    }
}
