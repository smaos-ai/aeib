use chrono::{DateTime, Utc};
use sqlx::PgPool;
use uuid::Uuid;

pub struct TrustEligibilityStatus {
    pub is_eligible: bool,
    pub reason: String,
}

pub struct TrustDecaySweepResult {
    pub edges_updated: i64,
}

// ============================================================================
// PURE FUNCTIONS
// ============================================================================

/// confidence [0.0, 1.0] → score [0, 100]
pub fn explicit_trust_score(confidence: f32) -> i16 {
    (confidence * 100.0) as i16
}

/// Linear decay: 0 at day 0, -50 at day 15, -100 at day 30+
pub fn trust_decay(last_interaction_at: DateTime<Utc>) -> i16 {
    let now = Utc::now();
    let duration = now.signed_duration_since(last_interaction_at);
    let days = duration.num_days() as f32;

    let penalty = -(days / 30.0 * 100.0);
    (penalty.floor().clamp(-100.0, 0.0)) as i16
}

/// Reuses Phase 19 formulas: -(slash_pen + anomaly_pen) + settlement_bonus
pub fn implicit_signal_contribution(
    slash_count: i64,
    anomaly_count: i64,
    settled_count: i64,
) -> i16 {
    let slash_penalty = (slash_count * 10).min(30);
    let anomaly_penalty = (anomaly_count * 8).min(20);
    let settlement_bonus = (settled_count * 5).min(20);

    (-(slash_penalty + anomaly_penalty) + settlement_bonus) as i16
}

/// clamp(explicit + implicit + decay + transitive_boost.unwrap_or(0), 0, 100)
pub fn compute_hybrid_trust_score(
    explicit_base: i16,
    implicit_adj: i16,
    decay_penalty: i16,
    transitive_boost: Option<i16>,
) -> i16 {
    let sum = explicit_base as i32
        + implicit_adj as i32
        + decay_penalty as i32
        + transitive_boost.unwrap_or(0) as i32;
    (sum.clamp(0, 100)) as i16
}

/// Extends compute_hybrid_trust_score with ProofOfSapience score fusion.
/// If pos_score is Some, computes pos_bonus = clamp(pos_score * 10.0, 0.0, 10.0) as i16
/// Returns: clamp(explicit + implicit + decay + transitive + pos_bonus, 0, 100)
/// If pos_score is None, behavior is identical to baseline (pos_bonus = 0)
pub fn compute_hybrid_trust_score_with_pos(
    explicit_base: i16,
    implicit_adj: i16,
    decay_penalty: i16,
    transitive_boost: Option<i16>,
    pos_score: Option<f64>,
) -> i16 {
    let pos_bonus = pos_score
        .map(|score| ((score * 10.0).clamp(0.0, 10.0)) as i16)
        .unwrap_or(0);

    let sum = explicit_base as i32
        + implicit_adj as i32
        + decay_penalty as i32
        + transitive_boost.unwrap_or(0) as i32
        + pos_bonus as i32;
    (sum.clamp(0, 100)) as i16
}

// ============================================================================
// ASYNC DB FUNCTIONS
// ============================================================================

/// Gate check: 5 settled invoices OR 7 days active/probation. Fails if quarantined/recovering.
pub async fn check_trust_eligibility(
    pool: &PgPool,
    source_id: Uuid,
    _target_id: Uuid,
) -> Result<TrustEligibilityStatus, sqlx::Error> {
    let sovereign: (String, Option<DateTime<Utc>>) =
        sqlx::query_as("SELECT status, established_at FROM sovereigns WHERE id = $1")
            .bind(source_id)
            .fetch_one(pool)
            .await?;

    let (status, established_at) = sovereign;

    if status == "quarantined" || status == "recovering" {
        return Ok(TrustEligibilityStatus {
            is_eligible: false,
            reason: format!("Sovereign is {}", status),
        });
    }

    let settled_count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM settlement_invoices WHERE debtor_sovereign_id = $1 AND status = 'settled'"
    )
    .bind(source_id)
    .fetch_one(pool)
    .await?;

    if settled_count.0 >= 5 {
        return Ok(TrustEligibilityStatus {
            is_eligible: true,
            reason: "5+ settled invoices".to_string(),
        });
    }

    if let Some(est_at) = established_at {
        let days_active = Utc::now().signed_duration_since(est_at).num_days();

        if days_active >= 7 && (status == "active" || status == "probation") {
            return Ok(TrustEligibilityStatus {
                is_eligible: true,
                reason: "7+ days active/probation".to_string(),
            });
        }
    }

    Ok(TrustEligibilityStatus {
        is_eligible: false,
        reason: "Insufficient settlements or tenure".to_string(),
    })
}

