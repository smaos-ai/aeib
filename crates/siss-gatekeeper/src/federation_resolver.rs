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
pub fn resolve_federated_tier(attestation_tier: u32, bilateral_max_admitted_tier: u16) -> u32 {
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
                .and_then(|payload| {
                    payload
                        .get("sovereign_id")
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string())
                })
        })
}

/// Build canonical agreement payload for deterministic Ed25519 signing.
///
/// Uses BTreeMap to ensure alphabetical key ordering, guaranteeing consistent
/// byte sequences across all verifiers. Same pattern as canonical attestation payloads.
pub fn build_canonical_agreement_payload(
    sovereign_a_id: &str,
    sovereign_b_id: &str,
    max_admitted_tier: u16,
    granted_attestation_types: &[String],
    foreign_agent_budget_cap: i64,
    effective_at: &str, // RFC3339 timestamp
) -> String {
    use std::collections::BTreeMap;

    let mut map = BTreeMap::new();
    map.insert(
        "effective_at",
        serde_json::Value::String(effective_at.to_string()),
    );
    map.insert(
        "foreign_agent_budget_cap",
        serde_json::Value::Number(foreign_agent_budget_cap.into()),
    );
    map.insert(
        "granted_attestation_types",
        serde_json::to_value(granted_attestation_types).unwrap_or(serde_json::Value::Array(vec![])),
    );
    map.insert(
        "max_admitted_tier",
        serde_json::Value::Number(max_admitted_tier.into()),
    );
    map.insert(
        "sovereign_a_id",
        serde_json::Value::String(sovereign_a_id.to_string()),
    );
    map.insert(
        "sovereign_b_id",
        serde_json::Value::String(sovereign_b_id.to_string()),
    );

    serde_json::to_string(&map).unwrap_or_default()
}

/// Build canonical invoice payload for deterministic Ed25519 signing.
///
/// Uses BTreeMap for alphabetical key ordering, enabling forensic verification
/// of settlement invoices across bilateral peers.
pub fn build_canonical_invoice_payload(
    invoice_id: &str,
    creditor_sovereign_id: &str,
    debtor_sovereign_id: &str,
    period_start: &str, // RFC3339 timestamp
    period_end: &str,   // RFC3339 timestamp
    total_tokens: i64,
    entry_count: i32,
) -> String {
    use std::collections::BTreeMap;

    let mut map = BTreeMap::new();
    map.insert(
        "creditor_sovereign_id",
        serde_json::Value::String(creditor_sovereign_id.to_string()),
    );
    map.insert(
        "debtor_sovereign_id",
        serde_json::Value::String(debtor_sovereign_id.to_string()),
    );
    map.insert("entry_count", serde_json::Value::Number(entry_count.into()));
    map.insert(
        "invoice_id",
        serde_json::Value::String(invoice_id.to_string()),
    );
    map.insert(
        "period_end",
        serde_json::Value::String(period_end.to_string()),
    );
    map.insert(
        "period_start",
        serde_json::Value::String(period_start.to_string()),
    );
    map.insert(
        "total_tokens",
        serde_json::Value::Number(total_tokens.into()),
    );

    serde_json::to_string(&map).unwrap_or_default()
}

