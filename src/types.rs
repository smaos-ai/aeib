"""
Type Consolidation: Cryptographic Signature Unification
Resolves Vec<u8> vs String mismatch across L3 and L8.
"""

use serde::{Deserialize, Serialize};


#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SovereignSignature {
    pub key_id: String,
    pub algorithm: String, // "Ed25519-PQC"
    pub raw_bytes: Vec<u8>,
    pub hex_repr: String,
}

impl SovereignSignature {
    pub fn from_bytes(bytes: &[u8], key_id: &str) -> Self {
        Self {
            key_id: key_id.to_string(),
            algorithm: "Ed25519-PQC".to_string(),
            raw_bytes: bytes.to_vec(),
            hex_repr: hex::encode(bytes),
        }
    }

    pub fn from_hex(hex_str: &str, key_id: &str) -> Result<Self, String> {
        let bytes = hex::decode(hex_str).map_err(|e| format!("Invalid hex: {}", e))?;
        Ok(Self::from_bytes(&bytes, key_id))
    }

    pub fn verify(&self) -> bool {
        // Verify internal consistency
        self.hex_repr == hex::encode(&self.raw_bytes)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_signature_consistency() {
        let sig = SovereignSignature::from_bytes(b"test_signature", "key_123");
        assert!(sig.verify());
        assert_eq!(sig.algorithm, "Ed25519-PQC");
    }

    #[test]
    fn test_signature_hex_roundtrip() {
        let original_hex = "48656c6c6f"; // "Hello" in hex
        let sig = SovereignSignature::from_hex(original_hex, "key_456").unwrap();
        assert_eq!(sig.hex_repr, original_hex);
        assert!(sig.verify());
    }
}
