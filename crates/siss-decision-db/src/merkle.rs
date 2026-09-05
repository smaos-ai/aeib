use sha2::{Digest, Sha256};

/// Compute SHA256 hash of prev_hash || content
pub fn compute_hash(prev_hash: &str, content: &str) -> String {
    let combined = format!("{}{}", prev_hash, content);
    let mut hasher = Sha256::new();
    hasher.update(combined.as_bytes());
    format!("{:x}", hasher.finalize())
}

/// Verify Merkle chain integrity (all hashes must chain correctly)
pub fn verify_chain(entries: &[(String, String)]) -> Result<(), String> {
    let mut prev_hash = "0".to_string();
    for (current_hash, content) in entries {
        let expected = compute_hash(&prev_hash, content);
        if expected != *current_hash {
            return Err(format!(
                "Hash mismatch at entry: {} != {}",
                expected, current_hash
            ));
        }
        prev_hash = current_hash.clone();
    }
    Ok(())
}

/// Get final Merkle root (last hash in chain)
pub fn merkle_root(entries: &[(String, String)]) -> Option<String> {
    entries.last().map(|(hash, _)| hash.clone())
}
