// Content-addressed hashing via blake3
// Ensures same artifact always produces same hash

use std::fmt;

/// Content hasher using blake3
pub struct ContentHasher;

impl ContentHasher {
    /// Hash artifact bytes to content hash
    pub fn hash(data: &[u8]) -> ContentHash {
        let hash = blake3::hash(data);
        ContentHash {
            hex: hash.to_hex().to_string(),
        }
    }

    /// Verify artifact matches expected hash
    pub fn verify(data: &[u8], expected_hash: &ContentHash) -> bool {
        let computed = Self::hash(data);
        computed.hex == expected_hash.hex
    }
}

/// Content hash (blake3 hex string)
#[derive(Clone, Debug, PartialEq, Eq, serde::Serialize, serde::Deserialize)]
pub struct ContentHash {
    pub hex: String,
}

impl ContentHash {
    pub fn new(hex: String) -> Self {
        ContentHash { hex }
    }

    pub fn as_str(&self) -> &str {
        &self.hex
    }
}

impl fmt::Display for ContentHash {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.hex)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_content_hash_consistency() {
        // Same artifact should produce same hash
        let data = b"test artifact data";
        let hash1 = ContentHasher::hash(data);
        let hash2 = ContentHasher::hash(data);
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_content_hash_deterministic() {
        // Multiple hashes of same data are identical
        let data = b"fixed artifact content";
        let hash1 = ContentHasher::hash(data);
        let hash2 = ContentHasher::hash(data);
        let hash3 = ContentHasher::hash(data);
        assert_eq!(hash1.hex, hash2.hex);
        assert_eq!(hash2.hex, hash3.hex);
    }

    #[test]
    fn test_content_hash_different_data() {
        // Different data produces different hashes
        let data1 = b"artifact v1";
        let data2 = b"artifact v2";
        let hash1 = ContentHasher::hash(data1);
        let hash2 = ContentHasher::hash(data2);
        assert_ne!(hash1, hash2);
    }

    #[test]
    fn test_content_hash_hex_length() {
        // blake3 produces 64-char hex string
        let data = b"test";
        let hash = ContentHasher::hash(data);
        assert_eq!(hash.hex.len(), 64);
    }

    #[test]
    fn test_content_hash_verify_success() {
        // Verification passes when hash matches
        let data = b"artifact bytes";
        let hash = ContentHasher::hash(data);
        assert!(ContentHasher::verify(data, &hash));
    }

    #[test]
    fn test_content_hash_verify_failure() {
        // Verification fails when data differs
        let data1 = b"original";
        let data2 = b"modified";
        let hash = ContentHasher::hash(data1);
        assert!(!ContentHasher::verify(data2, &hash));
    }

    #[test]
    fn test_content_hash_serialization() {
        // Hash can be serialized to JSON
        let hash = ContentHasher::hash(b"test");
        let json = serde_json::to_string(&hash).unwrap();
        let deserialized: ContentHash = serde_json::from_str(&json).unwrap();
        assert_eq!(hash, deserialized);
    }

    #[test]
    fn test_content_hash_display() {
        // Hash displays as hex string
        let hash = ContentHasher::hash(b"test");
        let displayed = format!("{}", hash);
        assert_eq!(displayed, hash.hex);
    }

    #[test]
    fn test_content_hash_as_str() {
        // as_str() returns slice of hex
        let hash = ContentHasher::hash(b"data");
        let str_ref = hash.as_str();
        assert_eq!(str_ref, hash.hex);
        assert_eq!(str_ref.len(), 64);
    }

    #[test]
    fn test_large_artifact_hash() {
        // Hashing large artifacts works correctly
        let large_data = vec![0u8; 1024 * 1024]; // 1MB
        let hash1 = ContentHasher::hash(&large_data);
        let hash2 = ContentHasher::hash(&large_data);
        assert_eq!(hash1, hash2);
    }
}
