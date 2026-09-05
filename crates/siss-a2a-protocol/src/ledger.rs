use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use uuid::Uuid;

/// A2A message entry in joint ledger
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerEntry {
    /// Entry ID
    pub id: String,
    /// A2A message ID
    pub message_id: String,
    /// Source agent
    pub source: String,
    /// Target agent
    pub target: String,
    /// Message digest (SHA256)
    pub digest: String,
    /// Previous entry digest (chain link)
    pub prev_digest: Option<String>,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
    /// Git commit digest (regulatory audit trail)
    pub git_commit_digest: Option<String>,
}

impl LedgerEntry {
    /// Create new ledger entry
    pub fn new(
        message_id: String,
        source: String,
        target: String,
        digest: String,
    ) -> Self {
        LedgerEntry {
            id: Uuid::new_v4().to_string(),
            message_id,
            source,
            target,
            digest,
            prev_digest: None,
            timestamp: Utc::now(),
            git_commit_digest: None,
        }
    }

    /// Compute ledger entry hash
    pub fn entry_hash(&self) -> String {
        let data = format!(
            "{}|{}|{}|{}|{}",
            self.message_id, self.source, self.target, self.digest, self.timestamp
        );
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Set git commit digest
    pub fn with_git_digest(mut self, git_digest: String) -> Self {
        self.git_commit_digest = Some(git_digest);
        self
    }
}

/// Joint ledger for A2A handoffs
pub struct JointLedger {
    entries: Vec<LedgerEntry>,
    last_digest: Option<String>,
}

impl JointLedger {
    /// Create new ledger
    pub fn new() -> Self {
        JointLedger {
            entries: vec![],
            last_digest: None,
        }
    }

    /// Append A2A handoff to ledger
    pub fn append(&mut self, mut entry: LedgerEntry) -> String {
        // Link to previous entry for immutability
        entry.prev_digest = self.last_digest.clone();

        // Compute entry hash
        let entry_hash = entry.entry_hash();
        self.last_digest = Some(entry_hash.clone());
        self.entries.push(entry);

        entry_hash
    }

    /// Get all entries
    pub fn entries(&self) -> &[LedgerEntry] {
        &self.entries
    }

    /// Get merkle root (all entries hashed)
    pub fn merkle_root(&self) -> String {
        if self.entries.is_empty() {
            return "0".to_string();
        }

        let entry_hashes: Vec<String> = self.entries.iter().map(|e| e.entry_hash()).collect();
        let combined = entry_hashes.join("|");
        let mut hasher = Sha256::new();
        hasher.update(combined.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Get last entry
    pub fn last_entry(&self) -> Option<&LedgerEntry> {
        self.entries.last()
    }

    /// Count entries
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Is empty
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Serialize ledger to JSON
    pub fn to_json(&self) -> anyhow::Result<String> {
        Ok(serde_json::to_string(&self.entries)?)
    }

    /// Verify ledger integrity (chain links)
    pub fn verify_integrity(&self) -> bool {
        if self.entries.is_empty() {
            return true;
        }

        for i in 1..self.entries.len() {
            let current = &self.entries[i];
            let previous = &self.entries[i - 1];

            // Check chain link
            if current.prev_digest != Some(previous.entry_hash()) {
                return false;
            }
        }
        true
    }
}

impl Default for JointLedger {
    fn default() -> Self {
        Self::new()
    }
}

/// Ledger anchor: git commit + merkle root for regulatory audit
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LedgerAnchor {
    /// Git commit hash
    pub git_commit: String,
    /// Ledger merkle root at commit time
    pub merkle_root: String,
    /// Number of entries in ledger
    pub entry_count: usize,
    /// Timestamp of anchor
    pub timestamp: DateTime<Utc>,
    /// Signature (Ed25519) over (git_commit + merkle_root)
    pub signature: Option<String>,
}

impl LedgerAnchor {
    /// Create new anchor
    pub fn new(git_commit: String, merkle_root: String, entry_count: usize) -> Self {
        LedgerAnchor {
            git_commit,
            merkle_root,
            entry_count,
            timestamp: Utc::now(),
            signature: None,
        }
    }

    /// Sign anchor
    pub fn sign(&mut self, signature: String) {
        self.signature = Some(signature);
    }

    /// Verify anchor format
    pub fn is_valid(&self) -> bool {
        !self.git_commit.is_empty() && !self.merkle_root.is_empty() && self.signature.is_some()
    }

    /// Serialize anchor to bytes
    pub fn to_bytes(&self) -> anyhow::Result<Vec<u8>> {
        Ok(serde_json::to_vec(self)?)
    }

    /// Deserialize anchor from bytes
    pub fn from_bytes(bytes: &[u8]) -> anyhow::Result<Self> {
        Ok(serde_json::from_slice(bytes)?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ledger_entry_creation() {
        let entry = LedgerEntry::new(
            "msg-123".to_string(),
            "agent-1".to_string(),
            "agent-2".to_string(),
            "digest123".to_string(),
        );
        assert_eq!(entry.message_id, "msg-123");
        assert_eq!(entry.prev_digest, None);
    }

    #[test]
    fn test_ledger_append() {
        let mut ledger = JointLedger::new();
        let entry1 = LedgerEntry::new(
            "msg-1".to_string(),
            "agent-1".to_string(),
            "agent-2".to_string(),
            "digest1".to_string(),
        );
        let hash1 = ledger.append(entry1);
        assert!(!hash1.is_empty());
        assert_eq!(ledger.len(), 1);
    }

    #[test]
    fn test_ledger_chain_integrity() {
        let mut ledger = JointLedger::new();
        let entry1 = LedgerEntry::new(
            "msg-1".to_string(),
            "agent-1".to_string(),
            "agent-2".to_string(),
            "digest1".to_string(),
        );
        let entry2 = LedgerEntry::new(
            "msg-2".to_string(),
            "agent-2".to_string(),
            "agent-1".to_string(),
            "digest2".to_string(),
        );

        ledger.append(entry1);
        ledger.append(entry2);

        assert!(ledger.verify_integrity());
        assert_eq!(ledger.len(), 2);
    }

    #[test]
    fn test_ledger_merkle_root() {
        let mut ledger = JointLedger::new();
        let entry = LedgerEntry::new(
            "msg-1".to_string(),
            "agent-1".to_string(),
            "agent-2".to_string(),
            "digest1".to_string(),
        );
        ledger.append(entry);

        let root = ledger.merkle_root();
        assert!(!root.is_empty());
        assert_eq!(root.len(), 64); // SHA256 hex
    }

    #[test]
    fn test_ledger_anchor() {
        let anchor = LedgerAnchor::new(
            "abc1234567890".to_string(),
            "merkle_root_hash".to_string(),
            42,
        );
        assert!(!anchor.is_valid()); // No signature yet

        let mut signed_anchor = anchor;
        signed_anchor.sign("sig123".to_string());
        assert!(signed_anchor.is_valid());
    }

    #[test]
    fn test_ledger_serialization() {
        let ledger = JointLedger::new();
        let json = ledger.to_json().expect("serialize");
        assert_eq!(json, "[]");
    }
}
