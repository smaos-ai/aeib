/// Phase 36: Resumable Cognitive Execution (RCE)
///
/// Core state machine for human-in-the-loop agentic orchestration.
/// Enables agents to pause on critical intelligence projections, await
/// human approval, and resume with preserved context.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

// =====================================================================
// STATE MACHINE TYPES
// =====================================================================

/// RCE execution state
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ExecutionState {
    Idle,
    Perform,
    Paused,
    Resumed,
}

/// A single step in a workflow
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Step {
    pub id: Uuid,
    pub name: String,
    pub timeout_ms: u64,
    pub idempotent: bool,
}

/// Checkpoint captures execution state at pause point
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Checkpoint {
    pub step_index: usize,
    pub state_snapshot: Vec<u8>,
    pub timestamp: DateTime<Utc>,
    pub reason: String,
    pub checksum: String,
    pub version: usize,
}

/// Event in the audit trail
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    pub id: Uuid,
    pub event_type: String,
    pub timestamp: DateTime<Utc>,
    pub step_id: Option<Uuid>,
    pub details: serde_json::Value,
}

/// Human decision on paused workflow
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HumanDecision {
    Approve,
    Reject { reason: String },
    Modify { new_plan: Vec<Step> },
}

/// Interrupt signal from π+ projections
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InterruptSignal {
    pub workflow_id: Uuid,
    pub severity: String,
    pub reason: String,
    pub human_approval_required: bool,
    pub timestamp: DateTime<Utc>,
}

/// Core Resumable Cognitive Execution state machine
#[derive(Debug, Serialize, Deserialize)]
pub struct ResumableCognitiveExecution {
    pub workflow_id: Uuid,
    pub state: ExecutionState,
    pub plan: Vec<Step>,
    pub current_step_index: usize,
    pub checkpoint: Option<Checkpoint>,
    pub history: Vec<Event>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    #[serde(skip)]
    pub executed_non_idempotent_steps: std::collections::HashSet<Uuid>,
}

impl ResumableCognitiveExecution {
    /// Create a new RCE instance in Idle state
    pub fn new(workflow_id: Uuid) -> Self {
        Self {
            workflow_id,
            state: ExecutionState::Idle,
            plan: Vec::new(),
            current_step_index: 0,
            checkpoint: None,
            history: Vec::new(),
            created_at: Utc::now(),
            updated_at: Utc::now(),
            executed_non_idempotent_steps: std::collections::HashSet::new(),
        }
    }

    /// Start workflow: Idle → Perform
    pub fn start_workflow(&mut self, plan: Vec<Step>) -> Result<(), String> {
        if self.state != ExecutionState::Idle {
            return Err(format!("Cannot start workflow in {:?} state", self.state));
        }

        if plan.is_empty() {
            return Err("Plan cannot be empty".to_string());
        }

        self.plan = plan;
        self.current_step_index = 0;
        self.state = ExecutionState::Perform;
        self.updated_at = Utc::now();

        // Record event
        self.history.push(Event {
            id: Uuid::new_v4(),
            event_type: "workflow_started".to_string(),
            timestamp: Utc::now(),
            step_id: None,
            details: serde_json::json!({
                "workflow_id": self.workflow_id,
                "step_count": self.plan.len(),
            }),
        });

        Ok(())
    }

    /// Pause workflow: Perform → Paused
    pub fn pause_workflow(
        &mut self,
        interrupt_signal: InterruptSignal,
        state_snapshot: Vec<u8>,
    ) -> Result<(), String> {
        if self.state != ExecutionState::Perform {
            return Err(format!(
                "Cannot pause workflow in {:?} state",
                self.state
            ));
        }

        // Compute checksum
        let checksum = self.compute_checksum(&state_snapshot);

        self.checkpoint = Some(Checkpoint {
            step_index: self.current_step_index,
            state_snapshot,
            timestamp: Utc::now(),
            reason: interrupt_signal.reason.clone(),
            checksum,
            version: 1,
        });

        self.state = ExecutionState::Paused;
        self.updated_at = Utc::now();

        // Record event
        self.history.push(Event {
            id: Uuid::new_v4(),
            event_type: "workflow_paused".to_string(),
            timestamp: Utc::now(),
            step_id: Some(self.plan[self.current_step_index].id),
            details: serde_json::json!({
                "reason": interrupt_signal.reason,
                "severity": interrupt_signal.severity,
            }),
        });

        Ok(())
    }

