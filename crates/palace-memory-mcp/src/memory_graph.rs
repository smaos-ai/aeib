use chrono::{DateTime, Utc};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::hash::{Hash, Hasher};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MemoryZone {
    BlackFog,     // System internal
    GrayFog,      // User restricted
    VisibleField, // Public/agent accessible
}

impl Hash for MemoryZone {
    fn hash<H: Hasher>(&self, state: &mut H) {
        (*self as u8).hash(state);
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEntry {
    pub id: Uuid,
    pub zone: MemoryZone,
    pub content: String,
    pub created_at: DateTime<Utc>,
    pub merkle_hash: [u8; 32],
}

#[derive(Debug)]
pub struct MemoryGraph {
    entries: DashMap<Uuid, MemoryEntry>,
}

impl MemoryGraph {
    pub fn new() -> Self {
        Self {
            entries: DashMap::new(),
        }
    }

    pub async fn append(&self, zone: MemoryZone, content: String) -> Result<MemoryEntry, String> {
        let id = Uuid::new_v4();
        let hash = self.compute_merkle_hash(&content);
        let entry = MemoryEntry {
            id,
            zone,
            content,
            created_at: Utc::now(),
            merkle_hash: hash,
        };
        self.entries.insert(id, entry.clone());
        Ok(entry)
    }

    pub async fn log_invocation(&self, tool_name: String) {
        let _ = self
            .append(MemoryZone::VisibleField, format!("invoked:{}", tool_name))
            .await;
    }

    pub fn get(&self, id: Uuid) -> Option<MemoryEntry> {
        self.entries.get(&id).map(|e| e.clone())
    }

    fn compute_merkle_hash(&self, data: &str) -> [u8; 32] {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(data.as_bytes());
        let result = hasher.finalize();
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&result[..]);
        hash
    }
}

impl Default for MemoryGraph {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_memory_append() {
        let graph = MemoryGraph::new();
        let result = graph
            .append(MemoryZone::VisibleField, "test".to_string())
            .await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_memory_retrieve() {
        let graph = MemoryGraph::new();
        let entry = graph
            .append(MemoryZone::BlackFog, "secret".to_string())
            .await
            .unwrap();
        let retrieved = graph.get(entry.id);
        assert!(retrieved.is_some());
    }
}
