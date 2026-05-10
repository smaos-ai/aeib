use crate::attestation::Attestation;
use crate::tokens::{SessionToken, CapabilityToken};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

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

/// Response enum for POST /.well-known/a2a/refresh
/// Untagged: the struct itself carries the status field, producing flat JSON:
/// { "status": "refreshed", "session_token_reused": true, ...fields... }
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum AttestationRefreshResponse {
    Success(AttestationRefreshResponseSuccess),
    Error(AttestationRefreshResponseError),
}

#[cfg(test)]
mod tests {
    use super::*;

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
        assert_eq!(req.ephemeral_nonce, "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0");
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
        });

        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("\"status\":\"refreshed\""));
        assert!(json.contains("\"score\":80"));
        assert!(json.contains("\"tier\":2"));
    }
}
