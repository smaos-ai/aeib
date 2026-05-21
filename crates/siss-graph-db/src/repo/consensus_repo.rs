/// Phase 13 Task 68: 2-Phase Consensus Protocol
/// Quorum-based consensus for escrow release with cryptographic vote signatures
use chrono::{DateTime, Utc};
use ed25519_dalek::{Signature, VerifyingKey};
use sqlx::PgPool;
use uuid::Uuid;

/// Constitutional invariant: majority of active peers must approve escrow release
pub const CONSENSUS_QUORUM_REQUIRED: &str = "majority_of_active_peers_must_approve";

/// Consensus protocol errors
#[derive(Debug, Clone)]
pub enum ConsensusError {
    ProposalNotFound,
    AlreadyVoted,
    InvalidVote(String), // not "yes"/"no"/"abstain"
    InvalidSignature,
    VoterNotActivePeer,
    NotPendingStatus,        // tried to vote on expired/finalized proposal
    QuorumNotReached,        // called finalize before quorum reached
    InvalidProposal(String), // escrow_id not found, etc.
    Database(String),
}

impl From<sqlx::Error> for ConsensusError {
    fn from(err: sqlx::Error) -> Self {
        ConsensusError::Database(err.to_string())
    }
}

impl std::fmt::Display for ConsensusError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ConsensusError::ProposalNotFound => write!(f, "Proposal not found"),
            ConsensusError::AlreadyVoted => write!(f, "Voter has already voted on this proposal"),
            ConsensusError::InvalidVote(v) => write!(f, "Invalid vote: {}", v),
            ConsensusError::InvalidSignature => write!(f, "Signature verification failed"),
            ConsensusError::VoterNotActivePeer => write!(f, "Voter is not an active peer"),
            ConsensusError::NotPendingStatus => write!(f, "Proposal is not in pending status"),
            ConsensusError::QuorumNotReached => write!(f, "Quorum has not been reached"),
            ConsensusError::InvalidProposal(e) => write!(f, "Invalid proposal: {}", e),
            ConsensusError::Database(e) => write!(f, "Database error: {}", e),
        }
    }
}

impl std::error::Error for ConsensusError {}

/// Result of quorum check
#[derive(Debug, Clone, sqlx::FromRow)]
pub struct ConsensusResult {
    pub proposal_id: Uuid,
    pub status: String,
    pub total_votes: i64,
    pub yes_votes: i64,
    pub no_votes: i64,
    pub abstain_votes: i64,
    pub required_quorum: i32,
    pub quorum_reached: bool,
    pub decided_at: Option<DateTime<Utc>>,
}

/// Initiate consensus: create proposal and compute quorum from active peers.
///
/// Quorum = ceil((peer_count + 1) / 2) — simple majority.
pub async fn initiate_consensus(
    pool: &PgPool,
    initiator_id: Uuid,
    escrow_id: Option<Uuid>,
    proposal_type: &str,
) -> Result<Uuid, ConsensusError> {
    // Validate proposal type
    if ![
        "release_escrow",
        "cycle_break",
        "arbitration",
        "quarantine",
        "appeal_quarantine",
    ]
    .contains(&proposal_type)
    {
        return Err(ConsensusError::InvalidVote(format!(
            "Invalid proposal_type: {}",
            proposal_type
        )));
    }

    // Verify escrow exists if release_escrow
    if proposal_type == "release_escrow" {
        let escrow_id = escrow_id.ok_or(ConsensusError::InvalidProposal(
            "escrow_id required for release_escrow".to_string(),
        ))?;

        let exists: bool =
            sqlx::query_scalar("SELECT EXISTS(SELECT 1 FROM escrow_ledger WHERE id = $1)")
                .bind(escrow_id)
                .fetch_one(pool)
                .await?;

        if !exists {
            return Err(ConsensusError::InvalidProposal(
                "escrow_id not found".to_string(),
            ));
        }
    }

    // Count active peers (bidirectional)
    let peer_list: Vec<(Uuid, String, String)> = sqlx::query_as(
        "SELECT fp.sovereign_b_id, s.endpoint_url, 'outbound'::text as direction
         FROM federation_peers fp
         JOIN sovereigns s ON s.id = fp.sovereign_b_id
         WHERE fp.sovereign_a_id = $1 AND fp.status = 'active'
         AND (fp.expires_at IS NULL OR fp.expires_at > NOW())
         AND s.endpoint_url IS NOT NULL
         UNION ALL
         SELECT fp.sovereign_a_id, s.endpoint_url, 'inbound'::text
         FROM federation_peers fp
         JOIN sovereigns s ON s.id = fp.sovereign_a_id
         WHERE fp.sovereign_b_id = $1 AND fp.status = 'active'
         AND (fp.expires_at IS NULL OR fp.expires_at > NOW())
         AND s.endpoint_url IS NOT NULL",
    )
    .bind(initiator_id)
    .fetch_all(pool)
    .await?;

    let peer_count = peer_list.len() as i32;

    // Quorum calculation: simple majority for most, super-majority (2/3) for quarantine/appeal
    let required_quorum = if proposal_type == "quarantine" || proposal_type == "appeal_quarantine" {
        // Super-majority: ceil(2 * (peer_count + 1) / 3), minimum 2
        ((2 * (peer_count + 1) + 2) / 3).max(2)
    } else {
        // Simple majority: ceil((peer_count + 1) / 2), minimum 1
        ((peer_count + 1) / 2).max(1)
    };

    // Insert proposal
    let proposal_id: Uuid = sqlx::query_scalar(
        "INSERT INTO consensus_proposals (
            initiator_sovereign_id, escrow_id, proposal_type, peer_count, required_quorum
        ) VALUES ($1, $2, $3, $4, $5)
        RETURNING id",
    )
    .bind(initiator_id)
    .bind(escrow_id)
    .bind(proposal_type)
    .bind(peer_count)
    .bind(required_quorum)
    .fetch_one(pool)
    .await
    .map_err(|e| ConsensusError::Database(e.to_string()))?;

    Ok(proposal_id)
}

