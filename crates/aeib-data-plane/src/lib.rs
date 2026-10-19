//! crates/aeib-data-plane/src/lib.rs
//! ============================================================================
//! AEIB Native Rust Data Plane: Constant-Time Station 1 Admissibility Gate,
//! Group-Commit Durability WAL, and TEE Ephemeral Attestation Scaffold.
//!
//! Epistemic Boundaries (AGENTS.md):
//! - Evaluated and tested under the stated adversarial threat model.
//! - Prototype and structural scaffold for kernel/hardware-isolated execution.
//! - No universal claims; provides observed timing-channel mitigation and
//!   fail-closed admissibility gating.
//! ============================================================================

pub mod attestation;
pub mod scitt;
pub mod wal;

use ed25519_dalek::{Signature, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;

/// Five-tuple pre-dispatch admission payload submitted to Station 1 Gate.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PreDispatchIntent {
    /// Unique identifier for this operation.
    pub operation_id: String,
    /// Targeted external contract / resource URI.
    pub target_contract_id: String,
    /// Monotonic policy epoch at evaluation time.
    pub policy_epoch: u64,
    /// SHA-256 digest of the execution harness and runtime context (32 bytes).
    pub harness_digest: [u8; 32],
    /// RFC 8785 canonical action identity digest (32 bytes).
    pub action_caid: [u8; 32],
    /// Hex-encoded Ed25519 signature from the designated authority.
    pub authority_signature_hex: String,
}

/// Evaluation verdict emitted by Station 1 Gate.
#[derive(Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum AdmissibilityVerdict {
    /// Action verified and admitted for pre-dispatch wire latching.
    Admitted {
        operation_id: String,
        commitment_digest: [u8; 32],
        policy_epoch: u64,
    },
    /// Action rejected fail-closed with concrete reason.
    Rejected {
        operation_id: String,
        rejection_code: AdmissibilityRejectionCode,
        detail: String,
    },
}

/// Specific failure codes for fail-closed rejection.
#[derive(Debug, PartialEq, Eq, Clone, Copy, Serialize, Deserialize)]
pub enum AdmissibilityRejectionCode {
    TargetContractMismatch,
    StalePolicyEpoch,
    HarnessDigestMismatch,
    ActionCaidMismatch,
    InvalidAuthoritySignature,
    MalformedSignature,
}

/// Configuration and pinned anchors for Station 1 Gate.
#[derive(Clone)]
pub struct Station1GateConfig {
    pub expected_target_contract_id: String,
    pub min_policy_epoch: u64,
    pub expected_harness_digest: [u8; 32],
    pub authority_verifying_key: VerifyingKey,
}

/// Station 1 Constant-Time Admissibility Gate.
pub struct Station1Gate {
    config: Station1GateConfig,
}

impl Station1Gate {
    pub fn new(config: Station1GateConfig) -> Self {
        Self { config }
    }

    /// Computes the canonical SHA-256 commitment for the 5-tuple.
    pub fn compute_tuple_commitment(
        operation_id: &str,
        target_contract_id: &str,
        policy_epoch: u64,
        harness_digest: &[u8; 32],
        action_caid: &[u8; 32],
    ) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(b"AEIB_STATION1_COMMITMENT_V1:");
        hasher.update(operation_id.as_bytes());
        hasher.update(b":");
        hasher.update(target_contract_id.as_bytes());
        hasher.update(b":");
        hasher.update(&policy_epoch.to_be_bytes());
        hasher.update(b":");
        hasher.update(harness_digest);
        hasher.update(b":");
        hasher.update(action_caid);
        let result = hasher.finalize();
        let mut out = [0u8; 32];
        out.copy_from_slice(&result);
        out
    }

    /// Evaluates pre-dispatch intent with branchless/constant-time comparisons
    /// for cryptographic digests to mitigate timing side-channel leakage.
    pub fn evaluate(
        &self,
        intent: &PreDispatchIntent,
        expected_action_caid: &[u8; 32],
    ) -> AdmissibilityVerdict {
        // 1. Target Contract ID verification (fail-closed if mismatch)
        if intent.target_contract_id != self.config.expected_target_contract_id {
            return AdmissibilityVerdict::Rejected {
                operation_id: intent.operation_id.clone(),
                rejection_code: AdmissibilityRejectionCode::TargetContractMismatch,
                detail: format!(
                    "Contract '{}' does not match expected '{}'",
                    intent.target_contract_id, self.config.expected_target_contract_id
                ),
            };
        }

        // 2. Policy Epoch freshness check
        if intent.policy_epoch < self.config.min_policy_epoch {
            return AdmissibilityVerdict::Rejected {
                operation_id: intent.operation_id.clone(),
                rejection_code: AdmissibilityRejectionCode::StalePolicyEpoch,
                detail: format!(
                    "Policy epoch {} is older than minimum active epoch {}",
                    intent.policy_epoch, self.config.min_policy_epoch
                ),
            };
        }

        // 3. Constant-time harness digest verification
        let harness_matches = intent
            .harness_digest
            .ct_eq(&self.config.expected_harness_digest);
        if bool::from(!harness_matches) {
            return AdmissibilityVerdict::Rejected {
                operation_id: intent.operation_id.clone(),
                rejection_code: AdmissibilityRejectionCode::HarnessDigestMismatch,
                detail: "Harness digest does not match pinned runtime configuration".to_string(),
            };
        }

        // 4. Constant-time action CAID verification
        let caid_matches = intent.action_caid.ct_eq(expected_action_caid);
        if bool::from(!caid_matches) {
            return AdmissibilityVerdict::Rejected {
                operation_id: intent.operation_id.clone(),
                rejection_code: AdmissibilityRejectionCode::ActionCaidMismatch,
                detail: "Action CAID does not match computed RFC 8785 wire payload digest"
                    .to_string(),
            };
        }

        // 5. Authority Ed25519 signature verification
        let sig_bytes = match hex::decode(&intent.authority_signature_hex) {
            Ok(b) if b.len() == 64 => {
                let mut arr = [0u8; 64];
                arr.copy_from_slice(&b);
                arr
            }
            _ => {
                return AdmissibilityVerdict::Rejected {
                    operation_id: intent.operation_id.clone(),
                    rejection_code: AdmissibilityRejectionCode::MalformedSignature,
                    detail: "Signature bytes are invalid or not 64-byte Ed25519 signature"
                        .to_string(),
                };
            }
        };

        let signature = Signature::from_bytes(&sig_bytes);
        let commitment = Self::compute_tuple_commitment(
            &intent.operation_id,
            &intent.target_contract_id,
            intent.policy_epoch,
            &intent.harness_digest,
            &intent.action_caid,
        );

        if self
            .config
            .authority_verifying_key
            .verify_strict(&commitment, &signature)
            .is_err()
        {
            return AdmissibilityVerdict::Rejected {
                operation_id: intent.operation_id.clone(),
                rejection_code: AdmissibilityRejectionCode::InvalidAuthoritySignature,
                detail: "Ed25519 signature verification failed over 5-tuple commitment".to_string(),
            };
        }

        AdmissibilityVerdict::Admitted {
            operation_id: intent.operation_id.clone(),
            commitment_digest: commitment,
            policy_epoch: intent.policy_epoch,
        }
    }
}
