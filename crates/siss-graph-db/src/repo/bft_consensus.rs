use chrono::{DateTime, Duration, Utc};
use sha2::{Digest, Sha256};
use sqlx::{PgPool, Row};
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct QuorumState {
    pub quorum_id: Uuid,
    pub initiator_sovereign_id: Uuid,
    pub participant_sovereigns: Vec<Uuid>,
    pub required_quorum: i64,
    pub yes_votes: i64,
    pub no_votes: i64,
    pub status: String,
    pub merkle_root: String,
    pub merkle_proof_ref: String,
    pub created_at: DateTime<Utc>,
    pub finalized_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone)]
pub enum BftError {
    QuorumNotFound,
    InvalidQuorum(String),
    Database(String),
    QuorumAlreadyFinalized,
    InsufficientVotes,
    DuplicateVote,
}

impl From<sqlx::Error> for BftError {
    fn from(err: sqlx::Error) -> Self {
        BftError::Database(err.to_string())
    }
}

impl std::fmt::Display for BftError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            BftError::QuorumNotFound => write!(f, "Quorum not found"),
            BftError::InvalidQuorum(msg) => write!(f, "Invalid quorum: {}", msg),
            BftError::Database(msg) => write!(f, "Database error: {}", msg),
            BftError::QuorumAlreadyFinalized => write!(f, "Quorum already finalized"),
            BftError::InsufficientVotes => write!(f, "Insufficient votes to finalize"),
            BftError::DuplicateVote => write!(f, "Duplicate vote from voter"),
        }
    }
}

impl std::error::Error for BftError {}

/// Calculate majority quorum using formula: ceil(N/2) + 1
/// For N=1: special case = 1
/// For N=3: ceil(1.5) + 1 = 2 + 1 = 3
/// For N=5: ceil(2.5) + 1 = 3 + 1 = 4
/// For N=7: ceil(3.5) + 1 = 4 + 1 = 5
fn calculate_required_quorum(participant_count: usize) -> i64 {
    let n = participant_count as i64;
    if n == 1 {
        1
    } else {
        ((n + 1) / 2) + 1 // ceil(n/2) + 1 using integer division
    }
}

/// Initiate a BFT quorum with the given initiator and participants.
/// Returns the quorum_id on success.
pub async fn initiate_bft_quorum(
    pool: &PgPool,
    initiator: Uuid,
    participants: Vec<Uuid>,
) -> Result<Uuid, BftError> {
    let quorum_id = Uuid::new_v4();
    let required_quorum = calculate_required_quorum(participants.len());

    sqlx::query(
        r#"
        INSERT INTO bft_quorum_rounds
        (quorum_id, initiator_sovereign_id, participant_sovereigns, required_quorum, status)
        VALUES ($1, $2, $3, $4, 'active')
        "#,
    )
    .bind(quorum_id)
    .bind(initiator)
    .bind(&participants)
    .bind(required_quorum)
    .execute(pool)
    .await?;

    Ok(quorum_id)
}

/// Cast a signed vote on a quorum.
/// vote: true for yes, false for no
/// signature: Ed25519 signature bytes
pub async fn cast_signed_vote(
    pool: &PgPool,
    quorum_id: Uuid,
    voter_id: Uuid,
    vote: bool,
    signature: Vec<u8>,
) -> Result<(), BftError> {
    // Check if quorum exists, is still active, and hasn't expired (24h timeout)
    let quorum_data: (String, DateTime<Utc>) =
        sqlx::query_as("SELECT status, created_at FROM bft_quorum_rounds WHERE quorum_id = $1")
            .bind(quorum_id)
            .fetch_optional(pool)
            .await?
            .ok_or(BftError::QuorumNotFound)?;

    let (quorum_status, created_at) = quorum_data;

    if quorum_status != "active" {
        return Err(BftError::QuorumAlreadyFinalized);
    }

    // Check if quorum has expired (older than 24 hours)
    let now = Utc::now();
    let age = now.signed_duration_since(created_at);
    let twenty_four_hours = Duration::hours(24);
    if age > twenty_four_hours {
        return Err(BftError::InvalidQuorum(
            "Quorum has expired (24h timeout)".to_string(),
        ));
    }

    // Check if this voter has already voted (UNIQUE constraint will catch this too)
    let already_voted: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM bft_quorum_signatures WHERE quorum_id = $1 AND voter_sovereign_id = $2)"
    )
    .bind(quorum_id)
    .bind(voter_id)
    .fetch_one(pool)
    .await?;

    if already_voted {
        return Err(BftError::DuplicateVote);
    }

    let vote_str = if vote { "yes" } else { "no" };
    let signature_hex = hex::encode(&signature);
    let vote_id = Uuid::new_v4();

    // Use SERIALIZABLE transaction isolation for vote insertion
    let mut tx = pool.begin().await?;

    sqlx::query(
        r#"
        INSERT INTO bft_quorum_signatures
        (id, quorum_id, voter_sovereign_id, vote, signature)
        VALUES ($1, $2, $3, $4, $5)
        "#,
    )
    .bind(vote_id)
    .bind(quorum_id)
    .bind(voter_id)
    .bind(vote_str)
    .bind(&signature_hex)
    .execute(&mut *tx)
    .await?;

    // Update vote counts
    if vote {
        sqlx::query("UPDATE bft_quorum_rounds SET yes_votes = yes_votes + 1 WHERE quorum_id = $1")
            .bind(quorum_id)
            .execute(&mut *tx)
            .await?;
    } else {
        sqlx::query("UPDATE bft_quorum_rounds SET no_votes = no_votes + 1 WHERE quorum_id = $1")
            .bind(quorum_id)
            .execute(&mut *tx)
            .await?;
    }

    tx.commit().await?;

    Ok(())
}