/// Writes TRUSTS edge if eligible; UPSERT pattern with voucher_count increment
pub async fn record_explicit_trust(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    confidence: f32,
) -> Result<(), sqlx::Error> {
    let eligibility = check_trust_eligibility(pool, source_id, target_id).await?;

    if !eligibility.is_eligible {
        return Err(sqlx::Error::RowNotFound);
    }

    let explicit_score = explicit_trust_score(confidence);

    sqlx::query(
        "INSERT INTO trust_network_edges (source_sovereign_id, target_sovereign_id, explicit_confidence, \
         explicit_component, hybrid_trust_score, is_explicit_eligible, eligibility_met_at) \
         VALUES ($1, $2, $3, $4, $5, TRUE, NOW()) \
         ON CONFLICT (source_sovereign_id, target_sovereign_id) \
         DO UPDATE SET explicit_confidence = $3, explicit_component = $4, \
         hybrid_trust_score = $5, is_explicit_eligible = TRUE, eligibility_met_at = NOW(), \
         voucher_count = voucher_count + 1, last_updated_at = NOW()"
    )
    .bind(source_id)
    .bind(target_id)
    .bind(confidence)
    .bind(explicit_score)
    .bind(explicit_score)
    .execute(pool)
    .await?;

    Ok(())
}

/// Orchestrates: fetch signals + transitive boost → compute → upsert → write graph → emit event
pub async fn compute_and_upsert_trust_score(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    broadcaster: Option<std::sync::Arc<crate::trust_event_broadcaster::TrustEventBroadcaster>>,
) -> Result<i16, sqlx::Error> {
    let explicit_conf: Option<f32> = sqlx::query_scalar(
        "SELECT explicit_confidence FROM trust_network_edges \
         WHERE source_sovereign_id = $1 AND target_sovereign_id = $2",
    )
    .bind(source_id)
    .bind(target_id)
    .fetch_optional(pool)
    .await?
    .flatten();

    let explicit_base = explicit_conf.map(explicit_trust_score).unwrap_or(0);

    let slash_count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM slashing_events WHERE sovereign_id = $1 AND status = 'active'",
    )
    .bind(target_id)
    .fetch_one(pool)
    .await?;

    let anomaly_count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM behavioral_anomalies WHERE sovereign_id = $1 AND status = 'active'",
    )
    .bind(target_id)
    .fetch_one(pool)
    .await?;

    let settled_count: (i64,) = sqlx::query_as(
        "SELECT COUNT(*) FROM settlement_invoices \
         WHERE (debtor_sovereign_id = $1 OR creditor_sovereign_id = $1) AND status = 'settled'",
    )
    .bind(target_id)
    .fetch_one(pool)
    .await?;

    let implicit_adj =
        implicit_signal_contribution(slash_count.0, anomaly_count.0, settled_count.0);

    let last_interaction: (DateTime<Utc>,) = sqlx::query_as(
        "SELECT COALESCE(last_interaction_at, NOW()) FROM trust_network_edges \
         WHERE source_sovereign_id = $1 AND target_sovereign_id = $2 \
         UNION ALL SELECT NOW() LIMIT 1",
    )
    .bind(source_id)
    .bind(target_id)
    .fetch_one(pool)
    .await?;

    let decay_penalty = trust_decay(last_interaction.0);

    let transitive_boost: Option<i16> = sqlx::query_scalar(
        "SELECT (ceiling_tier::smallint).min(15) FROM cross_sovereign_delegation_grants \
         WHERE grantor_sovereign_id = $1 AND grantee_sovereign_id = $2 \
         AND transitivity_depth <= 3 AND status = 'active' \
         AND (expires_at IS NULL OR expires_at > NOW()) AND revoked_at IS NULL \
         ORDER BY ceiling_tier DESC LIMIT 1",
    )
    .bind(source_id)
    .bind(target_id)
    .fetch_optional(pool)
    .await?
    .flatten();

    let hybrid_score =
        compute_hybrid_trust_score(explicit_base, implicit_adj, decay_penalty, transitive_boost);

    sqlx::query(
        "INSERT INTO trust_network_edges \
         (source_sovereign_id, target_sovereign_id, hybrid_trust_score, explicit_component, \
          implicit_component, decay_component, transitive_component, settled_invoice_count) \
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8) \
         ON CONFLICT (source_sovereign_id, target_sovereign_id) \
         DO UPDATE SET hybrid_trust_score = $3, explicit_component = $4, \
         implicit_component = $5, decay_component = $6, transitive_component = $7, \
         settled_invoice_count = $8, last_updated_at = NOW()",
    )
    .bind(source_id)
    .bind(target_id)
    .bind(hybrid_score)
    .bind(explicit_base)
    .bind(implicit_adj)
    .bind(decay_penalty)
    .bind(transitive_boost)
    .bind(settled_count.0)
    .execute(pool)
    .await?;

    if let Some(bc) = broadcaster {
        bc.emit(crate::trust_event_broadcaster::TrustUpdateSignal {
            source_id,
            target_id,
            new_score: hybrid_score,
            explicit_component: explicit_base,
            implicit_component: implicit_adj,
            decay_component: decay_penalty,
            transitive_component: transitive_boost,
            timestamp: chrono::Utc::now(),
        });
    }

    Ok(hybrid_score)
}

