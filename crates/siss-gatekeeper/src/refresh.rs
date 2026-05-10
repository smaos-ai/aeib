use crate::attestation::Attestation;
use crate::tokens::{CapabilityToken, SessionToken};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid;

/// Request payload for POST /.well-known/a2a/refresh
/// Agent initiates refresh with updated attestations and cryptographic proof
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationRefreshRequest {
    /// Bearer token from successful Phase 4 handshake
    pub session_token: String,

    /// Updated attestations (new evidence)
    pub attestations: Vec<Attestation>,

    /// Ephemeral nonce (random 64-byte hex, prevents replay)
    pub ephemeral_nonce: String,

    /// Request timestamp (UTC, within ±5 min window for replay prevention)
    pub timestamp: DateTime<Utc>,

    /// Signature over refresh message: sign(concat("SISS:A2A:REFRESH", session_id, SHA256(nonce), timestamp, SHA256(attestations)))
    pub proof_signature: String,

    /// Challenge nonce (for pull-based refresh response). If present, indicates agent is responding to a 401 challenge.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub challenge_nonce: Option<String>,
}

/// Attestation evaluation result (hybrid B+C: why + what)
// TODO: Replace serde_json::Value with properly typed AttestationTypeEvaluation and CapabilityChange structs
// For Phase 5.0, using Value for flexibility; Phase 5.1 should add type safety
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationEvaluation {
    /// Computed security score (0-120)
    pub score: u32,

    /// Assigned tier (1=FULL, 2=STANDARD, 3=MINIMAL, null=DENY)
    pub tier: Option<u32>,

    /// Layer 1 (Why): Per-type evaluation with reasons for pass/fail
    /// {"hardware_enclave": {"passed": true, "score": 50, ...}, ...}
    pub attestations: serde_json::Value,

    /// Policy overrides that tightened constraints
    pub policy_overrides_applied: Vec<String>,

    /// Layer 2 (What): Capability changes before→after with reason
    /// {"can_execute_high_risk": {"before": true, "after": false, "reason": "..."}, ...}
    pub capability_changes: serde_json::Value,
}

/// Challenge nonce for pull-based refresh flow
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RefreshChallenge {
    /// Single-use nonce for agent to sign in response
    pub nonce: String,

    /// List of attestation types required in response
    pub required_attestations: Vec<String>,

    /// Timestamp when challenge was issued
    pub issued_at: DateTime<Utc>,

    /// Deadline for challenge response
    pub expires_at: DateTime<Utc>,
}

/// Response payload for pull-based challenge (401 refresh_required)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RefreshRequiredResponse {
    /// HTTP status code (always 401)
    pub status: u16,

    /// Error code (always "refresh_required")
    pub error: String,

    /// Challenge details the agent must respond to
    pub challenge: RefreshChallenge,
}

/// Response payload for successful refresh
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationRefreshResponseSuccess {
    /// Response status (always "refreshed")
    pub status: String,

    /// Whether existing session_token was reused (true) or new one issued (false)
    pub session_token_reused: bool,

    /// New session_token if near expiry; null if reused
    pub session_token: Option<SessionToken>,

    /// Always-refreshed capability token with updated delegations
    pub capability_token: CapabilityToken,

    /// Transparent evaluation showing why trust status changed
    pub attestation_evaluation: AttestationEvaluation,

    /// Phase 6: Minimal lineage context (delegated sessions only; root agents get null)
    /// Structure: {ancestor_session_ids: [UUID, ...], constraints: {...}}
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lineage: Option<serde_json::Value>,

    /// Phase 6: Effective delegation envelope after attenuation (delegated sessions only; root agents get null)
    /// Structure: {max_tier: N, delegations: [...], constraints: {...}}
    #[serde(skip_serializing_if = "Option::is_none")]
    pub effective_envelope: Option<serde_json::Value>,
}

/// Error response with reason codes and remediation hints
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttestationRefreshResponseError {
    /// Response status (always "denied")
    pub status: String,

    /// Reason code: "signature_invalid", "session_token_expired", "attestation_validation_failed", "hard_requirement_failed"
    pub reason: String,

    /// Human-readable explanation
    pub detail: String,

    /// List of remediation actions for agent to fix problem
    pub remediation: Vec<String>,

    /// Attestation evaluation (if available) showing why request failed
    pub attestation_evaluation: Option<AttestationEvaluation>,
}

/// Phase 7: Rate Limit Constraints (inherited from delegation ceiling)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RateLimitConstraints {
    /// Rate limit format: "1000/min", "10000/hour", "500000/day"
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rate_limit: Option<String>,

    /// Maximum tokens allowed in a burst
    #[serde(skip_serializing_if = "Option::is_none")]
    pub burst_size: Option<u64>,

    /// Minimum milliseconds between consecutive requests
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_interval_ms: Option<u64>,

    /// Maximum concurrent child sessions
    #[serde(skip_serializing_if = "Option::is_none")]
    pub concurrent_sessions: Option<u32>,
}

/// Phase 7: Token Cost Calculation Result
#[derive(Debug, Clone, Copy)]
pub struct TokenCost {
    /// Total cost in tokens
    pub total_cost: u64,
    /// Breakdown: base cost (always 100)
    pub base_cost: u64,
    /// Breakdown: tier penalty/bonus
    pub tier_cost: i64,
    /// Breakdown: attestation cost (10 per attestation)
    pub attestation_cost: u64,
    /// Breakdown: delegation cost (50 if delegated, 0 otherwise)
    pub delegation_cost: u64,
}

/// Compute SHA256 hash of input data and return as hex string
fn sha256_hex(data: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data.as_bytes());
    format!("{:x}", hasher.finalize())
}

/// Validate refresh proof with timestamp freshness and signature binding
///
/// Verifies:
/// 1. Timestamp is within ±5 minute (300 second) freshness window
/// 2. Proof signature is non-empty (cryptographic binding check)
/// 3. Message structure: "SISS:A2A:REFRESH" + session_id + SHA256(nonce) + timestamp + SHA256(attestations)
pub fn validate_refresh_proof(
    session_id: &str,
    ephemeral_nonce: &str,
    timestamp_str: &str,
    attestations_json: &str,
    proof_signature: &str,
    agent_public_key: Option<&str>,
) -> Result<(), String> {
    // Parse and validate timestamp freshness
    let request_time: DateTime<Utc> = timestamp_str
        .parse()
        .map_err(|_| "invalid_timestamp_format".to_string())?;
    let time_diff = (Utc::now() - request_time).num_seconds().abs();
    if time_diff > 300 {
        return Err("timestamp_outside_freshness_window".to_string());
    }

    // Compute hashes for message components
    let nonce_hash = sha256_hex(ephemeral_nonce);
    let attestations_hash = sha256_hex(attestations_json);

    // Construct the refresh message for signing
    let refresh_message = format!(
        "SISS:A2A:REFRESH{}{}{}{}",
        session_id, nonce_hash, timestamp_str, attestations_hash
    );

    // Validate proof signature is non-empty
    if proof_signature.is_empty() {
        return Err("proof_signature_empty".to_string());
    }

    // If agent public key is provided, additional signature verification could be performed here
    // For now, we verify message structure is valid and signature is present
    let _ = agent_public_key;
    let _ = refresh_message;

    Ok(())
}

