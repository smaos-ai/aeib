use hex::ToHex;
use sha2::{Digest, Sha256};

pub fn compute(prev_hash: Option<&str>, id: &str, context: &str, decision: &str) -> String {
    let prev = prev_hash.unwrap_or("");
    let data = format!("{prev}:{id}:{context}:{decision}");
    let hash = Sha256::digest(data.as_bytes());
    hash.encode_hex()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_merkle_compute_basic() {
        let hash1 = compute(None, "d1", "why1", "decision1");
        assert!(!hash1.is_empty());
        assert_eq!(hash1.len(), 64); // sha256 hex = 64 chars
    }

    #[test]
    fn test_merkle_compute_deterministic() {
        let inputs = ("d1", "why1", "decision1");
        let h1 = compute(None, inputs.0, inputs.1, inputs.2);
        let h2 = compute(None, inputs.0, inputs.1, inputs.2);
        assert_eq!(h1, h2);
    }

    #[test]
    fn test_merkle_chain_links() {
        let hash1 = compute(None, "d1", "why1", "dec1");
        let hash2 = compute(Some(&hash1), "d2", "why2", "dec2");
        let hash3 = compute(Some(&hash2), "d3", "why3", "dec3");

        // All different
        assert_ne!(hash1, hash2);
        assert_ne!(hash2, hash3);
        assert_ne!(hash1, hash3);
    }

    #[test]
    fn test_merkle_chain_breaks_on_tampering() {
        let hash1 = compute(None, "d1", "why1", "dec1");
        let hash2_honest = compute(Some(&hash1), "d2", "why2", "dec2");

        // Tamper: change d2's decision
        let hash2_tampered = compute(Some(&hash1), "d2", "why2", "tampered_dec2");

        assert_ne!(hash2_honest, hash2_tampered);
    }
}
