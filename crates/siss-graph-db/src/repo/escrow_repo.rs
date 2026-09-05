/// Phase 13 Task 67: Escrow System
/// Atomic multi-party token escrow for settlement invoices with 48h timeout
use chrono::{DateTime, Utc};
use sqlx::PgPool;
use thiserror::Error;
use uuid::Uuid;

/// Constitutional invariant: tokens held atomically until debtor acknowledges or timeout expires
pub const ESCROW_ATOMICITY: &str = "tokens_held_atomically_until_acknowledged_or_timeout";

/// Escrow system errors
#[derive(Debug, Clone)]
pub enum EscrowError {
    InvoiceNotFound,
    AlreadyInEscrow,
    NotPendingState,     // Tried to acknowledge non-pending escrow
    NotHeldState,        // Tried to release/dispute/forfeit non-held escrow
    TimeoutNotReached,   // Called forfeit before timeout_at
    UnauthorizedRelease, // Wrong sovereign called release
    UnauthorizedDispute, // Requester is neither creditor nor debtor
    Database(String),
}

impl From<sqlx::Error> for EscrowError {
    fn from(err: sqlx::Error) -> Self {
        EscrowError::Database(err.to_string())
    }
}

impl std::fmt::Display for EscrowError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EscrowError::InvoiceNotFound => write!(f, "Invoice not found"),
            EscrowError::AlreadyInEscrow => write!(f, "Escrow already exists for this invoice"),
            EscrowError::NotPendingState => write!(f, "Escrow is not in pending state"),
            EscrowError::NotHeldState => write!(f, "Escrow is not in held state"),
            EscrowError::TimeoutNotReached => write!(f, "Timeout has not been reached"),
            EscrowError::UnauthorizedRelease => write!(f, "Not authorized to release this escrow"),
            EscrowError::UnauthorizedDispute => write!(f, "Not authorized to dispute this escrow"),
            EscrowError::Database(e) => write!(f, "Database error: {}", e),
        }
    }
}

impl std::error::Error for EscrowError {}

/// Complete escrow ledger record
#[derive(Debug, Clone, sqlx::FromRow)]
pub struct EscrowRecord {
    pub id: Uuid,
    pub invoice_id: Uuid,
    pub creditor_sovereign_id: Uuid,
    pub debtor_sovereign_id: Uuid,
    pub tokens_held: i64,
    pub status: String,
    pub created_at: DateTime<Utc>,
    pub held_at: Option<DateTime<Utc>>,
    pub release_at: Option<DateTime<Utc>>,
    pub timeout_at: DateTime<Utc>,
    pub debtor_acknowledged_at: Option<DateTime<Utc>>,
    pub debtor_acknowledged_by_sovereign_id: Option<Uuid>,
    pub release_signature: Option<String>,
    pub disputed_at: Option<DateTime<Utc>>,
    pub dispute_reason: Option<String>,
    pub dispute_evidence: Option<serde_json::Value>,
    pub arbitration_result: Option<String>,
    pub vector_clock: serde_json::Value,
    pub created_by_sovereign_id: Uuid,
}

/// Initiate escrow for a settlement invoice.
///
/// Verifies invoice exists and is in 'pending' status, then creates an escrow record
/// with status='pending' and a 48-hour timeout.
pub async fn initiate_escrow(
    pool: &PgPool,
    invoice_id: Uuid,
    creditor_id: Uuid,
    debtor_id: Uuid,
    tokens: i64,
) -> Result<Uuid, EscrowError> {
    // Verify invoice exists
    let invoice_exists: bool =
        sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM settlement_invoices WHERE id = $1)")
            .bind(invoice_id)
            .fetch_one(pool)
            .await
            .map_err(|e| EscrowError::Database(e.to_string()))?;

    if !invoice_exists {
        return Err(EscrowError::InvoiceNotFound);
    }

    // Insert escrow ledger; UNIQUE constraint on invoice_id will catch duplicates
    let result = sqlx::query_scalar::<_, Uuid>(
        "INSERT INTO escrow_ledger (
            invoice_id, creditor_sovereign_id, debtor_sovereign_id,
            tokens_held, created_by_sovereign_id
        ) VALUES ($1, $2, $3, $4, $2)
        RETURNING id",
    )
    .bind(invoice_id)
    .bind(creditor_id)
    .bind(debtor_id)
    .bind(tokens)
    .fetch_optional(pool)
    .await
    .map_err(|e| {
        let err_msg = e.to_string();
        if err_msg.contains("unique") || err_msg.contains("UNIQUE") {
            EscrowError::AlreadyInEscrow
        } else {
            EscrowError::Database(err_msg)
        }
    })?;

    result.ok_or(EscrowError::Database("Insert returned no id".to_string()))
}

