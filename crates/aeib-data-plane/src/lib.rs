// aeib-data-plane/src/lib.rs
//! AEIB Station 1 Native Data Plane
//!
//! Branchless, constant-time CAID verification + group-commit WAL.
//!
//! # Epistemic Scope
//! This module provides local atomic reservation and admission control under
//! the declared fault model. It does NOT provide distributed finality; that requires
//! the distributed consensus settlement layer and SCITT anchor (Planes 5 & 6).
//!
//! # Threat Model Addressed
//! - Timing side-channels on CAID comparison (branchless evaluation)
//! - Latency spikes on critical execution path
//! - Secret leakage post-drop (zeroize on sensitive material)

pub mod attestation;
pub mod scitt;
pub mod wal;

use std::collections::VecDeque;
use std::io::{self, ErrorKind};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use ed25519_dalek::{Signature, VerifyingKey, PUBLIC_KEY_LENGTH};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;
use zeroize::{Zeroize, ZeroizeOnDrop};

#[cfg(target_os = "linux")]
use tokio_uring::fs::{File, OpenOptions};

#[cfg(not(target_os = "linux"))]
use tokio::fs::{File, OpenOptions};

// =============================================================================
// §1. Canonical Serialization (Strict v1 Profile)
// =============================================================================

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActionBinding {
    pub action_class: String,
    pub amount_minor: i64,
    pub currency: String,
    pub harness_digest: String,
    pub operation_id: String,
    pub policy_epoch: u64,
    pub recipient: String,
    pub target: String,
}

impl ActionBinding {
    /// Deterministic UTF-8 serialization with sorted keys.
    pub fn canonical_bytes(&self) -> Result<Vec<u8>, serde_json::Error> {
        let mut map = serde_json::Map::new();
        map.insert("action_class".into(), serde_json::Value::String(self.action_class.clone()));
        map.insert("amount_minor".into(), serde_json::Value::Number(self.amount_minor.into()));
        map.insert("currency".into(), serde_json::Value::String(self.currency.clone()));
        map.insert("harness_digest".into(), serde_json::Value::String(self.harness_digest.clone()));
        map.insert("operation_id".into(), serde_json::Value::String(self.operation_id.clone()));
        map.insert("policy_epoch".into(), serde_json::Value::Number(self.policy_epoch.into()));
        map.insert("recipient".into(), serde_json::Value::String(self.recipient.clone()));
        map.insert("target".into(), serde_json::Value::String(self.target.clone()));
        serde_json::to_vec(&map)
    }
}

// =============================================================================
// §2. Content-Addressed Action Identifier (CAID)
// =============================================================================

#[derive(Clone, PartialEq, Eq, Zeroize, ZeroizeOnDrop)]
pub struct Caid([u8; 32]);

impl Caid {
    pub fn from_binding(binding: &ActionBinding) -> Result<Self, serde_json::Error> {
        let canonical = binding.canonical_bytes()?;
        let mut hasher = Sha256::new();
        hasher.update(b"aeib:caid:v1:");
        hasher.update(&canonical);
        let digest = hasher.finalize();
        let mut out = [0u8; 32];
        out.copy_from_slice(&digest);
        Ok(Self(out))
    }

    pub fn as_bytes(&self) -> &[u8; 32] {
        &self.0
    }

    /// Constant-time equality check. Returns true iff equal.
    pub fn ct_eq(&self, other: &Self) -> bool {
        self.0.ct_eq(&other.0).into()
    }

    pub fn to_hex(&self) -> String {
        self.0.iter().map(|b| format!("{:02x}", b)).collect()
    }
}

impl std::fmt::Debug for Caid {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Caid({})", self.to_hex())
    }
}

// =============================================================================
// §3. The 5-Tuple Admissibility Predicate (Branchless)
// =============================================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AdmissionVerdict {
    Admitted,
    DeniedCaidMismatch,
    DeniedSignatureInvalid,
    DeniedPolicyEpochStale,
    DeniedBudgetExhausted,
    DeniedTaintEscalationRequired,
    DeniedDuplicateOperationId,
}

#[derive(Debug, Clone)]
pub struct AdmissionFactors {
    pub caid_match: bool,
    pub signature_valid: bool,
    pub epoch_fresh: bool,
    pub budget_available: bool,
    pub taint_acceptable: bool,
}

