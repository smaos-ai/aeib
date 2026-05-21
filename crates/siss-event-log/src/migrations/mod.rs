use sqlx::PgPool;

const MIGRATIONS: &[(&str, &str)] = &[
    ("001_create_event_log", include_str!("001_create_event_log.sql")),
    ("002_add_immutability_trigger", include_str!("002_add_immutability_trigger.sql")),
];

pub async fn run_all(pool: &PgPool) -> Result<(), sqlx::Error> {
    // Create migrations table if not exists
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS _event_log_migrations (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT NOW()
        )
        "#,
    )
    .execute(pool)
    .await?;

    // Run each migration
    for (name, sql) in MIGRATIONS {
        let already_applied = sqlx::query_scalar::<_, bool>(
            "SELECT EXISTS(SELECT 1 FROM _event_log_migrations WHERE name = $1)",
        )
        .bind(*name)
        .fetch_one(pool)
        .await?;

        if !already_applied {
            sqlx::query(sql).execute(pool).await?;
            sqlx::query("INSERT INTO _event_log_migrations (name) VALUES ($1)")
                .bind(*name)
                .execute(pool)
                .await?;
        }
    }

    Ok(())
}

#[cfg(test)]
pub mod test_helpers {
    use sqlx::PgPool;

    pub async fn setup_test_pool() -> PgPool {
        let db_url = std::env::var("DATABASE_URL")
            .unwrap_or_else(|_| "postgres://localhost/siss_event_log_test".to_string());

        let pool = PgPool::connect(&db_url)
            .await
            .expect("Failed to create pool");

        super::run_all(&pool)
            .await
            .expect("Failed to run migrations");

        pool
    }
}
