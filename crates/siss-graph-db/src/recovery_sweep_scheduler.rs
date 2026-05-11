use sqlx::PgPool;
use std::time::Duration;
use crate::repo::reputation_recovery_repo;

/// Start background recovery sweep loop
/// Runs weekly: advances recovery progress, checks for 8-week completion, detects violations
pub fn start_recovery_sweep(
    pool: PgPool,
    interval: Duration,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let mut ticker = tokio::time::interval(interval);
        loop {
            ticker.tick().await;
            let _ = run_recovery_sweep_pass(&pool).await;
        }
    })
}

/// Run one recovery sweep pass
pub async fn run_recovery_sweep_pass(pool: &PgPool) -> Result<RecoverySweepResult, sqlx::Error> {
    reputation_recovery_repo::sweep_recovery_progress(pool).await.map(|result| {
        RecoverySweepResult {
            sovereigns_advanced: result.sovereigns_advanced,
            sovereigns_completed: result.sovereigns_completed,
            sovereigns_violated: result.sovereigns_violated,
        }
    })
}

#[derive(Debug, Clone)]
pub struct RecoverySweepResult {
    pub sovereigns_advanced: i32,
    pub sovereigns_completed: i32,
    pub sovereigns_violated: i32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_recovery_sweep_result_creation() {
        let result = RecoverySweepResult {
            sovereigns_advanced: 5,
            sovereigns_completed: 2,
            sovereigns_violated: 0,
        };
        assert_eq!(result.sovereigns_advanced, 5);
    }
}
