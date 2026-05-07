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
         ) < $2"
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
         WHERE id = $1"
    )
    .bind(memory_id)
    .bind(confidence_boost)
    .execute(pool)
    .await?;
    Ok(())
}
