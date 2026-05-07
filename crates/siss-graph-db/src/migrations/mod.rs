use sqlx::PgPool;

const MIGRATIONS: &[(&str, &str)] = &[
    ("001_create_base_schema", include_str!("001_create_base_schema.sql")),
    ("002_create_edges", include_str!("002_create_edges.sql")),
    ("003_create_age_graph", include_str!("003_create_age_graph.sql")),
    ("004_seed_governance", include_str!("004_seed_governance.sql")),
    ("005_create_agent_cards", include_str!("005_create_agent_cards.sql")),
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