/// Cast a consensus vote with signature verification.
///
/// Signature = Ed25519(voter.private_key, "{proposal_id}:{vote}")
/// Returns current quorum status.
pub async fn cast_consensus_vote(
    pool: &PgPool,
    proposal_id: Uuid,
    voter_id: Uuid,
    vote: &str,
    signature_hex: &str,
) -> Result<ConsensusResult, ConsensusError> {
    // Validate vote value
    if !["yes", "no", "abstain"].contains(&vote) {
        return Err(ConsensusError::InvalidVote(vote.to_string()));
    }

    // Load proposal: verify pending and not expired
    let proposal: Option<(String, DateTime<Utc>)> =
        sqlx::query_as("SELECT status, expires_at FROM consensus_proposals WHERE id = $1")
            .bind(proposal_id)
            .fetch_optional(pool)
            .await?;

    let (status, expires_at) = proposal.ok_or(ConsensusError::ProposalNotFound)?;

    if status != "pending" {
        return Err(ConsensusError::NotPendingStatus);
    }

    if expires_at <= Utc::now() {
        return Err(ConsensusError::NotPendingStatus);
    }

    // Fetch voter's public key
    let public_key_pem: Option<String> =
        sqlx::query_scalar("SELECT public_key_pem FROM sovereigns WHERE id = $1")
            .bind(voter_id)
            .fetch_optional(pool)
            .await?;

    let public_key_pem = public_key_pem.ok_or(ConsensusError::VoterNotActivePeer)?;

    // Parse Ed25519 public key from PEM
    let verifying_key =
        parse_ed25519_pem(&public_key_pem).map_err(|_| ConsensusError::InvalidSignature)?;

    // Construct canonical payload: "{proposal_id}:{vote}"
    let canonical_payload = format!("{}:{}", proposal_id, vote);

    // Decode signature hex
    let sig_bytes = hex::decode(signature_hex).map_err(|_| ConsensusError::InvalidSignature)?;
    if sig_bytes.len() != 64 {
        return Err(ConsensusError::InvalidSignature);
    }

    let mut sig_array = [0u8; 64];
    sig_array.copy_from_slice(&sig_bytes);
    let signature = Signature::from_bytes(&sig_array);

    // Verify signature strictly
    verifying_key
        .verify_strict(canonical_payload.as_bytes(), &signature)
        .map_err(|_| ConsensusError::InvalidSignature)?;

    // Insert vote (UNIQUE constraint handles duplicate silently)
    let vote_id: Option<Uuid> = sqlx::query_scalar(
        "INSERT INTO consensus_votes (proposal_id, voter_sovereign_id, vote, signature)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT (proposal_id, voter_sovereign_id) DO NOTHING
         RETURNING id",
    )
    .bind(proposal_id)
    .bind(voter_id)
    .bind(vote)
    .bind(signature_hex)
    .fetch_optional(pool)
    .await?;

    if vote_id.is_none() {
        return Err(ConsensusError::AlreadyVoted);
    }

    // Return quorum status
    check_consensus_quorum(pool, proposal_id).await
}

/// Check if quorum has been reached and update proposal status if needed.
pub async fn check_consensus_quorum(
    pool: &PgPool,
    proposal_id: Uuid,
) -> Result<ConsensusResult, ConsensusError> {
    // Load proposal
    let proposal: Option<(String, i32, i32, DateTime<Utc>)> = sqlx::query_as(
        "SELECT status, required_quorum, peer_count, expires_at FROM consensus_proposals WHERE id = $1"
    )
    .bind(proposal_id)
    .fetch_optional(pool)
    .await?;

    let (mut status, required_quorum, _peer_count, expires_at) =
        proposal.ok_or(ConsensusError::ProposalNotFound)?;

    // Count votes
    let vote_counts: Vec<(String, i64)> = sqlx::query_as(
        "SELECT vote, COUNT(*) as count FROM consensus_votes WHERE proposal_id = $1 GROUP BY vote",
    )
    .bind(proposal_id)
    .fetch_all(pool)
    .await?;

    let mut yes_votes = 0i64;
    let mut no_votes = 0i64;
    let mut abstain_votes = 0i64;

    for (vote, count) in vote_counts {
        match vote.as_str() {
            "yes" => yes_votes = count,
            "no" => no_votes = count,
            "abstain" => abstain_votes = count,
            _ => {}
        }
    }

    let total_votes = yes_votes + no_votes + abstain_votes;

    // Check expiration
    if expires_at <= Utc::now() && status == "pending" {
        sqlx::query("UPDATE consensus_proposals SET status = 'expired' WHERE id = $1")
            .bind(proposal_id)
            .execute(pool)
            .await?;
        status = "expired".to_string();
    }

    // Check quorum reached (approval)
    if yes_votes >= required_quorum as i64 && status == "pending" {
        sqlx::query(
            "UPDATE consensus_proposals SET status = 'approved', decided_at = NOW() WHERE id = $1",
        )
        .bind(proposal_id)
        .execute(pool)
        .await?;
        status = "approved".to_string();
    }

    let quorum_reached = yes_votes >= required_quorum as i64;
    let decided_at = if status != "pending" {
        Some(Utc::now())
    } else {
        None
    };

    Ok(ConsensusResult {
        proposal_id,
        status,
        total_votes,
        yes_votes,
        no_votes,
        abstain_votes,
        required_quorum,
        quorum_reached,
        decided_at,
    })
}