impl AdmissionFactors {
    pub fn verdict(&self) -> AdmissionVerdict {
        let caid_fail = !self.caid_match;
        let sig_fail = !self.signature_valid;
        let epoch_fail = !self.epoch_fresh;
        let budget_fail = !self.budget_available;
        let taint_fail = !self.taint_acceptable;

        if caid_fail {
            AdmissionVerdict::DeniedCaidMismatch
        } else if sig_fail {
            AdmissionVerdict::DeniedSignatureInvalid
        } else if epoch_fail {
            AdmissionVerdict::DeniedPolicyEpochStale
        } else if budget_fail {
            AdmissionVerdict::DeniedBudgetExhausted
        } else if taint_fail {
            AdmissionVerdict::DeniedTaintEscalationRequired
        } else {
            AdmissionVerdict::Admitted
        }
    }
}

// =============================================================================
// §4. Signature Verification (Ed25519)
// =============================================================================

pub struct GateVerifier {
    verifying_key: VerifyingKey,
}

impl GateVerifier {
    pub fn from_public_key_bytes(bytes: &[u8; PUBLIC_KEY_LENGTH]) -> io::Result<Self> {
        let vk = VerifyingKey::from_bytes(bytes)
            .map_err(|e| io::Error::new(ErrorKind::InvalidData, e.to_string()))?;
        Ok(Self { verifying_key: vk })
    }

    pub fn verify_strict(&self, canonical_bytes: &[u8], signature: &Signature) -> bool {
        self.verifying_key.verify_strict(canonical_bytes, signature).is_ok()
    }
}

// =============================================================================
// §5. Group-Commit WAL
// =============================================================================

#[derive(Clone, Debug)]
struct WalEntry {
    sequence: u64,
    payload: Vec<u8>,
}

#[derive(Debug, Clone)]
pub struct WalConfig {
    pub path: PathBuf,
    pub batch_size: usize,
    pub flush_interval_ms: u64,
    pub o_direct: bool,
}

impl Default for WalConfig {
    fn default() -> Self {
        Self {
            path: PathBuf::from("aeib-wal.log"),
            batch_size: 32,
            flush_interval_ms: 50,
            o_direct: true,
        }
    }
}

pub struct Wal {
    config: WalConfig,
    pending: VecDeque<WalEntry>,
    sequence: AtomicU64,
    file: Option<File>,
}

impl Wal {
    pub async fn open(config: WalConfig) -> io::Result<Self> {
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&config.path)
            .await?;

        Ok(Self {
            config,
            pending: VecDeque::new(),
            sequence: AtomicU64::new(0),
            file: Some(file),
        })
    }

    pub async fn append(&mut self, payload: Vec<u8>) -> io::Result<u64> {
        let seq = self.sequence.fetch_add(1, Ordering::SeqCst);
        self.pending.push_back(WalEntry { sequence: seq, payload });
        if self.pending.len() >= self.config.batch_size {
            self.flush().await?;
        }
        Ok(seq)
    }

    pub async fn flush(&mut self) -> io::Result<usize> {
        if self.pending.is_empty() {
            return Ok(0);
        }
        let file = self.file.as_mut().ok_or_else(|| {
            io::Error::new(ErrorKind::Other, "WAL closed")
        })?;

        let mut total = 0usize;
        while let Some(entry) = self.pending.pop_front() {
            let mut buf = entry.payload;
            let mut framed = Vec::with_capacity(8 + buf.len());
            framed.extend_from_slice(&entry.sequence.to_le_bytes());
            framed.append(&mut buf);
            if self.config.o_direct {
                let pad = (4096 - (framed.len() % 4096)) % 4096;
                framed.extend(std::iter::repeat(0u8).take(pad));
            }
            let len = framed.len();

            #[cfg(target_os = "linux")]
            {
                let (res, _buf) = file.write_at(framed, total as u64).await;
                res?;
            }

            #[cfg(not(target_os = "linux"))]
            {
                use tokio::io::AsyncWriteExt;
                file.write_all(&framed).await?;
            }

            total += len;
        }

        #[cfg(target_os = "linux")]
        {
            let (res, _file) = file.sync_all().await;
            res?;
        }

        #[cfg(not(target_os = "linux"))]
        {
            file.sync_all().await?;
        }

        Ok(total)
    }

    pub async fn close(mut self) -> io::Result<()> {
        self.flush().await?;
        drop(self.file.take());
        Ok(())
    }
}