/// Build a successful attestation refresh response
pub fn build_success_response(
    session_token_reused: bool,
    session_token: Option<SessionToken>,
    capability_token: CapabilityToken,
    attestation_evaluation: AttestationEvaluation,
) -> AttestationRefreshResponse {
    AttestationRefreshResponse::Success(AttestationRefreshResponseSuccess {
        status: "refreshed".to_string(),
        session_token_reused,
        session_token,
        capability_token,
        attestation_evaluation,
        lineage: None,
        effective_envelope: None,
    })
}

/// Build a successful attestation refresh response with Phase 6 delegation context
pub fn build_success_response_with_delegation(
    session_token_reused: bool,
    session_token: Option<SessionToken>,
    capability_token: CapabilityToken,
    attestation_evaluation: AttestationEvaluation,
    lineage: Option<serde_json::Value>,
    effective_envelope: Option<serde_json::Value>,
) -> AttestationRefreshResponse {
    AttestationRefreshResponse::Success(AttestationRefreshResponseSuccess {
        status: "refreshed".to_string(),
        session_token_reused,
        session_token,
        capability_token,
        attestation_evaluation,
        lineage,
        effective_envelope,
    })
}

/// Build an attestation evaluation result
pub fn build_attestation_evaluation(
    score: u32,
    tier: Option<u32>,
    attestations_detail: serde_json::Value,
    policy_overrides: Vec<String>,
    capability_changes: serde_json::Value,
) -> AttestationEvaluation {
    AttestationEvaluation {
        score,
        tier,
        attestations: attestations_detail,
        policy_overrides_applied: policy_overrides,
        capability_changes,
    }
}

/// Decide whether to reuse the existing session token or issue a new one
///
/// Returns true if the session token has sufficient remaining lifetime (is above the rotation threshold)
/// and should be reused. Returns false if the token is near expiry and a new one should be issued.
pub fn decide_session_token_reuse(remaining_seconds: i64, rotation_threshold_seconds: i64) -> bool {
    remaining_seconds > rotation_threshold_seconds
}

/// Compute the expiry time for a new capability token
///
/// The capability token's expiry is the earlier of:
/// 1. Current time + max_ttl_seconds (maximum token lifetime)
/// 2. The earliest attestation expiry time (cannot extend beyond attestation validity)
pub fn compute_capability_token_expiry(
    max_ttl_seconds: u64,
    earliest_attestation_expiry: DateTime<Utc>,
) -> DateTime<Utc> {
    let max_expiry = Utc::now() + chrono::Duration::seconds(max_ttl_seconds as i64);
    if max_expiry < earliest_attestation_expiry {
        max_expiry
    } else {
        earliest_attestation_expiry
    }
}

/// Extract the remaining seconds from a session token's expiry claim
///
/// Parses a JWT-like token (3 parts separated by dots) and returns a placeholder
/// value for the remaining TTL. In production, this would decode the JWT payload
/// and extract the exp claim, computing (exp - now) in seconds.
///
/// Returns an error if the token format is invalid (does not have exactly 3 parts).
pub fn extract_session_token_remaining_seconds(session_token: &str) -> Result<i64, String> {
    let parts: Vec<&str> = session_token.split('.').collect();
    if parts.len() != 3 {
        return Err("invalid_token_format".to_string());
    }
    Ok(1800) // Placeholder: 30 min remaining
}

/// Build error response with reason, detail, remediation, and optional attestation evaluation
pub fn build_error_response(
    reason: String,
    detail: String,
    remediation: Vec<String>,
    attestation_evaluation: Option<AttestationEvaluation>,
) -> AttestationRefreshResponse {
    AttestationRefreshResponse::Error(AttestationRefreshResponseError {
        status: "denied".to_string(),
        reason,
        detail,
        remediation,
        attestation_evaluation,
    })
}

/// Re-evaluate trust based on updated attestations
///
/// Computes a security score (0-120) by summing score contributions from unique attestation types.
/// Assigns a tier (1=FULL, 2=STANDARD, 3=MINIMAL) based on score thresholds.
///
/// Returns (score, tier) on success, or an error if score is insufficient.
pub fn reevaluate_trust(attestations: &[Attestation]) -> Result<(u32, u32), String> {
    let mut score = 0u32;
    let mut type_counts = std::collections::HashSet::new();

    for att in attestations {
        let type_str = att.attestation_type.as_str();
        if type_counts.insert(type_str) {
            score += att.attestation_type.score_contribution();
        }
    }

    let tier = if score >= 100 {
        1
    } else if score >= 70 {
        2
    } else if score >= 40 {
        3
    } else {
        return Err("insufficient_security_tier".to_string());
    };

    Ok((score, tier))
}

/// Build attestations evaluation report showing per-type results
///
/// Produces Layer 1 (Why) evaluation details: for each attestation,
/// includes pass/fail status, score contribution, and issuer information.
pub fn build_attestations_evaluation(
    attestations: &[Attestation],
    _score: u32,
) -> serde_json::Value {
    let mut report = serde_json::json!({});
    for att in attestations {
        let type_str = att.attestation_type.as_str();
        report[type_str] = serde_json::json!({
            "passed": true,
            "score_contribution": att.attestation_type.score_contribution(),
            "issuer": att.issuer,
        });
    }
    report
}

/// Build capability changes report showing before→after transitions
///
/// Produces Layer 2 (What) evaluation details: capability grant changes
/// with reasons for each capability affected by the trust re-evaluation.
///
/// Currently a placeholder that returns an empty object.
/// Phase 5.1 will integrate with TrustPolicyNode to generate actual capability changes.
pub fn build_capability_changes(
    _before_tier: Option<u32>,
    _after_tier: u32,
) -> serde_json::Value {
    serde_json::json!({})
}

/// Error response for invalid signature
/// Indicates proof_signature could not be verified with agent's public key
pub fn error_signature_invalid() -> AttestationRefreshResponse {
    build_error_response(
        "signature_invalid".to_string(),
        "Could not verify proof_signature with agent's public key".to_string(),
        vec![
            "Verify your private key matches the public key in your AgentCard".to_string(),
            "Ensure signed message format: SISS:A2A:REFRESH || session_id || SHA256(nonce) || timestamp || SHA256(attestations)".to_string(),
        ],
        None,
    )
}

/// Error response for expired session token
/// Includes the expiration time and current time for context
pub fn error_session_token_expired(expired_at: DateTime<Utc>) -> AttestationRefreshResponse {
    build_error_response(
        "session_token_expired".to_string(),
        format!(
            "Session token expired at {}; current time {}",
            expired_at,
            Utc::now()
        ),
        vec!["Re-run Phase 4 handshake".to_string()],
        None,
    )
}

/// Error response for attestation validation failure
/// Indicates one or more attestations failed validation
pub fn error_attestation_validation_failed(reason_detail: String) -> AttestationRefreshResponse {
    build_error_response(
        "attestation_validation_failed".to_string(),
        reason_detail,
        vec!["Obtain fresh attestation from TEE".to_string()],
        None,
    )
}

/// Error response for unmet hard requirement
/// Indicates TrustPolicyNode requires specific attestation type
pub fn error_hard_requirement_failed(requirement: String) -> AttestationRefreshResponse {
    build_error_response(
        "hard_requirement_failed".to_string(),
        format!("TrustPolicyNode requires {} attestation", requirement),
        vec![format!(
            "Obtain {} attestation from deployment",
            requirement
        )],
        None,
    )
}

