use wasm_bindgen::prelude::*;
use ed25519_dalek::{VerifyingKey, Signature};
use sha2::{Sha256, Digest};
use hex;

#[wasm_bindgen]
pub fn verify_receipt_signature(public_key_hex: &str, signature_hex: &str, message_bytes: &[u8]) -> bool {
    let pk_bytes = match hex::decode(public_key_hex) {
        Ok(b) => b,
        Err(_) => return false,
    };
    let sig_bytes = match hex::decode(signature_hex) {
        Ok(b) => b,
        Err(_) => return false,
    };

    if pk_bytes.len() != 32 || sig_bytes.len() != 64 {
        return false;
    }

    let mut pk_array = [0u8; 32];
    pk_array.copy_from_slice(&pk_bytes);
    
    let mut sig_array = [0u8; 64];
    sig_array.copy_from_slice(&sig_bytes);

    let public_key = match VerifyingKey::from_bytes(&pk_array) {
        Ok(pk) => pk,
        Err(_) => return false,
    };

    let signature = Signature::from_bytes(&sig_array);

    // Use verify_strict to reject malleable and non-canonical signatures
    public_key.verify_strict(message_bytes, &signature).is_ok()
}

#[wasm_bindgen]
pub fn compute_sha256_hex(input_bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(input_bytes);
    let result = hasher.finalize();
    hex::encode(result)
}

#[wasm_bindgen]
pub fn compute_jcs_caid(canonical_payload_str: &str) -> String {
    compute_sha256_hex(canonical_payload_str.as_bytes())
}

#[wasm_bindgen]
pub fn derive_action_caid(noun: &str, verb: &str, canonical_payload_str: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(noun.trim().as_bytes());
    hasher.update(b"::");
    hasher.update(verb.trim().as_bytes());
    hasher.update(b"::");
    hasher.update(canonical_payload_str.as_bytes());
    let digest = hasher.finalize();
    format!("caid:sha256:{}", hex::encode(digest))
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{SigningKey, Signer};
    use rand::rngs::OsRng;

    #[test]
    fn test_verify_receipt_signature_success() {
        let mut csprng = OsRng;
        let signing_key = SigningKey::generate(&mut csprng);
        let public_key = signing_key.verifying_key();
        
        let message = b"test message";
        let signature = signing_key.sign(message);
        
        let pk_hex = hex::encode(public_key.as_bytes());
        let sig_hex = hex::encode(signature.to_bytes());
        
        assert!(verify_receipt_signature(&pk_hex, &sig_hex, message));
    }

    #[test]
    fn test_verify_receipt_signature_tampered_fails() {
        let mut csprng = OsRng;
        let signing_key = SigningKey::generate(&mut csprng);
        let public_key = signing_key.verifying_key();
        
        let message = b"test message";
        let signature = signing_key.sign(message);
        
        let pk_hex = hex::encode(public_key.as_bytes());
        let sig_hex = hex::encode(signature.to_bytes());
        
        // Tampered message
        assert!(!verify_receipt_signature(&pk_hex, &sig_hex, b"tampered message"));
        
        // Tampered signature
        let mut bad_sig = signature.to_bytes();
        bad_sig[0] ^= 0xFF;
        assert!(!verify_receipt_signature(&pk_hex, &hex::encode(bad_sig), message));
        
        // Wrong public key
        let wrong_key = SigningKey::generate(&mut csprng);
        let wrong_pk_hex = hex::encode(wrong_key.verifying_key().as_bytes());
        assert!(!verify_receipt_signature(&wrong_pk_hex, &sig_hex, message));
    }

    #[test]
    fn test_compute_jcs_caid() {
        let json = "{\"hello\":\"world\"}";
        let digest = compute_jcs_caid(json);
        assert_eq!(digest, "93a23971a914e5eacbf0a8d25154cda309c3c1c72fbb9914d47c60f3cb681588");
    }

    #[test]
    fn test_derive_action_caid() {
        let caid = derive_action_caid("treasury:account:acct_alpha", "DEBIT", "{\"amount\":100}");
        assert!(caid.starts_with("caid:sha256:"));
        assert_eq!(caid.len(), 12 + 64);
    }

    /// RFC 8785 Section 3.2.4 canonical UTF-8 bytes, transcribed from the RFC.
    const RFC8785_SECTION_3_2_4_HEX: &str = "7b226c69746572616c73223a5b6e756c6c2c747275652c66616c73655d2c226e756d62657273223a5b3333333333333333332e333333333333332c31652b33302c342e352c302e3030322c31652d32375d2c22737472696e67223a22e282ac245c75303030665c6e4127425c225c5c5c5c5c222f227d";
    /// SHA-256 over those bytes, shared with src/jcs_canonicalizer.py.
    const RFC8785_SECTION_3_2_4_SHA256: &str =
        "2d5e01a318d0f0879ab568c4be289c8b1f64ef8921a53c6277d5e069978baacb";

    #[test]
    fn test_rfc8785_section_3_2_4_canonical_bytes_hash() {
        // Byte-exact agreement with the RFC-published canonical form (Section 3.2.4).
        let canonical = String::from_utf8(hex::decode(RFC8785_SECTION_3_2_4_HEX).unwrap()).unwrap();
        assert_eq!(compute_jcs_caid(&canonical), RFC8785_SECTION_3_2_4_SHA256);

        let caid = derive_action_caid("file", "write", &canonical);
        // CAID is H(noun || "::" || verb || "::" || JCS(payload)), so it differs from
        // the bare payload hash but must remain a well-formed, deterministic identifier.
        assert!(caid.starts_with("caid:sha256:"));
        assert_ne!(caid, format!("caid:sha256:{}", RFC8785_SECTION_3_2_4_SHA256));
        assert_eq!(derive_action_caid("file", "write", &canonical), caid);
    }
}