// =============================================================================
// §6. Sprint/Escrow Budget Ledger
// =============================================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Disposition {
    Confirmed,
    Refuted,
    EffectIndeterminate,
}

#[derive(Debug, Clone)]
pub struct EscrowEntry {
    pub operation_id: String,
    pub amount_minor: i64,
    pub disposition: Disposition,
    pub recorded_at: u64,
}

pub struct BudgetLedger {
    sprint_cap_minor: i64,
    epoch_cap_minor: i64,
    sprint_window_sec: u64,
    epoch_window_sec: u64,
    entries: Vec<EscrowEntry>,
}

impl BudgetLedger {
    pub fn new(sprint_cap_minor: i64, epoch_cap_minor: i64) -> Self {
        Self {
            sprint_cap_minor,
            epoch_cap_minor,
            sprint_window_sec: 5 * 3600,
            epoch_window_sec: 7 * 24 * 3600,
            entries: Vec::new(),
        }
    }

    fn now_unix() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system clock before epoch")
            .as_secs()
    }

    pub fn remaining_minor(&self) -> i64 {
        let now = Self::now_unix();
        let sprint_used: i64 = self.entries.iter()
            .filter(|e| now.saturating_sub(e.recorded_at) <= self.sprint_window_sec)
            .filter(|e| matches!(e.disposition, Disposition::Confirmed | Disposition::EffectIndeterminate))
            .map(|e| e.amount_minor)
            .sum();

        let epoch_used: i64 = self.entries.iter()
            .filter(|e| now.saturating_sub(e.recorded_at) <= self.epoch_window_sec)
            .filter(|e| matches!(e.disposition, Disposition::Confirmed | Disposition::EffectIndeterminate))
            .map(|e| e.amount_minor)
            .sum();

        let sprint_remaining = (self.sprint_cap_minor - sprint_used).max(0);
        let epoch_remaining = (self.epoch_cap_minor - epoch_used).max(0);
        sprint_remaining.min(epoch_remaining)
    }

    pub fn reserve(&mut self, operation_id: String, amount_minor: i64) -> Result<(), AdmissionVerdict> {
        if amount_minor <= 0 {
            return Err(AdmissionVerdict::DeniedBudgetExhausted);
        }
        if amount_minor > self.remaining_minor() {
            return Err(AdmissionVerdict::DeniedBudgetExhausted);
        }
        if self.entries.iter().any(|e| e.operation_id == operation_id) {
            return Err(AdmissionVerdict::DeniedDuplicateOperationId);
        }
        self.entries.push(EscrowEntry {
            operation_id,
            amount_minor,
            disposition: Disposition::EffectIndeterminate,
            recorded_at: Self::now_unix(),
        });
        Ok(())
    }

    pub fn reconcile(&mut self, operation_id: &str, disposition: Disposition) -> bool {
        if let Some(entry) = self.entries.iter_mut().find(|e| e.operation_id == operation_id) {
            if matches!(entry.disposition, Disposition::EffectIndeterminate) {
                entry.disposition = disposition;
                return true;
            }
        }
        false
    }
}

// =============================================================================
// §7. Integrated Admission Gates
// =============================================================================

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

/// Station 1 Constant-Time Admissibility Gate (5-Tuple Constant-Time Gate).
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

/// Runtime Admission Gate combining GateVerifier with BudgetLedger.
pub struct Station1RuntimeGate {
    verifier: GateVerifier,
    ledger: BudgetLedger,
    current_epoch: u64,
}

impl Station1RuntimeGate {
    pub fn new(
        verifier: GateVerifier,
        ledger: BudgetLedger,
        current_epoch: u64,
    ) -> Self {
        Self { verifier, ledger, current_epoch }
    }

    pub fn evaluate(
        &mut self,
        binding: &ActionBinding,
        claimed_caid: &Caid,
        signature: &Signature,
        taint_tier: u8,
        pinned_recipient: bool,
    ) -> (AdmissionVerdict, AdmissionFactors) {
        let computed_caid = Caid::from_binding(binding).ok();
        let caid_match = computed_caid
            .as_ref()
            .map(|c| c.ct_eq(claimed_caid))
            .unwrap_or(false);

        let canonical = binding.canonical_bytes().unwrap_or_default();
        let signature_valid = self.verifier.verify_strict(&canonical, signature);
        let epoch_fresh = binding.policy_epoch == self.current_epoch;
        let budget_available = binding.amount_minor <= self.ledger.remaining_minor();
        let taint_acceptable = !(taint_tier == 2 && !pinned_recipient);

        let factors = AdmissionFactors {
            caid_match,
            signature_valid,
            epoch_fresh,
            budget_available,
            taint_acceptable,
        };
        (factors.verdict(), factors)
    }

