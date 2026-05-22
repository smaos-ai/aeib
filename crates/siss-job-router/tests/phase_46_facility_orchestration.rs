/// Phase 46: Sovereign AI Facility Orchestration
/// 8 TDD tests covering three physical deployment waves:
/// - Wave 1: Sneakernet Ingress Ritual & Chaos Petri Quarantine
/// - Wave 2: Rapid-MLX Fleet Topology
/// - Wave 3: AP2 Facility Mandate Syndication

use siss_job_router::facility_ingress::{FacilityBounds, IngressRejection, IngressRitual, SneakernetManifest};
use siss_job_router::mlx_fleet::{FleetError, FleetRouter, MlxFleet, MlxNode, NodeId};
use siss_gatekeeper::facility_mandate::{ExternalAgency, FacilityMandateEngine, FacilityMandateError};
use siss_gatekeeper::nonce::InMemoryNonceLedger;
use siss_gatekeeper::signer::MockSigner;
use uuid::Uuid;

// ============================================================================
// WAVE 1: SNEAKERNET INGRESS RITUAL & CHAOS PETRI QUARANTINE
// ============================================================================

// ============================================================================
// TEST 1: Ingress approves sovereign IL origin
// ============================================================================

#[test]
fn test_ingress_approves_sovereign_il_origin() {
    let bounds = FacilityBounds {
        allowed_jurisdictions: &["IL", "EU"],
        forbidden_origins: &["CN", "UNVERIFIED"],
        max_artifact_bytes: 10 * 1024 * 1024 * 1024,
        requires_sovereign_attestation: true,
    };

    let manifest = SneakernetManifest {
        artifact_id: Uuid::new_v4(),
        origin_jurisdiction: "IL".to_string(),
        hash_sha256: "a".repeat(64),
        size_bytes: 1024 * 1024,
        has_sovereign_attestation: true,
    };

    let result = IngressRitual::admit(&manifest, &bounds);
    assert!(result.is_ok(), "IL origin with sovereign attestation should be approved");
    assert!(result.unwrap().approved);
}

// ============================================================================
// TEST 2: Ingress rejects forbidden CN origin
// ============================================================================

#[test]
fn test_ingress_rejects_forbidden_cn_origin() {
    let bounds = FacilityBounds {
        allowed_jurisdictions: &["IL", "EU"],
        forbidden_origins: &["CN", "UNVERIFIED"],
        max_artifact_bytes: 10 * 1024 * 1024 * 1024,
        requires_sovereign_attestation: true,
    };

    let manifest = SneakernetManifest {
        artifact_id: Uuid::new_v4(),
        origin_jurisdiction: "CN".to_string(),
        hash_sha256: "a".repeat(64),
        size_bytes: 1024,
        has_sovereign_attestation: true,
    };

    let result = IngressRitual::admit(&manifest, &bounds);
    assert!(matches!(
        result,
        Err(IngressRejection::ForbiddenOrigin { origin }) if origin == "CN"
    ), "CN origin should be rejected");
}

// ============================================================================
// TEST 3: Ingress rejects oversized artifact
// ============================================================================

#[test]
fn test_ingress_rejects_oversized_artifact() {
    let bounds = FacilityBounds {
        allowed_jurisdictions: &["IL"],
        forbidden_origins: &[],
        max_artifact_bytes: 1024 * 1024,
        requires_sovereign_attestation: false,
    };

    let manifest = SneakernetManifest {
        artifact_id: Uuid::new_v4(),
        origin_jurisdiction: "IL".to_string(),
        hash_sha256: "a".repeat(64),
        size_bytes: 10 * 1024 * 1024,
        has_sovereign_attestation: false,
    };

    let result = IngressRitual::admit(&manifest, &bounds);
    assert!(matches!(
        result,
        Err(IngressRejection::OversizedArtifact { .. })
    ), "oversized artifact should be rejected");
}

// ============================================================================
// TEST 4: Ingress rejects missing attestation
// ============================================================================