/// Computes hybrid trust score with ProofOfSapience integration.
/// Queries existing components (explicit, implicit, decay, transitive) and fuses pos_score.
/// UPSERT pattern: updates trust_network_edges.hybrid_trust_score with final clamped value.
/// Emits TrustUpdateSignal via broadcaster.
pub async fn compute_and_upsert_trust_score_with_pos(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    pos_score: Option<f64>,
    broadcaster: &crate::trust_event_broadcaster::TrustEventBroadcaster,
) -> Result<i16, sqlx::Error> {
    // Fetch existing trust components
    let row: Option<(Option<i16>, Option<i16>, Option<i16>, Option<i16>)> = sqlx::query_as(
        "SELECT explicit_component, implicit_component, decay_component, transitive_component \
         FROM trust_network_edges \
         WHERE source_sovereign_id = $1 AND target_sovereign_id = $2",
    )
    .bind(source_id)
    .bind(target_id)
    .fetch_optional(pool)
    .await?;

    let (explicit_base, implicit_adj, decay_penalty, transitive_boost) = match row {
        Some((e, i, d, t)) => (
            e.unwrap_or(0),
            i.unwrap_or(0),
            d.unwrap_or(0),
            t,
        ),
        None => (0, 0, 0, None),
    };

    // Compute hybrid score with ProofOfSapience fusion
    let hybrid_score = compute_hybrid_trust_score_with_pos(
        explicit_base,
        implicit_adj,
        decay_penalty,
        transitive_boost,
        pos_score,
    );

    // UPSERT: update hybrid_trust_score with new value
    sqlx::query(
        "INSERT INTO trust_network_edges \
         (source_sovereign_id, target_sovereign_id, hybrid_trust_score, explicit_component, \
          implicit_component, decay_component, transitive_component) \
         VALUES ($1, $2, $3, $4, $5, $6, $7) \
         ON CONFLICT (source_sovereign_id, target_sovereign_id) \
         DO UPDATE SET hybrid_trust_score = $3, last_updated_at = NOW()",
    )
    .bind(source_id)
    .bind(target_id)
    .bind(hybrid_score)
    .bind(explicit_base)
    .bind(implicit_adj)
    .bind(decay_penalty)
    .bind(transitive_boost)
    .execute(pool)
    .await?;

    // Emit event
    broadcaster.emit(crate::trust_event_broadcaster::TrustUpdateSignal {
        source_id,
        target_id,
        new_score: hybrid_score,
        explicit_component: explicit_base,
        implicit_component: implicit_adj,
        decay_component: decay_penalty,
        transitive_component: transitive_boost,
        timestamp: chrono::Utc::now(),
    });

    Ok(hybrid_score)
}