    /// Resume workflow: Paused → Resumed (Approve path)
    pub fn resume_workflow_approve(&mut self) -> Result<(), String> {
        if self.state != ExecutionState::Paused {
            return Err(format!(
                "Cannot resume workflow in {:?} state",
                self.state
            ));
        }

        // Validate checkpoint exists and integrity
        let checkpoint = self.checkpoint.as_ref().ok_or("No checkpoint found")?;
        let computed_checksum = self.compute_checksum(&checkpoint.state_snapshot);
        if computed_checksum != checkpoint.checksum {
            return Err("Checkpoint checksum mismatch".to_string());
        }

        self.state = ExecutionState::Resumed;
        self.current_step_index = checkpoint.step_index;
        self.updated_at = Utc::now();

        // Record event
        self.history.push(Event {
            id: Uuid::new_v4(),
            event_type: "workflow_resumed".to_string(),
            timestamp: Utc::now(),
            step_id: Some(self.plan[self.current_step_index].id),
            details: serde_json::json!({
                "decision": "approve",
            }),
        });

        Ok(())
    }

    /// Resume workflow: Paused → Idle (Reject path)
    pub fn resume_workflow_reject(&mut self, reason: String) -> Result<(), String> {
        if self.state != ExecutionState::Paused {
            return Err(format!(
                "Cannot reject workflow in {:?} state",
                self.state
            ));
        }

        // Clear checkpoint and reset
        self.checkpoint = None;
        self.state = ExecutionState::Idle;
        self.current_step_index = 0;
        self.updated_at = Utc::now();

        // Record event
        self.history.push(Event {
            id: Uuid::new_v4(),
            event_type: "workflow_rejected".to_string(),
            timestamp: Utc::now(),
            step_id: None,
            details: serde_json::json!({
                "reason": reason,
            }),
        });

        Ok(())
    }

    /// Resume workflow: Paused → Resumed (Modify path)
    pub fn resume_workflow_modify(&mut self, new_plan: Vec<Step>) -> Result<(), String> {
        if self.state != ExecutionState::Paused {
            return Err(format!(
                "Cannot modify workflow in {:?} state",
                self.state
            ));
        }

        if new_plan.is_empty() {
            return Err("Modified plan cannot be empty".to_string());
        }

        // Validate checkpoint
        let checkpoint = self.checkpoint.as_ref().ok_or("No checkpoint found")?;
        let computed_checksum = self.compute_checksum(&checkpoint.state_snapshot);
        if computed_checksum != checkpoint.checksum {
            return Err("Checkpoint checksum mismatch".to_string());
        }

        // Merge new plan with existing
        self.plan = new_plan;
        self.state = ExecutionState::Resumed;
        self.current_step_index = checkpoint.step_index;
        self.updated_at = Utc::now();

        // Record event
        self.history.push(Event {
            id: Uuid::new_v4(),
            event_type: "workflow_resumed".to_string(),
            timestamp: Utc::now(),
            step_id: Some(self.plan[self.current_step_index].id),
            details: serde_json::json!({
                "decision": "modify",
                "new_step_count": self.plan.len(),
            }),
        });

        Ok(())
    }

