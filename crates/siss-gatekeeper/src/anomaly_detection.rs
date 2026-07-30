use sqlx::PgPool;

/// Detect if there's a latency spike for an agent.
/// Returns true if the last N heartbeats all have latency > 1000ms.
pub async fn detect_latency_spike(
    pool: &PgPool,
    agent_id: &str,
    window_count: i64,
) -> Result<bool, sqlx::Error> {
    // Get last N heartbeats
    let heartbeats: Vec<(i64,)> = sqlx::query_as(
        "SELECT latency_ms FROM agent_heartbeats WHERE agent_id = $1 ORDER BY created_at DESC LIMIT $2"
    )
    .bind(agent_id)
    .bind(window_count)
    .fetch_all(pool)
    .await?;

    if heartbeats.len() < window_count as usize {
        return Ok(false);
    }

    // Check if all are > 1000ms
    let all_spiked = heartbeats.iter().all(|(latency_ms,)| *latency_ms > 1000);

    Ok(all_spiked)
}

/// Detect packet loss for an agent.
/// Returns true if more than threshold_loss_pct of expected heartbeats are missing.
/// This checks if we have enough heartbeats based on time elapsed.
pub async fn detect_packet_loss(
    pool: &PgPool,
    agent_id: &str,
    threshold_loss_pct: f64,
) -> Result<bool, sqlx::Error> {
    // Get all heartbeats for this agent
    let count: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM agent_heartbeats WHERE agent_id = $1")
        .bind(agent_id)
        .fetch_one(pool)
        .await?;

    let actual_count = count.0;

    // If we have no heartbeats, we can't reliably detect packet loss
    if actual_count == 0 {
        return Ok(false);
    }

    // Expected minimum: 10 heartbeats
    // Actual: N heartbeats
    // Loss % = (10 - N) / 10 * 100
    let expected_count = 10i64;

    if actual_count >= expected_count {
        return Ok(false); // We got at least what we expected
    }

    let loss_pct = ((expected_count - actual_count) as f64 / expected_count as f64) * 100.0;
    Ok(loss_pct > threshold_loss_pct)
}
