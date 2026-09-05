/// Phase 2B Part 1: @Evidence Agent (400 LOC)
/// Monitors swarm coordinator execution trace
/// Writes Merkle-signed receipts to l8-proof ledger
/// Queries l2-knowledge (pgvector) for compliance precedents

pub mod a2a_handler;

use anyhow::Result;
use chrono::{DateTime, Utc};
use ed25519_dalek::{SigningKey, Signer};
use serde::{Deserialize, Serialize};
use siss_a2a_ipc::{A2AMessage, IPCConfig, LocalIPCClient, MessageType};
use sha2::{Digest, Sha256};
use std::sync::Arc;
use uuid::Uuid;

/// Execution trace event from swarm coordinator
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionTraceEvent {
    pub event_id: Uuid,
    pub step_index: usize,
    pub action: String,
    pub result: String,
    pub timestamp: DateTime<Utc>,
}

/// Merkle proof receipt — immutable evidence of execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MerkleReceipt {
    pub receipt_id: Uuid,
    pub plan_id: Uuid,
    pub evaluation_id: Uuid,
    pub trace_hash: String, // SHA256 of execution trace
    pub merkle_root: String, // Merkle tree root of all events
    pub proof_chain: Vec<String>, // Merkle proof path for verification
    pub signature: String, // Ed25519 signature over merkle_root
    pub created_at: DateTime<Utc>,
}

/// Incoming evaluation from @Compliance
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IncomingEvaluation {
    pub evaluation_id: Uuid,
    pub plan_id: Uuid,
    pub verdict: String,
    pub triggered_gates: Vec<String>,
}

/// Compliance precedent from l2-knowledge (pgvector)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompliancePrecedent {
    pub precedent_id: Uuid,
    pub rule_name: String,
    pub case_reference: String,
    pub embedding: Vec<f32>, // pgvector embedding
    pub similarity_score: f32,
}

/// @Evidence Agent — collects traces, generates Merkle proofs, writes ledger
#[derive(Clone)]
pub struct EvidenceAgent {
    pub agent_id: Uuid,
    pub signing_key: SigningKey,
    pub ipc_client: Arc<LocalIPCClient>,
    pub execution_traces: Vec<ExecutionTraceEvent>,
}

impl EvidenceAgent {
    pub fn new(signing_key: SigningKey) -> Self {
        let agent_id = Uuid::new_v4();
        let ipc_config = IPCConfig::default();
        let signing_key_copy = SigningKey::from_bytes(signing_key.as_bytes());
        Self {
            agent_id,
            signing_key,
            ipc_client: Arc::new(LocalIPCClient::new(ipc_config, signing_key_copy, agent_id)),
            execution_traces: Vec::new(),
        }
    }

    pub async fn process_evaluation(&mut self, evaluation: &IncomingEvaluation) -> Result<()> {
        log::info!(
            "@Evidence: processing evaluation {} for plan {}",
            evaluation.evaluation_id,
            evaluation.plan_id
        );

        // Step 1: Collect execution traces (would come from swarm coordinator)
        self.collect_traces(evaluation).await?;

        // Step 2: Query compliance precedents from l2-knowledge
        let precedents = self.query_compliance_precedents(&evaluation.triggered_gates).await?;
        log::debug!(
            "@Evidence: found {} compliance precedents",
            precedents.len()
        );

        // Step 3: Generate Merkle proof
        let receipt = self.generate_merkle_proof(evaluation, &self.execution_traces).await?;

        // Step 4: Write receipt to l8-proof ledger
        self.write_to_ledger(&receipt).await?;

        Ok(())
    }

    async fn collect_traces(&mut self, evaluation: &IncomingEvaluation) -> Result<()> {
        log::debug!(
            "Collecting execution traces for evaluation {}",
            evaluation.evaluation_id
        );

        // Stub: in production, would query siss-swarm-coordinator for trace
        let traces = vec![
            ExecutionTraceEvent {
                event_id: Uuid::new_v4(),
                step_index: 0,
                action: "Initialize evaluation".to_string(),
                result: "success".to_string(),
                timestamp: Utc::now(),
            },
            ExecutionTraceEvent {
                event_id: Uuid::new_v4(),
                step_index: 1,
                action: "Load policies".to_string(),
                result: "success".to_string(),
                timestamp: Utc::now(),
            },
            ExecutionTraceEvent {
                event_id: Uuid::new_v4(),
                step_index: 2,
                action: "Evaluate compliance".to_string(),
                result: evaluation.verdict.clone(),
                timestamp: Utc::now(),
            },
        ];

        self.execution_traces = traces;
        Ok(())
    }

    async fn query_compliance_precedents(&self, gates: &[String]) -> Result<Vec<CompliancePrecedent>> {
        log::debug!("Querying l2-knowledge for {} compliance gates", gates.len());

        // Stub: in production, would query pgvector
        let precedents = vec![
            CompliancePrecedent {
                precedent_id: Uuid::new_v4(),
                rule_name: "BaselIII_CAR".to_string(),
                case_reference: "ECB/2023/001".to_string(),
                embedding: vec![0.1, 0.2, 0.3],
                similarity_score: 0.95,
            },
            CompliancePrecedent {
                precedent_id: Uuid::new_v4(),
                rule_name: "EU_AI_Act".to_string(),
                case_reference: "EDPB/2024/015".to_string(),
                embedding: vec![0.4, 0.5, 0.6],
                similarity_score: 0.87,
            },
        ];

        Ok(precedents)
    }