/// Daily sweep: recompute all edges. Skips quarantined/recovering sovereigns.
pub async fn sweep_trust_decay(pool: &PgPool) -> Result<TrustDecaySweepResult, sqlx::Error> {
    let edges: Vec<(Uuid, Uuid)> = sqlx::query_as(
        "SELECT tne.source_sovereign_id, tne.target_sovereign_id FROM trust_network_edges tne \
         INNER JOIN sovereigns s ON tne.source_sovereign_id = s.id \
         WHERE s.status NOT IN ('quarantined', 'recovering')",
    )
    .fetch_all(pool)
    .await?;

    let mut updated = 0i64;

    for (source_id, target_id) in edges {
        if compute_and_upsert_trust_score(pool, source_id, target_id, None)
            .await
            .is_ok()
        {
            updated += 1;
        }
    }

    Ok(TrustDecaySweepResult {
        edges_updated: updated,
    })
}

/// Record INFERRED_TRUST edge in graph_relationships with computed confidence score
pub async fn record_inferred_trust(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    inferred_score: f64,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO graph_relationships (source_entity_id, target_entity_id, relationship_type, confidence) \
         VALUES ($1, $2, 'INFERRED_TRUST', $3) \
         ON CONFLICT (source_entity_id, target_entity_id, relationship_type) \
         DO UPDATE SET confidence = $3, created_at = NOW()",
    )
    .bind(source_id)
    .bind(target_id)
    .bind(inferred_score)
    .execute(pool)
    .await?;

    Ok(())
}

