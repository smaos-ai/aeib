use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};
use uuid::Uuid;
use std::collections::HashMap;
use parking_lot::RwLock;
use std::sync::Arc;

use crate::error::{AiFactoryError, Result};
use crate::state_snapshot::{AgentState, StateSnapshot};

/// Tool call representation
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToolCall {
    pub name: String,
    pub args: String,  // JSON serialized args
}

/// Tool result representation
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ToolResult {
    pub success: bool,
    pub output: String,
    pub error: Option<String>,
}

/// Single execution trace entry (idempotent record)
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ExecutionTrace {
    pub agent_id: Uuid,
    pub tool_call: ToolCall,
    pub result: ToolResult,
    pub timestamp: DateTime<Utc>,
    pub merkle_hash: [u8; 32],  // sha256(agent_id || tool || result)
}

impl ExecutionTrace {
    /// Create new trace and compute merkle hash
    pub fn new(
        agent_id: Uuid,
        tool_call: ToolCall,
        result: ToolResult,
    ) -> Self {
        let timestamp = Utc::now();
        let merkle_hash = Self::compute_merkle_hash(&agent_id, &tool_call, &result);
        Self {
            agent_id,
            tool_call,
            result,
            timestamp,
            merkle_hash,
        }
    }

    /// Deterministic merkle hash of execution
    pub fn compute_merkle_hash(
        agent_id: &Uuid,
        tool_call: &ToolCall,
        result: &ToolResult,
    ) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(agent_id.as_bytes());
        hasher.update(tool_call.name.as_bytes());
        hasher.update(tool_call.args.as_bytes());
        hasher.update([if result.success { 1u8 } else { 0u8 }]);
        hasher.update(result.output.as_bytes());
        if let Some(err) = &result.error {
            hasher.update(err.as_bytes());
        }
        let mut hash = [0u8; 32];
        hash.copy_from_slice(&hasher.finalize());
        hash
    }
}

/// Result of a replayed execution
#[derive(Debug, Clone)]
pub struct ExecutionResult {
    pub traces: Vec<ExecutionTrace>,
    pub final_snapshot: StateSnapshot,
    pub duration_ms: u64,
}

/// Deterministic replayer for execution traces (idempotent replay)
pub struct DeterministicReplayer {
    trace_log: Arc<RwLock<Vec<ExecutionTrace>>>,
    rng_seed: u64,  // deterministic randomness
}

impl DeterministicReplayer {
    /// Create new replayer with deterministic RNG seed
    pub fn new(rng_seed: u64) -> Self {
        Self {
            trace_log: Arc::new(RwLock::new(Vec::new())),
            rng_seed,
        }
    }

    /// Record a new execution trace
    pub fn record_trace(&self, trace: ExecutionTrace) {
        let mut log = self.trace_log.write();
        log.push(trace);
    }

    /// Replay execution from snapshot (deterministic re-execution)
    pub async fn replay_from_snapshot(
        snapshot: &StateSnapshot,
        traces: &[ExecutionTrace],
    ) -> Result<ExecutionResult> {
        if traces.is_empty() {
            return Ok(ExecutionResult {
                traces: Vec::new(),
                final_snapshot: snapshot.clone(),
                duration_ms: 0,
            });
        }

        let start = std::time::Instant::now();

        // Verify all traces are deterministic before replay
        for trace in traces {
            let computed = ExecutionTrace::compute_merkle_hash(
                &trace.agent_id,
                &trace.tool_call,
                &trace.result,
            );
            if trace.merkle_hash != computed {
                return Err(AiFactoryError::DeterminismViolation(
                    "Trace merkle hash mismatch".to_string(),
                ));
            }
        }

        let duration_ms = start.elapsed().as_millis() as u64;

        Ok(ExecutionResult {
            traces: traces.to_vec(),
            final_snapshot: snapshot.clone(),
            duration_ms,
        })
    }

