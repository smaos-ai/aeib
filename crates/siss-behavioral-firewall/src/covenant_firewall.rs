use ed25519_dalek::{VerifyingKey, Signature, Verifier};
use sha2::{Sha256, Digest};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EconomicIntent {
    pub steward_pct: u8,      // Genesis Covenant: must be 1
    pub beneficiary_pct: u8,  // Genesis Covenant: must be 99
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CovenantViolation {
    IntentMismatch,    // Split is not 1/99 or does not sum to 100
    SignatureInvalid,  // Ed25519 signature does not verify over payload
    MalformedKey,      // Verifying key bytes are invalid length/format
}

impl std::fmt::Display for CovenantViolation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::IntentMismatch   => write!(f, "covenant intent mismatch: required 1%/99% split"),
            Self::SignatureInvalid => write!(f, "covenant signature invalid: Merkle root tampered"),
            Self::MalformedKey     => write!(f, "covenant verifying key malformed"),
        }
    }
}

pub struct CovenantFirewall;

impl CovenantFirewall {
    /// Canonical payload: SHA-256(merkle_root_bytes || steward_pct_byte || beneficiary_pct_byte)
    pub fn signing_payload(merkle_root: &[u8; 32], intent: &EconomicIntent) -> Vec<u8> {
        let mut h = Sha256::new();
        h.update(merkle_root);
        h.update([intent.steward_pct]);
        h.update([intent.beneficiary_pct]);
        h.finalize().to_vec()
    }

    /// Fail-closed gate. Returns Ok(()) only when ALL conditions hold:
    ///   1. steward_pct == 1, beneficiary_pct == 99, sum == 100
    ///   2. verifying_key_bytes decodes to valid Ed25519 VerifyingKey
    ///   3. signature verifies over signing_payload(merkle_root, intent)
    pub fn verify(
        merkle_root: &[u8; 32],
        intent: &EconomicIntent,
        signature_bytes: &[u8],
        verifying_key_bytes: &[u8],
    ) -> Result<(), CovenantViolation> {
        // Gate 1: Economic intent (Genesis Covenant invariant)
        if intent.steward_pct != 1
            || intent.beneficiary_pct != 99
            || intent.steward_pct.saturating_add(intent.beneficiary_pct) != 100
        {
            return Err(CovenantViolation::IntentMismatch);
        }
        // Gate 2: Decode verifying key
        let key_arr: [u8; 32] = verifying_key_bytes
            .try_into()
            .map_err(|_| CovenantViolation::MalformedKey)?;
        let vk = VerifyingKey::from_bytes(&key_arr)
            .map_err(|_| CovenantViolation::MalformedKey)?;
        // Gate 3: Verify Ed25519 signature
        let sig_arr: [u8; 64] = signature_bytes
            .try_into()
            .map_err(|_| CovenantViolation::SignatureInvalid)?;
        let sig = Signature::from_bytes(&sig_arr);
        let payload = Self::signing_payload(merkle_root, intent);
        vk.verify(&payload, &sig)
            .map_err(|_| CovenantViolation::SignatureInvalid)
    }
}
