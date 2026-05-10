/// Phase 11: Reputation Signals
/// Federated reputation signal storage with isolation enforcement
use chrono::{DateTime, Utc};
use serde_json::json;
use sqlx::PgPool;
use std::collections::BTreeMap;
use uuid::Uuid;

pub const REPUTATION_ISOLATION: &str = "foreign_signals_cannot_boost_local_tier";

/// Insert a reputation signal (foreign signals always have lineage_safe = false).
pub async fn insert_reputation_signal(
    pool: &PgPool,
    source_sovereign_id: Uuid,
    subject_agent_id: &str,
    signal_type: &str,
    signal_strength: i16,
    source_gossip_message_id: Option<Uuid>,
    observed_at: DateTime<Utc>,
    signal_signature: &str,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    // lineage_safe MUST be false (DB constraint enforces this)
    sqlx::query(
        "INSERT INTO federated_reputation_signals \
         (id, source_sovereign_id, subject_agent_id, signal_type, signal_strength, \
          source_gossip_message_id, observed_at, signal_signature, lineage_safe) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, false)",
    )
    .bind(id)
    .bind(source_sovereign_id)
    .bind(subject_agent_id)
    .bind(signal_type)
    .bind(signal_strength)
    .bind(source_gossip_message_id)
    .bind(observed_at)
    .bind(signal_signature)
    .execute(pool)
    .await?;

    Ok(id)
}

/// Fetch reputation signals for an agent within a time window (days).
/// Returns (signal_strength, observed_at) tuples.
pub async fn fetch_reputation_signals_for_agent(
    pool: &PgPool,
    source_sovereign_id: Uuid,
    subject_agent_id: &str,
    window_days: i64,
) -> Result<Vec<(i16, DateTime<Utc>)>, sqlx::Error> {
    let cutoff = Utc::now() - chrono::Duration::days(window_days);

    sqlx::query_as::<_, (i16, DateTime<Utc>)>(
        "SELECT signal_strength, observed_at \
         FROM federated_reputation_signals \
         WHERE source_sovereign_id = $1 AND subject_agent_id = $2 AND observed_at >= $3 \
         ORDER BY observed_at DESC",
    )
    .bind(source_sovereign_id)
    .bind(subject_agent_id)
    .bind(cutoff)
    .fetch_all(pool)
    .await
}

/// Update the reputation blend weight for a federation peer (directional).
pub async fn update_reputation_blend_weight(
    pool: &PgPool,
    federation_peer_id: Uuid,
    new_weight: f64,
) -> Result<bool, sqlx::Error> {
    if !(0.0..=1.0).contains(&new_weight) {
        return Ok(false);
    }

    let affected = sqlx::query_scalar::<_, i64>(
        "UPDATE federation_peers \
         SET reputation_blend_weight = $1 \
         WHERE id = $2 \
         RETURNING 1",
    )
    .bind(new_weight)
    .bind(federation_peer_id)
    .fetch_optional(pool)
    .await?
    .unwrap_or(0);

    Ok(affected > 0)
}

/// Get the reputation blend weight for a bilateral agreement.
pub async fn get_reputation_blend_weight(
    pool: &PgPool,
    sovereign_a_id: Uuid,
    sovereign_b_id: Uuid,
) -> Result<Option<f64>, sqlx::Error> {
    sqlx::query_scalar::<_, f64>(
        "SELECT reputation_blend_weight FROM federation_peers \
         WHERE sovereign_a_id = $1 AND sovereign_b_id = $2 AND status = 'active' \
         LIMIT 1",
    )
    .bind(sovereign_a_id)
    .bind(sovereign_b_id)
    .fetch_optional(pool)
    .await
}