    /// Execute next step (for testing state transitions)
    pub fn execute_next_step(&mut self) -> Result<(), String> {
        if self.state != ExecutionState::Perform && self.state != ExecutionState::Resumed {
            return Err(format!(
                "Cannot execute step in {:?} state",
                self.state
            ));
        }

        if self.current_step_index >= self.plan.len() {
            // Workflow complete
            self.state = ExecutionState::Idle;
            self.history.push(Event {
                id: Uuid::new_v4(),
                event_type: "workflow_completed".to_string(),
                timestamp: Utc::now(),
                step_id: None,
                details: serde_json::json!({
                    "total_steps": self.plan.len(),
                }),
            });
            return Ok(());
        }

        let step = &self.plan[self.current_step_index];

        // Record step execution
        self.history.push(Event {
            id: Uuid::new_v4(),
            event_type: "step_executed".to_string(),
            timestamp: Utc::now(),
            step_id: Some(step.id),
            details: serde_json::json!({
                "step_index": self.current_step_index,
                "step_name": step.name,
            }),
        });

        self.current_step_index += 1;
        self.updated_at = Utc::now();
        Ok(())
    }

    /// Compute SHA-256 checksum of state snapshot
    fn compute_checksum(&self, data: &[u8]) -> String {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(data);
        format!("{:x}", hasher.finalize())
    }

    /// Get current state
    pub fn get_state(&self) -> ExecutionState {
        self.state
    }

    /// Get current step index
    pub fn get_current_step_index(&self) -> usize {
        self.current_step_index
    }

    /// Get full audit trail
    pub fn get_history(&self) -> &[Event] {
        &self.history
    }

    /// Check if checkpoint exists
    pub fn has_checkpoint(&self) -> bool {
        self.checkpoint.is_some()
    }

    /// Check interrupt from threat anticipation (π+_TA)
    /// Returns InterruptSignal if tokens_at_risk exceeds threshold
    pub fn check_threat_anticipation_interrupt(
        &self,
        tokens_at_risk: i64,
        threshold: i64,
    ) -> Option<InterruptSignal> {
        if tokens_at_risk > threshold {
            Some(InterruptSignal {
                workflow_id: self.workflow_id,
                severity: "High".to_string(),
                reason: format!(
                    "threat_anticipation_blast_radius_high: {} tokens at risk (threshold: {})",
                    tokens_at_risk, threshold
                ),
                human_approval_required: true,
                timestamp: Utc::now(),
            })
        } else {
            None
        }
    }

    /// Check interrupt from root cause discovery (π+_RC)
    /// Returns InterruptSignal if confidence exceeds threshold
    pub fn check_root_cause_interrupt(
        &self,
        confidence: f64,
        threshold: f64,
    ) -> Option<InterruptSignal> {
        if confidence > threshold {
            Some(InterruptSignal {
                workflow_id: self.workflow_id,
                severity: "Critical".to_string(),
                reason: format!(
                    "root_cause_discovered: confidence {:.2} exceeds threshold {:.2}",
                    confidence, threshold
                ),
                human_approval_required: true,
                timestamp: Utc::now(),
            })
        } else {
            None
        }
    }

    /// Check interrupt from SWOT degradation (π+_SWOT)
    /// Returns InterruptSignal if diversity_index falls below threshold
    pub fn check_swot_degradation_interrupt(
        &self,
        diversity_index: f64,
        threshold: f64,
    ) -> Option<InterruptSignal> {
        if diversity_index < threshold {
            Some(InterruptSignal {
                workflow_id: self.workflow_id,
                severity: "High".to_string(),
                reason: format!(
                    "swot_scenario_degradation: diversity index {:.2} below threshold {:.2}",
                    diversity_index, threshold
                ),
                human_approval_required: true,
                timestamp: Utc::now(),
            })
        } else {
            None
        }
    }

    /// Get severity level as numeric priority (higher = more urgent)
    pub fn severity_priority(severity: &str) -> u32 {
        match severity {
            "Critical" => 4,
            "High" => 3,
            "Medium" => 2,
            "Low" => 1,
            _ => 0,
        }
    }

    /// Sort interrupts by severity (Critical first)
    pub fn sort_interrupts_by_severity(interrupts: &mut [InterruptSignal]) {
        interrupts.sort_by(|a, b| {
            Self::severity_priority(&b.severity)
                .cmp(&Self::severity_priority(&a.severity))
        });
    }

