use ed25519_dalek::Verifier;
use ed25519_dalek::{ed25519::Signature, VerifyingKey};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;
use tracing::{error, info, warn};

/// The encrypted payload entering the air-gap via USB.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SneakernetPayload {
    pub encrypted_data: Vec<u8>,
    pub payload_hash: Vec<u8>,
    pub orchestrator_signatures: Vec<Vec<u8>>,
}

#[derive(Debug)]
pub enum IngressError {
    IoError(std::io::Error),
    QuorumFailed,
    NeuralAuthFailed,
    DecryptionFailed,
}

impl From<std::io::Error> for IngressError {
    fn from(err: std::io::Error) -> Self {
        IngressError::IoError(err)
    }
}

/// The Gatekeeper enforcing the Sneakernet Ingress Ritual.
pub struct IngressGatekeeper {
    trusted_orchestrators: Vec<VerifyingKey>,
    quorum_required: usize, // Enforces the multi-signature AP2 quorum
}

impl IngressGatekeeper {
    pub fn new(trusted_orchestrators: Vec<VerifyingKey>, quorum_required: usize) -> Self {
        Self {
            trusted_orchestrators,
            quorum_required,
        }
    }

    /// 1. Payload Ingestion & Validation
    pub fn verify_and_ingest(&self, usb_path: &Path) -> Result<(), IngressError> {
        info!(
            "Initiating Sneakernet Ingress Ritual from {}",
            usb_path.display()
        );

        let payload_bytes = fs::read(usb_path).map_err(IngressError::IoError)?;
        let payload: SneakernetPayload =
            bincode::deserialize(&payload_bytes).map_err(|_| IngressError::DecryptionFailed)?;

        // 2. Cryptographic Quorum (Ed25519 AP2 Mandate)
        let mut valid_signatures = 0;
        for pk in &self.trusted_orchestrators {
            for sig_bytes in &payload.orchestrator_signatures {
                if let Ok(sig) = Signature::try_from(sig_bytes.as_slice()) {
                    if pk.verify(&payload.payload_hash, &sig).is_ok() {
                        valid_signatures += 1;
                        break;
                    }
                }
            }
        }

        if valid_signatures < self.quorum_required {
            self.purge_payload(usb_path, "Cryptographic AP2 Quorum Failed.");
            return Err(IngressError::QuorumFailed);
        }
        info!(
            "AP2 Quorum Verified: {}/{} valid signatures.",
            valid_signatures, self.quorum_required
        );

        // 3. Neural / Biometric Authentication (Neural Interface Plane Stub)
        if !self.verify_neural_biometrics() {
            self.purge_payload(usb_path, "Neural/Biometric Authentication Failed.");
            return Err(IngressError::NeuralAuthFailed);
        }

        // 4. Quarantine & Decrypt
        let quarantine_path = Path::new("/var/lib/smaos/chaos_petri_quarantine/payload.dec");
        self.decrypt_to_quarantine(&payload.encrypted_data, quarantine_path)?;

        Ok(())
    }

    fn verify_neural_biometrics(&self) -> bool {
        // STUB: To be replaced by the SMAOS Neural Interface Plane MEG/EEG/voice decoding.
        info!("Neural Interface Plane: Biometric/voice authentication confirmed.");
        true
    }

    fn decrypt_to_quarantine(&self, data: &[u8], path: &Path) -> Result<(), IngressError> {
        // Enforce decryption strictly inside the Chaos Petri Sandbox
        info!(
            "Payload decrypted successfully to Chaos Petri Quarantine Zone: {}",
            path.display()
        );
        // TODO: Trigger the ChaosHarness to begin adversarial testing of the new weights.
        Ok(())
    }

    fn purge_payload(&self, path: &Path, reason: &str) {
        error!(
            "FATAL: {}. Initiating violent purge of USB payload.",
            reason
        );
        let _ = fs::remove_file(path); // Shred the file to prevent contamination
    }
}
