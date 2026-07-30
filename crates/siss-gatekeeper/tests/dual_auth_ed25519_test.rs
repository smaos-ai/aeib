use ed25519_dalek::{Signer, SigningKey};
use rand::SeedableRng;
/// C-2: Real Ed25519 Dual-Custodian Verification Tests
use siss_gatekeeper::sneakernet_ingress::{DualAuthTransfer, SneakernetError};

#[test]
fn test_dual_auth_real_ed25519_both_sign_and_verify() {
    // Create two signing keys for custodians A and B
    let mut rng_a = rand::rngs::StdRng::seed_from_u64(1);
    let mut rng_b = rand::rngs::StdRng::seed_from_u64(2);
    let signing_key_a = SigningKey::generate(&mut rng_a);
    let signing_key_b = SigningKey::generate(&mut rng_b);

    let pk_a = *signing_key_a.verifying_key().as_bytes();
    let pk_b = *signing_key_b.verifying_key().as_bytes();

    // Create manifest hash
    let manifest_hash = "test_manifest_hash_v1".to_string();

    // Create transfer with both custodians
    let mut transfer = DualAuthTransfer::with_custodians(manifest_hash.clone(), pk_a, pk_b);

    // Sign the manifest with both keys
    let sig_a = signing_key_a.sign(manifest_hash.as_bytes());
    let sig_a_hex = hex::encode(sig_a.to_bytes());

    let sig_b = signing_key_b.sign(manifest_hash.as_bytes());
    let sig_b_hex = hex::encode(sig_b.to_bytes());

    // Apply signatures
    assert!(transfer.sign_by_custodian_a(sig_a_hex).is_ok());
    assert!(transfer.sign_by_custodian_b(sig_b_hex).is_ok());
    assert!(transfer.both_signed);

    // Verify both signatures
    let result = transfer.verify_signatures();
    assert!(result.is_ok());
}

#[test]
fn test_dual_auth_rejects_wrong_custodian_b_signature() {
    let mut rng_a = rand::rngs::StdRng::seed_from_u64(1);
    let mut rng_b = rand::rngs::StdRng::seed_from_u64(2);
    let signing_key_a = SigningKey::generate(&mut rng_a);
    let signing_key_b = SigningKey::generate(&mut rng_b);

    let pk_a = *signing_key_a.verifying_key().as_bytes();
    let pk_b = *signing_key_b.verifying_key().as_bytes();

    let manifest_hash = "test_manifest_hash_v1".to_string();

    let mut transfer = DualAuthTransfer::with_custodians(manifest_hash.clone(), pk_a, pk_b);

    // Sign correctly with A
    let sig_a = signing_key_a.sign(manifest_hash.as_bytes());
    let sig_a_hex = hex::encode(sig_a.to_bytes());

    // Sign with B but using a DIFFERENT message
    let wrong_message = "tampered_manifest_hash";
    let sig_b = signing_key_b.sign(wrong_message.as_bytes());
    let sig_b_hex = hex::encode(sig_b.to_bytes());

    transfer.sign_by_custodian_a(sig_a_hex).ok();
    transfer.sign_by_custodian_b(sig_b_hex).ok();

    // Verify should fail because sig_b doesn't match manifest_hash
    let result = transfer.verify_signatures();
    assert!(
        matches!(result, Err(SneakernetError::InvalidSignature { custodian }) if custodian == "B")
    );
}

#[test]
fn test_dual_auth_rejects_tampered_manifest_hash() {
    let mut rng_a = rand::rngs::StdRng::seed_from_u64(1);
    let mut rng_b = rand::rngs::StdRng::seed_from_u64(2);
    let signing_key_a = SigningKey::generate(&mut rng_a);
    let signing_key_b = SigningKey::generate(&mut rng_b);

    let pk_a = *signing_key_a.verifying_key().as_bytes();
    let pk_b = *signing_key_b.verifying_key().as_bytes();

    let manifest_hash = "test_manifest_hash_v1".to_string();

    let mut transfer = DualAuthTransfer::with_custodians(manifest_hash.clone(), pk_a, pk_b);

    // Sign correctly with both keys
    let sig_a = signing_key_a.sign(manifest_hash.as_bytes());
    let sig_a_hex = hex::encode(sig_a.to_bytes());

    let sig_b = signing_key_b.sign(manifest_hash.as_bytes());
    let sig_b_hex = hex::encode(sig_b.to_bytes());

    transfer.sign_by_custodian_a(sig_a_hex).ok();
    transfer.sign_by_custodian_b(sig_b_hex).ok();

    // Tamper with the manifest_hash after signatures are applied
    transfer.manifest_hash = "tampered_hash".to_string();

    // Verification should fail because manifest no longer matches the signed hash
    let result = transfer.verify_signatures();
    assert!(matches!(
        result,
        Err(SneakernetError::InvalidSignature { .. })
    ));
}

#[test]
fn test_signature_format_validation_128_hex_chars() {
    let mut transfer = DualAuthTransfer::new("hash".to_string());

    // Too short signature
    let short_sig = "deadbeef".to_string();
    assert!(transfer.sign_by_custodian_a(short_sig).is_err());

    // Non-hex characters
    let bad_sig = "z".repeat(128);
    assert!(transfer.sign_by_custodian_a(bad_sig).is_err());

    // Valid 128 hex chars
    let valid_sig = "a".repeat(128);
    assert!(transfer.sign_by_custodian_a(valid_sig).is_ok());
}

#[test]
fn test_aes256_encrypt_decrypt_roundtrip() {
    let plaintext = b"Sovereign model weights in sneakernet";
    let key: [u8; 32] = [42; 32];

    // Encrypt
    let encrypted = DualAuthTransfer::aes256_encrypt(plaintext, &key);

    // Decrypt
    let decrypted =
        DualAuthTransfer::aes256_decrypt(&encrypted, &key).expect("Decryption should succeed");

    assert_eq!(decrypted, plaintext);
}

#[test]
fn test_aes256_rejects_tampered_ciphertext() {
    let plaintext = b"Sovereign model weights";
    let key: [u8; 32] = [42; 32];

    let mut encrypted = DualAuthTransfer::aes256_encrypt(plaintext, &key);

    // Tamper with the ciphertext (skip the nonce and tamper the payload)
    if encrypted.len() > 20 {
        encrypted[20] ^= 0xFF;
    }

    // Decryption should fail due to GCM auth tag failure
    let result = DualAuthTransfer::aes256_decrypt(&encrypted, &key);
    assert!(
        result.is_none(),
        "Tampered ciphertext should fail GCM verification"
    );
}
