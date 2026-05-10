use sqlx::PgPool;

const MIGRATIONS: &[(&str, &str)] = &[
    ("001_create_base_schema", include_str!("001_create_base_schema.sql")),
    ("002_create_edges", include_str!("002_create_edges.sql")),
    ("003_create_age_graph", include_str!("003_create_age_graph.sql")),
    ("004_seed_governance", include_str!("004_seed_governance.sql")),
    ("005_create_agent_cards", include_str!("005_create_agent_cards.sql")),
    ("006_create_trust_policy_nodes", include_str!("006_create_trust_policy_nodes.sql")),
    ("007_extend_sessions_phase5", include_str!("007_extend_sessions_phase5.sql")),
    ("008_add_session_revocation", include_str!("008_add_session_revocation.sql")),
    ("009_create_challenges", include_str!("009_create_challenges.sql")),
    ("010_add_delegation_schema", include_str!("010_add_delegation_schema.sql")),
    ("011_create_delegation_edges", include_str!("011_create_delegation_edges.sql")),
    ("012_add_phase7_budget_fields", include_str!("012_add_phase7_budget_fields.sql")),
    ("013_add_phase8_behavior_events", include_str!("013_add_phase8_behavior_events.sql")),
];

/// Run all migrations in order. Idempotent — tracks applied migrations in a metadata table.
pub async fn run_all(pool: &PgPool) -> Result<(), sqlx::Error> {
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS _siss_migrations (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )"
    )
    .execute(pool)
    .await?;

    for (name, sql) in MIGRATIONS {
        let already_applied: bool = sqlx::query_scalar(
            "SELECT EXISTS(SELECT 1 FROM _siss_migrations WHERE name = $1)"
        )
        .bind(name)
        .fetch_one(pool)
        .await?;

        if !already_applied {
            sqlx::raw_sql(sql).execute(pool).await?;
            sqlx::query("INSERT INTO _siss_migrations (name) VALUES ($1)")
                .bind(name)
                .execute(pool)
                .await?;
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{core::WaitFor, GenericImage, ImageExt};

    async fn setup_postgres() -> (testcontainers::ContainerAsync<GenericImage>, PgPool) {
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
        run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    #[tokio::test]
    async fn test_trust_policy_nodes_table_exists() {
        let (_container, pool) = setup_postgres().await;

        let result: (i64,) = sqlx::query_as(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'trust_policy_nodes'"
        )
        .fetch_one(&pool)
        .await
        .expect("query");

        assert_eq!(result.0, 1, "trust_policy_nodes table should exist");
    }

    #[tokio::test]
    async fn test_has_trust_policy_edge_type_exists() {
        let (_container, pool) = setup_postgres().await;

        let result: (String,) = sqlx::query_as(
            "SELECT 'has_trust_policy'::edge_type"
        )
        .fetch_one(&pool)
        .await
        .expect("query");

        assert_eq!(result.0, "has_trust_policy");
    }
}
