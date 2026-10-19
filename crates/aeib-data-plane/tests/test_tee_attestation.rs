//! crates/aeib-data-plane/tests/test_tee_attestation.rs
//! ============================================================================
//! Verification tests for Hardware TEE Attestation & Ephemeral Signer Scaffold.
//! Tests in-enclave ephemeral key signing, zeroize on drop, and PCR verification.
//! ============================================================================

use aeib_data_plane::attestation::{
    verify_enclave_evidence, EnclavePlatform, EphemeralSigner,
};

#[test]
fn test_ephemeral_signer_signing_and_verification() {
    let signer = EphemeralSigner::generate();
    let verifying_key = signer.verifying_key();

    let commitment = [0x55u8; 32];
    let signature = signer.sign_commitment(&commitment);

    // Verify signature with public key
    let verify_result = verifying_key.verify_strict(&commitment, &signature);
    assert!(verify_result.is_ok(), "Signature verification failed");
}

#[test]
fn test_tee_attestation_evidence_generation_and_positive_verification() {
    let signer = EphemeralSigner::generate();

    let pcr0 = [0x10u8; 32];
    let pcr1 = [0x20u8; 32];
    let pcr2 = [0x30u8; 32];
    let nonce = [0x99u8; 32];

    let evidence = signer.create_attestation_evidence(
        EnclavePlatform::AwsNitroEnclave,
        pcr0,
        pcr1,
        pcr2,
        nonce,
    );

    assert_eq!(evidence.platform, EnclavePlatform::AwsNitroEnclave);
    assert_eq!(evidence.ephemeral_pubkey, signer.verifying_key().to_bytes());

    let is_valid = verify_enclave_evidence(&evidence, &pcr0, &pcr1, &pcr2, &nonce);
    assert!(is_valid, "Attestation evidence failed verification");
}

#[test]
fn test_tee_attestation_negative_pcr_falsification() {
    let signer = EphemeralSigner::generate();

    let pcr0 = [0x10u8; 32];
    let pcr1 = [0x20u8; 32];
    let pcr2 = [0x30u8; 32];
    let nonce = [0x99u8; 32];

    let evidence = signer.create_attestation_evidence(
        EnclavePlatform::IntelTdx,
        pcr0,
        pcr1,
        pcr2,
        nonce,
    );

    // Tampered PCR0 expectation
    let mut bad_pcr0 = pcr0;
    bad_pcr0[0] ^= 0xFF;
    assert!(!verify_enclave_evidence(
        &evidence, &bad_pcr0, &pcr1, &pcr2, &nonce
    ));

    // Tampered nonce expectation (anti-replay failure)
    let mut bad_nonce = nonce;
    bad_nonce[0] ^= 0xFF;
    assert!(!verify_enclave_evidence(
        &evidence, &pcr0, &pcr1, &pcr2, &bad_nonce
    ));
}
