/// Federated Trust Resolution (Phase 9)
/// Pure functions for cross-sovereign tier capping and attestation analysis.
/// No database access; these are deterministic validators.

use super::attestation::Attestation;
use uuid::Uuid;

/// Context for a federated (cross-sovereign) operation
#[derive(Debug, Clone)]
pub struct FederatedContext {
    pub source_sovereign_id: Uuid,
    pub admitted_tier: u32,
    pub is_cross_sovereign: bool,
}

/// Compute the effective tier for a federated agent:
/// min(attestation_tier, bilateral_max_admitted_tier)
///
/// This is the tier capping rule: foreign agents are capped by the bilateral
/// agreement, regardless of their local tier.
pub fn resolve_federated_tier(
    attestation_tier: u32,
    bilateral_max_admitted_tier: u16,
) -> u32 {
    std::cmp::min(attestation_tier, bilateral_max_admitted_tier as u32)
}

/// Check if a SovereignOrigin attestation is present and extract sovereign_id.
/// Returns Some(sovereign_id_string) if found and has valid payload, None otherwise.
pub fn is_sovereign_origin_present(attestations: &[Attestation]) -> Option<String> {
    attestations
        .iter()
        .find(|att| att.attestation_type == super::attestation::AttestationType::SovereignOrigin)
        .and_then(|att| {
            serde_json::from_str::<serde_json::Value>(&att.payload)
                .ok()
                .and_then(|payload| payload.get("sovereign_id").and_then(|v| v.as_str()).map(|s| s.to_string()))
        })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::attestation::AttestationType;

    #[test]
    fn test_resolve_federated_tier_capped() {
        // Attestation tier (20) higher than bilateral cap (15) → capped to 15
        let result = resolve_federated_tier(20, 15);
        assert_eq!(result, 15);
    }

    #[test]
    fn test_resolve_federated_tier_not_capped() {
        // Attestation tier (10) lower than bilateral cap (15) → stays 10
        let result = resolve_federated_tier(10, 15);
        assert_eq!(result, 10);
    }

    #[test]
    fn test_resolve_federated_tier_equal_cap() {
        // Attestation tier (15) equals bilateral cap (15) → stays 15
        let result = resolve_federated_tier(15, 15);
        assert_eq!(result, 15);
    }

    #[test]
    fn test_is_sovereign_origin_present_found() {
        let attestations = vec![
            Attestation {
                attestation_type: AttestationType::HardwareEnclave,
                format: "sgx_quote".to_string(),
                payload: "irrelevant".to_string(),
                signature: "sig".to_string(),
                issuer: "intel".to_string(),
                issued_at: chrono::Utc::now(),
                valid_until: chrono::Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: AttestationType::SovereignOrigin,
                format: "jurisdiction_cert".to_string(),
                payload: r#"{"sovereign_id":"eu-sovereign-001","other_field":"value"}"#.to_string(),
                signature: "sig".to_string(),
                issuer: "eu-authority".to_string(),
                issued_at: chrono::Utc::now(),
                valid_until: chrono::Utc::now() + chrono::Duration::days(365),
            },
        ];

        let result = is_sovereign_origin_present(&attestations);
        assert_eq!(result, Some("eu-sovereign-001".to_string()));
    }

    #[test]
    fn test_is_sovereign_origin_present_not_found() {
        let attestations = vec![
            Attestation {
                attestation_type: AttestationType::HardwareEnclave,
                format: "sgx_quote".to_string(),
                payload: "irrelevant".to_string(),
                signature: "sig".to_string(),
                issuer: "intel".to_string(),
                issued_at: chrono::Utc::now(),
                valid_until: chrono::Utc::now() + chrono::Duration::hours(1),
            },
            Attestation {
                attestation_type: AttestationType::ModelIntegrity,
                format: "manifest".to_string(),
                payload: "manifest".to_string(),
                signature: "sig".to_string(),
                issuer: "anthropic".to_string(),
                issued_at: chrono::Utc::now(),
                valid_until: chrono::Utc::now() + chrono::Duration::days(30),
            },
        ];

        let result = is_sovereign_origin_present(&attestations);
        assert_eq!(result, None);
    }
}
