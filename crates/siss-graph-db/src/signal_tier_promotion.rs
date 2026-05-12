use chrono::{DateTime, Utc};
use sqlx::{PgPool, Row};
use uuid::Uuid;

/// Decay formula for signals, parameterized by tier.
/// Semantic tier uses 30-day half-life and ignores acceleration_mode.
/// Episodic tier uses 7-day or 2-day half-life depending on acceleration_mode.
/// Returns decayed confidence, floored at 0.05.
pub fn apply_decay_with_tier(
    confidence: f64,
    last_seen_at: DateTime<Utc>,
    tier: &str,
    acceleration_mode: bool,
) -> f64 {
    let elapsed = Utc::now() - last_seen_at;
    let days_since_last_seen = elapsed.num_days() as f64;

    if days_since_last_seen < 0.0 {
        return confidence; // Clock skew: return original confidence
    }

    let half_life = match tier {
        "semantic" => 30.0, // Semantic tier always uses 30-day half-life
        _ => if acceleration_mode { 2.0 } else { 7.0 }, // Episodic (or unknown) respects acceleration_mode
    };

    let decayed = confidence * 0.5_f64.powf(days_since_last_seen / half_life);
    decayed.max(0.05) // Floor at 0.05
}

/// Promote a signal from Episodic to Semantic tier when confidence >= 0.90.
/// Returns true if promotion occurred, false if already Semantic or confidence < 0.90.
pub async fn promote_signal_to_semantic_on_validation(
    pool: &PgPool,
    signal_id: Uuid,
    signal_type: &str,
    new_confidence: f64,
) -> Result<bool, sqlx::Error> {
    // Only promote if confidence >= 0.90
    if new_confidence < 0.90 {
        return Ok(false);
    }

    // Fetch the signal node
    let signal_row =
        sqlx::query("SELECT properties FROM graph_entities WHERE id = $1 AND label = $2")
            .bind(signal_id)
            .bind(signal_type)
            .fetch_optional(pool)
            .await?;

    let signal_props = match signal_row {
        None => return Ok(false), // Signal not found
        Some(row) => row.get::<serde_json::Value, _>(0),
    };

    // Check if already Semantic
    let current_tier = signal_props
        .get("tier")
        .and_then(|v| v.as_str())
        .unwrap_or("episodic");

    if current_tier == "semantic" {
        return Ok(false); // Already Semantic
    }

    // Promote to Semantic: update tier and promoted_at
    let update_result = sqlx::query(
        "UPDATE graph_entities
         SET properties = properties
             || jsonb_build_object('tier', 'semantic', 'promoted_at', $3::text)
         WHERE id = $1 AND label = $2 AND properties->>'tier' != 'semantic'",
    )
    .bind(signal_id)
    .bind(signal_type)
    .bind(Utc::now().to_rfc3339())
    .execute(pool)
    .await?;

    Ok(update_result.rows_affected() > 0)
}