#[test]
fn test_ingress_rejects_missing_attestation() {
    let bounds = FacilityBounds {
        allowed_jurisdictions: &["IL"],
        forbidden_origins: &[],
        max_artifact_bytes: 10 * 1024 * 1024 * 1024,
        requires_sovereign_attestation: true,
    };

    let manifest = SneakernetManifest {
        artifact_id: Uuid::new_v4(),
        origin_jurisdiction: "IL".to_string(),
        hash_sha256: "a".repeat(64),
        size_bytes: 1024,
        has_sovereign_attestation: false,
    };

    let result = IngressRitual::admit(&manifest, &bounds);
    assert!(matches!(
        result,
        Err(IngressRejection::MissingAttestation)
    ), "missing sovereign attestation should be rejected");
}

// ============================================================================
// WAVE 2: RAPID-MLX FLEET TOPOLOGY
// ============================================================================

// ============================================================================
// TEST 5: Fleet routes to largest memory node
// ============================================================================

#[test]
fn test_fleet_routes_to_largest_memory_node() {
    let node1 = MlxNode {
        id: NodeId("mlx-node-01".to_string()),
        socket_path: "/var/run/node1.sock",
        memory_gb: 16,
        max_concurrent_tasks: 4,
    };

    let node2 = MlxNode {
        id: NodeId("mlx-node-02".to_string()),
        socket_path: "/var/run/node2.sock",
        memory_gb: 64,
        max_concurrent_tasks: 8,
    };

    // Use Box::leak to create static references for the test
    let nodes: &'static [MlxNode] = Box::leak(Box::new([node1, node2]));

    let fleet = MlxFleet {
        nodes,
        locality_zone: "facility-il-zone-a",
    };

    let result = FleetRouter::route(&fleet, 500);
    assert!(result.is_ok(), "fleet with available nodes should route successfully");

    let selected = result.unwrap();
    assert_eq!(
        selected.memory_gb, 64,
        "should route to node with largest memory"
    );
}

// ============================================================================
// TEST 6: Fleet error on empty fleet
// ============================================================================

#[test]
fn test_fleet_error_on_empty_fleet() {
    let fleet = MlxFleet {
        nodes: &[],
        locality_zone: "facility-il-zone-a",
    };

    let result = FleetRouter::route(&fleet, 500);
    assert_eq!(result, Err(FleetError::FleetEmpty), "empty fleet should error");
}

// ============================================================================
// WAVE 3: AP2 FACILITY MANDATE SYNDICATION
// ============================================================================

// ============================================================================
// TEST 7: Facility mandate within agency credit
// ============================================================================

#[test]
fn test_facility_mandate_within_agency_credit() {
    let agency_id = Uuid::new_v4();
    let capability_id = Uuid::new_v4();

    let agency = ExternalAgency {
        agency_id,
        name: "Ministry of Defense IL".to_string(),
        jurisdiction: "IL".to_string(),
        credit_limit: 1000,
        allowed_capability_ids: vec![capability_id],
    };

    let engine: FacilityMandateEngine<MockSigner, InMemoryNonceLedger> = FacilityMandateEngine {
        signer: MockSigner,
        nonce_ledger: InMemoryNonceLedger::new(),
    };

    let result = engine.issue(&agency, capability_id, 500, "test_nonce_wave3_1");
    assert!(result.is_ok(), "mandate within credit should be issued");

    let mandate = result.unwrap();
    assert_eq!(mandate.budget_limit, 500, "budget should be 500");
    assert!(!mandate.signature.is_empty(), "signature should be present");
    assert_eq!(mandate.agency_id, agency_id, "agency_id should match");
    assert_eq!(mandate.capability_id, capability_id, "capability_id should match");
}

// ============================================================================
// TEST 8: Facility mandate exceeds agency credit
// ============================================================================

#[test]
fn test_facility_mandate_exceeds_agency_credit() {
    let agency_id = Uuid::new_v4();
    let capability_id = Uuid::new_v4();

    let agency = ExternalAgency {
        agency_id,
        name: "Hospital".to_string(),
        jurisdiction: "DE".to_string(),
        credit_limit: 1000,
        allowed_capability_ids: vec![capability_id],
    };

    let engine: FacilityMandateEngine<MockSigner, InMemoryNonceLedger> = FacilityMandateEngine {
        signer: MockSigner,
        nonce_ledger: InMemoryNonceLedger::new(),
    };

    let result = engine.issue(&agency, capability_id, 1500, "test_nonce_wave3_2");
    assert!(matches!(
        result,
        Err(FacilityMandateError::BudgetExceedsAgencyCredit {
            requested: 1500,
            available: 1000
        })
    ), "mandate exceeding credit should be rejected");
}
