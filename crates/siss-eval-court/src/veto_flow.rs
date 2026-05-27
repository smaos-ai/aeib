use serde::{Deserialize, Serialize};
use uuid::Uuid;
use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VetoDecision {
    pub decision_id: Uuid,
    pub capsule_a_approved: bool,
    pub capsule_b_approved: bool,
    pub reason: String,
}

#[derive(Debug, Clone)]
pub struct SignedVetoDecision {
    pub decision: VetoDecision,
    pub signature: String,
    pub signed_at: u64,
}

pub struct EvalCourt;

impl EvalCourt {
    pub fn new() -> Self {
        EvalCourt
    }

    pub fn sign_decision(
        &self,
        decision: &VetoDecision,
        operator_key: &str,
    ) -> Result<String, String> {
        let decision_json =
            serde_json::to_string(decision).map_err(|e| format!("Serialization error: {}", e))?;

        let mut mac = HmacSha256::new_from_slice(operator_key.as_bytes())
            .map_err(|_| "Invalid key length".to_string())?;
        mac.update(decision_json.as_bytes());

        let signature = hex::encode(mac.finalize().into_bytes());
        Ok(signature)
    }

    pub fn verify_signature(
        &self,
        decision: &VetoDecision,
        signature: &str,
        operator_key: &str,
    ) -> Result<bool, String> {
        let decision_json =
            serde_json::to_string(decision).map_err(|e| format!("Serialization error: {}", e))?;

        let mut mac = HmacSha256::new_from_slice(operator_key.as_bytes())
            .map_err(|_| "Invalid key length".to_string())?;
        mac.update(decision_json.as_bytes());

        let expected_signature = hex::encode(mac.finalize().into_bytes());
        Ok(signature == expected_signature)
    }

    pub fn create_signed_decision(
        &self,
        capsule_a_approved: bool,
        capsule_b_approved: bool,
        reason: String,
        operator_key: &str,
    ) -> Result<SignedVetoDecision, String> {
        let decision = VetoDecision {
            decision_id: Uuid::new_v4(),
            capsule_a_approved,
            capsule_b_approved,
            reason,
        };

        let signature = self.sign_decision(&decision, operator_key)?;
        let signed_at = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|e| format!("Time error: {}", e))?
            .as_secs();

        Ok(SignedVetoDecision {
            decision,
            signature,
            signed_at,
        })
    }
}

impl Default for EvalCourt {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_veto_decision_requires_cryptographic_signature() {
        let court = EvalCourt::new();

        let decision = VetoDecision {
            decision_id: Uuid::new_v4(),
            capsule_a_approved: true,
            capsule_b_approved: false,
            reason: "B modifies too many callers".to_string(),
        };

        let operator_key = "operator-secret-key";
        let signature = court.sign_decision(&decision, operator_key).unwrap();

        assert!(!signature.is_empty());
        assert!(court
            .verify_signature(&decision, &signature, operator_key)
            .unwrap());
    }

    #[test]
    fn test_signature_verification_fails_with_wrong_key() {
        let court = EvalCourt::new();

        let decision = VetoDecision {
            decision_id: Uuid::new_v4(),
            capsule_a_approved: true,
            capsule_b_approved: false,
            reason: "test".to_string(),
        };

        let key_a = "secret-key-a";
        let key_b = "secret-key-b";

        let signature = court.sign_decision(&decision, key_a).unwrap();
        let is_valid = court.verify_signature(&decision, &signature, key_b).unwrap();

        assert!(!is_valid, "Signature should fail with different key");
    }

    #[test]
    fn test_signature_fails_if_decision_tampered() {
        let court = EvalCourt::new();

        let mut decision = VetoDecision {
            decision_id: Uuid::new_v4(),
            capsule_a_approved: true,
            capsule_b_approved: false,
            reason: "original reason".to_string(),
        };

        let operator_key = "operator-secret-key";
        let signature = court.sign_decision(&decision, operator_key).unwrap();

        // Tamper with decision
        decision.reason = "tampered reason".to_string();
        let is_valid = court.verify_signature(&decision, &signature, operator_key).unwrap();

        assert!(!is_valid, "Signature should fail if decision tampered");
    }

    #[test]
    fn test_approve_capsule_a_reject_b() {
        let court = EvalCourt::new();
        let operator_key = "operator-key";

        let signed = court
            .create_signed_decision(true, false, "A is safe, B is unsafe".to_string(), operator_key)
            .unwrap();

        assert!(signed.decision.capsule_a_approved);
        assert!(!signed.decision.capsule_b_approved);
        assert!(!signed.signature.is_empty());
        assert!(signed.signed_at > 0);
    }

    #[test]
    fn test_reject_both_capsules_fail_closed() {
        let court = EvalCourt::new();
        let operator_key = "operator-key";

        let signed = court
            .create_signed_decision(
                false,
                false,
                "Both capsules unsafe - fail-closed".to_string(),
                operator_key,
            )
            .unwrap();

        assert!(!signed.decision.capsule_a_approved);
        assert!(!signed.decision.capsule_b_approved);
    }

    #[test]
    fn test_multiple_decisions_have_unique_ids() {
        let court = EvalCourt::new();
        let operator_key = "operator-key";

        let signed1 = court
            .create_signed_decision(true, false, "reason1".to_string(), operator_key)
            .unwrap();

        let signed2 = court
            .create_signed_decision(false, true, "reason2".to_string(), operator_key)
            .unwrap();

        assert_ne!(
            signed1.decision.decision_id, signed2.decision.decision_id,
            "Each decision should have unique ID"
        );
    }
}
