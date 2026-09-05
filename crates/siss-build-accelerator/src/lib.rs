// siss-build-accelerator: Content-addressed cache for build artifacts
// Stage 1: In-memory + disk cache with LRU eviction and blake3 hashing

pub mod cache_store;
pub mod content_hash;

pub use cache_store::{CacheKey, CacheStore, CachedArtifact};
pub use content_hash::ContentHasher;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_module_imports() {
        // Verify module structure
        let _hasher = ContentHasher;
    }
}