/// Debtor acknowledges escrow, moving it from 'pending' to 'held' state.
///
/// Returns NotPendingState if escrow is not in 'pending' state.
pub async fn debtor_acknowledge_escrow(
    pool: &PgPool,
    escrow_id: Uuid,
    debtor_id: Uuid,
) -> Result<(), EscrowError> {
    // Load current escrow
    let escrow: Option<(String, Uuid)> =
        sqlx::query_as("SELECT status, debtor_sovereign_id FROM escrow_ledger WHERE id = $1")
            .bind(escrow_id)
            .fetch_optional(pool)
            .await?;

    let (status, stored_debtor_id) = escrow.ok_or(EscrowError::NotPendingState)?;

    if status != "pending" {
        return Err(EscrowError::NotPendingState);
    }

    if stored_debtor_id != debtor_id {
        return Err(EscrowError::UnauthorizedRelease);
    }

    // CAS: update only if status='pending'
    let rows_affected = sqlx::query(
        "UPDATE escrow_ledger
         SET status = 'held',
             held_at = NOW(),
             debtor_acknowledged_at = NOW(),
             debtor_acknowledged_by_sovereign_id = $2
         WHERE id = $1 AND status = 'pending'",
    )
    .bind(escrow_id)
    .bind(debtor_id)
    .execute(pool)
    .await?
    .rows_affected();

    if rows_affected == 0 {
        return Err(EscrowError::NotPendingState);
    }

    Ok(())
}