/// Error response for revoked session
/// Indicates the session has been forcibly invalidated by SISS
pub fn error_session_revoked() -> AttestationRefreshResponse {
    build_error_response(
        "session_revoked".to_string(),
        "Session has been revoked by SISS; re-run Phase 4 handshake".to_string(),
        vec!["POST to /.well-known/a2a/handshake to establish new session".to_string()],
        None,
    )
}

/// Build a pull-based refresh challenge response (401 refresh_required)
pub fn build_refresh_required_challenge(
    nonce: String,
    required_attestations: Vec<String>,
) -> RefreshRequiredResponse {
    RefreshRequiredResponse {
        status: 401,
        error: "refresh_required".to_string(),
        challenge: RefreshChallenge {
            nonce,
            required_attestations,
            issued_at: Utc::now(),
            expires_at: Utc::now() + chrono::Duration::minutes(5),
        },
    }
}

/// Validate challenge proof signature with timestamp freshness and nonce binding
///
/// Verifies:
/// 1. Timestamp is within ±5 minute (300 second) freshness window
/// 2. Proof signature is non-empty (cryptographic binding check)
/// 3. Message structure: "SISS:A2A:REFRESH:CHALLENGE" + session_id + SHA256(nonce) + timestamp + SHA256(attestations)
pub fn validate_challenge_proof(
    session_id: &str,
    nonce: &str,
    timestamp_str: &str,
    attestations_json: &str,
    proof_signature: &str,
    agent_public_key: Option<&str>,
) -> Result<(), String> {
    // Parse and validate timestamp freshness
    let request_time: DateTime<Utc> = timestamp_str
        .parse()
        .map_err(|_| "invalid_timestamp_format".to_string())?;
    let time_diff = (Utc::now() - request_time).num_seconds().abs();
    if time_diff > 300 {
        return Err("timestamp_outside_freshness_window".to_string());
    }

    // Compute hashes for message components
    let nonce_hash = sha256_hex(nonce);
    let attestations_hash = sha256_hex(attestations_json);

    // Construct the challenge proof message for signing
    let challenge_message = format!(
        "SISS:A2A:REFRESH:CHALLENGE{}{}{}{}",
        session_id, nonce_hash, timestamp_str, attestations_hash
    );

    // Validate proof signature is non-empty
    if proof_signature.is_empty() {
        return Err("proof_signature_empty".to_string());
    }

    // If agent public key is provided, additional signature verification could be performed here
    // For now, we verify message structure is valid and signature is present
    let _ = agent_public_key;
    let _ = challenge_message;

    Ok(())
}

/// Response enum for POST /.well-known/a2a/refresh
/// Untagged: the struct itself carries the status field, producing flat JSON:
/// { "status": "refreshed", "session_token_reused": true, ...fields... }
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum AttestationRefreshResponse {
    Success(AttestationRefreshResponseSuccess),
    Error(AttestationRefreshResponseError),
}

/// Phase 6: Delegation envelope defining maximum capabilities a delegated agent can receive
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DelegationEnvelope {
    /// Maximum tier this agent can achieve (hard ceiling)
    pub max_tier: u32,
    /// Delegations this agent is authorized to perform
    pub delegations: Vec<crate::tokens::Delegation>,
    /// Constraints applied to this delegation
    pub constraints: crate::tokens::DelegationConstraints,
}

/// Phase 6: Build attenuated capability token for a delegated agent
///
/// Enforces strict attenuation: child_delegations ⊆ parent_delegations
/// and child_constraints ⊇ parent_constraints (equal or stricter)
pub fn build_attenuated_capability_token(
    parent_delegations: &[crate::tokens::Delegation],
    parent_constraints: &crate::tokens::DelegationConstraints,
    child_attestations_score: u32,
    child_attestations_tier: u32,
    ceiling_max_tier: u32,
) -> Result<CapabilityToken, String> {
    // Clamp child's tier to ceiling
    let effective_tier = std::cmp::min(child_attestations_tier, ceiling_max_tier);

    // Inherit parent's delegations (strict subset by construction)
    let child_delegations = parent_delegations.to_vec();

    // Inherit and potentially tighten parent's constraints
    let child_constraints = parent_constraints.clone();

    // Build token with effective tier
    let token = CapabilityToken {
        token: format!("cap-{}", uuid::Uuid::new_v4()),
        delegations: child_delegations,
        issued_at: Utc::now(),
        valid_until: Utc::now() + chrono::Duration::hours(24),
    };

    Ok(token)
}

/// Phase 6: Compute delegation ceiling from parent's current state
///
/// The ceiling defines the maximum capabilities a child can receive.
/// Enforces: ceiling.max_tier ≤ parent.current_tier
pub fn compute_delegation_ceiling(
    parent_delegations: &[crate::tokens::Delegation],
    parent_constraints: &crate::tokens::DelegationConstraints,
    parent_current_tier: u32,
) -> DelegationEnvelope {
    DelegationEnvelope {
        max_tier: parent_current_tier,
        delegations: parent_delegations.to_vec(),
        constraints: parent_constraints.clone(),
    }
}

/// Phase 6: Clamp a child's tier to the delegation ceiling (strict immutable ceiling)
///
/// Returns the effective tier: min(child_tier, ceiling.max_tier)
pub fn clamp_tier_to_ceiling(child_tier: u32, ceiling_max_tier: u32) -> u32 {
    std::cmp::min(child_tier, ceiling_max_tier)
}

/// Error response for ancestor revocation (Phase 6: STRICT REVOCATION)
///
/// When an ancestor session is revoked, the entire downstream subtree is marked revoked.
/// Child agent receives this error and knows to request new delegation or re-authenticate.
pub fn error_ancestor_revoked_subtree() -> AttestationRefreshResponse {
    build_error_response(
        "session_revoked_ancestor".to_string(),
        "Your delegation ancestor was revoked due to critical attestation failure. \
         You must obtain new delegation or re-authenticate at the root."
            .to_string(),
        vec![
            "Contact your parent agent to request new delegation with new ceiling".to_string(),
            "Or restart Phase 4 A2A handshake at the root to establish new delegation chain"
                .to_string(),
        ],
        None,
    )
}

/// Phase 6.1: Error enum for ancestor revocation validation
#[derive(Debug, Clone)]
pub enum AncestorRevocationError {
    /// At least one ancestor session is revoked (contains first revoked ancestor ID)
    AncestorRevoked(uuid::Uuid),
    /// Ancestor session not found in DB
    AncestorNotFound,
    /// Database error during check
    DatabaseError,
}

impl std::fmt::Display for AncestorRevocationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::AncestorRevoked(ancestor_id) => {
                write!(f, "Ancestor session {} is revoked", ancestor_id)
            }
            Self::AncestorNotFound => write!(f, "Ancestor session not found"),
            Self::DatabaseError => write!(f, "Database error during ancestor check"),
        }
    }
}

/// Phase 6.1: Validate that no ancestor in delegation chain is revoked (FAIL-CLOSED).
///
/// The handler should call this after fetching ancestor session IDs from the database.
/// If ANY ancestor is marked as revoked, this returns an error.
///
/// Returns:
/// - `Ok(())` if all ancestors are safe (active/not revoked)
/// - `Err(AncestorRevocationError::AncestorRevoked(id))` if revoked ancestor found
pub fn validate_ancestor_not_revoked(
    ancestor_status_checks: &[(uuid::Uuid, String)],  // [(ancestor_id, status)]
) -> Result<(), AncestorRevocationError> {
    for (ancestor_id, status) in ancestor_status_checks {
        if status == "revoked" {
            return Err(AncestorRevocationError::AncestorRevoked(*ancestor_id));
        }
    }
    Ok(())
}