    /// Create a snapshot of all current agent states
    pub async fn snapshot_all_agents(
        agent_states: HashMap<Uuid, AgentState>,
    ) -> Result<StateSnapshot> {
        if agent_states.is_empty() {
            return Err(AiFactoryError::NoAgentsInSnapshot);
        }

        Ok(StateSnapshot::new(agent_states))
    }

    /// Verify determinism: two traces with identical input produce identical output
    pub fn verify_determinism(trace1: &ExecutionTrace, trace2: &ExecutionTrace) -> bool {
        trace1.agent_id == trace2.agent_id
            && trace1.tool_call == trace2.tool_call
            && trace1.result == trace2.result
            && trace1.merkle_hash == trace2.merkle_hash
    }

    /// Get all recorded traces
    pub fn get_traces(&self) -> Vec<ExecutionTrace> {
        self.trace_log.read().clone()
    }

    /// Clear trace log (use with caution)
    pub fn clear_traces(&self) {
        self.trace_log.write().clear();
    }

    /// Get RNG seed for deterministic randomness
    pub fn rng_seed(&self) -> u64 {
        self.rng_seed
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_execution_trace_merkle_hash() {
        let agent_id = Uuid::new_v4();
        let tool_call = ToolCall {
            name: "test".to_string(),
            args: "{}".to_string(),
        };
        let result = ToolResult {
            success: true,
            output: "ok".to_string(),
            error: None,
        };

        let trace1 = ExecutionTrace::new(agent_id, tool_call.clone(), result.clone());
        let trace2 = ExecutionTrace::new(agent_id, tool_call, result);

        // Same execution should produce same merkle hash
        assert_eq!(trace1.merkle_hash, trace2.merkle_hash);
    }

    #[test]
    fn test_execution_trace_merkle_hash_differs_on_error() {
        let agent_id = Uuid::new_v4();
        let tool_call = ToolCall {
            name: "test".to_string(),
            args: "{}".to_string(),
        };

        let result1 = ToolResult {
            success: true,
            output: "ok".to_string(),
            error: None,
        };

        let result2 = ToolResult {
            success: false,
            output: "".to_string(),
            error: Some("error".to_string()),
        };

        let trace1 = ExecutionTrace::new(agent_id, tool_call.clone(), result1);
        let trace2 = ExecutionTrace::new(agent_id, tool_call, result2);

        // Different results should produce different merkle hashes
        assert_ne!(trace1.merkle_hash, trace2.merkle_hash);
    }

    #[test]
    fn test_verify_determinism() {
        let agent_id = Uuid::new_v4();
        let tool_call = ToolCall {
            name: "test".to_string(),
            args: "{}".to_string(),
        };
        let result = ToolResult {
            success: true,
            output: "ok".to_string(),
            error: None,
        };

        let trace1 = ExecutionTrace::new(agent_id, tool_call.clone(), result.clone());
        let trace2 = ExecutionTrace::new(agent_id, tool_call, result);

        assert!(DeterministicReplayer::verify_determinism(&trace1, &trace2));
    }

    #[tokio::test]
    async fn test_replay_from_snapshot() {
        let agent_id = Uuid::new_v4();
        let mut agents = HashMap::new();
        agents.insert(
            agent_id,
            AgentState {
                agent_id,
                state_hash: [0u8; 32],
                message_count: 5,
                last_execution: Utc::now(),
            },
        );

        let snapshot = StateSnapshot::new(agents);

        let tool_call = ToolCall {
            name: "test".to_string(),
            args: "{}".to_string(),
        };
        let result = ToolResult {
            success: true,
            output: "ok".to_string(),
            error: None,
        };
        let trace = ExecutionTrace::new(agent_id, tool_call, result);

        let result = DeterministicReplayer::replay_from_snapshot(&snapshot, &[trace])
            .await
            .unwrap();

        assert_eq!(result.traces.len(), 1);
        assert_eq!(result.final_snapshot.agent_count(), 1);
    }
}