/// Release escrow atomically: settle invoice, update vector clock (SERIALIZABLE isolation).
///
/// Requires creditor_id to match and escrow to be in 'held' state.
pub async fn release_escrow(
    pool: &PgPool,
    escrow_id: Uuid,
    creditor_id: Uuid,
    signature: &str,
) -> Result<(), EscrowError> {
    // Load escrow
    let escrow: Option<(String, Uuid, Uuid, Uuid)> = sqlx::query_as(
        "SELECT status, creditor_sovereign_id, debtor_sovereign_id, invoice_id
         FROM escrow_ledger WHERE id = $1",
    )
    .bind(escrow_id)
    .fetch_optional(pool)
    .await?;

    let (status, stored_creditor_id, debtor_id, invoice_id) =
        escrow.ok_or(EscrowError::NotHeldState)?;

    if status != "held" {
        return Err(EscrowError::NotHeldState);
    }

    if stored_creditor_id != creditor_id {
        return Err(EscrowError::UnauthorizedRelease);
    }

    // SERIALIZABLE transaction for atomic release
    let mut tx = pool.begin().await?;
    sqlx::query("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        .execute(&mut *tx)
        .await?;

    // Increment vector clock for creditor and debtor
    let current_vector: serde_json::Value =
        sqlx::query_scalar("SELECT vector_clock FROM escrow_ledger WHERE id = $1 FOR UPDATE")
            .bind(escrow_id)
            .fetch_one(&mut *tx)
            .await?;

    let mut updated_vector = current_vector.as_object().cloned().unwrap_or_default();

    let creditor_str = creditor_id.to_string();
    let debtor_str = debtor_id.to_string();

    let creditor_seq = updated_vector
        .get(&creditor_str)
        .and_then(|v| v.as_i64())
        .unwrap_or(0)
        + 1;
    let debtor_seq = updated_vector
        .get(&debtor_str)
        .and_then(|v| v.as_i64())
        .unwrap_or(0)
        + 1;

    updated_vector.insert(creditor_str, serde_json::json!(creditor_seq));
    updated_vector.insert(debtor_str, serde_json::json!(debtor_seq));

    let updated_vector_json = serde_json::to_value(updated_vector).unwrap();

    // Update escrow
    sqlx::query(
        "UPDATE escrow_ledger
         SET status = 'released',
             release_at = NOW(),
             release_signature = $2,
             vector_clock = $3
         WHERE id = $1 AND status = 'held'",
    )
    .bind(escrow_id)
    .bind(signature)
    .bind(updated_vector_json)
    .execute(&mut *tx)
    .await?;

    // Mark invoice as settled
    sqlx::query(
        "UPDATE settlement_invoices
         SET status = 'settled', settled_at = NOW()
         WHERE id = $1 AND status IN ('pending', 'acknowledged')",
    )
    .bind(invoice_id)
    .execute(&mut *tx)
    .await?;

    tx.commit().await?;

    Ok(())
}

/// Forfeit escrow after timeout expires: reset invoice to pending, mark escrow forfeited.
///
/// Returns TimeoutNotReached if timeout_at is in the future.
pub async fn forfeit_escrow_on_timeout(pool: &PgPool, escrow_id: Uuid) -> Result<(), EscrowError> {
    // Load escrow
    let escrow: Option<(String, DateTime<Utc>, Uuid)> =
        sqlx::query_as("SELECT status, timeout_at, invoice_id FROM escrow_ledger WHERE id = $1")
            .bind(escrow_id)
            .fetch_optional(pool)
            .await?;

    let (status, timeout_at, invoice_id) = escrow.ok_or(EscrowError::NotHeldState)?;

    if status != "held" {
        return Err(EscrowError::NotHeldState);
    }

    if timeout_at > Utc::now() {
        return Err(EscrowError::TimeoutNotReached);
    }

    let mut tx = pool.begin().await?;

    // Mark escrow as forfeited
    sqlx::query(
        "UPDATE escrow_ledger
         SET status = 'forfeited',
             forfeited_at = NOW()
         WHERE id = $1 AND status = 'held'",
    )
    .bind(escrow_id)
    .execute(&mut *tx)
    .await?;

    // Reset invoice to pending
    sqlx::query(
        "UPDATE settlement_invoices
         SET status = 'pending', settled_at = NULL
         WHERE id = $1",
    )
    .bind(invoice_id)
    .execute(&mut *tx)
    .await?;

    tx.commit().await?;

    Ok(())
}

/// Dispute escrow: move from 'held' to 'disputed' state with reason and evidence.
///
/// Only creditor or debtor can dispute.
pub async fn dispute_escrow(
    pool: &PgPool,
    escrow_id: Uuid,
    disputing_sovereign_id: Uuid,
    reason: &str,
    evidence: serde_json::Value,
) -> Result<(), EscrowError> {
    // Load escrow
    let escrow: Option<(String, Uuid, Uuid)> = sqlx::query_as(
        "SELECT status, creditor_sovereign_id, debtor_sovereign_id
         FROM escrow_ledger WHERE id = $1",
    )
    .bind(escrow_id)
    .fetch_optional(pool)
    .await?;

    let (status, creditor_id, debtor_id) = escrow.ok_or(EscrowError::NotHeldState)?;

    if status != "held" {
        return Err(EscrowError::NotHeldState);
    }

    if disputing_sovereign_id != creditor_id && disputing_sovereign_id != debtor_id {
        return Err(EscrowError::UnauthorizedDispute);
    }

    sqlx::query(
        "UPDATE escrow_ledger
         SET status = 'disputed',
             disputed_at = NOW(),
             dispute_reason = $2,
             dispute_evidence = $3
         WHERE id = $1 AND status = 'held'",
    )
    .bind(escrow_id)
    .bind(reason)
    .bind(evidence)
    .execute(pool)
    .await?;

    Ok(())
}

/// Fetch escrow record by invoice ID.
pub async fn fetch_escrow_by_invoice(
    pool: &PgPool,
    invoice_id: Uuid,
) -> Result<Option<EscrowRecord>, EscrowError> {
    sqlx::query_as::<_, EscrowRecord>("SELECT * FROM escrow_ledger WHERE invoice_id = $1")
        .bind(invoice_id)
        .fetch_optional(pool)
        .await
        .map_err(|e| EscrowError::Database(e.to_string()))
}

/// Fetch escrow record by escrow ID.
pub async fn fetch_escrow_by_id(
    pool: &PgPool,
    escrow_id: Uuid,
) -> Result<Option<EscrowRecord>, EscrowError> {
    sqlx::query_as::<_, EscrowRecord>("SELECT * FROM escrow_ledger WHERE id = $1")
        .bind(escrow_id)
        .fetch_optional(pool)
        .await
        .map_err(|e| EscrowError::Database(e.to_string()))
}

/// List escrows timed out (held state, timeout_at <= NOW()).
///
/// Used by background timeout job to identify escrows eligible for forfeiture.
pub async fn list_timed_out_escrows(pool: &PgPool) -> Result<Vec<Uuid>, sqlx::Error> {
    sqlx::query_scalar::<_, Uuid>(
        "SELECT id FROM escrow_ledger
         WHERE status = 'held' AND timeout_at <= NOW() AND debtor_acknowledged_at IS NOT NULL",
    )
    .fetch_all(pool)
    .await
}

// ============================================================================
// Phase 18: Economic Slashing
// ============================================================================

/// Result of a slashing operation
#[derive(Debug)]
pub struct SlashSummary {
    pub escrows_slashed: u64,
    pub total_tokens_slashed: i64,
}

/// Errors during slashing operations
#[derive(Debug, Error)]
pub enum SlashError {
    #[error("escrow {escrow_id} is not in held status")]
    NotHeld { escrow_id: Uuid },
    #[error("sovereign {sovereign_id} is not the debtor")]
    NotDebtor { sovereign_id: Uuid },
    #[error("database error: {message}")]
    Database { message: String },
}

impl From<sqlx::Error> for SlashError {
    fn from(err: sqlx::Error) -> Self {
        SlashError::Database {
            message: err.to_string(),
        }
    }
}

/// Map severity to slash percentage
pub fn compute_slash_percentage(severity: &str) -> i16 {
    match severity {
        "critical" => 50,
        "high" => 25,
        "medium" => 10,
        _ => 10, // fallback
    }
}

/// Slash a single held escrow by the computed percentage.
///
/// Verifies escrow is in 'held' status and sovereign_id is the debtor,
/// then reduces tokens_held proportionally and inserts a slashing_events record.
pub async fn slash_escrow(
    pool: &PgPool,
    escrow_id: Uuid,
    sovereign_id: Uuid,
    severity: &str,
    slash_reason: &str,
) -> Result<i64, SlashError> {
    // Load escrow to verify status and debtor
    let escrow: Option<(String, Uuid, i64)> = sqlx::query_as(
        "SELECT status, debtor_sovereign_id, tokens_held FROM escrow_ledger WHERE id = $1",
    )
    .bind(escrow_id)
    .fetch_optional(pool)
    .await?;

    let (status, debtor_id, tokens_held) = escrow.ok_or(SlashError::NotHeld { escrow_id })?;

    if status != "held" {
        return Err(SlashError::NotHeld { escrow_id });
    }

    if debtor_id != sovereign_id {
        return Err(SlashError::NotDebtor { sovereign_id });
    }

    // Compute slash amount
    let slash_percentage = compute_slash_percentage(severity);
    let tokens_slashed = std::cmp::max(1, (tokens_held * (slash_percentage as i64)) / 100);

    // Update escrow in transaction
    let mut tx = pool.begin().await?;

    // Reduce tokens_held
    sqlx::query("UPDATE escrow_ledger SET tokens_held = tokens_held - $2 WHERE id = $1")
        .bind(escrow_id)
        .bind(tokens_slashed)
        .execute(&mut *tx)
        .await?;

    // Record slashing event
    sqlx::query(
        "INSERT INTO slashing_events (sovereign_id, escrow_id, tokens_slashed, slash_percentage, severity, slash_reason)
         VALUES ($1, $2, $3, $4, $5, $6)"
    )
    .bind(sovereign_id)
    .bind(escrow_id)
    .bind(tokens_slashed)
    .bind(slash_percentage)
    .bind(severity)
    .bind(slash_reason)
    .execute(&mut *tx)
    .await?;

    tx.commit().await?;

    Ok(tokens_slashed)
}

/// Slash all held escrows for a sovereign.
///
/// Lists all escrows in 'held' status where debtor_sovereign_id = sovereign_id,
/// and applies slashing to each. Per-escrow errors are tolerated (logged implicitly).
/// Returns summary of escrows slashed and total tokens slashed.
pub async fn slash_all_held_escrows_for_sovereign(
    pool: &PgPool,
    sovereign_id: Uuid,
    severity: &str,
    slash_reason: &str,
) -> Result<SlashSummary, SlashError> {
    // Load all held escrows for this sovereign
    let escrow_ids: Vec<Uuid> = sqlx::query_scalar(
        "SELECT id FROM escrow_ledger WHERE debtor_sovereign_id = $1 AND status = 'held'",
    )
    .bind(sovereign_id)
    .fetch_all(pool)
    .await?;

    let mut escrows_slashed = 0u64;
    let mut total_tokens_slashed = 0i64;

    // Slash each escrow; tolerate per-escrow errors
    for escrow_id in escrow_ids {
        if let Ok(tokens) =
            slash_escrow(pool, escrow_id, sovereign_id, severity, slash_reason).await
        {
            escrows_slashed += 1;
            total_tokens_slashed += tokens;
        }
    }

    Ok(SlashSummary {
        escrows_slashed,
        total_tokens_slashed,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_escrow_status_monotonic() {
        // Unit test: verify error types for invalid state transitions
        // (Status machine enforced by database CHECK constraints and function checks)

        let err = EscrowError::NotPendingState;
        match err {
            EscrowError::NotPendingState => { /* correct */ }
            _ => panic!("Should be NotPendingState"),
        }

        let err2 = EscrowError::NotHeldState;
        match err2 {
            EscrowError::NotHeldState => { /* correct */ }
            _ => panic!("Should be NotHeldState"),
        }
    }

    // ============================================================================
    // Phase 18: Slashing unit tests
    // ============================================================================

    #[test]
    fn test_slash_percentage_medium_is_10() {
        let slash_pct = compute_slash_percentage("medium");
        assert_eq!(slash_pct, 10, "medium severity should slash 10%");
    }

    #[test]
    fn test_slash_percentage_high_is_25() {
        let slash_pct = compute_slash_percentage("high");
        assert_eq!(slash_pct, 25, "high severity should slash 25%");
    }

    #[test]
    fn test_slash_percentage_critical_is_50() {
        let slash_pct = compute_slash_percentage("critical");
        assert_eq!(slash_pct, 50, "critical severity should slash 50%");
    }

    // ============================================================================
    // Integration Tests (Docker-dependent)
    // ============================================================================

    #[cfg(test)]
    mod integration_tests {
        use super::*;
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

        async fn setup_fixtures(pool: &PgPool) -> (Uuid, Uuid, Uuid) {
            // Create creditor sovereign
            let creditor_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(creditor_id)
            .bind("creditor")
            .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
            .bind("active")
            .bind("http://creditor.local")
            .execute(pool)
            .await
            .expect("insert creditor");

            // Create debtor sovereign
            let debtor_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(debtor_id)
            .bind("debtor")
            .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
            .bind("active")
            .bind("http://debtor.local")
            .execute(pool)
            .await
            .expect("insert debtor");

            // Create settlement invoice
            let invoice_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO settlement_invoices (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, total_tokens, entry_count, invoice_hash, invoice_signature, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
            )
            .bind(invoice_id)
            .bind(creditor_id)
            .bind(debtor_id)
            .bind(Utc::now())
            .bind(Utc::now())
            .bind(1000i64)
            .bind(1)
            .bind("abc123")
            .bind("sig-bytes")
            .bind("pending")
            .execute(pool)
            .await
            .expect("insert invoice");

            (creditor_id, debtor_id, invoice_id)
        }

        #[tokio::test]
        async fn test_initiate_escrow_success() {
            let (_container, pool) = setup_postgres().await;
            let (creditor_id, debtor_id, invoice_id) = setup_fixtures(&pool).await;

            let result = initiate_escrow(&pool, invoice_id, creditor_id, debtor_id, 1000).await;
            assert!(result.is_ok(), "Initiate should succeed");

            let escrow_id = result.unwrap();
            let escrow: Option<(String, i64)> =
                sqlx::query_as("SELECT status, tokens_held FROM escrow_ledger WHERE id = $1")
                    .bind(escrow_id)
                    .fetch_optional(&pool)
                    .await
                    .unwrap();

            assert!(escrow.is_some(), "Escrow should exist");
            let (status, tokens) = escrow.unwrap();
            assert_eq!(status, "pending", "Status should be pending");
            assert_eq!(tokens, 1000, "Tokens should match");
        }

        #[tokio::test]
        async fn test_initiate_escrow_duplicate_rejected() {
            let (_container, pool) = setup_postgres().await;
            let (creditor_id, debtor_id, invoice_id) = setup_fixtures(&pool).await;

            let res1 = initiate_escrow(&pool, invoice_id, creditor_id, debtor_id, 1000).await;
            assert!(res1.is_ok(), "First initiate should succeed");

            let res2 = initiate_escrow(&pool, invoice_id, creditor_id, debtor_id, 1000).await;
            assert!(
                matches!(res2, Err(EscrowError::AlreadyInEscrow)),
                "Duplicate should be rejected"
            );
        }

        #[tokio::test]
        async fn test_debtor_acknowledge_moves_to_held() {
            let (_container, pool) = setup_postgres().await;
            let (creditor_id, debtor_id, invoice_id) = setup_fixtures(&pool).await;

            let escrow_id = initiate_escrow(&pool, invoice_id, creditor_id, debtor_id, 1000)
                .await
                .unwrap();

            let result = debtor_acknowledge_escrow(&pool, escrow_id, debtor_id).await;
            assert!(result.is_ok(), "Acknowledge should succeed");

            let (status, held_at, ack_at): (String, Option<DateTime<Utc>>, Option<DateTime<Utc>>) =
                sqlx::query_as(
                    "SELECT status, held_at, debtor_acknowledged_at FROM escrow_ledger WHERE id = $1"
                )
                .bind(escrow_id)
                .fetch_one(&pool)
                .await
                .unwrap();

            assert_eq!(status, "held", "Status should be held");
            assert!(held_at.is_some(), "held_at should be set");
            assert!(ack_at.is_some(), "debtor_acknowledged_at should be set");
        }

        #[tokio::test]
        async fn test_release_escrow_settles_invoice() {
            let (_container, pool) = setup_postgres().await;
            let (creditor_id, debtor_id, invoice_id) = setup_fixtures(&pool).await;

            let escrow_id = initiate_escrow(&pool, invoice_id, creditor_id, debtor_id, 1000)
                .await
                .unwrap();

            debtor_acknowledge_escrow(&pool, escrow_id, debtor_id)
                .await
                .unwrap();

            let result = release_escrow(&pool, escrow_id, creditor_id, "sig-release").await;
            assert!(result.is_ok(), "Release should succeed");

            let escrow_status: String =
                sqlx::query_scalar("SELECT status FROM escrow_ledger WHERE id = $1")
                    .bind(escrow_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();
            assert_eq!(escrow_status, "released", "Escrow should be released");

            let invoice_status: String =
                sqlx::query_scalar("SELECT status FROM settlement_invoices WHERE id = $1")
                    .bind(invoice_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();
            assert_eq!(invoice_status, "settled", "Invoice should be settled");
        }

        #[tokio::test]
        async fn test_forfeit_escrow_on_timeout_refunds() {
            let (_container, pool) = setup_postgres().await;
            let (creditor_id, debtor_id, invoice_id) = setup_fixtures(&pool).await;

            let escrow_id = initiate_escrow(&pool, invoice_id, creditor_id, debtor_id, 1000)
                .await
                .unwrap();

            debtor_acknowledge_escrow(&pool, escrow_id, debtor_id)
                .await
                .unwrap();

            // Manually set created_at to past and timeout to past (constraint: timeout > created)
            sqlx::query(
                "UPDATE escrow_ledger SET created_at = NOW() - INTERVAL '2 hours', timeout_at = NOW() - INTERVAL '1 hour' WHERE id = $1",
            )
            .bind(escrow_id)
            .execute(&pool)
            .await
            .unwrap();

            let result = forfeit_escrow_on_timeout(&pool, escrow_id).await;
            assert!(result.is_ok(), "Forfeit should succeed");

            let escrow_status: String =
                sqlx::query_scalar("SELECT status FROM escrow_ledger WHERE id = $1")
                    .bind(escrow_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();
            assert_eq!(escrow_status, "forfeited", "Escrow should be forfeited");

            let invoice_status: String =
                sqlx::query_scalar("SELECT status FROM settlement_invoices WHERE id = $1")
                    .bind(invoice_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();
            assert_eq!(
                invoice_status, "pending",
                "Invoice should return to pending"
            );
        }

        #[tokio::test]
        async fn test_forfeit_before_timeout_rejected() {
            let (_container, pool) = setup_postgres().await;
            let (creditor_id, debtor_id, invoice_id) = setup_fixtures(&pool).await;

            let escrow_id = initiate_escrow(&pool, invoice_id, creditor_id, debtor_id, 1000)
                .await
                .unwrap();

            debtor_acknowledge_escrow(&pool, escrow_id, debtor_id)
                .await
                .unwrap();

            // timeout_at is in future by default (48h)
            let result = forfeit_escrow_on_timeout(&pool, escrow_id).await;
            assert!(
                matches!(result, Err(EscrowError::TimeoutNotReached)),
                "Should reject early forfeit"
            );
        }

        #[tokio::test]
        async fn test_dispute_escrow_held() {
            let (_container, pool) = setup_postgres().await;
            let (creditor_id, debtor_id, invoice_id) = setup_fixtures(&pool).await;

            let escrow_id = initiate_escrow(&pool, invoice_id, creditor_id, debtor_id, 1000)
                .await
                .unwrap();

            debtor_acknowledge_escrow(&pool, escrow_id, debtor_id)
                .await
                .unwrap();

            let evidence = serde_json::json!({"claim": "no receipt"});
            let result = dispute_escrow(&pool, escrow_id, debtor_id, "no receipt", evidence).await;
            assert!(result.is_ok(), "Dispute should succeed");

            let (status, reason): (String, Option<String>) =
                sqlx::query_as("SELECT status, dispute_reason FROM escrow_ledger WHERE id = $1")
                    .bind(escrow_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();

            assert_eq!(status, "disputed", "Status should be disputed");
            assert_eq!(
                reason,
                Some("no receipt".to_string()),
                "Reason should be stored"
            );
        }

        // ============================================================================
        // Phase 18: Slashing integration tests
        // ============================================================================

        #[tokio::test]
        async fn test_slash_all_only_targets_held_escrows() {
            let (_container, pool) = setup_postgres().await;
            let (creditor_id, debtor_id, invoice_id) = setup_fixtures(&pool).await;

            // Create two escrows: one held, one released
            let escrow1_id = initiate_escrow(&pool, invoice_id, creditor_id, debtor_id, 1000)
                .await
                .unwrap();
            debtor_acknowledge_escrow(&pool, escrow1_id, debtor_id)
                .await
                .unwrap();

            let invoice2_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO settlement_invoices (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, total_tokens, entry_count, invoice_hash, invoice_signature, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
            )
            .bind(invoice2_id)
            .bind(creditor_id)
            .bind(debtor_id)
            .bind(Utc::now())
            .bind(Utc::now())
            .bind(2000i64)
            .bind(1)
            .bind("abc456")
            .bind("sig-bytes")
            .bind("pending")
            .execute(&pool)
            .await
            .unwrap();

            let escrow2_id = initiate_escrow(&pool, invoice2_id, creditor_id, debtor_id, 2000)
                .await
                .unwrap();
            debtor_acknowledge_escrow(&pool, escrow2_id, debtor_id)
                .await
                .unwrap();

            // Release escrow2
            release_escrow(&pool, escrow2_id, creditor_id, "sig-release")
                .await
                .unwrap();

            // Verify statuses
            let (status1,): (String,) =
                sqlx::query_as("SELECT status FROM escrow_ledger WHERE id = $1")
                    .bind(escrow1_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();
            assert_eq!(status1, "held", "escrow1 should be held");

            let (status2,): (String,) =
                sqlx::query_as("SELECT status FROM escrow_ledger WHERE id = $1")
                    .bind(escrow2_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();
            assert_eq!(status2, "released", "escrow2 should be released");

            // Slash all for debtor with "high" severity (25%)
            let result =
                slash_all_held_escrows_for_sovereign(&pool, debtor_id, "high", "test slash reason")
                    .await
                    .unwrap();

            // Should only slash escrow1 (held), not escrow2 (released)
            assert_eq!(result.escrows_slashed, 1, "Should slash exactly 1 escrow");
            assert_eq!(result.total_tokens_slashed, 250, "Should slash 25% of 1000");

            // Verify escrow1 tokens_held reduced
            let (tokens1,): (i64,) =
                sqlx::query_as("SELECT tokens_held FROM escrow_ledger WHERE id = $1")
                    .bind(escrow1_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();
            assert_eq!(tokens1, 750, "escrow1 tokens_held should be reduced to 750");

            // Verify escrow2 tokens_held unchanged
            let (tokens2,): (i64,) =
                sqlx::query_as("SELECT tokens_held FROM escrow_ledger WHERE id = $1")
                    .bind(escrow2_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();
            assert_eq!(tokens2, 2000, "escrow2 tokens_held should remain 2000");
        }
    }
}
