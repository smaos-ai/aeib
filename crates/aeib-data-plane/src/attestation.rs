//! crates/aeib-data-plane/src/attestation.rs
//! ============================================================================
//! AEIB Hardware TEE Attestation & Ephemeral Signer Scaffold.
//!
//! Architectural Scaffolding Awareness (AGENTS.md §5):
//! - Code in this module provides structural scaffolding for Confidential VM
//!   deployments (AWS Nitro Enclaves, Intel TDX, AMD SEV-SNP).
//! - When executed in standard userspace or development environments, it operates
//!   under a stated prototype model and does NOT provide live hardware isolation.
//! - Enclave-static secrets are vulnerable to DDR5 bus interposition (TEE.Fail);
//!   therefore, AEIB uses ephemeral key derivation zeroized post-session.
//! ============================================================================

use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;
use zeroize::Zeroize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EnclavePlatform {
    AwsNitroEnclave,
    IntelTdx,
    AmdSevSnp,
    UserspaceScaffold,
}

/// Structural attestation evidence bundle binding enclave measurements to an ephemeral key.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnclaveAttestationEvidence {
    pub platform: EnclavePlatform,
    /// Platform Configuration Register 0 (e.g., enclave image file hash).
    pub pcr0: [u8; 32],
    /// Platform Configuration Register 1 (e.g., kernel and bootstrap hash).
    pub pcr1: [u8; 32],
    /// Platform Configuration Register 2 (e.g., application binary hash).
    pub pcr2: [u8; 32],
    /// Fresh nonce supplied by verifier to prevent replay.
    pub nonce: [u8; 32],
    /// Ephemeral public key generated inside the enclave.
    pub ephemeral_pubkey: [u8; 32],
    /// Attestation document digest.
    pub evidence_digest: [u8; 32],
}

/// An ephemeral in-enclave signer whose secret key material is zeroized on drop.
pub struct EphemeralSigner {
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
    raw_secret: [u8; 32],
}

impl EphemeralSigner {
    /// Generates a fresh ephemeral keypair inside the execution enclave.
    pub fn generate() -> Self {
        let mut csprng = OsRng;
        let signing_key = SigningKey::generate(&mut csprng);
        let verifying_key = signing_key.verifying_key();
        let raw_secret = signing_key.to_bytes();

        Self {
            signing_key,
            verifying_key,
            raw_secret,
        }
    }

    /// Returns the Ed25519 verifying key.
    pub fn verifying_key(&self) -> VerifyingKey {
        self.verifying_key
    }

    /// Signs an execution commitment using the in-enclave ephemeral key.
    pub fn sign_commitment(&self, commitment: &[u8; 32]) -> Signature {
        self.signing_key.sign(commitment)
    }

    /// Produces a structural attestation evidence bundle binding the ephemeral key to PCRs.
    pub fn create_attestation_evidence(
        &self,
        platform: EnclavePlatform,
        pcr0: [u8; 32],
        pcr1: [u8; 32],
        pcr2: [u8; 32],
        nonce: [u8; 32],
    ) -> EnclaveAttestationEvidence {
        let mut hasher = Sha256::new();
        hasher.update(b"AEIB_TEE_ATTESTATION_V1:");
        hasher.update(&pcr0);
        hasher.update(&pcr1);
        hasher.update(&pcr2);
        hasher.update(&nonce);
        hasher.update(self.verifying_key.as_bytes());
        let digest_bytes = hasher.finalize();

        let mut evidence_digest = [0u8; 32];
        evidence_digest.copy_from_slice(&digest_bytes);

        EnclaveAttestationEvidence {
            platform,
            pcr0,
            pcr1,
            pcr2,
            nonce,
            ephemeral_pubkey: self.verifying_key.to_bytes(),
            evidence_digest,
        }
    }
}

impl Drop for EphemeralSigner {
    fn drop(&mut self) {
        // Zeroize raw secret material immediately upon dropping the signer
        self.raw_secret.zeroize();
    }
}

/// Evaluates attestation evidence against expected pinned enclave PCRs in constant time.
pub fn verify_enclave_evidence(
    evidence: &EnclaveAttestationEvidence,
    expected_pcr0: &[u8; 32],
    expected_pcr1: &[u8; 32],
    expected_pcr2: &[u8; 32],
    expected_nonce: &[u8; 32],
) -> bool {
    let pcr0_match = evidence.pcr0.ct_eq(expected_pcr0);
    let pcr1_match = evidence.pcr1.ct_eq(expected_pcr1);
    let pcr2_match = evidence.pcr2.ct_eq(expected_pcr2);
    let nonce_match = evidence.nonce.ct_eq(expected_nonce);

    let mut hasher = Sha256::new();
    hasher.update(b"AEIB_TEE_ATTESTATION_V1:");
    hasher.update(&evidence.pcr0);
    hasher.update(&evidence.pcr1);
    hasher.update(&evidence.pcr2);
    hasher.update(&evidence.nonce);
    hasher.update(&evidence.ephemeral_pubkey);
    let computed_digest = hasher.finalize();

    let digest_match = evidence.evidence_digest.ct_eq(&computed_digest);

    bool::from(pcr0_match & pcr1_match & pcr2_match & nonce_match & digest_match)
}
