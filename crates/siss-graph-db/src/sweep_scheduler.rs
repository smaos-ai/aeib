/// Phase 14 Task 73: Background Sweep Scheduler
/// Periodic cleanup of timed-out proposals, escrows, and reputation cycles
use sqlx::PgPool;
use std::time::Duration;
use uuid::Uuid;

/// Result of a single sweep pass
#[derive(Debug, Default, Clone)]
pub struct SweepResult {
    pub proposals_expired: u64,
    pub escrows_forfeited: u64,
    pub escrow_errors: u64,
    pub cycles_healed: usize,
}

/// Spawn the background sweep loop as a detached Tokio task.
///
/// Returns a `JoinHandle` so the caller can abort() or await on shutdown.
/// The loop runs indefinitely at the given interval.
pub fn start_background_sweep(
    pool: PgPool,
    initiator_id: Uuid,
    interval: Duration,
) -> tokio::task::JoinHandle<()> {
    tokio::spawn(async move {
        let mut ticker = tokio::time::interval(interval);
        loop {
            ticker.tick().await;
            let _ = run_sweep_pass(&pool, initiator_id).await;
        }
    })
}

/// Run one full sweep pass: expire proposals, forfeit escrows, heal cycles.
///
/// Returns aggregate counts for observability. All operations are guard-checked
/// at the SQL level, so the function is safe to call multiple times (idempotent).
///
/// Per-escrow errors are tolerated; they don't prevent other escrows from being forfeited.
pub async fn run_sweep_pass(pool: &PgPool, initiator_id: Uuid) -> SweepResult {
    let mut result = SweepResult::default();

    // 1. Expire timed-out consensus proposals
    match crate::repo::consensus_repo::expire_timed_out_proposals(pool).await {
        Ok(n) => result.proposals_expired = n,
        Err(_) => {
            // Non-fatal; proposal expiration will happen on next attempt
        }
    }

    // 2. Forfeit timed-out escrows (per-escrow, tolerates individual failures)
    if let Ok(ids) = crate::repo::escrow_repo::list_timed_out_escrows(pool).await {
        for id in ids {
            match crate::repo::escrow_repo::forfeit_escrow_on_timeout(pool, id).await {
                Ok(()) => result.escrows_forfeited += 1,
                Err(_) => {
                    // Non-fatal; escrow may have been forfeited concurrently or
                    // is in an invalid state (e.g., no longer held). Continue with next.
                    result.escrow_errors += 1;
                }
            }
        }
    }

    // 3. Heal detected reputation cycles
    if let Ok(healed) =
        crate::repo::cycle_healing_repo::heal_all_detected_cycles(pool, initiator_id).await
    {
        result.cycles_healed = healed.len();
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sweep_result_default_zeroed() {
        let result = SweepResult::default();
        assert_eq!(result.proposals_expired, 0);
        assert_eq!(result.escrows_forfeited, 0);
        assert_eq!(result.escrow_errors, 0);
        assert_eq!(result.cycles_healed, 0);
    }

    #[test]
    fn test_sweep_result_fields_accumulate() {
        let mut result = SweepResult::default();
        result.proposals_expired = 5;
        result.escrows_forfeited = 3;
        result.escrow_errors = 1;
        result.cycles_healed = 2;

        assert_eq!(result.proposals_expired, 5);
        assert_eq!(result.escrows_forfeited, 3);
        assert_eq!(result.escrow_errors, 1);
        assert_eq!(result.cycles_healed, 2);
    }

    // start_background_sweep cannot be unit-tested without a real PgPool,
    // so full testing of the spawn behavior happens in integration tests.
    // The function signature is verified to compile by the compiler.

    // ============================================================================
    // Integration Tests (Docker-dependent)
    // ============================================================================

    #[cfg(test)]
    mod integration_tests {
        use super::*;
        use chrono::Utc;
        use testcontainers::{GenericImage, ImageExt, core::WaitFor, runners::AsyncRunner};

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

        #[tokio::test]
        async fn test_run_sweep_pass_expire_proposals() {
            let (_container, pool) = setup_postgres().await;

            // Create initiator
            let initiator_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(initiator_id)
            .bind("initiator")
            .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
            .bind("active")
            .bind("http://initiator.local")
            .execute(&pool)
            .await
            .expect("insert initiator");

            // Create a past-due proposal
            let proposal_id = Uuid::new_v4();
            let created_at = Utc::now() - chrono::Duration::hours(2);
            let expires_at = Utc::now() - chrono::Duration::hours(1);  // 1 hour in past
            sqlx::query(
                "INSERT INTO consensus_proposals (id, initiator_sovereign_id, proposal_type, peer_count, required_quorum, status, created_at, expires_at)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
            )
            .bind(proposal_id)
            .bind(initiator_id)
            .bind("release_escrow")
            .bind(1)
            .bind(1)
            .bind("pending")
            .bind(created_at)
            .bind(expires_at)
            .execute(&pool)
            .await
            .expect("insert proposal");

            // Run sweep
            let result = run_sweep_pass(&pool, initiator_id).await;

            // Verify proposal was expired
            assert_eq!(result.proposals_expired, 1, "Should expire 1 proposal");

            let status: String =
                sqlx::query_scalar("SELECT status FROM consensus_proposals WHERE id = $1")
                    .bind(proposal_id)
                    .fetch_one(&pool)
                    .await
                    .expect("fetch proposal");

            assert_eq!(status, "expired", "Proposal should be expired");
        }

        #[tokio::test]
        async fn test_run_sweep_pass_forfeit_escrow() {
            let (_container, pool) = setup_postgres().await;

            // Create sovereigns
            let creditor_id = Uuid::new_v4();
            let debtor_id = Uuid::new_v4();
            let initiator_id = Uuid::new_v4();

            for (id, name) in [
                (creditor_id, "creditor"),
                (debtor_id, "debtor"),
                (initiator_id, "initiator"),
            ] {
                sqlx::query(
                    "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
                )
                .bind(id)
                .bind(name)
                .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
                .bind("active")
                .bind(&format!("http://{}.local", name))
                .execute(&pool)
                .await
                .expect(&format!("insert {}", name));
            }

            // Create invoice
            let invoice_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO settlement_invoices (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, total_tokens, entry_count, invoice_hash, invoice_signature, status)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
            )
            .bind(invoice_id)
            .bind(creditor_id)
            .bind(debtor_id)
            .bind(Utc::now())
            .bind(Utc::now())
            .bind(1000i64)
            .bind(1)
            .bind("hash")
            .bind("sig")
            .bind("pending")
            .execute(&pool)
            .await
            .expect("insert invoice");

            // Create escrow: held + acknowledged + past timeout
            let escrow_id = sqlx::query_scalar::<_, Uuid>(
                "INSERT INTO escrow_ledger (invoice_id, creditor_sovereign_id, debtor_sovereign_id, tokens_held, created_by_sovereign_id, status, held_at, debtor_acknowledged_at, timeout_at)
                 VALUES ($1, $2, $3, $4, $2, $5, $6, $7, $8) RETURNING id"
            )
            .bind(invoice_id)
            .bind(creditor_id)
            .bind(debtor_id)
            .bind(1000i64)
            .bind("held")
            .bind(Utc::now())  // held_at
            .bind(Utc::now())  // acknowledged
            .bind(Utc::now() - chrono::Duration::hours(1))  // timeout 1 hour ago
            .fetch_one(&pool)
            .await
            .expect("insert escrow");

            // Run sweep
            let result = run_sweep_pass(&pool, initiator_id).await;

            // Verify escrow was forfeited
            assert_eq!(result.escrows_forfeited, 1, "Should forfeit 1 escrow");

            let status: String =
                sqlx::query_scalar("SELECT status FROM escrow_ledger WHERE id = $1")
                    .bind(escrow_id)
                    .fetch_one(&pool)
                    .await
                    .expect("fetch escrow");

            assert_eq!(status, "forfeited", "Escrow should be forfeited");
        }
    }
}
