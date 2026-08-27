//! L2: Knowledge layer with pgvector + BM25 + RRF hybrid search
//! EU AI Act policy compliance, semantic + keyword retrieval, <100ms latency target

pub mod database;
pub mod error;
pub mod search;

pub use database::KnowledgeDb;
pub use error::{L2AuditEntry, L2Error};
pub use search::{HybridSearcher, SearchResult};
