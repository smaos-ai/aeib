use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisMandate {
    pub mandate_id: String,
    pub document_id: String,
    pub analysis_type: AnalysisType,
    pub assigned_agent: String,
    pub nonce: String,
    pub timestamp_ms: u64,
    pub ttl_ms: u64,
    pub operator_did: Vec<u8>,
    pub signature: Vec<u8>,
    pub status: MandateStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AnalysisType {
    EntityExtraction,
    SemanticSearch { query: String },
    SummaryGeneration,
    ComplianceCheck,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum MandateStatus {
    Pending,
    Authorized,
    Executing,
    Completed { result: String },
    Failed { reason: String },
}
