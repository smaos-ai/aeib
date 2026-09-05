/// Wave 3: AP2 Facility Mandate Syndication
/// External agencies submit cryptographically-bound workloads to the facility.
use crate::nonce::NonceLedger;
use crate::signer::Signer;
use thiserror::Error;
use uuid::Uuid;

/// An external agency (Ministry, Hospital, etc.) with credit limits and allowed capabilities.
#[derive(Debug, Clone)]
pub struct ExternalAgency {
    pub agency_id: Uuid,
    pub name: String,
    pub jurisdiction: String,
    pub credit_limit: i64,
    pub allowed_capability_ids: Vec<Uuid>,
}

/// A facility-level mandate binding an agency's workload to spending and tool constraints.
#[derive(Debug, Clone)]
pub struct FacilityMandate {
    pub id: Uuid,
    pub agency_id: Uuid,
    pub capability_id: Uuid,
    pub budget_limit: i64,
    pub nonce: String,
    pub signature: Vec<u8>,
}

#[derive(Debug, Error, PartialEq, Eq)]
pub enum FacilityMandateError {
    #[error("budget {requested} exceeds agency credit {available}")]
    BudgetExceedsAgencyCredit { requested: i64, available: i64 },
    #[error("capability {0} not authorized")]
    CapabilityNotAuthorized(Uuid),
    #[error("nonce replayed")]
    NonceReplayed,
    #[error("signature invalid")]
    SignatureInvalid,
}

pub struct FacilityMandateEngine<S: Signer, N: NonceLedger> {
    pub signer: S,
    pub nonce_ledger: N,
}

impl<S: Signer, N: NonceLedger> FacilityMandateEngine<S, N> {
    /// Issue a facility mandate after validating budget and capability constraints (fail-closed).
    pub fn issue(
        &self,
        agency: &ExternalAgency,
        capability_id: Uuid,
        budget: i64,
        nonce: &str,
    ) -> Result<FacilityMandate, FacilityMandateError> {
        // RULE 1: Budget must not exceed agency credit (fail-closed)
        if budget > agency.credit_limit {
            return Err(FacilityMandateError::BudgetExceedsAgencyCredit {
                requested: budget,
                available: agency.credit_limit,
            });
        }

        // RULE 2: Capability must be authorized
        if !agency.allowed_capability_ids.contains(&capability_id) {
            return Err(FacilityMandateError::CapabilityNotAuthorized(capability_id));
        }

        // RULE 3: Nonce must not be replayed
        self.nonce_ledger
            .burn(nonce, agency.agency_id)
            .map_err(|_| FacilityMandateError::NonceReplayed)?;

        // RULE 4: Sign the payload
        let mandate_id = Uuid::new_v4();
        let payload = Self::build_payload(
            &mandate_id,
            &agency.agency_id,
            &capability_id,
            budget,
            nonce,
        );
        let signature = self
            .signer
            .sign(&payload)
            .map_err(|_| FacilityMandateError::SignatureInvalid)?;

        Ok(FacilityMandate {
            id: mandate_id,
            agency_id: agency.agency_id,
            capability_id,
            budget_limit: budget,
            nonce: nonce.to_string(),
            signature,
        })
    }

    /// Verify a facility mandate (check budget, capability, nonce, signature).
    pub fn verify(
        &self,
        mandate: &FacilityMandate,
        agency: &ExternalAgency,
    ) -> Result<(), FacilityMandateError> {
        // RULE 1: Budget must not exceed agency credit
        if mandate.budget_limit > agency.credit_limit {
            return Err(FacilityMandateError::BudgetExceedsAgencyCredit {
                requested: mandate.budget_limit,
                available: agency.credit_limit,
            });
        }

        // RULE 2: Capability must be authorized
        if !agency
            .allowed_capability_ids
            .contains(&mandate.capability_id)
        {
            return Err(FacilityMandateError::CapabilityNotAuthorized(
                mandate.capability_id,
            ));
        }

        // RULE 3: Nonce must not have been burned already (replay check)
        if self.nonce_ledger.is_burned(&mandate.nonce) {
            return Err(FacilityMandateError::NonceReplayed);
        }

        // RULE 4: Signature must be valid
        let payload = Self::build_payload(
            &mandate.id,
            &mandate.agency_id,
            &mandate.capability_id,
            mandate.budget_limit,
            &mandate.nonce,
        );
        let is_valid = self
            .signer
            .verify(&payload, &mandate.signature)
            .map_err(|_| FacilityMandateError::SignatureInvalid)?;

        if !is_valid {
            return Err(FacilityMandateError::SignatureInvalid);
        }

        Ok(())
    }

