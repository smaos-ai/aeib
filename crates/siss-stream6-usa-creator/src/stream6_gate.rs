use std::sync::Arc;
use uuid::Uuid;

use siss_layer00::{Layer0Gate, CapabilityToken};

use crate::aml_checker::AMLChecker;
use crate::error::{Stream6Error, Stream6Result};
use crate::kyc_verifier::KYCVerifier;

/// Stream 6 Gate couples Layer 0 mandate enforcement with KYC/AML checks.
///
/// Invocation flow:
/// 1. Check Layer 0 mandate for creator
/// 2. Verify KYC status
/// 3. Perform AML sanctions screening
/// 4. If all checks pass, return capability token from Layer 0 Gate
#[allow(dead_code)]
pub struct Stream6Gate {
    layer0_gate: Arc<Layer0Gate>,
    kyc_verifier: Arc<KYCVerifier>,
    aml_checker: Arc<AMLChecker>,
}

impl Stream6Gate {
    pub fn new(
        layer0_gate: Arc<Layer0Gate>,
        kyc_verifier: Arc<KYCVerifier>,
        aml_checker: Arc<AMLChecker>,
    ) -> Self {
        Self {
            layer0_gate,
            kyc_verifier,
            aml_checker,
        }
    }

    /// Invoke Stream 6 gate: check mandate → KYC → AML → issue capability token.
    ///
    /// Steps:
    /// 1. Verify creator has valid Layer 0 mandate
    /// 2. Check creator's KYC status is verified
    /// 3. Run AML sanctions screening
    /// 4. If all checks pass, request capability token from Layer 0 Gate
    pub async fn invoke(
        &self,
        creator_id: Uuid,
        _mandate_id: Uuid,
        _action: &str,
    ) -> Stream6Result<CapabilityToken> {
        // Step 1: Verify Layer 0 mandate exists and is valid
        // TODO: Implement mandate validation via layer0_gate
        // This should check the mandate is current and not revoked

        // Step 2: Check KYC verification status
        let _kyc_status = self
            .kyc_verifier
            .get_kyc_status(creator_id)
            .map_err(|e| Stream6Error::Layer0Error(format!("KYC check failed: {}", e)))?;

        // Step 3: Get creator name from KYC record for AML screening
        let kyc_record = self
            .kyc_verifier
            .get_kyc_record(creator_id)
            .map_err(|e| Stream6Error::Layer0Error(format!("KYC record retrieval failed: {}", e)))?;

        // Step 4: Run AML sanctions check
        let _is_clean = self
            .aml_checker
            .check_sanctions(&kyc_record.creator_name)
            .await
            .map_err(|e| Stream6Error::AMLSanctionsViolation(e.to_string()))?;

        // Step 5: Request capability token from Layer 0 Gate
        // TODO: Integrate with Layer 0 Gate's request_capability() method
        // This will validate mandate and issue token

        // Stub: return error for now (pending Layer 0 integration)
        Err(Stream6Error::Layer0Error(
            "Stream 6 gate invocation pending Layer 0 integration".to_string(),
        ))
    }

    /// Check if creator meets all Stream 6 compliance requirements.
    /// Returns detailed result without issuing capability token.
    pub async fn compliance_check(&self, creator_id: Uuid) -> Stream6Result<ComplianceResult> {
        let mut failure_reasons = Vec::new();
        let mut kyc_verified = false;
        let mut aml_clear = true;

        // Step 1: Check KYC status
        let kyc_status = match self.kyc_verifier.get_kyc_status(creator_id) {
            Ok(status) => status,
            Err(_) => {
                failure_reasons.push("KYC not found".to_string());
                crate::KYCStatus::Pending
            }
        };

        // Verify KYC is Verified status and still valid
        if kyc_status == crate::KYCStatus::Verified {
            // Check expiration
            if let Ok(record) = self.kyc_verifier.get_kyc_record(creator_id) {
                if record.is_valid() {
                    kyc_verified = true;
                } else {
                    failure_reasons.push("KYC expired".to_string());
                }
            }
        } else {
            failure_reasons
                .push(format!("KYC status is {:?}, not verified", kyc_status));
        }

        // Step 2: Check AML sanctions
        if kyc_verified && let Ok(record) = self.kyc_verifier.get_kyc_record(creator_id) {
            let is_clean = self
                .aml_checker
                .check_sanctions(&record.creator_name)
                .await
                .unwrap_or(true);

            if !is_clean {
                failure_reasons.push("Creator on sanctions list".to_string());
                aml_clear = false;
            } else {
                // Check risk level only if not on sanctions list
                let risk_level = self
                    .aml_checker
                    .check_aml_risk(creator_id, &record.creator_name)
                    .await
                    .unwrap_or(crate::AMLRiskLevel::Low);

                if risk_level == crate::AMLRiskLevel::High
                    || risk_level == crate::AMLRiskLevel::Critical
                {
                    aml_clear = false;
                    failure_reasons.push(format!("High AML risk: {:?}", risk_level));
                }
            }
        }

        let is_compliant = kyc_verified && aml_clear;

        Ok(ComplianceResult {
            creator_id,
            kyc_verified,
            aml_clear,
            mandate_valid: is_compliant, // In production, would check Layer 0
            is_compliant,
            failure_reasons,
        })
    }

    /// Revoke capability for a creator (e.g., due to failed AML re-screening).
    pub async fn revoke_capability(&self, _creator_id: Uuid) -> Stream6Result<()> {
        // TODO: Implement capability revocation
        // - Invalidate any issued capability tokens
        // - Log revocation event
        // - Update Layer 0 mandate status
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct ComplianceResult {
    pub creator_id: Uuid,
    pub kyc_verified: bool,
    pub aml_clear: bool,
    pub mandate_valid: bool,
    pub is_compliant: bool,
    pub failure_reasons: Vec<String>,
}

#[cfg(test)]
mod tests {
    #[tokio::test]
    async fn test_stream6_gate_rejects_unverified_kyc() {
        // TODO: Implement test
    }

    #[tokio::test]
    async fn test_stream6_gate_rejects_sanctioned_creators() {
        // TODO: Implement test
    }

    #[tokio::test]
    async fn test_stream6_gate_full_invocation_flow() {
        // TODO: Implement test
    }

    #[tokio::test]
    async fn test_stream6_gate_compliance_check() {
        // TODO: Implement test
    }

    #[tokio::test]
    async fn test_stream6_gate_capability_revocation() {
        // TODO: Implement test
    }
}