    async fn generate_merkle_proof(
        &self,
        evaluation: &IncomingEvaluation,
        traces: &[ExecutionTraceEvent],
    ) -> Result<MerkleReceipt> {
        log::debug!(
            "Generating Merkle proof for {} trace events",
            traces.len()
        );

        // Step 1: Compute trace hash
        let trace_bytes = serde_json::to_vec(traces)?;
        let mut hasher = Sha256::new();
        hasher.update(&trace_bytes);
        let trace_hash = hex::encode(hasher.finalize());

        // Step 2: Build Merkle tree (stub: simple implementation)
        let mut leaf_hashes: Vec<String> = traces
            .iter()
            .map(|t| {
                let mut h = Sha256::new();
                h.update(serde_json::to_vec(t).unwrap_or_default());
                hex::encode(h.finalize())
            })
            .collect();

        // Build tree from bottom up
        while leaf_hashes.len() > 1 {
            let mut next_level = Vec::new();
            for pair in leaf_hashes.chunks(2) {
                let mut h = Sha256::new();
                h.update(&pair[0]);
                if pair.len() > 1 {
                    h.update(&pair[1]);
                }
                next_level.push(hex::encode(h.finalize()));
            }
            leaf_hashes = next_level;
        }

        let merkle_root = leaf_hashes.first().cloned().unwrap_or_default();

        // Step 3: Sign root with Ed25519
        let signature = self.signing_key.sign(merkle_root.as_bytes());
        let signature_hex = hex::encode(signature.to_bytes());

        // Step 4: Create receipt
        let receipt = MerkleReceipt {
            receipt_id: Uuid::new_v4(),
            plan_id: evaluation.plan_id,
            evaluation_id: evaluation.evaluation_id,
            trace_hash,
            merkle_root,
            proof_chain: vec!["proof_0".to_string(), "proof_1".to_string()],
            signature: signature_hex,
            created_at: Utc::now(),
        };

        log::debug!(
            "@Evidence: Merkle root: {}, signature: {}",
            receipt.merkle_root,
            receipt.signature
        );

        Ok(receipt)
    }

    async fn write_to_ledger(&self, receipt: &MerkleReceipt) -> Result<()> {
        log::info!(
            "@Evidence: writing receipt {} to l8-proof ledger",
            receipt.receipt_id
        );

        // Stub: in production, would write to l8-proof ledger
        // This would involve executing a database INSERT with the Merkle receipt

        // Log the ledger entry
        log::debug!(
            "Ledger entry: receipt_id={}, merkle_root={}, signature={}",
            receipt.receipt_id,
            receipt.merkle_root,
            receipt.signature
        );

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_merkle_receipt_creation() {
        let receipt = MerkleReceipt {
            receipt_id: Uuid::new_v4(),
            plan_id: Uuid::new_v4(),
            evaluation_id: Uuid::new_v4(),
            trace_hash: "abc123".to_string(),
            merkle_root: "def456".to_string(),
            proof_chain: vec!["proof_0".to_string()],
            signature: "sig_xyz".to_string(),
            created_at: Utc::now(),
        };
        assert!(!receipt.signature.is_empty());
        assert!(!receipt.merkle_root.is_empty());
    }

    #[test]
    fn test_execution_trace_event() {
        let event = ExecutionTraceEvent {
            event_id: Uuid::new_v4(),
            step_index: 0,
            action: "test_action".to_string(),
            result: "success".to_string(),
            timestamp: Utc::now(),
        };
        assert_eq!(event.step_index, 0);
        assert_eq!(event.result, "success");
    }

    #[test]
    fn test_compliance_precedent() {
        let precedent = CompliancePrecedent {
            precedent_id: Uuid::new_v4(),
            rule_name: "test_rule".to_string(),
            case_reference: "CASE/2023/001".to_string(),
            embedding: vec![0.1, 0.2, 0.3],
            similarity_score: 0.95,
        };
        assert_eq!(precedent.similarity_score, 0.95);
        assert_eq!(precedent.embedding.len(), 3);
    }

    #[tokio::test]
    async fn test_trace_collection() {
        let secret_key_bytes = [42u8; 32];
        let signing_key = SigningKey::from_bytes(&secret_key_bytes);
        let mut agent = EvidenceAgent::new(signing_key);
        let evaluation = IncomingEvaluation {
            evaluation_id: Uuid::new_v4(),
            plan_id: Uuid::new_v4(),
            verdict: "Approved".to_string(),
            triggered_gates: vec![],
        };
        agent.collect_traces(&evaluation).await.unwrap();
        assert!(!agent.execution_traces.is_empty());
    }

    #[tokio::test]
    async fn test_merkle_proof_generation() {
        let secret_key_bytes = [42u8; 32];
        let signing_key = SigningKey::from_bytes(&secret_key_bytes);
        let agent = EvidenceAgent::new(signing_key);
        let evaluation = IncomingEvaluation {
            evaluation_id: Uuid::new_v4(),
            plan_id: Uuid::new_v4(),
            verdict: "Approved".to_string(),
            triggered_gates: vec![],
        };
        let traces = vec![
            ExecutionTraceEvent {
                event_id: Uuid::new_v4(),
                step_index: 0,
                action: "test".to_string(),
                result: "ok".to_string(),
                timestamp: Utc::now(),
            },
        ];
        let receipt = agent
            .generate_merkle_proof(&evaluation, &traces)
            .await
            .unwrap();
        assert!(!receipt.signature.is_empty());
        assert!(!receipt.merkle_root.is_empty());
    }
}
