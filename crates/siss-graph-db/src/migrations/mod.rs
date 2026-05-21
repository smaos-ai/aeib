use sqlx::PgPool;

const MIGRATIONS: &[(&str, &str)] = &[
    (
        "001_create_base_schema",
        include_str!("001_create_base_schema.sql"),
    ),
    ("002_create_edges", include_str!("002_create_edges.sql")),
    (
        "003_create_age_graph",
        include_str!("003_create_age_graph.sql"),
    ),
    (
        "004_seed_governance",
        include_str!("004_seed_governance.sql"),
    ),
    (
        "005_create_agent_cards",
        include_str!("005_create_agent_cards.sql"),
    ),
    (
        "006_create_trust_policy_nodes",
        include_str!("006_create_trust_policy_nodes.sql"),
    ),
    (
        "007_extend_sessions_phase5",
        include_str!("007_extend_sessions_phase5.sql"),
    ),
    (
        "008_add_session_revocation",
        include_str!("008_add_session_revocation.sql"),
    ),
    (
        "009_create_challenges",
        include_str!("009_create_challenges.sql"),
    ),
    (
        "010_add_delegation_schema",
        include_str!("010_add_delegation_schema.sql"),
    ),
    (
        "011_create_delegation_edges",
        include_str!("011_create_delegation_edges.sql"),
    ),
    (
        "012_add_phase7_budget_fields",
        include_str!("012_add_phase7_budget_fields.sql"),
    ),
    (
        "013_add_phase8_behavior_events",
        include_str!("013_add_phase8_behavior_events.sql"),
    ),
    (
        "014_add_phase9_sovereign_identity",
        include_str!("014_add_phase9_sovereign_identity.sql"),
    ),
    (
        "015_add_phase9_federation_peers",
        include_str!("015_add_phase9_federation_peers.sql"),
    ),
    (
        "016_add_phase9_settlement_ledger",
        include_str!("016_add_phase9_settlement_ledger.sql"),
    ),
    (
        "017_add_phase10_gossip",
        include_str!("017_add_phase10_gossip.sql"),
    ),
    (
        "018_add_phase10_settlement_invoices",
        include_str!("018_add_phase10_settlement_invoices.sql"),
    ),
    (
        "019_add_phase11_cross_sovereign_delegation",
        include_str!("019_add_phase11_cross_sovereign_delegation.sql"),
    ),
    (
        "020_add_phase11_reputation_signals",
        include_str!("020_add_phase11_reputation_signals.sql"),
    ),
    (
        "021_add_phase11_peer_discovery",
        include_str!("021_add_phase11_peer_discovery.sql"),
    ),
    (
        "022_add_phase11_invoice_lifecycle",
        include_str!("022_add_phase11_invoice_lifecycle.sql"),
    ),
    (
        "023_fix_phase11_gaps",
        include_str!("023_fix_phase11_gaps.sql"),
    ),
    (
        "024_add_phase13_escrow_ledger",
        include_str!("024_add_phase13_escrow_ledger.sql"),
    ),
    (
        "025_add_phase13_consensus",
        include_str!("025_add_phase13_consensus.sql"),
    ),
    (
        "026_add_phase13_cycle_healing",
        include_str!("026_add_phase13_cycle_healing.sql"),
    ),
    (
        "027_add_phase14_dispute_resolved",
        include_str!("027_add_phase14_dispute_resolved.sql"),
    ),
    (
        "028_add_phase15_behavioral_anomalies",
        include_str!("028_add_phase15_behavioral_anomalies.sql"),
    ),
    (
        "029_add_phase16_appeal_probation",
        include_str!("029_add_phase16_appeal_probation.sql"),
    ),
    (
        "030_add_phase17_topology_defense",
        include_str!("030_add_phase17_topology_defense.sql"),
    ),
    (
        "031_add_phase18_slashing",
        include_str!("031_add_phase18_slashing.sql"),
    ),
    (
        "032_add_smaos_intelligence_graph",
        include_str!("032_add_smaos_intelligence_graph.sql"),
    ),
    (
        "033_add_phase20_reputation_recovery",
        include_str!("033_add_phase20_reputation_recovery.sql"),
    ),
    (
        "034_add_phase21_trust_topology",
        include_str!("034_add_phase21_trust_topology.sql"),
    ),
    (
        "035_add_phase22_trust_anomaly_index",
        include_str!("035_add_phase22_trust_anomaly_index.sql"),
    ),
    (
        "036_add_phase23_observability_indexes",
        include_str!("036_add_phase23_observability_indexes.sql"),
    ),
    (
        "037_add_phase25_correlation_indexes",
        include_str!("037_add_phase25_correlation_indexes.sql"),
    ),
    (
        "038_add_phase26_chain_indexes",
        include_str!("038_add_phase26_chain_indexes.sql"),
    ),
    (
        "039_add_phase27_recovery_indexes",
        include_str!("039_add_phase27_recovery_indexes.sql"),
    ),
    (
        "040_add_phase28_prediction_indexes",
        include_str!("040_add_phase28_prediction_indexes.sql"),
    ),
    (
        "041_add_phase30_feedback_indexes",
        include_str!("041_add_phase30_feedback_indexes.sql"),
    ),
    (
        "042_add_rce_checkpoints",
        include_str!("042_add_rce_checkpoints.sql"),
    ),
    (
        "043_add_revocation_unique_constraint",
        include_str!("043_add_revocation_unique_constraint.sql"),
    ),
];

/// Run all migrations in order. Idempotent — tracks applied migrations in a metadata table.
pub async fn run_all(pool: &PgPool) -> Result<(), sqlx::Error> {
    sqlx::query(
        "CREATE TABLE IF NOT EXISTS _siss_migrations (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        )",
    )
    .execute(pool)
    .await?;

    for (name, sql) in MIGRATIONS {
        let already_applied: bool =
            sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM _siss_migrations WHERE name = $1)")
                .bind(name)
                .fetch_one(pool)
                .await?;

        if !already_applied {
            let mut tx = pool.begin().await?;
            sqlx::raw_sql(sql).execute(&mut *tx).await?;
            sqlx::query("INSERT INTO _siss_migrations (name) VALUES ($1)")
                .bind(name)
                .execute(&mut *tx)
                .await?;
            tx.commit().await?;
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt, core::WaitFor};

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

        let result: (String,) = sqlx::query_as("SELECT 'has_trust_policy'::edge_type::text")
            .fetch_one(&pool)
            .await
            .expect("query");

        assert_eq!(result.0, "has_trust_policy");
    }
}
