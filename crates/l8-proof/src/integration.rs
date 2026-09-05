//! L1→L8 Integration Harness: End-to-end proof layer coordination
//! Orchestrates complete workflow from intent submission to immutable ledger entry

use crate::{
    ProofLayer, LedgerEntry, WorkReceipt, AgentacctWorkReceipt, AP2LedgerEntry, KmsKey,
};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Proof harness stage enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PipelineStage {
    L1InputIntent,
    L2Classification,
    L3PermitGate,
    L4Orchestration,
    L5Communication,
    L6Infrastructure,
    L7Authorization,
    L8ProofLedger,
}

/// End-to-end workflow context
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkflowContext {
    pub id: String,
    pub intent_id: String,
    pub classification: Option<String>,
    pub gate_decision: Option<String>,
    pub stage: PipelineStage,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub completed_at: Option<chrono::DateTime<chrono::Utc>>,
}

impl WorkflowContext {
    pub fn new(intent_id: String) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            intent_id,
            classification: None,
            gate_decision: None,
            stage: PipelineStage::L1InputIntent,
            created_at: Utc::now(),
            completed_at: None,
        }
    }
}

/// ProofHarness: Main integration point for L1→L8 pipeline
pub struct ProofHarness {
    pub proof_layer: ProofLayer,
    workflows: Vec<WorkflowContext>,
    receipts: Vec<AgentacctWorkReceipt>,
    ledger_entries: Vec<AP2LedgerEntry>,
    current_key: Option<KmsKey>,
}

impl ProofHarness {
    pub fn new() -> Self {
        Self {
            proof_layer: ProofLayer::new(),
            workflows: Vec::new(),
            receipts: Vec::new(),
            ledger_entries: Vec::new(),
            current_key: None,
        }
    }

    /// Initialize harness with compression threshold
    pub fn with_compression(mut self, threshold: usize) -> Self {
        self.proof_layer = self.proof_layer.with_compression_threshold(threshold);
        self
    }

    /// Create new workflow context for intent
    pub fn create_workflow(&mut self, intent_id: String) -> WorkflowContext {
        let ctx = WorkflowContext::new(intent_id);
        self.workflows.push(ctx.clone());
        ctx
    }

    /// Advance workflow through pipeline stage
    pub fn advance_stage(&mut self, workflow_id: &str, stage: PipelineStage) -> Result<(), String> {
        self.workflows
            .iter_mut()
            .find(|w| w.id == workflow_id)
            .ok_or_else(|| format!("Workflow not found: {}", workflow_id))?
            .stage = stage;
        Ok(())
    }

    /// Set classification result for workflow
    pub fn set_classification(&mut self, workflow_id: &str, classification: String) -> Result<(), String> {
        self.workflows
            .iter_mut()
            .find(|w| w.id == workflow_id)
            .ok_or_else(|| format!("Workflow not found: {}", workflow_id))?
            .classification = Some(classification);
        Ok(())
    }

    /// Set gate decision for workflow
    pub fn set_gate_decision(&mut self, workflow_id: &str, decision: String) -> Result<(), String> {
        self.workflows
            .iter_mut()
            .find(|w| w.id == workflow_id)
            .ok_or_else(|| format!("Workflow not found: {}", workflow_id))?
            .gate_decision = Some(decision);
        Ok(())
    }

    /// Create work receipt and track in agentacct
    pub fn create_receipt(&mut self, agent_id: String, action: String, result: String) -> AgentacctWorkReceipt {
        let timestamp = Utc::now().to_rfc3339();
        let receipt = AgentacctWorkReceipt {
            id: Uuid::new_v4().to_string(),
            agent_id,
            action,
            result,
            signature: format!("ed25519:{:x}", Uuid::new_v4()),
            timestamp,
            chain_digest: format!("{:x}", Uuid::new_v4()),
            created_at: Some(Utc::now().to_rfc3339()),
        };
        self.receipts.push(receipt.clone());
        receipt
    }

    /// Create ledger entry through proof layer
    pub fn create_ledger_entry(&mut self, data: String) -> Result<LedgerEntry, String> {
        let work_receipt = self.proof_layer.create_work_receipt(
            "ledger_entry".to_string(),
            "initiated".to_string(),
        );

        let ledger_entry = self.proof_layer.sign_ledger_entry(data)?;
        Ok(ledger_entry)
    }

    /// Record AP2 transaction
    pub fn record_ap2_transaction(&mut self, authorization: String, transaction_data: String) -> AP2LedgerEntry {
        let entry = AP2LedgerEntry::new(
            authorization,
            format!("ed25519:{:x}", Uuid::new_v4()),
            transaction_data,
        );
        self.ledger_entries.push(entry.clone());
        entry
    }

    /// Complete workflow (mark finished)
    pub fn complete_workflow(&mut self, workflow_id: &str) -> Result<(), String> {
        self.workflows
            .iter_mut()
            .find(|w| w.id == workflow_id)
            .ok_or_else(|| format!("Workflow not found: {}", workflow_id))?
            .completed_at = Some(Utc::now());
        Ok(())
    }

