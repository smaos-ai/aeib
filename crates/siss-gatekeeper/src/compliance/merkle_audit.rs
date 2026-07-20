use uuid::Uuid;
use serde::{Deserialize, Serialize};

/// Single entry in the Merkle-DAG audit trail (EXEC_LOG)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MerkleAuditEntry {
    pub capsule_id: Uuid,
    pub timestamp: u64,                 // Unix seconds

    /// Model inference details
    pub model_name: String,
    pub input_hash: String,             // SHA256(input)
    pub output_hash: String,            // SHA256(output)

    /// Safety gates executed
    pub safety_gates_passed: bool,
    pub gates_detail: Vec<(String, bool)>, // (gate_name, passed)

    /// Human gate (if required)
    pub human_gate_required: bool,
    pub human_gate_approved: Option<bool>,
    pub approver_id: Option<Uuid>,

    /// Merkle chain
    pub merkle_root: String,            // SHA256(this entry + parent)
    pub parent_hash: String,            // SHA256(previous entry)

    /// Compliance claims
    pub compliance_claims: Vec<String>, // "OMB-M-24-10 § 4.2.1"
}

/// EXEC_LOG manager: maintains immutable Merkle-DAG audit trail
pub struct EXEC_LOG {
    entries: Vec<MerkleAuditEntry>,
    current_merkle_root: String,
}

impl EXEC_LOG {
    pub fn new() -> Self {
        Self {
            entries: vec![],
            current_merkle_root: "genesis".to_string(),
        }
    }

    /// Add a new entry to the audit trail
    pub fn append(&mut self, entry: MerkleAuditEntry) -> String {
        let parent_hash = self.current_merkle_root.clone();

        // Compute Merkle root: SHA256(entry_data || parent_hash)
        let entry_str = format!("{:?}|{}", entry, parent_hash);
        let merkle_root = format!("sha256:{:x}", simple_hash(&entry_str));

        let mut new_entry = entry;
        new_entry.parent_hash = parent_hash;
        new_entry.merkle_root = merkle_root.clone();

        self.entries.push(new_entry);
        self.current_merkle_root = merkle_root.clone();

        merkle_root
    }

    /// Get all entries
    pub fn entries(&self) -> &[MerkleAuditEntry] {
        &self.entries
    }

    /// Get current Merkle root (head of chain)
    pub fn current_root(&self) -> &str {
        &self.current_merkle_root
    }

    /// Verify chain integrity (simple check: all parents link correctly)
    pub fn verify_integrity(&self) -> bool {
        if self.entries.is_empty() {
            return true; // Empty log is valid
        }

        let mut expected_parent = "genesis".to_string();

        for entry in &self.entries {
            if entry.parent_hash != expected_parent {
                return false; // Chain broken
            }
            expected_parent = entry.merkle_root.clone();
        }

        // Final check: last entry should be current root
        expected_parent == self.current_merkle_root
    }

    /// Get entry by capsule_id
    pub fn get_by_capsule(&self, capsule_id: Uuid) -> Option<&MerkleAuditEntry> {
        self.entries.iter().find(|e| e.capsule_id == capsule_id)
    }

    /// Count entries
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Get summary stats
    pub fn summary(&self) -> String {
        let total = self.entries.len();
        let gates_passed = self.entries.iter().filter(|e| e.safety_gates_passed).count();
        let human_approved = self.entries.iter().filter(|e| e.human_gate_approved == Some(true)).count();

        format!(
            "EXEC_LOG: {} entries | {} gates passed | {} human approvals | Root: {}",
            total, gates_passed, human_approved, self.current_merkle_root
        )
    }
}

/// Simple hash function (in production use SHA256 from sha2 crate)
fn simple_hash(data: &str) -> u64 {
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    use std::hash::{Hash, Hasher};
    data.hash(&mut hasher);
    hasher.finish()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_exec_log_creation() {
        let log = EXEC_LOG::new();
        assert_eq!(log.len(), 0);
        assert_eq!(log.current_root(), "genesis");
    }

    #[test]
    fn test_exec_log_append() {
        let mut log = EXEC_LOG::new();
        let entry = MerkleAuditEntry {
            capsule_id: Uuid::new_v4(),
            timestamp: 1717500000,
            model_name: "Claude 3.5 Sonnet".to_string(),
            input_hash: "sha256:abc123".to_string(),
            output_hash: "sha256:def456".to_string(),
            safety_gates_passed: true,
            gates_detail: vec![
                ("XSSPrevention".to_string(), true),
                ("SQLInjectionPrevention".to_string(), true),
            ],
            human_gate_required: false,
            human_gate_approved: None,
            approver_id: None,
            merkle_root: String::new(),
            parent_hash: String::new(),
            compliance_claims: vec!["OMB-M-24-10 § 4.2.1".to_string()],
        };

        let root = log.append(entry);
        assert_eq!(log.len(), 1);
        assert_ne!(root, "genesis");
        assert_eq!(log.current_root(), root);
    }

    #[test]
    fn test_exec_log_integrity() {
        let mut log = EXEC_LOG::new();

        for i in 0..5 {
            let entry = MerkleAuditEntry {
                capsule_id: Uuid::new_v4(),
                timestamp: 1717500000 + i,
                model_name: "Claude".to_string(),
                input_hash: format!("sha256:in{}", i),
                output_hash: format!("sha256:out{}", i),
                safety_gates_passed: true,
                gates_detail: vec![("XSSPrevention".to_string(), true)],
                human_gate_required: false,
                human_gate_approved: None,
                approver_id: None,
                merkle_root: String::new(),
                parent_hash: String::new(),
                compliance_claims: vec![],
            };

            log.append(entry);
        }

        assert!(log.verify_integrity());
    }

    #[test]
    fn test_exec_log_get_by_capsule() {
        let mut log = EXEC_LOG::new();
        let capsule_id = Uuid::new_v4();

        let entry = MerkleAuditEntry {
            capsule_id,
            timestamp: 1717500000,
            model_name: "Claude".to_string(),
            input_hash: "sha256:abc".to_string(),
            output_hash: "sha256:def".to_string(),
            safety_gates_passed: true,
            gates_detail: vec![],
            human_gate_required: false,
            human_gate_approved: None,
            approver_id: None,
            merkle_root: String::new(),
            parent_hash: String::new(),
            compliance_claims: vec![],
        };

        log.append(entry);
        assert!(log.get_by_capsule(capsule_id).is_some());
    }

    #[test]
    fn test_exec_log_summary() {
        let mut log = EXEC_LOG::new();
        let entry = MerkleAuditEntry {
            capsule_id: Uuid::new_v4(),
            timestamp: 1717500000,
            model_name: "Claude".to_string(),
            input_hash: "sha256:abc".to_string(),
            output_hash: "sha256:def".to_string(),
            safety_gates_passed: true,
            gates_detail: vec![],
            human_gate_required: false,
            human_gate_approved: None,
            approver_id: None,
            merkle_root: String::new(),
            parent_hash: String::new(),
            compliance_claims: vec![],
        };

        log.append(entry);
        let summary = log.summary();
        assert!(summary.contains("1 entries"));
        assert!(summary.contains("Root:"));
    }
}
