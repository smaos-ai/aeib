use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DocumentStatus {
    Quarantined,
    ParsingInProgress,
    Parsed,
    Indexed,
    AnalysisComplete,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum IngestionSource {
    UsbSneakernet,
    LoopbackApi,
    MemoryBuffer,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DocumentManifest {
    pub document_id: String,
    pub filename: String,
    pub ingestion_timestamp_ms: u64,
    pub source: IngestionSource,
    pub total_pages: usize,
    pub quarantine_path: Option<PathBuf>,
    pub status: DocumentStatus,
    pub parsed_page_count: usize,
    pub entities_extracted: usize,
    pub l2_memory_budget_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedDocument {
    pub document_id: String,
    pub pages: Vec<ParsedPage>,
    pub embedding_cache: Option<Vec<f32>>,
    pub entity_index: HashMap<String, Vec<EntityMention>>,
    pub l2_memory_used: u64,
    pub last_accessed_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedPage {
    pub page_num: usize,
    pub text: String,
    pub extracted_entities: Vec<Entity>,
    pub tokens_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    pub text: String,
    pub entity_type: String,
    pub confidence: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityMention {
    pub page_num: usize,
    pub start_char: usize,
    pub end_char: usize,
}