/// Finalize a quorum if it has reached required majority.
/// Returns QuorumState with computed merkle_root on success.
pub async fn finalize_quorum(pool: &PgPool, quorum_id: Uuid) -> Result<QuorumState, BftError> {
    // Fetch current quorum state
    let quorum = sqlx::query(
        r#"
        SELECT
            quorum_id, initiator_sovereign_id, participant_sovereigns,
            required_quorum, yes_votes, no_votes, status, merkle_root,
            merkle_proof_ref, created_at, finalized_at
        FROM bft_quorum_rounds
        WHERE quorum_id = $1
        "#,
    )
    .bind(quorum_id)
    .fetch_optional(pool)
    .await?
    .ok_or(BftError::QuorumNotFound)?;

    let required_quorum: i64 = quorum.get("required_quorum");
    let yes_votes: i64 = quorum.get("yes_votes");
    let _no_votes: i64 = quorum.get("no_votes");
    let status: String = quorum.get("status");

    // Check if already finalized
    if status != "active" {
        return Err(BftError::QuorumAlreadyFinalized);
    }

    // Check if we have reached majority
    if yes_votes < required_quorum {
        return Err(BftError::InsufficientVotes);
    }

    // Compute merkle root from signatures
    let merkle_root = compute_merkle_root(pool, quorum_id).await?;
    let merkle_proof_ref = merkle_root.clone();

    // Update quorum with merkle root and finalize
    sqlx::query(
        r#"
        UPDATE bft_quorum_rounds
        SET status = 'finalized', merkle_root = $2, merkle_proof_ref = $3, finalized_at = NOW()
        WHERE quorum_id = $1
        "#,
    )
    .bind(quorum_id)
    .bind(&merkle_root)
    .bind(&merkle_proof_ref)
    .execute(pool)
    .await?;

    // Fetch and return updated state
    let updated = sqlx::query(
        r#"
        SELECT
            quorum_id, initiator_sovereign_id, participant_sovereigns,
            required_quorum, yes_votes, no_votes, status, merkle_root,
            merkle_proof_ref, created_at, finalized_at
        FROM bft_quorum_rounds
        WHERE quorum_id = $1
        "#,
    )
    .bind(quorum_id)
    .fetch_one(pool)
    .await?;

    Ok(QuorumState {
        quorum_id: updated.get("quorum_id"),
        initiator_sovereign_id: updated.get("initiator_sovereign_id"),
        participant_sovereigns: updated.get("participant_sovereigns"),
        required_quorum: updated.get("required_quorum"),
        yes_votes: updated.get("yes_votes"),
        no_votes: updated.get("no_votes"),
        status: updated.get("status"),
        merkle_root: updated.get("merkle_root"),
        merkle_proof_ref: updated.get("merkle_proof_ref"),
        created_at: updated.get("created_at"),
        finalized_at: updated.get("finalized_at"),
    })
}

/// Merge attestations and compute Merkle root.
/// Returns merkle_root as hex string (64 chars for SHA256).
pub async fn merge_attestations(pool: &PgPool, quorum_id: Uuid) -> Result<String, BftError> {
    let merkle_root = compute_merkle_root(pool, quorum_id).await?;

    // Update the quorum with merkle_proof_ref
    sqlx::query("UPDATE bft_quorum_rounds SET merkle_proof_ref = $2 WHERE quorum_id = $1")
        .bind(quorum_id)
        .bind(&merkle_root)
        .execute(pool)
        .await?;

    Ok(merkle_root)
}

/// Internal: Compute Merkle root from all signatures in the quorum.
async fn compute_merkle_root(pool: &PgPool, quorum_id: Uuid) -> Result<String, BftError> {
    // Fetch all signatures for this quorum, ordered by voter_sovereign_id for determinism
    let signatures: Vec<(String,)> = sqlx::query_as(
        r#"
        SELECT signature FROM bft_quorum_signatures
        WHERE quorum_id = $1
        ORDER BY voter_sovereign_id ASC
        "#,
    )
    .bind(quorum_id)
    .fetch_all(pool)
    .await?;

    // Concatenate all signatures
    let mut combined = Vec::new();
    for (sig,) in signatures {
        if let Ok(decoded) = hex::decode(&sig) {
            combined.extend_from_slice(&decoded);
        }
    }

    // If no signatures, hash empty
    if combined.is_empty() {
        let hasher = Sha256::digest(b"");
        Ok(hex::encode(hasher))
    } else {
        let hasher = Sha256::digest(&combined);
        Ok(hex::encode(hasher))
    }
}
