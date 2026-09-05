/// Phase 50: UCP/AP2 Cryptographic Checkout — Service Negotiation & Contract Signing
/// Reuses siss_gatekeeper::signer::{Signer, MockSigner} for Ed25519 signatures.
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use siss_gatekeeper::signer::Signer;
use siss_gatekeeper::tokens::IntentMandate;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UcpContract {
    pub contract_id: Uuid,
    pub buyer_agent_id: Uuid,
    pub seller_agent_id: Uuid,
    pub skill_id: String,
    pub agreed_price: i64,
    pub terms: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct SignedUcpContract {
    pub contract: UcpContract,
    pub buyer_signature: Vec<u8>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum UcpError {
    MandateExhausted,
    ContractPriceExceedsBudget { price: i64, budget: i64 },
    SigningFailed(String),
}

pub struct UcpCheckout<S: Signer> {
    pub signer: S,
    pub mandate: IntentMandate,
}

impl<S: Signer> UcpCheckout<S> {
    /// RULE 1: mandate not exhausted → Err(MandateExhausted)
    /// RULE 2: contract.agreed_price ≤ mandate.budget_remaining() → Err(ContractPriceExceedsBudget) if exceeds
    /// RULE 3: sign canonical_bytes(contract) → Err(SigningFailed) if sign fails
    /// RULE 4: Ok(SignedUcpContract) with buyer_signature (Ed25519 over deterministic canonical bytes)
    pub fn checkout(&mut self, contract: UcpContract) -> Result<SignedUcpContract, UcpError> {
        // RULE 1: Check mandate exhaustion
        if self.mandate.is_budget_exhausted() {
            return Err(UcpError::MandateExhausted);
        }

        // RULE 2: Check budget headroom
        let budget_remaining = self.mandate.budget_remaining();
        if contract.agreed_price > budget_remaining {
            return Err(UcpError::ContractPriceExceedsBudget {
                price: contract.agreed_price,
                budget: budget_remaining,
            });
        }

        // RULE 3: Sign canonical bytes
        let canonical = Self::canonical_bytes(&contract);
        let buyer_signature = self
            .signer
            .sign(&canonical)
            .map_err(|e| UcpError::SigningFailed(e.message))?;

        // RULE 4: Return signed contract
        Ok(SignedUcpContract {
            contract,
            buyer_signature,
        })
    }

    /// Canonical bytes: deterministic JSON of contract fields sorted by key.
    /// Used for non-repudiatable signing.
    fn canonical_bytes(contract: &UcpContract) -> Vec<u8> {
        let mut map = serde_json::Map::new();
        map.insert(
            "contract_id".to_string(),
            serde_json::to_value(&contract.contract_id).unwrap(),
        );
        map.insert(
            "buyer_agent_id".to_string(),
            serde_json::to_value(&contract.buyer_agent_id).unwrap(),
        );
        map.insert(
            "seller_agent_id".to_string(),
            serde_json::to_value(&contract.seller_agent_id).unwrap(),
        );
        map.insert(
            "skill_id".to_string(),
            serde_json::to_value(&contract.skill_id).unwrap(),
        );
        map.insert(
            "agreed_price".to_string(),
            serde_json::to_value(&contract.agreed_price).unwrap(),
        );
        map.insert(
            "terms".to_string(),
            serde_json::to_value(&contract.terms).unwrap(),
        );
        map.insert(
            "created_at".to_string(),
            serde_json::to_value(&contract.created_at).unwrap(),
        );

        let obj = serde_json::Value::Object(map);
        obj.to_string().into_bytes()
    }
}