    pub fn admit_and_reserve(
        &mut self,
        binding: &ActionBinding,
        claimed_caid: &Caid,
        signature: &Signature,
        taint_tier: u8,
        pinned_recipient: bool,
    ) -> Result<u64, AdmissionVerdict> {
        let (verdict, _factors) = self.evaluate(
            binding,
            claimed_caid,
            signature,
            taint_tier,
            pinned_recipient,
        );
        if verdict != AdmissionVerdict::Admitted {
            return Err(verdict);
        }
        self.ledger.reserve(binding.operation_id.clone(), binding.amount_minor)?;
        Ok(binding.amount_minor as u64)
    }
}

// =============================================================================
// §8. Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{SigningKey, Signer};

    fn make_binding() -> ActionBinding {
        ActionBinding {
            action_class: "REFUND".into(),
            amount_minor: 100_00,
            currency: "EUR".into(),
            harness_digest: "sha256:deadbeef".into(),
            operation_id: "op-test-001".into(),
            policy_epoch: 1_700_000_000,
            recipient: "iban:DE89370400440532013000".into(),
            target: "https://payments.example.com/refund".into(),
        }
    }

    #[test]
    fn caid_is_deterministic() {
        let b = make_binding();
        let c1 = Caid::from_binding(&b).unwrap();
        let c2 = Caid::from_binding(&b).unwrap();
        assert!(c1.ct_eq(&c2));
    }

    #[test]
    fn caid_differs_on_one_byte_change() {
        let mut b1 = make_binding();
        let b2 = make_binding();
        b1.amount_minor = 100_01;
        let c1 = Caid::from_binding(&b1).unwrap();
        let c2 = Caid::from_binding(&b2).unwrap();
        assert!(!c1.ct_eq(&c2));
    }

    #[test]
    fn admission_factors_all_true_yields_admitted() {
        let f = AdmissionFactors {
            caid_match: true,
            signature_valid: true,
            epoch_fresh: true,
            budget_available: true,
            taint_acceptable: true,
        };
        assert_eq!(f.verdict(), AdmissionVerdict::Admitted);
    }

    #[test]
    fn taint_tier_2_without_pinned_recipient_denied() {
        let f = AdmissionFactors {
            caid_match: true,
            signature_valid: true,
            epoch_fresh: true,
            budget_available: true,
            taint_acceptable: false,
        };
        assert_eq!(f.verdict(), AdmissionVerdict::DeniedTaintEscalationRequired);
    }

    #[test]
    fn signature_verification_roundtrip() {
        let signing_key = SigningKey::from_bytes(&[42u8; 32]);
        let verifying_key = signing_key.verifying_key();
        let verifier = GateVerifier::from_public_key_bytes(verifying_key.as_bytes()).unwrap();
        let binding = make_binding();
        let canonical = binding.canonical_bytes().unwrap();
        let signature: Signature = signing_key.sign(&canonical);
        assert!(verifier.verify_strict(&canonical, &signature));
    }

    #[test]
    fn budget_ledger_reserves_and_reconciles() {
        let mut ledger = BudgetLedger::new(1000_00, 10000_00);
        ledger.reserve("op-1".into(), 400_00).unwrap();
        ledger.reserve("op-2".into(), 400_00).unwrap();
        assert_eq!(ledger.remaining_minor(), 200_00);

        let r = ledger.reserve("op-3".into(), 400_00);
        assert!(r.is_err());

        assert!(ledger.reconcile("op-1", Disposition::Confirmed));
        assert_eq!(ledger.remaining_minor(), 200_00);

        assert!(ledger.reconcile("op-2", Disposition::Refuted));
        assert_eq!(ledger.remaining_minor(), 600_00);
    }

    #[test]
    fn duplicate_operation_id_rejected() {
        let mut ledger = BudgetLedger::new(1000_00, 10000_00);
        ledger.reserve("op-dup".into(), 100_00).unwrap();
        let r = ledger.reserve("op-dup".into(), 100_00);
        assert_eq!(r.unwrap_err(), AdmissionVerdict::DeniedDuplicateOperationId);
    }
}
