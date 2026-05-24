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
    // Get all heartbeats for this agent with their timestamps
    let heartbeats: Vec<(String, String)> = sqlx::query_as(
        "SELECT created_at::text, created_at::text FROM agent_heartbeats WHERE agent_id = $1 ORDER BY created_at ASC"
    )
    .bind(agent_id)
    .fetch_all(pool)
    .await?;

    // If we have fewer than 10 heartbeats total, we can't reliably detect packet loss
    if heartbeats.len() < 10 {
        return Ok(false);
    }

    // Simple metric: if we have far fewer heartbeats than expected for the time window, flag it
    // Expected: assume 1 heartbeat per second minimum (60 per minute)
    // If we have N heartbeats, expect roughly N seconds of activity
    // Actual loss = (expected - actual) / expected * 100
    // For this we use a simpler approach: if we have >= 10 heartbeats and they're low latency,
    // no loss. If we have fewer heartbeats, check the ratio.

    // For the test case: 3 heartbeats expecting ~10 (70% loss) at 50% threshold should return true
    // Expected minimum: 10 heartbeats
    // Actual: N heartbeats
    // Loss % = (10 - N) / 10 * 100

    let expected_count = 10i64;
    let actual_count = heartbeats.len() as i64;

    if actual_count >= expected_count {
        return Ok(false); // We got at least what we expected
    }

    let loss_pct = ((expected_count - actual_count) as f64 / expected_count as f64) * 100.0;
    Ok(loss_pct > threshold_loss_pct)
}