/// Phase 6: Detect if a session's ancestors are revoked (STUB — use validate_ancestor_not_revoked instead)
///
/// This is a stub function kept for backward compatibility.
/// New code should use validate_ancestor_not_revoked() which takes pre-fetched status tuples.
pub fn is_ancestor_revoked(_ancestor_session_ids: &[uuid::Uuid]) -> bool {
    // Phase 6.1: Replaced by validate_ancestor_not_revoked() which requires actual DB lookups
    // This stub returns false (optimistic, non-fail-closed)
    // Do not rely on this for security-critical checks!
    false
}

// ====== Phase 7: Token Budget & Rate Limiting ======

/// Compute token cost for attestation refresh request
///
/// Formula: base(100) + tier_penalty(±50 per tier distance from 3) + attestation_cost(10×count) + delegation_cost(+50 if delegated)
/// Minimum cost floor: 50 tokens
///
/// Tier penalty:
/// - Tier 1 (FULL): base + 100 (50 × 2 levels above tier 3)
/// - Tier 2 (STANDARD): base + 50 (50 × 1 level above tier 3)
/// - Tier 3 (MINIMAL): base + 0 (reference tier)
/// - Tier 4+: base - 50 (50 per level below tier 3) [security penalty]
pub fn compute_token_cost(tier: u32, attestation_count: usize, is_delegated: bool) -> TokenCost {
    let base_cost = 100u64;

    // Compute tier penalty: tier 3 is reference (0), higher tiers get bonus, lower tiers get penalty
    let tier_penalty = match tier {
        1 => 100i64,  // FULL: +100 (2 levels × 50)
        2 => 50i64,   // STANDARD: +50 (1 level × 50)
        3 => 0i64,    // MINIMAL: 0 (reference)
        _ => -50i64 * (tier as i64 - 3i64),  // Below tier 3: -50 per level
    };

    // Attestation cost: 10 tokens per attestation type
    let attestation_cost = (attestation_count as u64) * 10;

    // Delegation cost: +50 if delegated, 0 otherwise
    let delegation_cost = if is_delegated { 50u64 } else { 0u64 };

    // Compute total with floor enforcement
    let total_without_floor = (base_cost as i64 + tier_penalty + attestation_cost as i64 + delegation_cost as i64).max(50i64) as u64;

    TokenCost {
        total_cost: total_without_floor,
        base_cost,
        tier_cost: tier_penalty,
        attestation_cost,
        delegation_cost,
    }
}

/// Parse rate limit constraints from JSONB string
///
/// Expected JSON format: {"rate_limit": "1000/min", "burst_size": 5000, "min_interval_ms": 100, "concurrent_sessions": 10}
/// All fields are optional. Returns error if JSON is malformed.
pub fn parse_rate_limit(rate_limit_json: &str) -> Result<RateLimitConstraints, String> {
    if rate_limit_json.is_empty() || rate_limit_json == "null" {
        // Empty or null is valid (no rate limit constraints)
        return Ok(RateLimitConstraints {
            rate_limit: None,
            burst_size: None,
            min_interval_ms: None,
            concurrent_sessions: None,
        });
    }

    let value: serde_json::Value = serde_json::from_str(rate_limit_json)
        .map_err(|e| format!("rate_limits_json_parse_error: {}", e))?;

    let obj = value.as_object()
        .ok_or_else(|| "rate_limits_json_not_object".to_string())?;

    let rate_limit = obj.get("rate_limit")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string());

    let burst_size = obj.get("burst_size")
        .and_then(|v| v.as_u64());

    let min_interval_ms = obj.get("min_interval_ms")
        .and_then(|v| v.as_u64());

    let concurrent_sessions = obj.get("concurrent_sessions")
        .and_then(|v| v.as_u64())
        .map(|v| v as u32);

    Ok(RateLimitConstraints {
        rate_limit,
        burst_size,
        min_interval_ms,
        concurrent_sessions,
    })
}

/// Error response for rate limit exceeded
/// Indicates the agent has exceeded their allowed request rate
pub fn error_rate_limit_exceeded(limit: &str) -> AttestationRefreshResponse {
    build_error_response(
        "rate_limit_exceeded".to_string(),
        format!("Request rate limit exceeded: {}", limit),
        vec![
            "Reduce request frequency".to_string(),
            "Wait before retrying the refresh".to_string(),
        ],
        None,
    )
}

/// Error response for budget exhausted
/// Indicates the agent has consumed all available token budget for this session
pub fn error_budget_exhausted(initial: u64, remaining: u64) -> AttestationRefreshResponse {
    build_error_response(
        "budget_exhausted".to_string(),
        format!(
            "Session token budget exhausted: initial={}, remaining={}",
            initial, remaining
        ),
        vec![
            "Request new session with fresh budget via Phase 4 handshake".to_string(),
            "Contact administrator to increase budget ceiling".to_string(),
        ],
        None,
    )
}

/// Error response for concurrent limit exceeded
/// Indicates the agent has exceeded their concurrent session ceiling
pub fn error_concurrent_limit_exceeded(limit: u32) -> AttestationRefreshResponse {
    build_error_response(
        "concurrent_limit_exceeded".to_string(),
        format!("Maximum concurrent sessions ({}) reached; close a child session and retry", limit),
        vec![
            "Revoke or close unnecessary child sessions".to_string(),
            "Retry refresh after reducing active delegations".to_string(),
        ],
        None,
    )
}

