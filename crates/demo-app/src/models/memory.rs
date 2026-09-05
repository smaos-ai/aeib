use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MemoryTier {
    L2Semantic,
    L2VisibleField,
    L2GrayFog,
    L3Ledger,
    L3Profile,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryWrite {
    pub memory_type: MemoryTier,
    pub task_id: String,
    pub raw_span: String,
    pub structured_fields: HashMap<String, String>,
    pub operator_signature: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemorySnippet {
    pub memory_id: String,
    pub snippet_type: MemoryTier,
    pub relevance_score: f32,
    pub compressed_summary: String,
}