/// Finalize consensus and execute the approved action (e.g., release escrow).
pub async fn finalize_consensus(pool: &PgPool, proposal_id: Uuid) -> Result<(), ConsensusError> {
    // Load proposal
    let proposal: Option<(String, String, Option<Uuid>, Uuid, serde_json::Value)> = sqlx::query_as(
        "SELECT status, proposal_type, escrow_id, initiator_sovereign_id, payload FROM consensus_proposals WHERE id = $1"
    )
    .bind(proposal_id)
    .fetch_optional(pool)
    .await?;

    let (status, proposal_type, escrow_id, initiator_id, payload) =
        proposal.ok_or(ConsensusError::ProposalNotFound)?;

    if status != "approved" {
        return Err(ConsensusError::QuorumNotReached);
    }

    // Execute proposal action
    match proposal_type.as_str() {
        "release_escrow" => {
            let escrow_id = escrow_id.ok_or(ConsensusError::InvalidProposal(
                "release_escrow requires escrow_id".to_string(),
            ))?;

            // Call escrow_repo::release_escrow using consensus as authorization
            // Signature parameter = "consensus_approved"
            crate::repo::escrow_repo::release_escrow(pool, escrow_id, initiator_id, "consensus")
                .await
                .map_err(|e| ConsensusError::Database(e.to_string()))?;
        }
        "cycle_break" => {
            let grant_id_str =
                payload["grant_id_to_revoke"]
                    .as_str()
                    .ok_or(ConsensusError::InvalidProposal(
                        "missing grant_id_to_revoke".to_string(),
                    ))?;
            let grant_id = Uuid::parse_str(grant_id_str).map_err(|_| {
                ConsensusError::InvalidProposal("invalid grant_id_to_revoke UUID".to_string())
            })?;
            let grantor_id_str =
                payload["grantor_sovereign_id"]
                    .as_str()
                    .ok_or(ConsensusError::InvalidProposal(
                        "missing grantor_sovereign_id".to_string(),
                    ))?;
            let grantor_id = Uuid::parse_str(grantor_id_str).map_err(|_| {
                ConsensusError::InvalidProposal("invalid grantor_sovereign_id UUID".to_string())
            })?;

            crate::repo::cross_sovereign_delegation_repo::revoke_grant(
                pool, grant_id, grantor_id, true,
            )
            .await
            .map_err(|e| ConsensusError::Database(e.to_string()))?;
        }
        "arbitration" => {
            // 1. Extract payload fields
            let arb_id_str = payload["arbitrator_sovereign_id"].as_str().ok_or(
                ConsensusError::InvalidProposal("missing arbitrator_sovereign_id".to_string()),
            )?;
            let arbitrator_id = Uuid::parse_str(arb_id_str).map_err(|_| {
                ConsensusError::InvalidProposal("invalid arbitrator_sovereign_id".to_string())
            })?;
            let verdict = payload["verdict"]
                .as_str()
                .ok_or(ConsensusError::InvalidProposal(
                    "missing verdict".to_string(),
                ))?;
            let escrow_disposition =
                payload["escrow_disposition"]
                    .as_str()
                    .ok_or(ConsensusError::InvalidProposal(
                        "missing escrow_disposition".to_string(),
                    ))?;
            let invoice_id_str =
                payload["invoice_id"]
                    .as_str()
                    .ok_or(ConsensusError::InvalidProposal(
                        "missing invoice_id".to_string(),
                    ))?;
            let invoice_id = Uuid::parse_str(invoice_id_str)
                .map_err(|_| ConsensusError::InvalidProposal("invalid invoice_id".to_string()))?;
            let verdict_sig_hex =
                payload["verdict_signature"]
                    .as_str()
                    .ok_or(ConsensusError::InvalidProposal(
                        "missing verdict_signature".to_string(),
                    ))?;

            // 2. Verify arbitrator Ed25519 signature (same pattern as cast_consensus_vote)
            let pem: String =
                sqlx::query_scalar("SELECT public_key_pem FROM sovereigns WHERE id = $1")
                    .bind(arbitrator_id)
                    .fetch_optional(pool)
                    .await
                    .map_err(|e| ConsensusError::Database(e.to_string()))?
                    .ok_or(ConsensusError::InvalidSignature)?;

            let verifying_key =
                parse_ed25519_pem(&pem).map_err(|_| ConsensusError::InvalidSignature)?;
            let canonical = format!("{}:{}:{}", proposal_id, verdict, escrow_disposition);
            let sig_bytes =
                hex::decode(verdict_sig_hex).map_err(|_| ConsensusError::InvalidSignature)?;
            let signature =
                Signature::from_slice(&sig_bytes).map_err(|_| ConsensusError::InvalidSignature)?;
            verifying_key
                .verify_strict(canonical.as_bytes(), &signature)
                .map_err(|_| ConsensusError::InvalidSignature)?;

            // 3. Validate verdict and disposition values
            if !["creditor_wins", "debtor_wins", "split"].contains(&verdict) {
                return Err(ConsensusError::InvalidProposal(format!(
                    "invalid verdict: {verdict}"
                )));
            }
            let new_escrow_status = match escrow_disposition {
                "release" => "released",
                "forfeit" => "forfeited",
                other => {
                    return Err(ConsensusError::InvalidProposal(format!(
                        "invalid escrow_disposition: {other}"
                    )));
                }
            };

            // 4. Atomically update escrow + invoice in a transaction
            //    Cannot use release_escrow()/forfeit_escrow_on_timeout() — both guard status='held'
            let escrow_id = escrow_id.ok_or_else(|| {
                ConsensusError::InvalidProposal(
                    "arbitration proposal missing escrow_id".to_string(),
                )
            })?;

            let dispute_resolution = format!("arbitration:{verdict}:arbitrator={arbitrator_id}");

            let mut tx = pool
                .begin()
                .await
                .map_err(|e| ConsensusError::Database(e.to_string()))?;

            sqlx::query(
                "UPDATE escrow_ledger \
                 SET status = $1, arbitration_result = $2 \
                 WHERE id = $3 AND status = 'disputed'",
            )
            .bind(new_escrow_status)
            .bind(verdict)
            .bind(escrow_id)
            .execute(&mut *tx)
            .await
            .map_err(|e| ConsensusError::Database(e.to_string()))?;

            sqlx::query(
                "UPDATE settlement_invoices \
                 SET status = 'resolved', dispute_resolved_at = NOW(), dispute_resolution = $1 \
                 WHERE id = $2 AND status = 'disputed'",
            )
            .bind(&dispute_resolution)
            .bind(invoice_id)
            .execute(&mut *tx)
            .await
            .map_err(|e| ConsensusError::Database(e.to_string()))?;

            tx.commit()
                .await
                .map_err(|e| ConsensusError::Database(e.to_string()))?;
        }
        "quarantine" => {
            // 1. Extract payload fields
            let target_id_str =
                payload["target_sovereign_id"]
                    .as_str()
                    .ok_or(ConsensusError::InvalidProposal(
                        "missing target_sovereign_id".to_string(),
                    ))?;
            let target_id = Uuid::parse_str(target_id_str).map_err(|_| {
                ConsensusError::InvalidProposal("invalid target_sovereign_id".to_string())
            })?;
            let anomaly_type =
                payload["anomaly_type"]
                    .as_str()
                    .ok_or(ConsensusError::InvalidProposal(
                        "missing anomaly_type".to_string(),
                    ))?;
            let evidence_summary =
                payload["evidence_summary"]
                    .as_str()
                    .ok_or(ConsensusError::InvalidProposal(
                        "missing evidence_summary".to_string(),
                    ))?;
            let severity = payload
                .get("severity")
                .and_then(|v| v.as_str())
                .unwrap_or("high");

            // 2. Quarantine the sovereign (UPDATE sovereigns SET status='quarantined')
            sqlx::query("UPDATE sovereigns SET status = 'quarantined' WHERE id = $1")
                .bind(target_id)
                .execute(pool)
                .await
                .map_err(|e| ConsensusError::Database(e.to_string()))?;

            // 3. Insert threat intelligence record (crystallization to DB)
            sqlx::query(
                "INSERT INTO threat_intelligence (sovereign_id, anomaly_type, evidence_summary, severity, consensus_proposal_id)
                 VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(target_id)
            .bind(anomaly_type)
            .bind(evidence_summary)
            .bind(severity)
            .bind(proposal_id)
            .execute(pool)
            .await
            .map_err(|e| ConsensusError::Database(e.to_string()))?;

            // 4. Crystallization: append to docs/wiki/semantic/threat-patterns.md (file I/O is best-effort, non-fatal)
            let entry = format!(
                "\n## Threat Pattern — {}\n\
                - **Sovereign:** {}\n\
                - **Anomaly:** {}\n\
                - **Severity:** {}\n\
                - **Evidence:** {}\n\
                - **Crystallized:** {}\n",
                anomaly_type,
                target_id,
                anomaly_type,
                severity,
                evidence_summary,
                chrono::Utc::now().to_rfc3339()
            );
            // Attempt to append to file (non-fatal if fails — DB record is authoritative)
            if let Ok(mut file) = tokio::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open("docs/wiki/semantic/threat-patterns.md")
                .await
            {
                use tokio::io::AsyncWriteExt;
                let _ = file.write_all(entry.as_bytes()).await;
            }

            // 5. Phase 18: Slash all held escrows for the quarantined sovereign (non-fatal)
            let slash_reason = format!(
                "Quarantine consensus finalized: anomaly_type={}, proposal_id={}",
                anomaly_type, proposal_id
            );
            let _ = crate::repo::escrow_repo::slash_all_held_escrows_for_sovereign(
                pool,
                target_id,
                severity,
                &slash_reason,
            )
            .await; // non-fatal: slash failure does not roll back quarantine
        }
        "appeal_quarantine" => {
            // 1. Extract payload fields
            let target_id_str =
                payload["sovereign_id"]
                    .as_str()
                    .ok_or(ConsensusError::InvalidProposal(
                        "missing sovereign_id".to_string(),
                    ))?;
            let target_id = Uuid::parse_str(target_id_str)
                .map_err(|_| ConsensusError::InvalidProposal("invalid sovereign_id".to_string()))?;

            // 2. Transition from quarantine to probation
            sqlx::query("UPDATE sovereigns SET status = 'probation' WHERE id = $1")
                .bind(target_id)
                .execute(pool)
                .await
                .map_err(|e| ConsensusError::Database(e.to_string()))?;

            // 3. Mark appeal as approved
            sqlx::query(
                "UPDATE appeal_proposals SET is_approved = TRUE, appeal_resolved_at = NOW()
                 WHERE sovereign_id = $1 AND is_approved IS NULL",
            )
            .bind(target_id)
            .execute(pool)
            .await
            .map_err(|e| ConsensusError::Database(e.to_string()))?;

            // 4. Log probation start in audit log
            sqlx::query(
                "INSERT INTO probation_audit_log (sovereign_id, probation_started_at, event_type, event_details)
                 VALUES ($1, NOW(), 'activity_logged', '{\"event\": \"probation_started\"}'::jsonb)"
            )
            .bind(target_id)
            .execute(pool)
            .await
            .map_err(|e| ConsensusError::Database(e.to_string()))?;
        }
        other => {
            return Err(ConsensusError::InvalidProposal(format!(
                "unknown proposal_type: {other}"
            )));
        }
    }

    // Mark proposal as finalized
    sqlx::query(
        "UPDATE consensus_proposals SET status = 'finalized', finalized_at = NOW() WHERE id = $1",
    )
    .bind(proposal_id)
    .execute(pool)
    .await?;

    Ok(())
}

/// Background game-loop sweep: expire proposals past their timeout.
///
/// Returns count of proposals expired.
pub async fn expire_timed_out_proposals(pool: &PgPool) -> Result<u64, sqlx::Error> {
    sqlx::query("UPDATE consensus_proposals SET status = 'expired' WHERE status = 'pending' AND expires_at <= NOW()")
        .execute(pool)
        .await
        .map(|res| res.rows_affected())
}

/// Parse Ed25519 public key from PEM-encoded string.
fn parse_ed25519_pem(pem: &str) -> Result<VerifyingKey, Box<dyn std::error::Error>> {
    use base64::engine::Engine;

    // Extract base64 content between PEM headers
    let lines: Vec<&str> = pem.lines().collect();
    let mut b64_content = String::new();

    let mut in_key = false;
    for line in lines {
        if line.contains("BEGIN PUBLIC KEY") {
            in_key = true;
            continue;
        }
        if line.contains("END PUBLIC KEY") {
            break;
        }
        if in_key {
            b64_content.push_str(line);
        }
    }

    // Decode base64
    let der_bytes = base64::engine::general_purpose::STANDARD
        .decode(&b64_content)
        .map_err(|e| Box::new(e) as Box<dyn std::error::Error>)?;

    // Extract raw public key (32 bytes) from DER-encoded SubjectPublicKeyInfo
    // DER structure: SEQUENCE { SEQUENCE { OID, ... }, BIT STRING { raw_key } }
    // The raw 32-byte public key is typically at bytes [27..59] in PKIX format
    if der_bytes.len() < 32 {
        return Err("DER encoded key too short".into());
    }

    let mut key_array = [0u8; 32];
    // Try offset 27 (standard PKIX position)
    if der_bytes.len() >= 59 {
        key_array.copy_from_slice(&der_bytes[27..59]);
    } else {
        // Fallback: use last 32 bytes
        let start = der_bytes.len().saturating_sub(32);
        key_array.copy_from_slice(&der_bytes[start..]);
    }

    Ok(VerifyingKey::from_bytes(&key_array)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_quorum_formula_1_peer() {
        let peer_count = 1i32;
        let required = ((peer_count + 1) / 2).max(1);
        assert_eq!(required, 1, "1 peer → quorum 1");
    }

    #[test]
    fn test_quorum_formula_5_peers() {
        let peer_count = 5i32;
        let required = ((peer_count + 1) / 2).max(1);
        assert_eq!(required, 3, "5 peers → quorum 3 (majority of 5)");
    }

    #[test]
    fn test_quorum_formula_0_peers() {
        let peer_count = 0i32;
        let required = ((peer_count + 1) / 2).max(1);
        assert_eq!(required, 1, "0 peers → quorum 1 (minimum)");
    }

    #[test]
    fn test_quarantine_supermajority_formula_3_peers() {
        // 3 peers → required_quorum = max(2, ceil(2*4/3)) = max(2, 3) = 3
        let peer_count = 3i32;
        let required = ((2 * (peer_count + 1) + 2) / 3).max(2);
        assert_eq!(required, 3, "3 peers → supermajority quorum 3");
    }

    #[test]
    fn test_quarantine_supermajority_formula_6_peers() {
        // 6 peers → required_quorum = max(2, ceil(2*7/3)) = max(2, 5) = 5
        let peer_count = 6i32;
        let required = ((2 * (peer_count + 1) + 2) / 3).max(2);
        assert_eq!(required, 5, "6 peers → supermajority quorum 5");
    }

    #[test]
    fn test_quarantine_supermajority_min_2() {
        // 0 peers → required_quorum = max(2, ceil(2*1/3)) = max(2, 1) = 2
        let peer_count = 0i32;
        let required = ((2 * (peer_count + 1) + 2) / 3).max(2);
        assert_eq!(required, 2, "0 peers → supermajority min 2");
    }

    #[test]
    fn test_appeal_quarantine_uses_supermajority_quorum() {
        // appeal_quarantine should use same formula as quarantine
        let peer_count = 3i32;
        let required = ((2 * (peer_count + 1) + 2) / 3).max(2);
        assert_eq!(required, 3, "3 peers → supermajority quorum 3 for appeal");
    }

    #[test]
    fn test_invalid_vote_rejected() {
        let vote = "maybe";
        let is_valid = ["yes", "no", "abstain"].contains(&vote);
        assert!(!is_valid, "Invalid vote should be rejected");
    }

    #[test]
    fn test_consensus_result_quorum_reached() {
        let yes_votes = 3i64;
        let required_quorum = 3i32;
        let quorum_reached = yes_votes >= required_quorum as i64;
        assert!(quorum_reached, "3 yes votes >= 3 quorum → quorum reached");
    }

    #[test]
    fn test_arbitration_invalid_verdict_value() {
        let verdict = "unknown";
        let is_valid = ["creditor_wins", "debtor_wins", "split"].contains(&verdict);
        assert!(!is_valid, "Invalid verdict should be rejected");
    }

    #[test]
    fn test_arbitration_invalid_disposition_value() {
        let disposition = "burn";
        let is_valid = ["release", "forfeit"].contains(&disposition);
        assert!(!is_valid, "Invalid disposition should be rejected");
    }

    #[test]
    fn test_arbitration_bad_signature_hex() {
        let verdict_sig_hex = "not_valid_hex";
        let result = hex::decode(verdict_sig_hex);
        assert!(result.is_err(), "Invalid hex should fail decode");
    }

    #[test]
    fn test_quarantine_severity_high_maps_to_25_percent() {
        let severity = "high";
        let slash_pct = crate::repo::escrow_repo::compute_slash_percentage(severity);
        assert_eq!(slash_pct, 25, "severity=high should map to 25% slash");
    }

    // ============================================================================
    // Integration Tests (Docker-dependent)
    // ============================================================================

    #[cfg(test)]
    mod integration_tests {
        use super::*;
        use base64::Engine;
        use ed25519_dalek::Signer;
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
        async fn test_initiate_consensus_success() {
            let (_container, pool) = setup_postgres().await;

            // Create initiator sovereign
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
            .execute(&pool)
            .await
            .expect("insert debtor");

            // Create bilateral agreement
            let _peer_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO federation_peers (sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, status) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(initiator_id)
            .bind(debtor_id)
            .bind(100i16)
            .bind(vec!["test"])
            .bind("active")
            .execute(&pool)
            .await
            .expect("insert peer");

            // Create invoice and escrow
            let invoice_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO settlement_invoices (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, total_tokens, entry_count, invoice_hash, invoice_signature, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
            )
            .bind(invoice_id)
            .bind(initiator_id)
            .bind(debtor_id)
            .bind(Utc::now())
            .bind(Utc::now())
            .bind(1000i64)
            .bind(1)
            .bind("abc123")
            .bind("sig-bytes")
            .bind("pending")
            .execute(&pool)
            .await
            .expect("insert invoice");

            let escrow_id = sqlx::query_scalar::<_, Uuid>(
                "INSERT INTO escrow_ledger (invoice_id, creditor_sovereign_id, debtor_sovereign_id, tokens_held, created_by_sovereign_id) VALUES ($1, $2, $3, $4, $2) RETURNING id"
            )
            .bind(invoice_id)
            .bind(initiator_id)
            .bind(debtor_id)
            .bind(1000i64)
            .fetch_one(&pool)
            .await
            .expect("insert escrow");

            // Initiate consensus
            let result =
                initiate_consensus(&pool, initiator_id, Some(escrow_id), "release_escrow").await;
            assert!(result.is_ok(), "Initiate should succeed");

            let proposal_id = result.unwrap();
            let (status, required_q, peer_c): (String, i32, i32) = sqlx::query_as(
                "SELECT status, required_quorum, peer_count FROM consensus_proposals WHERE id = $1",
            )
            .bind(proposal_id)
            .fetch_one(&pool)
            .await
            .unwrap();

            assert_eq!(status, "pending", "Status should be pending");
            assert_eq!(required_q, 1, "Quorum should be 1 (1 peer)");
            assert_eq!(peer_c, 1, "Peer count should be 1");
        }

        #[tokio::test]
        async fn test_quorum_formula_computed() {
            let (_container, pool) = setup_postgres().await;

            // Create 5 sovereigns
            let sovereigns: Vec<Uuid> = (0..5).map(|_| Uuid::new_v4()).collect();

            for (i, sid) in sovereigns.iter().enumerate() {
                sqlx::query(
                    "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
                )
                .bind(sid)
                .bind(format!("s{}", i))
                .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
                .bind("active")
                .bind(format!("http://s{}.local", i))
                .execute(&pool)
                .await
                .expect("insert sovereign");
            }

            // Create bilateral agreements: 0 is hub, connected to 1,2,3,4 (4 peers)
            for i in 1..5 {
                sqlx::query(
                    "INSERT INTO federation_peers (sovereign_a_id, sovereign_b_id, max_admitted_tier, granted_attestation_types, status) VALUES ($1, $2, $3, $4, $5)"
                )
                .bind(sovereigns[0])
                .bind(sovereigns[i])
                .bind(100i16)
                .bind(vec!["test"])
                .bind("active")
                .execute(&pool)
                .await
                .expect("insert peer");
            }

            // Create invoice and escrow
            let invoice_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO settlement_invoices (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, total_tokens, entry_count, invoice_hash, invoice_signature, status) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)"
            )
            .bind(invoice_id)
            .bind(sovereigns[0])
            .bind(sovereigns[1])
            .bind(Utc::now())
            .bind(Utc::now())
            .bind(1000i64)
            .bind(1)
            .bind("abc123")
            .bind("sig-bytes")
            .bind("pending")
            .execute(&pool)
            .await
            .expect("insert invoice");

            let escrow_id = sqlx::query_scalar::<_, Uuid>(
                "INSERT INTO escrow_ledger (invoice_id, creditor_sovereign_id, debtor_sovereign_id, tokens_held, created_by_sovereign_id) VALUES ($1, $2, $3, $4, $2) RETURNING id"
            )
            .bind(invoice_id)
            .bind(sovereigns[0])
            .bind(sovereigns[1])
            .bind(1000i64)
            .fetch_one(&pool)
            .await
            .expect("insert escrow");

            // Initiate with 4 peers → quorum should be 3 (ceil(5/2))
            let result =
                initiate_consensus(&pool, sovereigns[0], Some(escrow_id), "release_escrow").await;
            assert!(result.is_ok());

            let required_q: i32 =
                sqlx::query_scalar("SELECT required_quorum FROM consensus_proposals WHERE id = $1")
                    .bind(result.unwrap())
                    .fetch_one(&pool)
                    .await
                    .unwrap();

            assert_eq!(required_q, 3, "4 peers → quorum 3 (ceil(5/2))");
        }

        #[tokio::test]
        async fn test_expire_timed_out_proposals() {
            let (_container, pool) = setup_postgres().await;

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
            .unwrap();

            // Manually insert a proposal with expires_at in the past
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
            .unwrap();

            // Sweep
            let expired_count = expire_timed_out_proposals(&pool).await.unwrap();
            assert!(expired_count > 0, "Should expire at least 1 proposal");

            // Verify status changed
            let status: String =
                sqlx::query_scalar("SELECT status FROM consensus_proposals WHERE id = $1")
                    .bind(proposal_id)
                    .fetch_one(&pool)
                    .await
                    .unwrap();

            assert_eq!(status, "expired", "Status should be expired");
        }

        #[tokio::test]
        async fn test_arbitration_releases_escrow_and_resolves_invoice() {
            let (_container, pool) = setup_postgres().await;

            // Generate test Ed25519 key pair for arbitrator with a fixed seed
            use ed25519_dalek::{SigningKey, VerifyingKey};
            let seed: [u8; 32] = [
                1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
                24, 25, 26, 27, 28, 29, 30, 31, 32,
            ];
            let signing_key: SigningKey = SigningKey::from_bytes(&seed);
            let verifying_key: VerifyingKey = signing_key.verifying_key();

            // Encode verifying key to PEM
            let pub_key_bytes = verifying_key.to_bytes();
            // Construct minimal PKIX DER structure with 32-byte key at offset 27
            let mut der_bytes = vec![
                0x30, 0x2a, // SEQUENCE, length 42
                0x30, 0x05, // SEQUENCE, length 5 (algorithm ID)
                0x06, 0x03, 0x2b, 0x65, 0x70, // OID for Ed25519
                0x03, 0x21, // BIT STRING, length 33
                0x00, // No unused bits
            ];
            der_bytes.extend_from_slice(&pub_key_bytes);
            let b64_key = base64::engine::general_purpose::STANDARD.encode(&der_bytes);
            let pem = format!(
                "-----BEGIN PUBLIC KEY-----\n{}\n-----END PUBLIC KEY-----",
                b64_key
            );

            // Create sovereigns
            let arbitrator_id = Uuid::new_v4();
            let creditor_id = Uuid::new_v4();
            let debtor_id = Uuid::new_v4();

            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(arbitrator_id)
            .bind("arbitrator")
            .bind(&pem)
            .bind("active")
            .bind("http://arbitrator.local")
            .execute(&pool)
            .await
            .expect("insert arbitrator");

            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(creditor_id)
            .bind("creditor")
            .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
            .bind("active")
            .bind("http://creditor.local")
            .execute(&pool)
            .await
            .expect("insert creditor");

            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(debtor_id)
            .bind("debtor")
            .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
            .bind("active")
            .bind("http://debtor.local")
            .execute(&pool)
            .await
            .expect("insert debtor");

            // Create invoice in disputed status
            let invoice_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO settlement_invoices (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, total_tokens, entry_count, invoice_hash, invoice_signature, status, dispute_resolved_at, dispute_resolution)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)"
            )
            .bind(invoice_id)
            .bind(creditor_id)
            .bind(debtor_id)
            .bind(Utc::now())
            .bind(Utc::now())
            .bind(1000i64)
            .bind(1)
            .bind("invoice_hash")
            .bind("sig_bytes")
            .bind("disputed")
            .bind::<Option<DateTime<Utc>>>(None)
            .bind::<Option<String>>(None)
            .execute(&pool)
            .await
            .expect("insert invoice");

            // Create escrow in disputed status
            let escrow_id = sqlx::query_scalar::<_, Uuid>(
                "INSERT INTO escrow_ledger (invoice_id, creditor_sovereign_id, debtor_sovereign_id, tokens_held, created_by_sovereign_id, status, arbitration_result)
                 VALUES ($1, $2, $3, $4, $2, $5, $6) RETURNING id"
            )
            .bind(invoice_id)
            .bind(creditor_id)
            .bind(debtor_id)
            .bind(1000i64)
            .bind("disputed")
            .bind::<Option<String>>(None)
            .fetch_one(&pool)
            .await
            .expect("insert escrow");

            // Create arbitration proposal
            let proposal_id = Uuid::new_v4();
            let verdict = "creditor_wins";
            let escrow_disposition = "release";
            let canonical = format!("{}:{}:{}", proposal_id, verdict, escrow_disposition);

            let signature = signing_key.sign(canonical.as_bytes());
            let sig_hex = hex::encode(signature.to_bytes());

            let payload = serde_json::json!({
                "arbitrator_sovereign_id": arbitrator_id.to_string(),
                "verdict": verdict,
                "escrow_disposition": escrow_disposition,
                "invoice_id": invoice_id.to_string(),
                "verdict_signature": sig_hex,
            });

            sqlx::query(
                "INSERT INTO consensus_proposals (id, initiator_sovereign_id, escrow_id, proposal_type, peer_count, required_quorum, status, payload)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
            )
            .bind(proposal_id)
            .bind(creditor_id)
            .bind(escrow_id)
            .bind("arbitration")
            .bind(1)
            .bind(1)
            .bind("approved")
            .bind(&payload)
            .execute(&pool)
            .await
            .expect("insert proposal");

            // Finalize consensus
            let result = finalize_consensus(&pool, proposal_id).await;
            assert!(result.is_ok(), "finalize_consensus should succeed");

            // Verify escrow status
            let (escrow_status, arbitration_result): (String, Option<String>) = sqlx::query_as(
                "SELECT status, arbitration_result FROM escrow_ledger WHERE id = $1",
            )
            .bind(escrow_id)
            .fetch_one(&pool)
            .await
            .expect("fetch escrow");

            assert_eq!(escrow_status, "released", "Escrow should be released");
            assert_eq!(
                arbitration_result,
                Some("creditor_wins".to_string()),
                "Arbitration result should be recorded"
            );

            // Verify invoice status
            let (invoice_status, dispute_resolved_at): (String, Option<DateTime<Utc>>) =
                sqlx::query_as(
                    "SELECT status, dispute_resolved_at FROM settlement_invoices WHERE id = $1",
                )
                .bind(invoice_id)
                .fetch_one(&pool)
                .await
                .expect("fetch invoice");

            assert_eq!(invoice_status, "resolved", "Invoice should be resolved");
            assert!(
                dispute_resolved_at.is_some(),
                "dispute_resolved_at should be set"
            );
        }

        #[tokio::test]
        async fn test_arbitration_forfeits_escrow() {
            let (_container, pool) = setup_postgres().await;

            // Generate test Ed25519 key pair for arbitrator with a fixed seed
            use ed25519_dalek::{SigningKey, VerifyingKey};
            let seed: [u8; 32] = [
                33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53,
                54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64,
            ];
            let signing_key: SigningKey = SigningKey::from_bytes(&seed);
            let verifying_key: VerifyingKey = signing_key.verifying_key();

            // Encode verifying key to PEM
            let pub_key_bytes = verifying_key.to_bytes();
            let mut der_bytes = vec![
                0x30, 0x2a, // SEQUENCE, length 42
                0x30, 0x05, // SEQUENCE, length 5 (algorithm ID)
                0x06, 0x03, 0x2b, 0x65, 0x70, // OID for Ed25519
                0x03, 0x21, // BIT STRING, length 33
                0x00, // No unused bits
            ];
            der_bytes.extend_from_slice(&pub_key_bytes);
            let b64_key = base64::engine::general_purpose::STANDARD.encode(&der_bytes);
            let pem = format!(
                "-----BEGIN PUBLIC KEY-----\n{}\n-----END PUBLIC KEY-----",
                b64_key
            );

            // Create sovereigns
            let arbitrator_id = Uuid::new_v4();
            let creditor_id = Uuid::new_v4();
            let debtor_id = Uuid::new_v4();

            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(arbitrator_id)
            .bind("arbitrator")
            .bind(&pem)
            .bind("active")
            .bind("http://arbitrator.local")
            .execute(&pool)
            .await
            .expect("insert arbitrator");

            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(creditor_id)
            .bind("creditor")
            .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
            .bind("active")
            .bind("http://creditor.local")
            .execute(&pool)
            .await
            .expect("insert creditor");

            sqlx::query(
                "INSERT INTO sovereigns (id, name, public_key_pem, status, endpoint_url) VALUES ($1, $2, $3, $4, $5)"
            )
            .bind(debtor_id)
            .bind("debtor")
            .bind("-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAI...")
            .bind("active")
            .bind("http://debtor.local")
            .execute(&pool)
            .await
            .expect("insert debtor");

            // Create invoice in disputed status
            let invoice_id = Uuid::new_v4();
            sqlx::query(
                "INSERT INTO settlement_invoices (id, creditor_sovereign_id, debtor_sovereign_id, period_start, period_end, total_tokens, entry_count, invoice_hash, invoice_signature, status, dispute_resolved_at, dispute_resolution)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)"
            )
            .bind(invoice_id)
            .bind(creditor_id)
            .bind(debtor_id)
            .bind(Utc::now())
            .bind(Utc::now())
            .bind(1000i64)
            .bind(1)
            .bind("invoice_hash")
            .bind("sig_bytes")
            .bind("disputed")
            .bind::<Option<DateTime<Utc>>>(None)
            .bind::<Option<String>>(None)
            .execute(&pool)
            .await
            .expect("insert invoice");

            // Create escrow in disputed status
            let escrow_id = sqlx::query_scalar::<_, Uuid>(
                "INSERT INTO escrow_ledger (invoice_id, creditor_sovereign_id, debtor_sovereign_id, tokens_held, created_by_sovereign_id, status, arbitration_result)
                 VALUES ($1, $2, $3, $4, $2, $5, $6) RETURNING id"
            )
            .bind(invoice_id)
            .bind(creditor_id)
            .bind(debtor_id)
            .bind(1000i64)
            .bind("disputed")
            .bind::<Option<String>>(None)
            .fetch_one(&pool)
            .await
            .expect("insert escrow");

            // Create arbitration proposal with forfeit disposition
            let proposal_id = Uuid::new_v4();
            let verdict = "debtor_wins";
            let escrow_disposition = "forfeit";
            let canonical = format!("{}:{}:{}", proposal_id, verdict, escrow_disposition);

            let signature = signing_key.sign(canonical.as_bytes());
            let sig_hex = hex::encode(signature.to_bytes());

            let payload = serde_json::json!({
                "arbitrator_sovereign_id": arbitrator_id.to_string(),
                "verdict": verdict,
                "escrow_disposition": escrow_disposition,
                "invoice_id": invoice_id.to_string(),
                "verdict_signature": sig_hex,
            });

            sqlx::query(
                "INSERT INTO consensus_proposals (id, initiator_sovereign_id, escrow_id, proposal_type, peer_count, required_quorum, status, payload)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
            )
            .bind(proposal_id)
            .bind(creditor_id)
            .bind(escrow_id)
            .bind("arbitration")
            .bind(1)
            .bind(1)
            .bind("approved")
            .bind(&payload)
            .execute(&pool)
            .await
            .expect("insert proposal");

            // Finalize consensus
            let result = finalize_consensus(&pool, proposal_id).await;
            assert!(result.is_ok(), "finalize_consensus should succeed");

            // Verify escrow status is forfeited
            let escrow_status: String =
                sqlx::query_scalar("SELECT status FROM escrow_ledger WHERE id = $1")
                    .bind(escrow_id)
                    .fetch_one(&pool)
                    .await
                    .expect("fetch escrow");

            assert_eq!(escrow_status, "forfeited", "Escrow should be forfeited");
        }
    }
}