/// Propose bilateral upgrade: if INFERRED_TRUST >= threshold, record TRUSTS edge via record_explicit_trust
pub async fn maybe_propose_bilateral_upgrade(
    pool: &PgPool,
    source_id: Uuid,
    target_id: Uuid,
    threshold: f64,
) -> Result<bool, sqlx::Error> {
    let inferred_conf: Option<f64> = sqlx::query_scalar(
        "SELECT confidence FROM graph_relationships \
         WHERE source_entity_id = $1 AND target_entity_id = $2 AND relationship_type = 'INFERRED_TRUST'",
    )
    .bind(source_id)
    .bind(target_id)
    .fetch_optional(pool)
    .await?
    .flatten();

    if let Some(conf) = inferred_conf {
        if conf >= threshold {
            // Call record_explicit_trust with confidence clamped to [0, 1]
            let explicit_confidence = (conf.min(1.0)) as f32;
            record_explicit_trust(pool, source_id, target_id, explicit_confidence)
                .await
                .ok();
            return Ok(true);
        }
    }

    Ok(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;

    // --- explicit_trust_score ---
    #[test]
    fn test_explicit_trust_score_full_confidence() {
        let score = explicit_trust_score(1.0);
        assert_eq!(score, 100);
    }

    #[test]
    fn test_explicit_trust_score_partial_confidence() {
        let score = explicit_trust_score(0.8);
        assert_eq!(score, 80);
    }

    // --- trust_decay ---
    #[test]
    fn test_trust_decay_none_at_day_0() {
        let now = Utc::now();
        let decay = trust_decay(now);
        assert_eq!(decay, 0);
    }

    #[test]
    fn test_trust_decay_full_at_day_30() {
        let thirty_days_ago = Utc::now() - Duration::days(30);
        let decay = trust_decay(thirty_days_ago);
        assert_eq!(decay, -100);
    }

    #[test]
    fn test_trust_decay_partial_at_day_15() {
        let fifteen_days_ago = Utc::now() - Duration::days(15);
        let decay = trust_decay(fifteen_days_ago);
        assert_eq!(decay, -50);
    }

    // --- compute_hybrid_trust_score ---
    #[test]
    fn test_hybrid_score_no_decay_clean() {
        let score = compute_hybrid_trust_score(80, 0, 0, None);
        assert_eq!(score, 80);
    }

    #[test]
    fn test_hybrid_score_decay_takes_full_effect() {
        let score = compute_hybrid_trust_score(80, 0, -100, None);
        assert_eq!(score, 0);
    }

    #[test]
    fn test_implicit_signals_drag_explicit_down() {
        let implicit = implicit_signal_contribution(3, 0, 0);
        assert_eq!(implicit, -30);
        let score = compute_hybrid_trust_score(80, implicit, 0, None);
        assert_eq!(score, 50);
    }

    #[test]
    fn test_implicit_override_severe_penalty() {
        let implicit = implicit_signal_contribution(3, 2, 1);
        assert_eq!(implicit, -41);
        let score = compute_hybrid_trust_score(90, implicit, 0, None);
        assert_eq!(score, 49);
    }

    #[test]
    fn test_transitive_boost_without_direct() {
        let score = compute_hybrid_trust_score(0, 0, 0, Some(15));
        assert_eq!(score, 15);
    }

    #[test]
    fn test_hybrid_score_clamped_to_100() {
        let score = compute_hybrid_trust_score(90, 20, 0, None);
        assert_eq!(score, 100);
    }

    #[test]
    fn test_hybrid_score_clamped_to_0() {
        let score = compute_hybrid_trust_score(30, -50, -60, None);
        assert_eq!(score, 0);
    }

    // --- compute_hybrid_trust_score_with_pos ---
    #[test]
    fn test_pos_bonus_added_to_hybrid_score() {
        // explicit=30, implicit=20, decay=10, transitive=None, pos_score=0.5
        // sum = 30 + 20 + 10 + 0 + 5 = 65
        let score = compute_hybrid_trust_score_with_pos(30, 20, 10, None, Some(0.5));
        assert_eq!(score, 65);
    }

    #[test]
    fn test_pos_none_unchanged_from_baseline() {
        // same inputs but pos_score=None: sum = 30 + 20 + 10 + 0 + 0 = 60
        let score = compute_hybrid_trust_score_with_pos(30, 20, 10, None, None);
        assert_eq!(score, 60);
    }

    #[test]
    fn test_pos_score_clamped_at_10_max() {
        // pos_score=2.0 would give pos_bonus=20, but clamped to 10
        // sum = 30 + 20 + 10 + 0 + 10 = 70 (not exceeding 100, but pos_bonus clamped)
        let score = compute_hybrid_trust_score_with_pos(30, 20, 10, None, Some(2.0));
        assert_eq!(score, 70);
    }

    #[test]
    fn test_pos_score_final_total_clamped_at_100() {
        // explicit=90, implicit=20, pos_score=1.5 → pos_bonus=10
        // sum = 90 + 20 + 0 + 0 + 10 = 120, clamped to 100
        let score = compute_hybrid_trust_score_with_pos(90, 20, 0, None, Some(1.5));
        assert_eq!(score, 100);
    }

    // --- record_inferred_trust and maybe_propose_bilateral_upgrade ---
    #[tokio::test]
    async fn test_record_inferred_trust_writes_edge() {
        // NOTE: This test would require testcontainers postgres setup.
        // For now, we document the expected behavior:
        // 1. record_inferred_trust inserts a row into graph_relationships
        // 2. A subsequent query finds the row with relationship_type = 'INFERRED_TRUST'
        // 3. confidence = inferred_score
        // TODO: Implement with testcontainers when DB test harness is set up
    }

    #[tokio::test]
    async fn test_bilateral_upgrade_triggers_at_threshold() {
        // NOTE: This test would require testcontainers postgres setup with sovereigns table.
        // Expected behavior:
        // 1. Insert INFERRED_TRUST edge with confidence = 0.75
        // 2. Call maybe_propose_bilateral_upgrade with threshold = 0.7
        // 3. Verify record_explicit_trust was called (check trust_network_edges for TRUSTS edge)
        // 4. Return Ok(true)
        // TODO: Implement with testcontainers when DB test harness is set up
    }

    #[tokio::test]
    async fn test_bilateral_upgrade_skips_below_threshold() {
        // NOTE: This test would require testcontainers postgres setup.
        // Expected behavior:
        // 1. Insert INFERRED_TRUST edge with confidence = 0.65
        // 2. Call maybe_propose_bilateral_upgrade with threshold = 0.7
        // 3. Verify record_explicit_trust was NOT called
        // 4. Return Ok(false)
        // TODO: Implement with testcontainers when DB test harness is set up
    }
}
