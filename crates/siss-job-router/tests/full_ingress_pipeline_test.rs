/// C-3: Full Sneakernet Ingress Pipeline Tests
/// Integration tests covering IngressRitual → SneakernetGateway → AP2 mandate validation

use siss_job_router::facility_ingress::{
    FullIngressPipeline, FacilityBounds, IngressRitual, SneakernetManifest, QuarantineVerdict,
    IngressRejection,
};
use siss_gatekeeper::sneakernet_ingress::{SneakernetGateway, DualAuthTransfer};
use uuid::Uuid;

#[test]
fn test_full_pipeline_passes_valid_transfer() {
    // Set up facility bounds
    let bounds = FacilityBounds {
        allowed_jurisdictions: &["IL", "EU"],
        forbidden_origins: &[],
        max_artifact_bytes: 10 * 1024 * 1024 * 1024,
        requires_sovereign_attestation: false,
    };

    // Create a valid manifest
    let manifest = SneakernetManifest {
        artifact_id: Uuid::new_v4(),
        origin_jurisdiction: "IL".to_string(),
        hash_sha256: "a".repeat(64),
        size_bytes: 1024,
        has_sovereign_attestation: false,
    };

    // Create gateway and transfer
    let mut gateway = SneakernetGateway::new();
    let transfer_id = gateway.create_transfer("manifest".to_string());

    // Add a chunk so the transfer has content
    if let Some(transfer) = gateway.get_transfer_mut(transfer_id) {
        transfer.add_chunk(0, vec![1u8; 100], DualAuthTransfer::compute_checksum(&vec![1u8; 100]));
    }

    // Run full pipeline
    let result = FullIngressPipeline::run(&manifest, &bounds, transfer_id, &mut gateway);

    assert!(result.is_ok());
    let verdict = result.unwrap();
    assert!(verdict.approved);
}

#[test]
fn test_full_pipeline_rejects_forbidden_origin_before_gateway() {
    // Set up facility bounds that forbid China
    let bounds = FacilityBounds {
        allowed_jurisdictions: &["IL"],
        forbidden_origins: &["CN"],
        max_artifact_bytes: 10 * 1024 * 1024 * 1024,
        requires_sovereign_attestation: false,
    };

    // Create a manifest from forbidden origin
    let manifest = SneakernetManifest {
        artifact_id: Uuid::new_v4(),
        origin_jurisdiction: "CN".to_string(),
        hash_sha256: "a".repeat(64),
        size_bytes: 1024,
        has_sovereign_attestation: false,
    };

    let mut gateway = SneakernetGateway::new();
    let transfer_id = gateway.create_transfer("manifest".to_string());

    // Pipeline should reject before reaching gateway
    let result = FullIngressPipeline::run(&manifest, &bounds, transfer_id, &mut gateway);

    assert!(matches!(result, Err(IngressRejection::ForbiddenOrigin { .. })));
}

#[test]
fn test_full_pipeline_rejects_gateway_unsigned_transfer() {
    // Set up facility bounds
    let bounds = FacilityBounds {
        allowed_jurisdictions: &["IL"],
        forbidden_origins: &[],
        max_artifact_bytes: 10 * 1024 * 1024 * 1024,
        requires_sovereign_attestation: false,
    };

    // Create a valid manifest
    let manifest = SneakernetManifest {
        artifact_id: Uuid::new_v4(),
        origin_jurisdiction: "IL".to_string(),
        hash_sha256: "a".repeat(64),
        size_bytes: 1024,
        has_sovereign_attestation: false,
    };

    let mut gateway = SneakernetGateway::new();
    let transfer_id = gateway.create_transfer("manifest".to_string());

    // Add chunk to transfer but don't sign it
    if let Some(transfer) = gateway.get_transfer_mut(transfer_id) {
        transfer.add_chunk(0, vec![1u8; 100], DualAuthTransfer::compute_checksum(&vec![1u8; 100]));
    }

    // Pipeline should pass IngressRitual but fail on gateway.authorize_transfer
    // because transfer is not signed
    let result = FullIngressPipeline::run(&manifest, &bounds, transfer_id, &mut gateway);

    // Should fail at gateway stage (missing signatures)
    assert!(matches!(result, Err(IngressRejection::MissingAttestation)));
}

#[test]
fn test_ingress_ritual_standalone() {
    let bounds = FacilityBounds {
        allowed_jurisdictions: &["IL", "EU"],
        forbidden_origins: &["CN"],
        max_artifact_bytes: 10 * 1024 * 1024 * 1024,
        requires_sovereign_attestation: true,
    };

    let manifest = SneakernetManifest {
        artifact_id: Uuid::new_v4(),
        origin_jurisdiction: "IL".to_string(),
        hash_sha256: "a".repeat(64),
        size_bytes: 1024,
        has_sovereign_attestation: true,
    };

    let result = IngressRitual::admit(&manifest, &bounds);
    assert!(result.is_ok());
    assert!(result.unwrap().approved);
}
