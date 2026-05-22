/// Production database interface for Night Cycle state management.
/// Stub for Phase 43; implements atomic archive-and-prune pattern.

use sqlx::PgPool;

/// Archive COMPLETE rows to crystallized_archive, then purge from swarm_state.
/// Fails-closed: no rows are removed unless both operations succeed.
pub async fn archive_and_prune(
    pool: &PgPool,
    crystallized_keys: &[String],
) -> Result<usize, sqlx::Error> {
    let mut tx = pool.begin().await?;

    // STEP 1: move to archive table
    for key in crystallized_keys {
        sqlx::query(
            "INSERT INTO crystallized_archive (idempotency_key, agent_id, phase, status, payload_json, crystallized_at)
             SELECT idempotency_key, agent_id, phase, status, payload_json, NOW()
             FROM swarm_state WHERE idempotency_key = $1"
        )
        .bind(key)
        .execute(&mut *tx)
        .await?;
    }

    // STEP 2: remove from hot store only after archive succeeds
    let mut pruned = 0;
    for key in crystallized_keys {
        let result = sqlx::query(
            "DELETE FROM swarm_state WHERE idempotency_key = $1 AND status IN ('COMPLETE', 'FAILED')"
        )
        .bind(key)
        .execute(&mut *tx)
        .await?;
        pruned += result.rows_affected() as usize;
    }

    tx.commit().await?;
    Ok(pruned)
}

#[cfg(test)]
mod tests {
    // Stub: production tests would use testcontainers with real PostgreSQL
}
