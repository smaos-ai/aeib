use sqlx::PgPool;
use uuid::Uuid;

/// Find all memory nodes below the confidence threshold (eligible for GC).
/// Uses the Ebbinghaus decay formula computed in SQL.
pub async fn find_gc_candidates(
    pool: &PgPool,
    threshold: f64,
    tenant_id: Uuid,
) -> Result<Vec<Uuid>, sqlx::Error> {
    let ids: Vec<Uuid> = sqlx::query_scalar(
        "SELECT id FROM memories \
         WHERE tenant_id = $1 \
         AND consolidation_tier != 'working' \
         AND confidence_score * EXP(
             -EXTRACT(EPOCH FROM (NOW() - last_reinforced_at)) / 3600.0 / \
             CASE consolidation_tier \
                 WHEN 'episodic' THEN 48.0 \
                 WHEN 'semantic' THEN 168.0 \
                 WHEN 'procedural' THEN 720.0 \
                 ELSE 1.0 \
             END \
         ) < $2",
    )
    .bind(tenant_id)
    .bind(threshold)
    .fetch_all(pool)
    .await?;
    Ok(ids)
}

/// Delete memory nodes by ID (garbage collection).
pub async fn delete_memories(pool: &PgPool, ids: &[Uuid]) -> Result<u64, sqlx::Error> {
    if ids.is_empty() {
        return Ok(0);
    }
    let result = sqlx::query("DELETE FROM memories WHERE id = ANY($1)")
        .bind(ids)
        .execute(pool)
        .await?;
    Ok(result.rows_affected())
}

/// Reinforce a memory node: reset last_reinforced_at to now and optionally boost confidence.
pub async fn reinforce_memory(
    pool: &PgPool,
    memory_id: Uuid,
    confidence_boost: f64,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE memories \
         SET last_reinforced_at = NOW(), \
             confidence_score = LEAST(1.0, confidence_score + $2) \
         WHERE id = $1",
    )
    .bind(memory_id)
    .bind(confidence_boost)
    .execute(pool)
    .await?;
    Ok(())
}

/// Fetch memories of a given tier for a tenant, above the confidence threshold.
/// For procedural/semantic: sorted by confidence descending.
/// For episodic: sorted by created_at descending (most recent first).
pub async fn fetch_memories_by_tier(
    pool: &PgPool,
    tier: &str,
    tenant_id: Uuid,
    confidence_threshold: f64,
    limit: i64,
) -> Result<Vec<(Uuid, String, f64, String)>, sqlx::Error> {
    let order_clause = if tier == "episodic" {
        "ORDER BY created_at DESC"
    } else {
        "ORDER BY confidence_score DESC"
    };

    let query = format!(
        "SELECT id, content, confidence_score, consolidation_tier::text \
         FROM memories \
         WHERE tenant_id = $1 \
         AND consolidation_tier = $2::consolidation_tier \
         AND confidence_score * EXP( \
             -EXTRACT(EPOCH FROM (NOW() - last_reinforced_at)) / 3600.0 / \
             CASE consolidation_tier \
                 WHEN 'episodic' THEN 48.0 \
                 WHEN 'semantic' THEN 168.0 \
                 WHEN 'procedural' THEN 720.0 \
                 ELSE 1.0 \
             END \
         ) >= $3 \
         {} \
         LIMIT $4",
        order_clause
    );

    let rows: Vec<(Uuid, String, f64, String)> = sqlx::query_as(&query)
        .bind(tenant_id)
        .bind(tier)
        .bind(confidence_threshold)
        .bind(limit)
        .fetch_all(pool)
        .await?;

    Ok(rows)
}

/// Get all memory IDs that a Persona can read (via direct CAN_READ edges).
pub async fn fetch_accessible_memory_ids(
    pool: &PgPool,
    persona_id: Uuid,
    tenant_id: Uuid,
) -> Result<Vec<Uuid>, sqlx::Error> {
    let ids: Vec<Uuid> = sqlx::query_scalar(
        "SELECT target_id FROM edges \
         WHERE source_id = $1 \
         AND edge_type = 'can_read' \
         AND tenant_id = $2",
    )
    .bind(persona_id)
    .bind(tenant_id)
    .fetch_all(pool)
    .await?;
    Ok(ids)
}

/// Insert a new memory node. Returns its ID.
pub async fn insert_memory(
    pool: &PgPool,
    content: &str,
    tier: &str,
    confidence_score: f64,
    quality_score: f64,
    tenant_id: Uuid,
) -> Result<Uuid, sqlx::Error> {
    let id = Uuid::new_v4();
    sqlx::query(
        "INSERT INTO memories (id, tenant_id, content, consolidation_tier, confidence_score, quality_score) \
         VALUES ($1, $2, $3, $4::consolidation_tier, $5, $6)"
    )
    .bind(id)
    .bind(tenant_id)
    .bind(content)
    .bind(tier)
    .bind(confidence_score)
    .bind(quality_score)
    .execute(pool)
    .await?;
    Ok(id)
}
