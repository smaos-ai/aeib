use sqlx::PgPool;
use uuid::Uuid;

/// Map peer score to cluster label
fn score_to_cluster(score: i16) -> &'static str {
    match score {
        90..=100 => "clean",
        50..=89 => "probation",
        _ => "risky",
    }
}

/// Assign cluster label to a sovereign based on its peer score
pub async fn assign_cluster(
    pool: &PgPool,
    sovereign_id: Uuid,
    score: i16,
) -> Result<String, sqlx::Error> {
    let cluster_label = score_to_cluster(score);

    // Upsert peer_clusters
    sqlx::query(
        "INSERT INTO peer_clusters (sovereign_id, cluster_label, score_at_assignment, assigned_at)
         VALUES ($1, $2, $3, NOW())
         ON CONFLICT (sovereign_id) DO UPDATE
         SET cluster_label = EXCLUDED.cluster_label, score_at_assignment = EXCLUDED.score_at_assignment, assigned_at = NOW()",
    )
    .bind(sovereign_id)
    .bind(cluster_label)
    .bind(score)
    .execute(pool)
    .await?;

    Ok(cluster_label.to_string())
}

/// Run one sweep pass: assign clusters for all sovereigns based on peer_scoring
pub async fn run_cluster_pass(pool: &PgPool) -> Result<u64, sqlx::Error> {
    let scores: Vec<(Uuid, i16)> = sqlx::query_as("SELECT sovereign_id, score FROM peer_scoring")
        .fetch_all(pool)
        .await?;

    let mut count = 0u64;
    for (sovereign_id, score) in scores {
        if assign_cluster(pool, sovereign_id, score).await.is_ok() {
            count += 1;
        }
    }

    Ok(count)
}

/// Start background cluster assignment sweep
pub fn start_peer_cluster_sweep(
    pool: PgPool,
    interval: std::time::Duration,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let mut ticker = tokio::time::interval(interval);
        loop {
            ticker.tick().await;
            let _ = run_cluster_pass(&pool).await;
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cluster_assignment_score_90_is_clean() {
        let cluster = score_to_cluster(90);
        assert_eq!(cluster, "clean", "score 90 should map to clean cluster");
    }

    #[test]
    fn test_cluster_assignment_score_49_is_risky() {
        let cluster = score_to_cluster(49);
        assert_eq!(cluster, "risky", "score 49 should map to risky cluster");
    }
}