/// Phase 11: Resolve transitive federated tier with delegation grant ceiling.
///
/// Computes: min(attestation_tier, bilateral_max_admitted_tier, grant_ceiling_tier)
///
/// When a foreign agent holds a cross-sovereign delegation grant, the grant's
/// ceiling_tier further caps their effective tier.
pub fn resolve_transitive_federated_tier(
    attestation_tier: u32,
    bilateral_max_admitted_tier: u16,
    grant_ceiling_tier: Option<u32>,
) -> u32 {
    let with_bilateral = std::cmp::min(attestation_tier, bilateral_max_admitted_tier as u32);
    match grant_ceiling_tier {
        Some(ceiling) => std::cmp::min(with_bilateral, ceiling),
        None => with_bilateral,
    }
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

    #[test]
    fn test_build_canonical_agreement_payload_alphabetical_keys() {
        let payload = build_canonical_agreement_payload(
            "sovereign-a",
            "sovereign-b",
            10,
            &[
                "attestation_type_1".to_string(),
                "attestation_type_2".to_string(),
            ],
            500000,
            "2026-05-10T10:00:00Z",
        );

        // Parse and verify keys are alphabetically ordered
        let json: serde_json::Value = serde_json::from_str(&payload).unwrap();
        let obj = json.as_object().unwrap();
        let keys: Vec<&String> = obj.keys().collect();

        // Verify alphabetical order
        assert_eq!(keys[0], "effective_at");
        assert_eq!(keys[1], "foreign_agent_budget_cap");
        assert_eq!(keys[2], "granted_attestation_types");
        assert_eq!(keys[3], "max_admitted_tier");
        assert_eq!(keys[4], "sovereign_a_id");
        assert_eq!(keys[5], "sovereign_b_id");
    }

    #[test]
    fn test_build_canonical_agreement_payload_deterministic() {
        let payload1 = build_canonical_agreement_payload(
            "sovereign-a",
            "sovereign-b",
            10,
            &["type1".to_string(), "type2".to_string()],
            500000,
            "2026-05-10T10:00:00Z",
        );

        let payload2 = build_canonical_agreement_payload(
            "sovereign-a",
            "sovereign-b",
            10,
            &["type1".to_string(), "type2".to_string()],
            500000,
            "2026-05-10T10:00:00Z",
        );

        assert_eq!(
            payload1, payload2,
            "Same inputs must produce identical canonical payloads"
        );
    }

    #[test]
    fn test_build_canonical_invoice_payload_alphabetical_keys() {
        let payload = build_canonical_invoice_payload(
            "invoice-uuid",
            "creditor-uuid",
            "debtor-uuid",
            "2026-05-01T00:00:00Z",
            "2026-05-31T23:59:59Z",
            1000000,
            42,
        );

        let json: serde_json::Value = serde_json::from_str(&payload).unwrap();
        let obj = json.as_object().unwrap();
        let keys: Vec<&String> = obj.keys().collect();

        // Verify alphabetical order
        assert_eq!(keys[0], "creditor_sovereign_id");
        assert_eq!(keys[1], "debtor_sovereign_id");
        assert_eq!(keys[2], "entry_count");
        assert_eq!(keys[3], "invoice_id");
        assert_eq!(keys[4], "period_end");
        assert_eq!(keys[5], "period_start");
        assert_eq!(keys[6], "total_tokens");
    }

    #[test]
    fn test_build_canonical_invoice_payload_deterministic() {
        let payload1 = build_canonical_invoice_payload(
            "inv-1",
            "cred-1",
            "deb-1",
            "2026-05-01T00:00:00Z",
            "2026-05-31T23:59:59Z",
            1000000,
            42,
        );

        let payload2 = build_canonical_invoice_payload(
            "inv-1",
            "cred-1",
            "deb-1",
            "2026-05-01T00:00:00Z",
            "2026-05-31T23:59:59Z",
            1000000,
            42,
        );

        assert_eq!(
            payload1, payload2,
            "Same invoice inputs must produce identical canonical payloads"
        );
    }

    #[test]
    fn test_resolve_transitive_tier_no_grant() {
        // Without grant, falls back to bilateral cap
        let result = resolve_transitive_federated_tier(100, 50, None);
        assert_eq!(result, 50, "should cap to bilateral max");
    }

    #[test]
    fn test_resolve_transitive_tier_grant_more_restrictive() {
        // Grant ceiling is tighter than bilateral max → grant wins
        let result = resolve_transitive_federated_tier(100, 50, Some(30));
        assert_eq!(result, 30, "grant ceiling should be the minimum");
    }

    #[test]
    fn test_resolve_transitive_tier_grant_less_restrictive() {
        // Grant ceiling is looser than bilateral max → bilateral wins
        let result = resolve_transitive_federated_tier(100, 30, Some(50));
        assert_eq!(result, 30, "bilateral max should be the minimum");
    }

    #[test]
    fn test_resolve_transitive_tier_all_three_caps() {
        // All three tiers apply: min(100, 80, 60) = 60
        let result = resolve_transitive_federated_tier(100, 80, Some(60));
        assert_eq!(result, 60, "minimum of all three should apply");
    }
}
