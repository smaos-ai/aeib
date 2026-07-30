use chrono::{DateTime, Utc};
use sqlx::{PgPool, Row};
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct MultiSovereignProposal {
    pub proposal_id: Uuid,
    pub sovereign_participants: Vec<Uuid>,
    pub proposal_type: String,
    pub required_quorum: i64,
    pub status: String,
}

#[derive(Debug, Clone)]
pub enum ConsensusError {
    ProposalNotFound,
    InvalidProposal(String),
    Database(String),
    Unimplemented,
}

impl From<sqlx::Error> for ConsensusError {
    fn from(err: sqlx::Error) -> Self {
        ConsensusError::Database(err.to_string())
    }
}

/// Initiate distributed consensus across multiple sovereigns with default 24h expiry.
pub async fn initiate_distributed_consensus(
    pool: &PgPool,
    initiator_sovereign: Uuid,
    participant_sovereigns: Vec<Uuid>,
    proposal_type: &str,
) -> Result<Uuid, ConsensusError> {
    let expiry = Utc::now() + chrono::Duration::hours(24);
    initiate_distributed_consensus_with_expiry(
        pool,
        initiator_sovereign,
        participant_sovereigns,
        proposal_type,
        expiry,
    )
    .await
}

/// Initiate distributed consensus with custom expiry.
pub async fn initiate_distributed_consensus_with_expiry(
    pool: &PgPool,
    initiator_sovereign: Uuid,
    participant_sovereigns: Vec<Uuid>,
    proposal_type: &str,
    expires_at: DateTime<Utc>,
) -> Result<Uuid, ConsensusError> {
    let proposal_id = Uuid::new_v4();
    let quorum = calculate_quorum(participant_sovereigns.len());

    sqlx::query(
        r#"
        INSERT INTO multi_sovereign_proposals
        (proposal_id, initiator_sovereign_id, sovereign_participants, proposal_type, required_quorum, expires_at, status)
        VALUES ($1, $2, $3, $4, $5, $6, 'pending')
        "#,
    )
    .bind(proposal_id)
    .bind(initiator_sovereign)
    .bind(&participant_sovereigns)
    .bind(proposal_type)
    .bind(quorum)
    .bind(expires_at)
    .execute(pool)
    .await?;

    Ok(proposal_id)
}

/// Cast a vote on a distributed consensus proposal.
pub async fn cast_vote(
    pool: &PgPool,
    proposal_id: Uuid,
    voter_sovereign: Uuid,
    vote: bool,
) -> Result<(), ConsensusError> {
    let vote_str = if vote { "yes" } else { "no" };

    sqlx::query(
        r#"
        INSERT INTO distributed_consensus_votes
        (proposal_id, voter_sovereign_id, vote, voted_at)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (proposal_id, voter_sovereign_id) DO UPDATE
        SET vote = $3, voted_at = NOW()
        "#,
    )
    .bind(proposal_id)
    .bind(voter_sovereign)
    .bind(vote_str)
    .execute(pool)
    .await?;

    Ok(())
}

/// Get vote count for a proposal.
pub async fn get_vote_count(
    pool: &PgPool,
    proposal_id: Uuid,
) -> Result<(i64, i64), ConsensusError> {
    let row = sqlx::query(
        r#"
        SELECT
            COUNT(CASE WHEN vote = 'yes' THEN 1 END) as yes_count,
            COUNT(CASE WHEN vote = 'no' THEN 1 END) as no_count
        FROM distributed_consensus_votes
        WHERE proposal_id = $1
        "#,
    )
    .bind(proposal_id)
    .fetch_one(pool)
    .await?;

    let yes_count: i64 = row.get("yes_count");
    let no_count: i64 = row.get("no_count");

    Ok((yes_count, no_count))
}

/// Check if quorum has been reached for a proposal.
pub async fn check_quorum(pool: &PgPool, proposal_id: Uuid) -> Result<bool, ConsensusError> {
    let proposal: (i64, i64) = sqlx::query_as(
        r#"
        SELECT required_quorum, COALESCE(
            (SELECT COUNT(*) FROM distributed_consensus_votes
             WHERE proposal_id = $1 AND vote = 'yes'), 0
        ) as yes_votes
        FROM multi_sovereign_proposals
        WHERE proposal_id = $1
        "#,
    )
    .bind(proposal_id)
    .fetch_optional(pool)
    .await?
    .ok_or(ConsensusError::ProposalNotFound)?;

    Ok(proposal.1 >= proposal.0)
}

/// Check if proposal has expired.
pub async fn check_expired(pool: &PgPool, proposal_id: Uuid) -> Result<bool, ConsensusError> {
    let expired: bool = sqlx::query_scalar(
        r#"
        SELECT expires_at < NOW()
        FROM multi_sovereign_proposals
        WHERE proposal_id = $1
        "#,
    )
    .bind(proposal_id)
    .fetch_optional(pool)
    .await?
    .ok_or(ConsensusError::ProposalNotFound)?;

    Ok(expired)
}

/// Phase 75 placeholder: finalization not yet implemented.
pub async fn finalize_distributed_consensus(
    _pool: &PgPool,
    _proposal_id: Uuid,
) -> Result<(), ConsensusError> {
    Err(ConsensusError::Unimplemented)
}

fn calculate_quorum(participant_count: usize) -> i64 {
    ((participant_count as i64) + 1) / 2
}