    /// Verify checkpoint integrity: checksum and version match
    pub fn verify_checkpoint_integrity(
        &self,
        checkpoint: &Checkpoint,
        expected_version: usize,
    ) -> Result<(), String> {
        // Check version
        if checkpoint.version != expected_version {
            return Err(format!(
                "Checkpoint version mismatch: got {}, expected {}",
                checkpoint.version, expected_version
            ));
        }

        // Check checksum
        let computed_checksum = self.compute_checksum(&checkpoint.state_snapshot);
        if computed_checksum != checkpoint.checksum {
            return Err("Checkpoint checksum mismatch: data may be corrupted".to_string());
        }

        Ok(())
    }

    /// Serialize RCE state to JSON bytes
    pub fn serialize_state(&self) -> Result<Vec<u8>, String> {
        serde_json::to_vec(&self)
            .map_err(|e| format!("Serialization failed: {}", e))
    }

    /// Deserialize RCE state from JSON bytes
    pub fn deserialize_state(data: &[u8]) -> Result<Self, String> {
        serde_json::from_slice(data)
            .map_err(|e| format!("Deserialization failed: {}", e))
    }

    /// Check if a step is safe to execute (idempotent or not yet executed)
    pub fn is_step_safe_to_execute(&self, step: &Step) -> bool {
        if step.idempotent {
            true
        } else {
            !self.executed_non_idempotent_steps.contains(&step.id)
        }
    }

    /// Mark a non-idempotent step as executed
    pub fn mark_step_executed(&mut self, step_id: Uuid) {
        self.executed_non_idempotent_steps.insert(step_id);
    }

    /// Check for resource exhaustion based on heap usage
    pub fn check_resource_exhaustion(&self, heap_usage_percent: f64, threshold: f64) -> bool {
        heap_usage_percent > threshold
    }

    /// Trigger resource exhaustion interrupt if needed
    pub fn check_resource_exhaustion_interrupt(
        &self,
        heap_usage_percent: f64,
        threshold: f64,
    ) -> Option<InterruptSignal> {
        if self.check_resource_exhaustion(heap_usage_percent, threshold) {
            Some(InterruptSignal {
                workflow_id: self.workflow_id,
                severity: "High".to_string(),
                reason: format!(
                    "resource_exhaustion: heap usage {:.1}% exceeds threshold {:.1}%",
                    heap_usage_percent, threshold
                ),
                human_approval_required: true,
                timestamp: Utc::now(),
            })
        } else {
            None
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_rce_starts_in_idle() {
        let rce = ResumableCognitiveExecution::new(Uuid::new_v4());
        assert_eq!(rce.state, ExecutionState::Idle);
        assert_eq!(rce.current_step_index, 0);
        assert!(rce.checkpoint.is_none());
    }

    #[test]
    fn test_start_workflow_transitions_to_perform() {
        let mut rce = ResumableCognitiveExecution::new(Uuid::new_v4());
        let plan = vec![Step {
            id: Uuid::new_v4(),
            name: "step_1".to_string(),
            timeout_ms: 1000,
            idempotent: true,
        }];

        rce.start_workflow(plan).unwrap();
        assert_eq!(rce.state, ExecutionState::Perform);
        assert_eq!(rce.current_step_index, 0);
    }

    #[test]
    fn test_pause_creates_checkpoint() {
        let mut rce = ResumableCognitiveExecution::new(Uuid::new_v4());
        let plan = vec![Step {
            id: Uuid::new_v4(),
            name: "step_1".to_string(),
            timeout_ms: 1000,
            idempotent: true,
        }];

        rce.start_workflow(plan).unwrap();

        let snapshot = vec![1, 2, 3, 4, 5];
        let signal = InterruptSignal {
            workflow_id: rce.workflow_id,
            severity: "High".to_string(),
            reason: "test_interrupt".to_string(),
            human_approval_required: true,
            timestamp: Utc::now(),
        };

        rce.pause_workflow(signal, snapshot).unwrap();
        assert_eq!(rce.state, ExecutionState::Paused);
        assert!(rce.checkpoint.is_some());
    }
}