/// Demote a signal from Semantic to Episodic tier when confidence < 0.85.
/// Returns true if demotion occurred, false if stayed Semantic or still above threshold.
pub async fn demote_signal_to_episodic_on_failure(
    pool: &PgPool,
    signal_id: Uuid,
    signal_type: &str,
    confidence_after_decay: f64,
) -> Result<bool, sqlx::Error> {
    // Only demote if confidence < 0.85
    if confidence_after_decay >= 0.85 {
        return Ok(false);
    }

    // Fetch the signal node
    let signal_row =
        sqlx::query("SELECT properties FROM graph_entities WHERE id = $1 AND label = $2")
            .bind(signal_id)
            .bind(signal_type)
            .fetch_optional(pool)
            .await?;

    let mut signal_props = match signal_row {
        None => return Ok(false), // Signal not found
        Some(row) => row.get::<serde_json::Value, _>(0),
    };

    // Check if Semantic
    let current_tier = signal_props
        .get("tier")
        .and_then(|v| v.as_str())
        .unwrap_or("episodic");

    if current_tier != "semantic" {
        return Ok(false); // Not Semantic, cannot demote
    }

    // Demote to Episodic: update tier, last_demotion_at, and reset acceleration_mode
    signal_props["tier"] = serde_json::json!("episodic");
    signal_props["last_demotion_at"] = serde_json::json!(Utc::now().to_rfc3339());
    signal_props["acceleration_mode"] = serde_json::json!(false); // Reset acceleration mode

    sqlx::query(
        "INSERT INTO graph_entities (id, label, properties)
         VALUES ($1, $2, $3)
         ON CONFLICT (id) DO UPDATE SET properties = $3",
    )
    .bind(signal_id)
    .bind(signal_type)
    .bind(signal_props)
    .execute(pool)
    .await?;

    Ok(true)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;
    use serde_json::json;
    use sqlx::Row;
    use testcontainers::core::WaitFor;
    use testcontainers::runners::AsyncRunner;
    use testcontainers::{GenericImage, ImageExt};

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

        let pool = sqlx::postgres::PgPoolOptions::new()
            .max_connections(5)
            .connect(&url)
            .await
            .expect("postgres pool created");

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS graph_entities (
                id UUID PRIMARY KEY,
                label TEXT NOT NULL,
                properties JSONB NOT NULL
            )",
        )
        .execute(&pool)
        .await
        .expect("graph_entities table created");

        (container, pool)
    }

    #[tokio::test]
    async fn test_promote_signal_at_0_90_threshold() {
        let (_container, pool) = setup_postgres().await;

        let signal_id = Uuid::new_v4();
        let signal_type = "AnomalyChainNode";

        // Insert signal: tier=episodic, confidence=0.90
        let props = json!({
            "tier": "episodic",
            "confidence": 0.90,
            "last_seen_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind(signal_type)
            .bind(props)
            .execute(&pool)
            .await
            .expect("signal inserted");

        // Promote at exactly 0.90
        let promoted =
            promote_signal_to_semantic_on_validation(&pool, signal_id, signal_type, 0.90)
                .await
                .expect("promotion succeeded");

        assert!(promoted, "Signal should be promoted at 0.90 confidence");

        // Verify tier is now semantic
        let row = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("signal fetched");

        let props: serde_json::Value = row.get(0);
        assert_eq!(props["tier"].as_str(), Some("semantic"));
        assert!(props["promoted_at"].as_str().is_some());
    }

    #[tokio::test]
    async fn test_no_promote_below_0_90_threshold() {
        let (_container, pool) = setup_postgres().await;

        let signal_id = Uuid::new_v4();
        let signal_type = "AnomalyChainNode";

        let props = json!({
            "tier": "episodic",
            "confidence": 0.89,
            "last_seen_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind(signal_type)
            .bind(props)
            .execute(&pool)
            .await
            .expect("signal inserted");

        // Try to promote below 0.90
        let promoted =
            promote_signal_to_semantic_on_validation(&pool, signal_id, signal_type, 0.89)
                .await
                .expect("promotion check succeeded");

        assert!(!promoted, "Signal below 0.90 should not be promoted");

        // Verify tier is still episodic
        let row = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("signal fetched");

        let props: serde_json::Value = row.get(0);
        assert_eq!(props["tier"].as_str(), Some("episodic"));
    }

    #[tokio::test]
    async fn test_demote_signal_at_0_85_threshold() {
        let (_container, pool) = setup_postgres().await;

        let signal_id = Uuid::new_v4();
        let signal_type = "AnomalyChainNode";

        // Insert signal: tier=semantic, confidence=0.90
        let props = json!({
            "tier": "semantic",
            "confidence": 0.90,
            "last_seen_at": Utc::now().to_rfc3339(),
            "acceleration_mode": true,
        });

        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind(signal_type)
            .bind(props)
            .execute(&pool)
            .await
            .expect("signal inserted");

        // Demote when confidence drops to 0.85
        let demoted = demote_signal_to_episodic_on_failure(&pool, signal_id, signal_type, 0.85)
            .await
            .expect("demotion check succeeded");

        assert!(
            !demoted,
            "Signal at exactly 0.85 should not be demoted (>=0.85 stays)"
        );

        // Now try with 0.84 (strictly below)
        let demoted = demote_signal_to_episodic_on_failure(&pool, signal_id, signal_type, 0.84)
            .await
            .expect("demotion check succeeded");

        assert!(demoted, "Signal strictly below 0.85 should be demoted");

        // Verify tier is now episodic and acceleration_mode is reset
        let row = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("signal fetched");

        let props: serde_json::Value = row.get(0);
        assert_eq!(props["tier"].as_str(), Some("episodic"));
        assert_eq!(props["acceleration_mode"].as_bool(), Some(false));
        assert!(props["last_demotion_at"].as_str().is_some());
    }

    #[tokio::test]
    async fn test_no_demote_above_0_85_threshold() {
        let (_container, pool) = setup_postgres().await;

        let signal_id = Uuid::new_v4();
        let signal_type = "AnomalyChainNode";

        let props = json!({
            "tier": "semantic",
            "confidence": 0.86,
            "last_seen_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind(signal_type)
            .bind(props)
            .execute(&pool)
            .await
            .expect("signal inserted");

        // Try to demote above 0.85
        let demoted = demote_signal_to_episodic_on_failure(&pool, signal_id, signal_type, 0.86)
            .await
            .expect("demotion check succeeded");

        assert!(!demoted, "Signal above 0.85 should not be demoted");

        // Verify tier is still semantic
        let row = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("signal fetched");

        let props: serde_json::Value = row.get(0);
        assert_eq!(props["tier"].as_str(), Some("semantic"));
    }

    #[tokio::test]
    async fn test_hysteresis_at_0_88_stays_semantic() {
        let (_container, pool) = setup_postgres().await;

        let signal_id = Uuid::new_v4();
        let signal_type = "AnomalyChainNode";

        // Insert signal: tier=semantic, confidence=0.88
        let props = json!({
            "tier": "semantic",
            "confidence": 0.88,
            "last_seen_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind(signal_type)
            .bind(props)
            .execute(&pool)
            .await
            .expect("signal inserted");

        // Apply minor decay: 0.88 × 0.9999 ≈ 0.879
        let decayed =
            apply_decay_with_tier(0.88, Utc::now() - Duration::seconds(1), "semantic", false);
        assert!(
            decayed >= 0.87 && decayed <= 0.89,
            "Decay of ~1 second should barely affect confidence"
        );

        // Try to demote at 0.879 (still above 0.85)
        let demoted = demote_signal_to_episodic_on_failure(&pool, signal_id, signal_type, decayed)
            .await
            .expect("demotion check succeeded");

        assert!(
            !demoted,
            "Signal at 0.88 with minor decay should stay Semantic (doesn't hit 0.85)"
        );

        // Verify tier is still semantic
        let row = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("signal fetched");

        let props: serde_json::Value = row.get(0);
        assert_eq!(props["tier"].as_str(), Some("semantic"));
    }

    #[tokio::test]
    async fn test_semantic_decay_uses_30_day_half_life() {
        // Test 6: Semantic signal, last_seen=30 days ago, confidence=0.8
        // Expected: decayed = 0.4 (0.8 × 0.5^(30/30) = 0.8 × 0.5 = 0.4)

        let last_seen = Utc::now() - Duration::days(30);
        let decayed = apply_decay_with_tier(0.8, last_seen, "semantic", false);

        assert!(
            (decayed - 0.4).abs() < 0.001,
            "Semantic decay at 30 days should be 0.4, got {}",
            decayed
        );
    }

    #[tokio::test]
    async fn test_semantic_decay_ignores_acceleration_mode() {
        // Test 7: Semantic signal, acceleration_mode=true, last_seen=14 days ago
        // Expected: Uses 30-day half-life (not 2-day), decayed ≈ 0.575
        // CRITICAL: acceleration_mode must be IGNORED for Semantic tier

        let last_seen = Utc::now() - Duration::days(14);
        let decayed = apply_decay_with_tier(0.8, last_seen, "semantic", true);

        // 0.8 × 0.5^(14/30) ≈ 0.8 × 0.7206 ≈ 0.576
        let expected = 0.8 * 0.5_f64.powf(14.0 / 30.0);
        assert!(
            (decayed - expected).abs() < 0.01,
            "Semantic decay with acceleration_mode=true should ignore acceleration and use 30-day half-life. Got {}, expected ~{}",
            decayed,
            expected
        );
    }

    #[tokio::test]
    async fn test_episodic_decay_with_acceleration_uses_2_day_half_life() {
        // Test 8: Episodic signal, acceleration_mode=true, last_seen=14 days ago
        // Expected: Uses 2-day half-life, decayed ≈ 0.008 → floored to 0.05
        // 0.8 × 0.5^(14/2) = 0.8 × 0.5^7 = 0.8 × 0.0078125 ≈ 0.00625
        // Floored to 0.05

        let last_seen = Utc::now() - Duration::days(14);
        let decayed = apply_decay_with_tier(0.8, last_seen, "episodic", true);

        // Should be floored at 0.05
        assert_eq!(
            decayed, 0.05,
            "Episodic decay with acceleration should floor at 0.05, got {}",
            decayed
        );
    }

    #[tokio::test]
    async fn test_promotion_on_reinforcement_integration() {
        let (_container, pool) = setup_postgres().await;

        let signal_id = Uuid::new_v4();
        let signal_type = "AnomalyChainNode";

        // Insert signal: tier=episodic, confidence=0.85
        let props = json!({
            "tier": "episodic",
            "confidence": 0.85,
            "last_seen_at": Utc::now().to_rfc3339(),
        });

        sqlx::query("INSERT INTO graph_entities (id, label, properties) VALUES ($1, $2, $3)")
            .bind(signal_id)
            .bind(signal_type)
            .bind(props)
            .execute(&pool)
            .await
            .expect("signal inserted");

        // Simulate reinforcement: boost confidence until >= 0.90
        // Formula: confidence += (1.0 - confidence) * 0.05
        // Need 8 boosts to reach >= 0.90 from 0.85
        let mut confidence = 0.85;
        for _ in 0..8 {
            confidence = confidence + ((1.0 - confidence) * 0.05);
        }

        // Trigger promotion
        let promoted =
            promote_signal_to_semantic_on_validation(&pool, signal_id, signal_type, confidence)
                .await
                .expect("Promote failed");

        assert!(promoted, "Should promote when confidence > 0.90");

        // Verify tier is now Semantic
        let signal = sqlx::query("SELECT properties FROM graph_entities WHERE id = $1")
            .bind(signal_id)
            .fetch_one(&pool)
            .await
            .expect("Signal not found");

        let props: serde_json::Value = signal.get(0);
        assert_eq!(
            props["tier"].as_str(),
            Some("semantic"),
            "Integration test: reinforced signal should promote to Semantic"
        );
    }
}
