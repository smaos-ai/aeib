use siss_agent_shell::covenant_firewall::{
    CovenantFirewall, EconomicIntent, CovenantViolation,
};
use ed25519_dalek::{SigningKey, Signer as DalekSigner};
use rand::rngs::OsRng;

fn sign_intent(merkle: &[u8; 32], s: u8, b: u8, key: &SigningKey) -> (EconomicIntent, Vec<u8>) {
    let intent = EconomicIntent { steward_pct: s, beneficiary_pct: b };
    let payload = CovenantFirewall::signing_payload(merkle, &intent);
    let sig = key.sign(&payload).to_bytes().to_vec();
    (intent, sig)
}

#[test]
fn test_accept_valid_1_99_covenant() {
    let key = SigningKey::generate(&mut OsRng);
    let merkle = [0u8; 32];
    let (intent, sig) = sign_intent(&merkle, 1, 99, &key);
    let vk = key.verifying_key().to_bytes().to_vec();
    assert!(CovenantFirewall::verify(&merkle, &intent, &sig, &vk).is_ok());
}

#[test]
fn test_reject_wrong_split() {
    let key = SigningKey::generate(&mut OsRng);
    let merkle = [0u8; 32];
    let (intent, sig) = sign_intent(&merkle, 50, 50, &key);
    let vk = key.verifying_key().to_bytes().to_vec();
    assert_eq!(
        CovenantFirewall::verify(&merkle, &intent, &sig, &vk).unwrap_err(),
        CovenantViolation::IntentMismatch
    );
}

#[test]
fn test_reject_tampered_signature() {
    let key = SigningKey::generate(&mut OsRng);
    let merkle = [0u8; 32];
    let (intent, _) = sign_intent(&merkle, 1, 99, &key);
    let bad_sig = vec![0u8; 64];
    let vk = key.verifying_key().to_bytes().to_vec();
    assert_eq!(
        CovenantFirewall::verify(&merkle, &intent, &bad_sig, &vk).unwrap_err(),
        CovenantViolation::SignatureInvalid
    );
}

#[test]
fn test_reject_split_not_summing_to_100() {
    let key = SigningKey::generate(&mut OsRng);
    let merkle = [0u8; 32];
    let (intent, sig) = sign_intent(&merkle, 1, 98, &key);
    let vk = key.verifying_key().to_bytes().to_vec();
    assert_eq!(
        CovenantFirewall::verify(&merkle, &intent, &sig, &vk).unwrap_err(),
        CovenantViolation::IntentMismatch
    );
}

#[test]
fn test_reject_tampered_merkle_root() {
    let key = SigningKey::generate(&mut OsRng);
    let original = [0u8; 32];
    let tampered = [1u8; 32];
    let (intent, sig) = sign_intent(&original, 1, 99, &key);
    let vk = key.verifying_key().to_bytes().to_vec();
    assert_eq!(
        CovenantFirewall::verify(&tampered, &intent, &sig, &vk).unwrap_err(),
        CovenantViolation::SignatureInvalid
    );
}
