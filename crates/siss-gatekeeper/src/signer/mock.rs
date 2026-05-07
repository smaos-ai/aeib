use super::{Signer, SigningError};

/// A deterministic mock signer for tests. Always produces `[0xAA; 64]` signatures.
pub struct MockSigner;

impl Signer for MockSigner {
    fn sign(&self, _payload: &[u8]) -> Result<Vec<u8>, SigningError> {
        Ok(vec![0xAA; 64])
    }

    fn verify(&self, _payload: &[u8], _signature: &[u8]) -> Result<bool, SigningError> {
        Ok(true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mock_signer_produces_deterministic_signature() {
        let signer = MockSigner;
        let sig = signer.sign(b"anything").unwrap();
        assert_eq!(sig.len(), 64);
        assert!(sig.iter().all(|&b| b == 0xAA));
    }

    #[test]
    fn test_mock_signer_always_verifies() {
        let signer = MockSigner;
        assert!(signer.verify(b"anything", &[0; 64]).unwrap());
    }
}
