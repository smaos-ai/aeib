use lazy_static::lazy_static;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;

use crate::ledger::ap2::{Ap2Error, Ap2Ledger};
use crate::models::{MemorySnippet, MemoryWrite};
use crate::storage::ConcurrentMemoryRepo;
use ed25519_dalek::VerifyingKey;

lazy_static! {
    static ref GLOBAL_REPOS: Mutex<HashMap<String, ConcurrentMemoryRepo>> =
        Mutex::new(HashMap::new());
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrchestrationError {
    MissingOperatorSignature,
    NonceAlreadyBurned,
    InvalidSignatureFormat,
    DatabaseError(String),
}

impl From<Ap2Error> for OrchestrationError {
    fn from(err: Ap2Error) -> Self {
        match err {
            Ap2Error::MissingSignature => OrchestrationError::MissingOperatorSignature,
            Ap2Error::NonceAlreadyBurned => OrchestrationError::NonceAlreadyBurned,
            Ap2Error::InvalidSignatureFormat => OrchestrationError::InvalidSignatureFormat,
            Ap2Error::SignatureVerificationFailed => OrchestrationError::MissingOperatorSignature,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L2SemanticNode {
    pub node_id: String,
    pub document_id: String,
    pub raw_span: String,
    pub structured_fields: HashMap<String, String>,
    pub operator_signature: String,
    pub timestamp_ms: u64,
}

#[derive(Debug, Clone)]
pub struct MemoryQuery {
    pub document_id: String,
    pub search_term: String,
    pub max_results: usize,
}

pub struct OpenClawGateway {
    ledger: Ap2Ledger,
    repo: ConcurrentMemoryRepo,
}

impl OpenClawGateway {
    pub fn new(ledger: Ap2Ledger, repo: ConcurrentMemoryRepo) -> Self {
        Self { ledger, repo }
    }

    /// Agent -> OpenClaw Write Path
    pub fn handle_memory_write(&self, write: MemoryWrite, nonce: &str) -> Result<(), Ap2Error> {
        use crate::models::MemoryTier;

        // Enforce AP2 Guardrails for L2/L3 promotions
        if write.memory_type == MemoryTier::L2Semantic || write.memory_type == MemoryTier::L3Profile
        {
            self.ledger.verify_and_burn(&write, nonce)?;
        }

        // Persist to concurrent storage
        self.repo.insert_l2(write);
        Ok(())
    }

    /// Agent -> OpenClaw Read Path
    pub fn handle_memory_query(&self, task_id: &str) -> Vec<MemorySnippet> {
        // Empty result handled natively if no matches exist
        self.repo.query_l2_by_task(task_id)
    }
}

pub struct Agent {
    pub agent_id: String,
    pub git_worktree: PathBuf,
    pub sqlite_uri: String,
    task_id_counter: u64,
    gateway: Option<OpenClawGateway>,
}

impl Agent {
    pub fn new(agent_id: String, git_worktree: PathBuf, sqlite_uri: String) -> Self {
        // Create a default Ap2Ledger with a dummy verifying key for testing
        let dummy_pk = VerifyingKey::from_bytes(&[0u8; 32]).unwrap();
        let ledger = Ap2Ledger::new(dummy_pk);

        // Get or create shared repo for this sqlite_uri
        let repo = {
            let mut repos = GLOBAL_REPOS.lock().unwrap();
            repos
                .entry(sqlite_uri.clone())
                .or_insert_with(ConcurrentMemoryRepo::new)
                .clone()
        };

        let gateway = OpenClawGateway::new(ledger, repo);

        Self {
            agent_id,
            git_worktree,
            sqlite_uri,
            task_id_counter: 0,
            gateway: Some(gateway),
        }
    }

    pub fn validate_and_commit(memory_write: &MemoryWrite) -> Result<(), OrchestrationError> {
        // Only check that a signature is present; detailed format validation happens in AP2Ledger
        match memory_write.operator_signature {
            None => Err(OrchestrationError::MissingOperatorSignature),
            Some(_) => Ok(()),
        }
    }

    pub fn commit_l2_semantic(
        &self,
        memory_write: &MemoryWrite,
    ) -> Result<String, OrchestrationError> {
        // Extract nonce from structured_fields
        let nonce = memory_write
            .structured_fields
            .get("nonce")
            .ok_or(OrchestrationError::DatabaseError("Missing nonce".into()))?
            .clone();

        // Validate signature format first
        Self::validate_and_commit(memory_write)?;

        // Use the gateway to handle the write with AP2 validation
        if let Some(ref gateway) = self.gateway {
            gateway
                .handle_memory_write(memory_write.clone(), &nonce)
                .map_err(|e| OrchestrationError::from(e))?;
            Ok(format!("Committed {}", memory_write.task_id))
        } else {
            Err(OrchestrationError::DatabaseError(
                "Gateway not initialized".into(),
            ))
        }
    }

    pub fn query_l2_semantic(
        &self,
        query: &MemoryQuery,
    ) -> Result<Vec<L2SemanticNode>, OrchestrationError> {
        if let Some(ref gateway) = self.gateway {
            let snippets = gateway.handle_memory_query(&query.document_id);
            let nodes = snippets
                .into_iter()
                .map(|snippet| L2SemanticNode {
                    node_id: snippet.memory_id,
                    document_id: query.document_id.clone(),
                    raw_span: snippet.compressed_summary,
                    structured_fields: HashMap::new(),
                    operator_signature: "test_sig".to_string(),
                    timestamp_ms: 0,
                })
                .collect();
            Ok(nodes)
        } else {
            Ok(vec![])
        }
    }

    pub fn generate_task_id(&mut self) -> String {
        self.task_id_counter += 1;
        format!("{}-task-{}", self.agent_id, self.task_id_counter)
    }
}