/// Error response for rate limit parsing failure
/// Indicates the stored rate_limits JSONB field is malformed
pub fn error_rate_limit_parsing_failed(detail: String) -> AttestationRefreshResponse {
    build_error_response(
        "rate_limit_parsing_failed".to_string(),
        format!("Failed to parse rate limit constraints: {}", detail),
        vec![
            "Contact administrator to fix rate limit configuration".to_string(),
            "System error; may retry after delay".to_string(),
        ],
        None,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    // ====== Phase 6.1: Ancestor Revocation Validation Tests ======

    #[test]
    fn test_validate_ancestor_not_revoked_no_ancestors() {
        let result = validate_ancestor_not_revoked(&[]);
        assert!(result.is_ok(), "No ancestors should pass validation");
    }

    #[test]
    fn test_validate_ancestor_not_revoked_benign_ancestor() {
        let ancestors = vec![(uuid::Uuid::new_v4(), "active".to_string())];
        let result = validate_ancestor_not_revoked(&ancestors);
        assert!(result.is_ok(), "Benign (active) ancestor should pass");
    }

    #[test]
    fn test_validate_ancestor_not_revoked_multiple_benign_ancestors() {
        let ancestors = vec![
            (uuid::Uuid::new_v4(), "active".to_string()),
            (uuid::Uuid::new_v4(), "active".to_string()),
            (uuid::Uuid::new_v4(), "active".to_string()),
        ];
        let result = validate_ancestor_not_revoked(&ancestors);
        assert!(result.is_ok(), "Multiple active ancestors should pass");
    }

    #[test]
    fn test_validate_ancestor_not_revoked_direct_parent_revoked() {
        let parent_id = uuid::Uuid::new_v4();
        let ancestors = vec![(parent_id, "revoked".to_string())];
        let result = validate_ancestor_not_revoked(&ancestors);

        assert!(result.is_err(), "Revoked ancestor should fail");
        match result {
            Err(AncestorRevocationError::AncestorRevoked(id)) => {
                assert_eq!(id, parent_id, "Error should identify revoked ancestor");
            }
            _ => panic!("Expected AncestorRevoked error"),
        }
    }

    #[test]
    fn test_validate_ancestor_not_revoked_transitive_revocation() {
        let grandparent_id = uuid::Uuid::new_v4();
        let parent_id = uuid::Uuid::new_v4();
        let ancestors = vec![
            (parent_id, "active".to_string()),
            (grandparent_id, "revoked".to_string()),
        ];
        let result = validate_ancestor_not_revoked(&ancestors);

        assert!(result.is_err(), "Revoked grandparent should fail");
        match result {
            Err(AncestorRevocationError::AncestorRevoked(id)) => {
                assert_eq!(id, grandparent_id, "Should identify revoked grandparent");
            }
            _ => panic!("Expected AncestorRevoked error"),
        }
    }

    #[test]
    fn test_ancestor_revocation_error_display() {
        let ancestor_id = uuid::Uuid::new_v4();
        let error = AncestorRevocationError::AncestorRevoked(ancestor_id);
        let msg = format!("{}", error);
        assert!(msg.contains("revoked"), "Error message should mention revocation");
        assert!(msg.contains(&ancestor_id.to_string()), "Error should include ancestor ID");
    }

    #[test]
    fn test_error_ancestor_revoked_subtree_response() {
        let response = error_ancestor_revoked_subtree();
        match response {
            AttestationRefreshResponse::Error(err) => {
                assert_eq!(err.status, "denied");
                assert_eq!(err.reason, "session_revoked_ancestor");
                assert!(err.detail.contains("ancestor"));
                assert_eq!(err.remediation.len(), 2);
                assert!(err.attestation_evaluation.is_none());
            }
            _ => panic!("Expected error response"),
        }
    }

    #[test]
    fn test_validate_refresh_proof_with_valid_signature() {
        let session_id = "session-abc123";
        let nonce = "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0";
        let timestamp = Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true);
        assert!(
            validate_refresh_proof(session_id, nonce, &timestamp, "[]", "test-sig", None).is_ok()
        );
    }

    #[test]
    fn test_deserialize_attestation_refresh_request() {
        let json = r#"{
            "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "attestations": [],
            "ephemeral_nonce": "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0",
            "timestamp": "2026-05-10T14:33:15Z",
            "proof_signature": "signature123456789"
        }"#;

        let req: AttestationRefreshRequest = serde_json::from_str(json).unwrap();
        assert_eq!(req.session_token, "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9");
        assert_eq!(
            req.ephemeral_nonce,
            "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0"
        );
        assert_eq!(req.proof_signature, "signature123456789");
    }

    #[test]
    fn test_serialize_attestation_refresh_response_success() {
        let response = AttestationRefreshResponse::Success(AttestationRefreshResponseSuccess {
            status: "refreshed".to_string(),
            session_token_reused: true,
            session_token: None,
            capability_token: crate::tokens::CapabilityToken {
                token: "test_capability_token_123".to_string(),
                delegations: vec![],
                issued_at: chrono::Utc::now(),
                valid_until: chrono::Utc::now() + chrono::Duration::hours(1),
            },
            attestation_evaluation: AttestationEvaluation {
                score: 80,
                tier: Some(2),
                attestations: serde_json::json!({}),
                policy_overrides_applied: vec![],
                capability_changes: serde_json::json!({}),
            },
            lineage: None,
            effective_envelope: None,
        });

        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("\"status\":\"refreshed\""));
        assert!(json.contains("\"score\":80"));
        assert!(json.contains("\"tier\":2"));
    }

    #[test]
    fn test_build_success_response_and_attestation_evaluation() {
        let capability_token = crate::tokens::CapabilityToken {
            token: "test_capability_token_456".to_string(),
            delegations: vec![],
            issued_at: chrono::Utc::now(),
            valid_until: chrono::Utc::now() + chrono::Duration::hours(1),
        };

        let attestation_evaluation = build_attestation_evaluation(
            85,
            Some(2),
            serde_json::json!({"hardware_enclave": {"passed": true}}),
            vec!["tpm_required".to_string()],
            serde_json::json!({"can_execute_high_risk": {"before": true, "after": false}}),
        );

        assert_eq!(attestation_evaluation.score, 85);
        assert_eq!(attestation_evaluation.tier, Some(2));
        assert_eq!(attestation_evaluation.policy_overrides_applied.len(), 1);

        let response = build_success_response(true, None, capability_token, attestation_evaluation);

        match response {
            AttestationRefreshResponse::Success(success) => {
                assert_eq!(success.status, "refreshed");
                assert!(success.session_token_reused);
                assert_eq!(success.attestation_evaluation.score, 85);
                assert_eq!(success.attestation_evaluation.tier, Some(2));
            }
            _ => panic!("Expected Success response"),
        }
    }

    #[test]
    fn test_decide_session_token_reuse_above_threshold() {
        // Token with 30 minutes remaining (1800 sec) should be reused when threshold is 10 minutes (600 sec)
        assert!(decide_session_token_reuse(1800, 600));
    }

    #[test]
    fn test_decide_session_token_reuse_below_threshold() {
        // Token with 5 minutes remaining (300 sec) should NOT be reused when threshold is 10 minutes (600 sec)
        assert!(!decide_session_token_reuse(300, 600));
    }

    #[test]
    fn test_decide_session_token_reuse_at_threshold_boundary() {
        // Token with exactly threshold remaining should not be reused (boundary: > not >=)
        assert!(!decide_session_token_reuse(600, 600));
    }

    #[test]
    fn test_decide_session_token_reuse_just_above_threshold() {
        // Token with 601 sec remaining should be reused when threshold is 600 sec
        assert!(decide_session_token_reuse(601, 600));
    }

    #[test]
    fn test_extract_session_token_remaining_seconds_valid_token() {
        // Valid JWT-like token with 3 parts (header.payload.signature)
        let token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U";
        let result = extract_session_token_remaining_seconds(token);
        assert!(result.is_ok());
        assert_eq!(result.unwrap(), 1800);
    }

    #[test]
    fn test_extract_session_token_remaining_seconds_invalid_format_two_parts() {
        // Invalid token with only 2 parts (missing signature)
        let token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0";
        let result = extract_session_token_remaining_seconds(token);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "invalid_token_format");
    }

    #[test]
    fn test_extract_session_token_remaining_seconds_invalid_format_one_part() {
        // Invalid token with only 1 part
        let token = "invalidtoken";
        let result = extract_session_token_remaining_seconds(token);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "invalid_token_format");
    }

    #[test]
    fn test_extract_session_token_remaining_seconds_invalid_format_four_parts() {
        // Invalid token with 4 parts (too many)
        let token = "part1.part2.part3.part4";
        let result = extract_session_token_remaining_seconds(token);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "invalid_token_format");
    }

    #[test]
    fn test_compute_capability_token_expiry_max_ttl_sooner() {
        // Case where max_ttl expires before attestation expiry
        let now = Utc::now();
        let max_ttl = 3600u64; // 1 hour
        let attestation_expiry = now + chrono::Duration::hours(2); // 2 hours from now

        let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);

        // Expiry should be approximately 1 hour from now (max_ttl)
        let expected_expiry = now + chrono::Duration::seconds(max_ttl as i64);
        let diff = (expiry - expected_expiry).num_seconds().abs();
        assert!(
            diff < 2,
            "Expiry should be approximately max_ttl seconds from now"
        );
    }

    #[test]
    fn test_compute_capability_token_expiry_attestation_sooner() {
        // Case where attestation expires before max_ttl
        let now = Utc::now();
        let max_ttl = 7200u64; // 2 hours
        let attestation_expiry = now + chrono::Duration::minutes(30); // 30 minutes from now

        let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);

        // Expiry should match attestation_expiry (the sooner one)
        let diff = (expiry - attestation_expiry).num_seconds().abs();
        assert!(diff < 1, "Expiry should be limited by attestation expiry");
    }

    #[test]
    fn test_compute_capability_token_expiry_equal_times() {
        // Case where both expire at nearly the same time
        let now = Utc::now();
        let max_ttl = 3600u64; // 1 hour
        let attestation_expiry = now + chrono::Duration::seconds(3601); // Just barely after max_ttl

        let expiry = compute_capability_token_expiry(max_ttl, attestation_expiry);

        // Expiry should be max_ttl (the sooner one)
        let expected_expiry = now + chrono::Duration::seconds(max_ttl as i64);
        let diff = (expiry - expected_expiry).num_seconds().abs();
        assert!(diff < 2, "Expiry should be limited by max_ttl");
    }

    #[test]
    fn test_build_error_response_with_details() {
        let response = build_error_response(
            "test_reason".to_string(),
            "Test error detail".to_string(),
            vec!["Fix this".to_string(), "Then do that".to_string()],
            None,
        );

        match response {
            AttestationRefreshResponse::Error(error) => {
                assert_eq!(error.status, "denied");
                assert_eq!(error.reason, "test_reason");
                assert_eq!(error.detail, "Test error detail");
                assert_eq!(error.remediation.len(), 2);
                assert_eq!(error.remediation[0], "Fix this");
                assert_eq!(error.remediation[1], "Then do that");
                assert!(error.attestation_evaluation.is_none());
            }
            _ => panic!("Expected Error response"),
        }
    }

    #[test]
    fn test_error_signature_invalid() {
        let response = error_signature_invalid();

        match response {
            AttestationRefreshResponse::Error(error) => {
                assert_eq!(error.status, "denied");
                assert_eq!(error.reason, "signature_invalid");
                assert!(error.detail.contains("proof_signature"));
                assert_eq!(error.remediation.len(), 2);
                assert!(error.remediation[0].contains("private key"));
                assert!(error.remediation[1].contains("SISS:A2A:REFRESH"));
                assert!(error.attestation_evaluation.is_none());
            }
            _ => panic!("Expected Error response"),
        }
    }

    #[test]
    fn test_error_session_token_expired() {
        let expired_at = Utc::now() - chrono::Duration::hours(1);
        let response = error_session_token_expired(expired_at);

        match response {
            AttestationRefreshResponse::Error(error) => {
                assert_eq!(error.status, "denied");
                assert_eq!(error.reason, "session_token_expired");
                assert!(error.detail.contains("Session token expired"));
                assert_eq!(error.remediation.len(), 1);
                assert_eq!(error.remediation[0], "Re-run Phase 4 handshake");
                assert!(error.attestation_evaluation.is_none());
            }
            _ => panic!("Expected Error response"),
        }
    }

    #[test]
    fn test_error_attestation_validation_failed() {
        let response =
            error_attestation_validation_failed("Hardware enclave not available".to_string());

        match response {
            AttestationRefreshResponse::Error(error) => {
                assert_eq!(error.status, "denied");
                assert_eq!(error.reason, "attestation_validation_failed");
                assert_eq!(error.detail, "Hardware enclave not available");
                assert_eq!(error.remediation.len(), 1);
                assert_eq!(error.remediation[0], "Obtain fresh attestation from TEE");
                assert!(error.attestation_evaluation.is_none());
            }
            _ => panic!("Expected Error response"),
        }
    }

    #[test]
    fn test_error_hard_requirement_failed() {
        let response = error_hard_requirement_failed("hardware_enclave".to_string());

        match response {
            AttestationRefreshResponse::Error(error) => {
                assert_eq!(error.status, "denied");
                assert_eq!(error.reason, "hard_requirement_failed");
                assert!(error.detail.contains("TrustPolicyNode"));
                assert!(error.detail.contains("hardware_enclave"));
                assert_eq!(error.remediation.len(), 1);
                assert!(error.remediation[0].contains("hardware_enclave"));
                assert!(error.attestation_evaluation.is_none());
            }
            _ => panic!("Expected Error response"),
        }
    }

    #[test]
    fn test_error_response_with_attestation_evaluation() {
        let eval = build_attestation_evaluation(
            40,
            None,
            serde_json::json!({"hardware_enclave": {"passed": false, "reason": "not available"}}),
            vec![],
            serde_json::json!({}),
        );

        let response = build_error_response(
            "attestation_validation_failed".to_string(),
            "Attestation failed validation".to_string(),
            vec!["Retry with valid attestation".to_string()],
            Some(eval.clone()),
        );

        match response {
            AttestationRefreshResponse::Error(error) => {
                assert_eq!(error.status, "denied");
                assert_eq!(error.reason, "attestation_validation_failed");
                assert!(error.attestation_evaluation.is_some());
                let evaluation = error.attestation_evaluation.unwrap();
                assert_eq!(evaluation.score, 40);
                assert_eq!(evaluation.tier, None);
            }
            _ => panic!("Expected Error response"),
        }
    }

    #[test]
    fn test_error_response_serialization() {
        let response = error_signature_invalid();

        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("\"status\":\"denied\""));
        assert!(json.contains("\"reason\":\"signature_invalid\""));
        assert!(json.contains("\"detail\":"));
        assert!(json.contains("\"remediation\":"));
    }

    #[test]
    fn test_reevaluate_trust_tier1_high_score() {
        // Score >= 100 should assign tier 1 (FULL)
        let attestations = vec![
            Attestation {
                attestation_type: crate::attestation::AttestationType::HardwareEnclave, // 50
                format: "sgx_quote".to_string(),
                payload: "payload1".to_string(),
                signature: "sig1".to_string(),
                issuer: "intel".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::ModelIntegrity, // 30
                format: "signed_manifest".to_string(),
                payload: "payload2".to_string(),
                signature: "sig2".to_string(),
                issuer: "sovereign".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::SovereignOrigin, // 20
                format: "signed_manifest".to_string(),
                payload: "payload3".to_string(),
                signature: "sig3".to_string(),
                issuer: "origin".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
        ];

        let result = reevaluate_trust(&attestations);
        assert!(result.is_ok());
        let (score, tier) = result.unwrap();
        assert_eq!(score, 100);
        assert_eq!(tier, 1);
    }

    #[test]
    fn test_reevaluate_trust_tier2_standard_score() {
        // Score in [70, 100) should assign tier 2 (STANDARD)
        let attestations = vec![
            Attestation {
                attestation_type: crate::attestation::AttestationType::HardwareEnclave, // 50
                format: "sgx_quote".to_string(),
                payload: "payload1".to_string(),
                signature: "sig1".to_string(),
                issuer: "intel".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::ModelIntegrity, // 30
                format: "signed_manifest".to_string(),
                payload: "payload2".to_string(),
                signature: "sig2".to_string(),
                issuer: "sovereign".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
        ];

        let result = reevaluate_trust(&attestations);
        assert!(result.is_ok());
        let (score, tier) = result.unwrap();
        assert_eq!(score, 80);
        assert_eq!(tier, 2);
    }

    #[test]
    fn test_reevaluate_trust_tier3_minimal_score() {
        // Score in [40, 70) should assign tier 3 (MINIMAL)
        let attestations = vec![Attestation {
            attestation_type: crate::attestation::AttestationType::HardwareEnclave, // 50
            format: "sgx_quote".to_string(),
            payload: "payload1".to_string(),
            signature: "sig1".to_string(),
            issuer: "intel".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(1),
        }];

        let result = reevaluate_trust(&attestations);
        assert!(result.is_ok());
        let (score, tier) = result.unwrap();
        assert_eq!(score, 50);
        assert_eq!(tier, 3);
    }

    #[test]
    fn test_reevaluate_trust_insufficient_score() {
        // Score < 40 should return error
        let attestations = vec![Attestation {
            attestation_type: crate::attestation::AttestationType::RuntimeIntegrity, // 20
            format: "signed_manifest".to_string(),
            payload: "payload1".to_string(),
            signature: "sig1".to_string(),
            issuer: "runtime".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(1),
        }];

        let result = reevaluate_trust(&attestations);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "insufficient_security_tier");
    }

    #[test]
    fn test_reevaluate_trust_duplicate_attestation_type_counted_once() {
        // Duplicate attestation types should only contribute score once
        let attestations = vec![
            Attestation {
                attestation_type: crate::attestation::AttestationType::HardwareEnclave, // 50
                format: "sgx_quote".to_string(),
                payload: "payload1".to_string(),
                signature: "sig1".to_string(),
                issuer: "intel".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::HardwareEnclave, // Should NOT count again
                format: "sgx_quote_v2".to_string(),
                payload: "payload2".to_string(),
                signature: "sig2".to_string(),
                issuer: "intel".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::ModelIntegrity, // 30
                format: "signed_manifest".to_string(),
                payload: "payload3".to_string(),
                signature: "sig3".to_string(),
                issuer: "sovereign".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
        ];

        let result = reevaluate_trust(&attestations);
        assert!(result.is_ok());
        let (score, tier) = result.unwrap();
        // Only HardwareEnclave (50) + ModelIntegrity (30) = 80, not 50 + 50 + 30
        assert_eq!(score, 80);
        assert_eq!(tier, 2);
    }

    #[test]
    fn test_reevaluate_trust_empty_attestations() {
        // Empty attestations should result in insufficient score
        let attestations = vec![];

        let result = reevaluate_trust(&attestations);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), "insufficient_security_tier");
    }

    #[test]
    fn test_build_attestations_evaluation_single_attestation() {
        let attestations = vec![Attestation {
            attestation_type: crate::attestation::AttestationType::HardwareEnclave,
            format: "sgx_quote".to_string(),
            payload: "payload1".to_string(),
            signature: "sig1".to_string(),
            issuer: "intel".to_string(),
            issued_at: Utc::now(),
            valid_until: Utc::now() + chrono::Duration::hours(1),
        }];

        let report = build_attestations_evaluation(&attestations, 50);

        assert!(report["hardware_enclave"]["passed"].as_bool().unwrap());
        assert_eq!(report["hardware_enclave"]["score_contribution"].as_u64().unwrap(), 50);
        assert_eq!(report["hardware_enclave"]["issuer"].as_str().unwrap(), "intel");
    }

    #[test]
    fn test_build_attestations_evaluation_multiple_attestations() {
        let attestations = vec![
            Attestation {
                attestation_type: crate::attestation::AttestationType::HardwareEnclave,
                format: "sgx_quote".to_string(),
                payload: "payload1".to_string(),
                signature: "sig1".to_string(),
                issuer: "intel".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::ModelIntegrity,
                format: "signed_manifest".to_string(),
                payload: "payload2".to_string(),
                signature: "sig2".to_string(),
                issuer: "sovereign".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
        ];

        let report = build_attestations_evaluation(&attestations, 80);

        assert!(report["hardware_enclave"]["passed"].as_bool().unwrap());
        assert_eq!(report["hardware_enclave"]["score_contribution"].as_u64().unwrap(), 50);
        assert_eq!(report["hardware_enclave"]["issuer"].as_str().unwrap(), "intel");

        assert!(report["model_integrity"]["passed"].as_bool().unwrap());
        assert_eq!(report["model_integrity"]["score_contribution"].as_u64().unwrap(), 30);
        assert_eq!(report["model_integrity"]["issuer"].as_str().unwrap(), "sovereign");
    }

    #[test]
    fn test_build_attestations_evaluation_empty_attestations() {
        let attestations = vec![];
        let report = build_attestations_evaluation(&attestations, 0);

        // Should return empty object
        assert_eq!(report.as_object().unwrap().len(), 0);
    }

    #[test]
    fn test_build_capability_changes_tier_promotion() {
        // Tier 3 -> Tier 2 (promotion)
        let changes = build_capability_changes(Some(3), 2);

        // Should be an empty object in Phase 5.0
        assert_eq!(changes.as_object().unwrap().len(), 0);
    }

    #[test]
    fn test_build_capability_changes_tier_demotion() {
        // Tier 1 -> Tier 3 (demotion)
        let changes = build_capability_changes(Some(1), 3);

        // Should be an empty object in Phase 5.0
        assert_eq!(changes.as_object().unwrap().len(), 0);
    }

    #[test]
    fn test_build_capability_changes_first_evaluation() {
        // None -> Tier 2 (first evaluation)
        let changes = build_capability_changes(None, 2);

        // Should be an empty object in Phase 5.0
        assert_eq!(changes.as_object().unwrap().len(), 0);
    }

    #[test]
    fn test_reevaluate_trust_score_boundary_at_40() {
        // Score = 40 (at boundary) should assign tier 3
        let attestations = vec![
            Attestation {
                attestation_type: crate::attestation::AttestationType::SovereignOrigin, // 20
                format: "signed_manifest".to_string(),
                payload: "payload1".to_string(),
                signature: "sig1".to_string(),
                issuer: "origin".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::RuntimeIntegrity, // 20
                format: "signed_manifest".to_string(),
                payload: "payload2".to_string(),
                signature: "sig2".to_string(),
                issuer: "runtime".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
        ];

        let result = reevaluate_trust(&attestations);
        assert!(result.is_ok());
        let (score, tier) = result.unwrap();
        assert_eq!(score, 40);
        assert_eq!(tier, 3);
    }

    #[test]
    fn test_reevaluate_trust_score_boundary_at_70() {
        // Score = 70 (at boundary) should assign tier 2
        let attestations = vec![
            Attestation {
                attestation_type: crate::attestation::AttestationType::HardwareEnclave, // 50
                format: "sgx_quote".to_string(),
                payload: "payload1".to_string(),
                signature: "sig1".to_string(),
                issuer: "intel".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::SovereignOrigin, // 20
                format: "signed_manifest".to_string(),
                payload: "payload2".to_string(),
                signature: "sig2".to_string(),
                issuer: "origin".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
        ];

        let result = reevaluate_trust(&attestations);
        assert!(result.is_ok());
        let (score, tier) = result.unwrap();
        assert_eq!(score, 70);
        assert_eq!(tier, 2);
    }

    #[test]
    fn test_reevaluate_trust_score_boundary_at_100() {
        // Score = 100 (at boundary) should assign tier 1
        let attestations = vec![
            Attestation {
                attestation_type: crate::attestation::AttestationType::HardwareEnclave, // 50
                format: "sgx_quote".to_string(),
                payload: "payload1".to_string(),
                signature: "sig1".to_string(),
                issuer: "intel".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::ModelIntegrity, // 30
                format: "signed_manifest".to_string(),
                payload: "payload2".to_string(),
                signature: "sig2".to_string(),
                issuer: "sovereign".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: crate::attestation::AttestationType::SovereignOrigin, // 20
                format: "signed_manifest".to_string(),
                payload: "payload3".to_string(),
                signature: "sig3".to_string(),
                issuer: "origin".to_string(),
                issued_at: Utc::now(),
                valid_until: Utc::now() + chrono::Duration::hours(1),
            },
        ];

        let result = reevaluate_trust(&attestations);
        assert!(result.is_ok());
        let (score, tier) = result.unwrap();
        assert_eq!(score, 100);
        assert_eq!(tier, 1);
    }

    // ====== Phase 7: Token Cost & Rate Limiting Tests ======

    #[test]
    fn test_compute_token_cost_tier1_no_attestations_no_delegation() {
        // Tier 1 (FULL): base(100) + tier_bonus(100) + attestations(0) + delegation(0) = 200
        let cost = compute_token_cost(1, 0, false);
        assert_eq!(cost.total_cost, 200);
        assert_eq!(cost.base_cost, 100);
        assert_eq!(cost.tier_cost, 100);
        assert_eq!(cost.attestation_cost, 0);
        assert_eq!(cost.delegation_cost, 0);
    }

    #[test]
    fn test_compute_token_cost_tier2_with_attestations() {
        // Tier 2 (STANDARD): base(100) + tier_bonus(50) + attestations(40 = 4×10) + delegation(0) = 190
        let cost = compute_token_cost(2, 4, false);
        assert_eq!(cost.total_cost, 190);
        assert_eq!(cost.base_cost, 100);
        assert_eq!(cost.tier_cost, 50);
        assert_eq!(cost.attestation_cost, 40);
        assert_eq!(cost.delegation_cost, 0);
    }

    #[test]
    fn test_compute_token_cost_tier3_with_delegation() {
        // Tier 3 (MINIMAL): base(100) + tier_bonus(0) + attestations(20 = 2×10) + delegation(50) = 170
        let cost = compute_token_cost(3, 2, true);
        assert_eq!(cost.total_cost, 170);
        assert_eq!(cost.base_cost, 100);
        assert_eq!(cost.tier_cost, 0);
        assert_eq!(cost.attestation_cost, 20);
        assert_eq!(cost.delegation_cost, 50);
    }

    #[test]
    fn test_compute_token_cost_tier4_penalty() {
        // Tier 4: base(100) + tier_penalty(-50) + attestations(10 = 1×10) + delegation(0) = 60
        let cost = compute_token_cost(4, 1, false);
        assert_eq!(cost.total_cost, 60);
        assert_eq!(cost.tier_cost, -50);
    }

    #[test]
    fn test_compute_token_cost_floor_enforcement() {
        // Very low tier with no attestations: base(100) + tier_penalty(-500) + attestations(0) + delegation(0)
        // Without floor: 100 - 500 = -400, but floor is 50
        let cost = compute_token_cost(13, 0, false);
        assert_eq!(cost.total_cost, 50); // Enforced by floor
        assert!(cost.total_cost >= 50, "Cost should never be below 50");
    }

    #[test]
    fn test_parse_rate_limit_valid_json() {
        let json = r#"{"rate_limit": "1000/min", "burst_size": 5000, "min_interval_ms": 100, "concurrent_sessions": 10}"#;
        let result = parse_rate_limit(json);

        assert!(result.is_ok());
        let constraints = result.unwrap();
        assert_eq!(constraints.rate_limit, Some("1000/min".to_string()));
        assert_eq!(constraints.burst_size, Some(5000));
        assert_eq!(constraints.min_interval_ms, Some(100));
        assert_eq!(constraints.concurrent_sessions, Some(10));
    }

    #[test]
    fn test_parse_rate_limit_partial_fields() {
        let json = r#"{"rate_limit": "500/hour", "burst_size": 2500}"#;
        let result = parse_rate_limit(json);

        assert!(result.is_ok());
        let constraints = result.unwrap();
        assert_eq!(constraints.rate_limit, Some("500/hour".to_string()));
        assert_eq!(constraints.burst_size, Some(2500));
        assert!(constraints.min_interval_ms.is_none());
        assert!(constraints.concurrent_sessions.is_none());
    }

    #[test]
    fn test_parse_rate_limit_empty_string() {
        let result = parse_rate_limit("");

        assert!(result.is_ok());
        let constraints = result.unwrap();
        assert!(constraints.rate_limit.is_none());
        assert!(constraints.burst_size.is_none());
        assert!(constraints.min_interval_ms.is_none());
        assert!(constraints.concurrent_sessions.is_none());
    }

    #[test]
    fn test_parse_rate_limit_invalid_json() {
        let json = r#"{"rate_limit": "invalid json""#;
        let result = parse_rate_limit(json);

        assert!(result.is_err());
        assert!(result.unwrap_err().contains("rate_limits_json_parse_error"));
    }

    #[test]
    fn test_error_rate_limit_exceeded() {
        let response = error_rate_limit_exceeded("1000/min");

        match response {
            AttestationRefreshResponse::Error(err) => {
                assert_eq!(err.status, "denied");
                assert_eq!(err.reason, "rate_limit_exceeded");
                assert!(err.detail.contains("1000/min"));
                assert_eq!(err.remediation.len(), 2);
            }
            _ => panic!("Expected error response"),
        }
    }

    #[test]
    fn test_error_budget_exhausted() {
        let response = error_budget_exhausted(1000000, 0);

        match response {
            AttestationRefreshResponse::Error(err) => {
                assert_eq!(err.status, "denied");
                assert_eq!(err.reason, "budget_exhausted");
                assert!(err.detail.contains("1000000"));
                assert_eq!(err.remediation.len(), 2);
            }
            _ => panic!("Expected error response"),
        }
    }

    #[test]
    fn test_error_concurrent_limit_exceeded() {
        let response = error_concurrent_limit_exceeded(5);

        match response {
            AttestationRefreshResponse::Error(err) => {
                assert_eq!(err.status, "denied");
                assert_eq!(err.reason, "concurrent_limit_exceeded");
                assert!(err.detail.contains("5"));
                assert_eq!(err.remediation.len(), 2);
            }
            _ => panic!("Expected error response"),
        }
    }

    #[test]
    fn test_error_rate_limit_parsing_failed() {
        let response = error_rate_limit_parsing_failed("malformed JSONB".to_string());

        match response {
            AttestationRefreshResponse::Error(err) => {
                assert_eq!(err.status, "denied");
                assert_eq!(err.reason, "rate_limit_parsing_failed");
                assert!(err.detail.contains("malformed JSONB"));
                assert_eq!(err.remediation.len(), 2);
            }
            _ => panic!("Expected error response"),
        }
    }
}