/// Build canonical signal payload for signature verification (BTreeMap alphabetical order).
pub fn build_canonical_signal_payload(
    source_sovereign_id: &str,
    subject_agent_id: &str,
    signal_type: &str,
    signal_strength: i16,
    observed_at: &str,
) -> String {
    let mut map = BTreeMap::new();
    map.insert("observed_at", json!(observed_at));
    map.insert("signal_strength", json!(signal_strength));
    map.insert("signal_type", json!(signal_type));
    map.insert("source_sovereign_id", json!(source_sovereign_id));
    map.insert("subject_agent_id", json!(subject_agent_id));

    serde_json::to_string(&map).unwrap_or_default()
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

        crate::migrations::run_all(&pool).await.expect("migrations");
        (container, pool)
    }

    async fn setup_sovereigns(pool: &PgPool) -> (Uuid, Uuid) {
        let sovereign_a = Uuid::new_v4();
        let sovereign_b = Uuid::new_v4();

        sqlx::query(
            "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem) VALUES ($1, $2, $3, $4)"
        )
        .bind(sovereign_a)
        .bind("sovereign_a")
        .bind("http://localhost:8001")
        .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
        .execute(pool)
        .await
        .expect("insert sovereign_a");

        sqlx::query(
            "INSERT INTO sovereigns (id, name, endpoint_url, public_key_pem) VALUES ($1, $2, $3, $4)"
        )
        .bind(sovereign_b)
        .bind("sovereign_b")
        .bind("http://localhost:8002")
        .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBALqxBjq9i\n-----END PUBLIC KEY-----")
        .execute(pool)
        .await
        .expect("insert sovereign_b");

        (sovereign_a, sovereign_b)
    }

    #[tokio::test]
    async fn test_insert_signal_lineage_safe_always_false() {
        let (_container, pool) = setup_postgres().await;
        let (sovereign_a, _sovereign_b) = setup_sovereigns(&pool).await;

        let result = insert_reputation_signal(
            &pool,
            sovereign_a,
            "agent_subject",
            "positive",
            5,
            None,
            Utc::now(),
            "sig_hex",
        )
        .await;

        assert!(result.is_ok());
        let signal_id = result.unwrap();

        // Verify lineage_safe is false
        let lineage_safe: bool = sqlx::query_scalar(
            "SELECT lineage_safe FROM federated_reputation_signals WHERE id = $1",
        )
        .bind(signal_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert!(
            !lineage_safe,
            "lineage_safe must be false for all foreign signals"
        );
    }

    #[tokio::test]
    async fn test_fetch_signals_within_window() {
        let (_container, pool) = setup_postgres().await;
        let (sovereign_a, _sovereign_b) = setup_sovereigns(&pool).await;
        let now = Utc::now();

        // Insert signal from 2 days ago
        let _sig1 = insert_reputation_signal(
            &pool,
            sovereign_a,
            "agent_subject",
            "positive",
            5,
            None,
            now - chrono::Duration::days(2),
            "sig_1",
        )
        .await
        .expect("insert signal 1");

        // Insert signal from 10 days ago (outside 7-day window)
        let _sig2 = insert_reputation_signal(
            &pool,
            sovereign_a,
            "agent_subject",
            "negative",
            -3,
            None,
            now - chrono::Duration::days(10),
            "sig_2",
        )
        .await
        .expect("insert signal 2");

        let signals = fetch_reputation_signals_for_agent(&pool, sovereign_a, "agent_subject", 7)
            .await
            .expect("fetch");

        assert_eq!(
            signals.len(),
            1,
            "should only return signal within 7-day window"
        );
        assert_eq!(signals[0].0, 5, "signal strength should match");
    }

    #[tokio::test]
    async fn test_update_blend_weight_valid() {
        let (_container, pool) = setup_postgres().await;
        let (sovereign_a, sovereign_b) = setup_sovereigns(&pool).await;

        let peer_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, \
             granted_attestation_types, foreign_agent_budget_cap, status) \
             VALUES ($1, $2, $3, $4, $5, $6, 'active')",
        )
        .bind(peer_id)
        .bind(sovereign_a)
        .bind(sovereign_b)
        .bind(100i16)
        .bind(vec!["agent_identity"])
        .bind(1000000i64)
        .execute(&pool)
        .await
        .expect("insert peer");

        let result = update_reputation_blend_weight(&pool, peer_id, 0.5)
            .await
            .expect("update");
        assert!(result, "update should succeed with valid weight");

        let weight: f64 = sqlx::query_scalar(
            "SELECT reputation_blend_weight FROM federation_peers WHERE id = $1",
        )
        .bind(peer_id)
        .fetch_one(&pool)
        .await
        .expect("fetch");

        assert_eq!(weight, 0.5);
    }

    #[tokio::test]
    async fn test_update_blend_weight_out_of_range_rejected() {
        let (_container, pool) = setup_postgres().await;
        let (sovereign_a, sovereign_b) = setup_sovereigns(&pool).await;

        let peer_id = Uuid::new_v4();
        sqlx::query(
            "INSERT INTO federation_peers (id, sovereign_a_id, sovereign_b_id, max_admitted_tier, \
             granted_attestation_types, foreign_agent_budget_cap, status) \
             VALUES ($1, $2, $3, $4, $5, $6, 'active')",
        )
        .bind(peer_id)
        .bind(sovereign_a)
        .bind(sovereign_b)
        .bind(100i16)
        .bind(vec!["agent_identity"])
        .bind(1000000i64)
        .execute(&pool)
        .await
        .expect("insert peer");

        let result = update_reputation_blend_weight(&pool, peer_id, 1.5)
            .await
            .expect("update");
        assert!(!result, "update with weight > 1.0 should be rejected");
    }

    #[test]
    fn test_canonical_signal_payload_alphabetical() {
        let payload = build_canonical_signal_payload(
            "00000000-0000-0000-0000-000000000001",
            "agent_subject",
            "positive",
            5,
            "2026-01-01T00:00:00Z",
        );

        let observed_idx = payload.find("observed_at").unwrap();
        let strength_idx = payload.find("signal_strength").unwrap();
        let type_idx = payload.find("signal_type").unwrap();
        let source_idx = payload.find("source_sovereign_id").unwrap();
        let subject_idx = payload.find("subject_agent_id").unwrap();

        assert!(observed_idx < strength_idx);
        assert!(strength_idx < type_idx);
        assert!(type_idx < source_idx);
        assert!(source_idx < subject_idx);
    }
}
