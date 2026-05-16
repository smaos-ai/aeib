use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MemoryTier {
    L2Semantic,
    L2VisibleField,
    L2GrayFog,
    L3Ledger,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryWrite {
    pub memory_type: MemoryTier,
    pub task_id: String,
    pub raw_span: String,
    pub structured_fields: HashMap<String, String>,
    pub operator_signature: Option<String>,
}