    /// Build a deterministic payload for signing.
    fn build_payload(
        mandate_id: &Uuid,
        agency_id: &Uuid,
        capability_id: &Uuid,
        budget: i64,
        nonce: &str,
    ) -> Vec<u8> {
        let mut payload = Vec::new();
        payload.extend_from_slice(mandate_id.as_bytes());
        payload.extend_from_slice(agency_id.as_bytes());
        payload.extend_from_slice(capability_id.as_bytes());
        payload.extend_from_slice(&budget.to_le_bytes());
        payload.extend_from_slice(nonce.as_bytes());
        payload
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::nonce::InMemoryNonceLedger;
    use crate::signer::MockSigner;

    #[test]
    fn test_issue_within_credit() {
        let agency = ExternalAgency {
            agency_id: Uuid::new_v4(),
            name: "Ministry of Defense".to_string(),
            jurisdiction: "IL".to_string(),
            credit_limit: 1000,
            allowed_capability_ids: vec![Uuid::new_v4()],
        };

        let capability_id = agency.allowed_capability_ids[0];
        let engine: FacilityMandateEngine<MockSigner, InMemoryNonceLedger> =
            FacilityMandateEngine {
                signer: MockSigner,
                nonce_ledger: InMemoryNonceLedger::new(),
            };

        let result = engine.issue(&agency, capability_id, 500, "test_nonce_1");
        assert!(result.is_ok());
        let mandate = result.unwrap();
        assert_eq!(mandate.budget_limit, 500);
        assert!(!mandate.signature.is_empty());
    }

    #[test]
    fn test_issue_exceeds_credit() {
        let agency = ExternalAgency {
            agency_id: Uuid::new_v4(),
            name: "Hospital".to_string(),
            jurisdiction: "DE".to_string(),
            credit_limit: 1000,
            allowed_capability_ids: vec![Uuid::new_v4()],
        };

        let capability_id = agency.allowed_capability_ids[0];
        let engine: FacilityMandateEngine<MockSigner, InMemoryNonceLedger> =
            FacilityMandateEngine {
                signer: MockSigner,
                nonce_ledger: InMemoryNonceLedger::new(),
            };

        let result = engine.issue(&agency, capability_id, 1500, "test_nonce_2");
        assert!(matches!(
            result,
            Err(FacilityMandateError::BudgetExceedsAgencyCredit { .. })
        ));
    }

    #[test]
    fn test_issue_unauthorized_capability() {
        let agency = ExternalAgency {
            agency_id: Uuid::new_v4(),
            name: "Hospital".to_string(),
            jurisdiction: "DE".to_string(),
            credit_limit: 1000,
            allowed_capability_ids: vec![Uuid::new_v4()],
        };

        let unauthorized_capability = Uuid::new_v4();
        let engine: FacilityMandateEngine<MockSigner, InMemoryNonceLedger> =
            FacilityMandateEngine {
                signer: MockSigner,
                nonce_ledger: InMemoryNonceLedger::new(),
            };

        let result = engine.issue(&agency, unauthorized_capability, 500, "test_nonce_3");
        assert!(matches!(
            result,
            Err(FacilityMandateError::CapabilityNotAuthorized(_))
        ));
    }

    #[test]
    fn test_nonce_replay_protection() {
        let agency = ExternalAgency {
            agency_id: Uuid::new_v4(),
            name: "Agency".to_string(),
            jurisdiction: "IL".to_string(),
            credit_limit: 1000,
            allowed_capability_ids: vec![Uuid::new_v4()],
        };

        let capability_id = agency.allowed_capability_ids[0];
        let engine: FacilityMandateEngine<MockSigner, InMemoryNonceLedger> =
            FacilityMandateEngine {
                signer: MockSigner,
                nonce_ledger: InMemoryNonceLedger::new(),
            };

        let nonce = "replay_test_nonce";

        // First issue should succeed
        let result1 = engine.issue(&agency, capability_id, 500, nonce);
        assert!(result1.is_ok());

        // Second issue with same nonce should fail
        let result2 = engine.issue(&agency, capability_id, 500, nonce);
        assert!(matches!(result2, Err(FacilityMandateError::NonceReplayed)));
    }
}
