use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use siss_gatekeeper::signer::Signer;
use uuid::Uuid;

use crate::did_registry::DidRegistry;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TrustAttestation {
    pub fact_id: Uuid,
    pub signer_did: String,
    pub signature: Vec<u8>,
    pub claimed_confidence: f64,
    pub attested_at: DateTime<Utc>,
}

impl TrustAttestation {
    pub fn sign(
        fact_id: Uuid,
        content: &str,
        claimed_confidence: f64,
        signer: &dyn Signer,
        did: String,
        now: DateTime<Utc>,
    ) -> Result<Self, String> {
        let payload = content.as_bytes();
        let signature = signer.sign(payload).map_err(|e| e.to_string())?;

        Ok(TrustAttestation {
            fact_id,
            signer_did: did,
            signature,
            claimed_confidence,
            attested_at: now,
        })
    }

    pub fn verify(&self, content: &str, registry: &DidRegistry) -> bool {
        let payload = content.as_bytes();
        registry.verify_signature(&self.signer_did, payload, &self.signature)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_attestation_structure() {
        let fact_id = Uuid::new_v4();
        let now = Utc::now();
        let did = "did:smaos:test:agent".to_string();

        let attestation = TrustAttestation {
            fact_id,
            signer_did: did.clone(),
            signature: vec![1, 2, 3],
            claimed_confidence: 0.85,
            attested_at: now,
        };

        assert_eq!(attestation.fact_id, fact_id);
        assert_eq!(attestation.signer_did, did);
        assert_eq!(attestation.claimed_confidence, 0.85);
    }
}