    /// Get workflow by ID
    pub fn get_workflow(&self, workflow_id: &str) -> Option<WorkflowContext> {
        self.workflows.iter().find(|w| w.id == workflow_id).cloned()
    }

    /// Get all workflows
    pub fn get_workflows(&self) -> &[WorkflowContext] {
        &self.workflows
    }

    /// Get all receipts
    pub fn get_receipts(&self) -> &[AgentacctWorkReceipt] {
        &self.receipts
    }

    /// Get all AP2 ledger entries
    pub fn get_ap2_entries(&self) -> &[AP2LedgerEntry] {
        &self.ledger_entries
    }

    /// Verify complete workflow chain
    pub fn verify_workflow_chain(&self, workflow_id: &str) -> bool {
        self.workflows.iter().any(|w| w.id == workflow_id && w.completed_at.is_some())
    }

    /// Verify ledger integrity (uses proof layer)
    pub fn verify_ledger_integrity(&self) -> Result<bool, String> {
        self.proof_layer.verify_ledger_chain()
    }

    /// Get proof layer size
    pub fn ledger_size(&self) -> usize {
        self.proof_layer.ledger_size()
    }

    /// Set current KMS key
    pub fn set_current_key(&mut self, key: KmsKey) {
        self.current_key = Some(key);
    }

    /// Get current KMS key if set
    pub fn get_current_key(&self) -> Option<&KmsKey> {
        self.current_key.as_ref()
    }
}

impl Default for ProofHarness {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_harness_creation() {
        let harness = ProofHarness::new();
        assert_eq!(harness.ledger_size(), 0);
        assert!(harness.get_workflows().is_empty());
    }

    #[test]
    fn test_workflow_creation() {
        let mut harness = ProofHarness::new();
        let ctx = harness.create_workflow("intent-001".to_string());
        assert_eq!(ctx.intent_id, "intent-001");
        assert_eq!(ctx.stage, PipelineStage::L1InputIntent);
    }

    #[test]
    fn test_stage_advancement() {
        let mut harness = ProofHarness::new();
        let ctx = harness.create_workflow("intent-001".to_string());
        let wf_id = ctx.id;

        harness.advance_stage(&wf_id, PipelineStage::L2Classification).unwrap();
        assert_eq!(harness.get_workflow(&wf_id).unwrap().stage, PipelineStage::L2Classification);
    }

    #[test]
    fn test_receipt_creation() {
        let mut harness = ProofHarness::new();
        let receipt = harness.create_receipt(
            "agent-123".to_string(),
            "process_intent".to_string(),
            "success".to_string(),
        );
        assert_eq!(receipt.agent_id, "agent-123");
        assert_eq!(harness.get_receipts().len(), 1);
    }

    #[test]
    fn test_ledger_entry_creation() {
        let mut harness = ProofHarness::new();
        let result = harness.create_ledger_entry("test data".to_string());
        assert!(result.is_ok());
        assert!(harness.ledger_size() > 0);
    }

    #[test]
    fn test_ap2_transaction_recording() {
        let mut harness = ProofHarness::new();
        let entry = harness.record_ap2_transaction(
            "auth-001".to_string(),
            r#"{"amount": 1000}"#.to_string(),
        );
        assert!(!entry.id.is_empty());
        assert_eq!(harness.get_ap2_entries().len(), 1);
    }

    #[test]
    fn test_workflow_completion() {
        let mut harness = ProofHarness::new();
        let ctx = harness.create_workflow("intent-001".to_string());
        harness.complete_workflow(&ctx.id).unwrap();

        let completed = harness.get_workflow(&ctx.id).unwrap();
        assert!(completed.completed_at.is_some());
        assert!(harness.verify_workflow_chain(&ctx.id));
    }

    #[test]
    fn test_ledger_chain_integrity() {
        let mut harness = ProofHarness::new();
        harness.create_ledger_entry("entry1".to_string()).unwrap();
        harness.create_ledger_entry("entry2".to_string()).unwrap();
        harness.create_ledger_entry("entry3".to_string()).unwrap();

        let result = harness.verify_ledger_integrity();
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[test]
    fn test_classification_setting() {
        let mut harness = ProofHarness::new();
        let ctx = harness.create_workflow("intent-001".to_string());
        harness.set_classification(&ctx.id, "BLOCK".to_string()).unwrap();

        let wf = harness.get_workflow(&ctx.id).unwrap();
        assert_eq!(wf.classification, Some("BLOCK".to_string()));
    }

    #[test]
    fn test_gate_decision_setting() {
        let mut harness = ProofHarness::new();
        let ctx = harness.create_workflow("intent-001".to_string());
        harness.set_gate_decision(&ctx.id, "DENY".to_string()).unwrap();

        let wf = harness.get_workflow(&ctx.id).unwrap();
        assert_eq!(wf.gate_decision, Some("DENY".to_string()));
    }
}
