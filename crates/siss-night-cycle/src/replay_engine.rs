use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::operators::{OntologyEntity, OntologyState, OperatorResult};

/// StateTransitionRecord: immutable record of a single operator mutation
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StateTransitionRecord {
    /// Monotonically increasing sequence number
    pub sequence: u64,
    /// Timestamp of state transition (UTC)
    pub timestamp: DateTime<Utc>,
    /// Name of operator applied (Phi, Delta, Gamma)
    pub operator_name: String,
    /// Before-state hash (Merkle DAG link to prior)
    pub prev_state_hash: String,
    /// After-state hash (Merkle DAG link)
    pub state_hash: String,
    /// Entities before transition
    pub entities_before: Vec<OntologyEntity>,
    /// Entities after transition
    pub entities_after: Vec<OntologyEntity>,
    /// Operator metrics
    pub entities_processed: usize,
    pub entities_changed: usize,
    /// Confidence scores snapshot before
    pub confidence_scores_before: Vec<f64>,
    /// Confidence scores snapshot after
    pub confidence_scores_after: Vec<f64>,
}

impl StateTransitionRecord {
    /// Compute hash of a state (entities + confidence)
    fn hash_state(entities: &[OntologyEntity]) -> String {
        let mut hasher = Sha256::new();
        let serialized =
            serde_json::to_string(entities).expect("Failed to serialize entities for hashing");
        hasher.update(serialized.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Create a new transition record
    pub fn new(
        sequence: u64,
        operator_name: String,
        prev_state_hash: String,
        entities_before: Vec<OntologyEntity>,
        entities_after: Vec<OntologyEntity>,
        result: &OperatorResult,
    ) -> Self {
        let state_hash = Self::hash_state(&entities_after);
        let confidence_scores_before: Vec<f64> =
            entities_before.iter().map(|e| e.confidence).collect();
        let confidence_scores_after: Vec<f64> =
            entities_after.iter().map(|e| e.confidence).collect();

        StateTransitionRecord {
            sequence,
            timestamp: Utc::now(),
            operator_name,
            prev_state_hash,
            state_hash,
            entities_before,
            entities_after,
            entities_processed: result.entities_processed,
            entities_changed: result.entities_changed,
            confidence_scores_before,
            confidence_scores_after,
        }
    }
}

/// ReplayLog: sequence of StateTransitionRecords forming a Merkle DAG
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplayLog {
    /// Immutable sequence of state transitions
    pub records: Vec<StateTransitionRecord>,
}

impl ReplayLog {
    pub fn new() -> Self {
        ReplayLog {
            records: Vec::new(),
        }
    }

    /// Append a transition record to the log
    pub fn append(&mut self, record: StateTransitionRecord) {
        self.records.push(record);
    }

    /// Get total number of transitions
    pub fn len(&self) -> usize {
        self.records.len()
    }

    /// Check if replay log is empty
    pub fn is_empty(&self) -> bool {
        self.records.is_empty()
    }

    /// Validate Merkle DAG: each record's prev_state_hash matches prior record's state_hash
    pub fn validate_merkle_dag(&self) -> Result<(), String> {
        for i in 1..self.records.len() {
            let expected_prev = &self.records[i - 1].state_hash;
            let actual_prev = &self.records[i].prev_state_hash;
            if expected_prev != actual_prev {
                return Err(format!(
                    "Merkle DAG break at record {}: expected prev_hash {}, got {}",
                    i, expected_prev, actual_prev
                ));
            }
        }
        Ok(())
    }

    /// Validate causality: φ→δ→γ ordering preserved, no out-of-order consolidations
    pub fn validate_causality(&self) -> Result<(), String> {
        let expected_order = ["Phi", "Delta", "Gamma"];
        let mut last_seen_index: HashMap<&str, usize> = HashMap::new();

        for (idx, record) in self.records.iter().enumerate() {
            let op_name = record.operator_name.as_str();

            // Find position in expected order
            if let Some(pos) = expected_order.iter().position(|&op| op == op_name) {
                // Check that we haven't seen a later operator before this one
                for later_op in expected_order.iter().skip(pos + 1) {
                    if let Some(later_idx) = last_seen_index.get(later_op) {
                        return Err(format!(
                            "Causality violation: {} seen at index {}, but {} seen later at index {}",
                            later_op, later_idx, op_name, idx
                        ));
                    }
                }
                last_seen_index.insert(op_name, idx);
            }
        }
        Ok(())
    }
}

impl Default for ReplayLog {
    fn default() -> Self {
        Self::new()
    }
}

/// ReplayEngine: trait for deterministic replay implementations
pub trait ReplayEngine {
    /// Record a state transition
    fn record_transition(
        &mut self,
        operator_name: String,
        entities_before: Vec<OntologyEntity>,
        entities_after: Vec<OntologyEntity>,
        result: &OperatorResult,
    ) -> Result<(), String>;

    /// Replay log from start to end, reconstructing exact state
    fn replay(&self) -> Result<OntologyState, String>;

    /// Replay to a specific sequence number (inclusive)
    fn replay_to_sequence(&self, sequence: u64) -> Result<OntologyState, String>;

    /// Get the current log
    fn get_log(&self) -> &ReplayLog;

    /// Validate all constraints: Merkle DAG + causality + confidence decay
    fn validate_all(&self) -> Result<(), String>;
}

/// FileBasedReplayLog: stores replay log to disk (SQLite backend)
pub struct FileBasedReplayLog {
    log: ReplayLog,
    db_path: String,
    sequence_counter: u64,
}

impl FileBasedReplayLog {
    pub fn new(db_path: &str) -> Result<Self, String> {
        Ok(FileBasedReplayLog {
            log: ReplayLog::new(),
            db_path: db_path.to_string(),
            sequence_counter: 0,
        })
    }

    /// Load replay log from disk (JSON-based for simplicity; can migrate to SQLite)
    pub fn load_from_file(path: &str) -> Result<Self, String> {
        if Path::new(path).exists() {
            let contents = fs::read_to_string(path)
                .map_err(|e| format!("Failed to read replay log: {}", e))?;
            let log: ReplayLog = serde_json::from_str(&contents)
                .map_err(|e| format!("Failed to parse replay log JSON: {}", e))?;
            let sequence_counter = if log.records.is_empty() {
                0
            } else {
                log.records[log.records.len() - 1].sequence + 1
            };
            Ok(FileBasedReplayLog {
                log,
                db_path: path.to_string(),
                sequence_counter,
            })
        } else {
            Self::new(path)
        }
    }

    /// Persist log to disk
    pub fn persist(&self) -> Result<(), String> {
        let json = serde_json::to_string_pretty(&self.log)
            .map_err(|e| format!("Failed to serialize replay log: {}", e))?;
        fs::write(&self.db_path, json)
            .map_err(|e| format!("Failed to write replay log to disk: {}", e))?;
        Ok(())
    }
}

impl ReplayEngine for FileBasedReplayLog {
    fn record_transition(
        &mut self,
        operator_name: String,
        entities_before: Vec<OntologyEntity>,
        entities_after: Vec<OntologyEntity>,
        result: &OperatorResult,
    ) -> Result<(), String> {
        let prev_state_hash = if self.log.records.is_empty() {
            "0".to_string()
        } else {
            self.log.records[self.log.records.len() - 1]
                .state_hash
                .clone()
        };

        let record = StateTransitionRecord::new(
            self.sequence_counter,
            operator_name,
            prev_state_hash,
            entities_before,
            entities_after,
            result,
        );

        self.log.append(record);
        self.sequence_counter += 1;
        self.persist()?;
        Ok(())
    }

    fn replay(&self) -> Result<OntologyState, String> {
        self.replay_to_sequence(u64::MAX)
    }

    fn replay_to_sequence(&self, target_sequence: u64) -> Result<OntologyState, String> {
        let mut state = OntologyState {
            entities: Vec::new(),
            confidence_threshold: 0.0,
        };

        for record in &self.log.records {
            if record.sequence > target_sequence {
                break;
            }
            // Reconstruct state from "after" snapshot
            state.entities = record.entities_after.clone();
        }

        Ok(state)
    }

    fn get_log(&self) -> &ReplayLog {
        &self.log
    }

    fn validate_all(&self) -> Result<(), String> {
        // Validate Merkle DAG integrity
        self.log.validate_merkle_dag()?;

        // Validate φ→δ→γ causality
        self.log.validate_causality()?;

        // Validate confidence decay (γ-score): γ(t) = γ₀ × e^(-λt)
        // For now, just ensure confidence scores are monotonic or follow decay law
        for i in 1..self.log.records.len() {
            let prev_record = &self.log.records[i - 1];
            let curr_record = &self.log.records[i];

            // If operator is Gamma (confidence filtering), confidence should decrease or stay same
            if curr_record.operator_name == "Gamma"
                && !curr_record.confidence_scores_after.is_empty()
                && !prev_record.confidence_scores_after.is_empty()
            {
                // At least verify scores don't increase artificially
                let prev_max = prev_record
                    .confidence_scores_after
                    .iter()
                    .cloned()
                    .fold(0.0, f64::max);
                let curr_max = curr_record
                    .confidence_scores_after
                    .iter()
                    .cloned()
                    .fold(0.0, f64::max);
                // Gamma should not increase max confidence
                if curr_max > prev_max {
                    return Err(format!(
                        "Gamma decay violation: max confidence increased from {} to {}",
                        prev_max, curr_max
                    ));
                }
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn create_test_entity(id: &str, confidence: f64) -> OntologyEntity {
        OntologyEntity {
            id: id.to_string(),
            timestamp: 1000,
            confidence,
            data: json!({"value": "test"}),
        }
    }

    fn create_test_result() -> OperatorResult {
        OperatorResult {
            entities_processed: 5,
            entities_changed: 2,
            operator_name: "TestOp",
        }
    }

    #[test]
    fn test_replay_produces_exact_state_match() {
        let mut engine =
            FileBasedReplayLog::new("test_replay.json").expect("Failed to create engine");

        // Create initial state
        let entities_before = vec![create_test_entity("e1", 0.9), create_test_entity("e2", 0.8)];
        let entities_after = vec![create_test_entity("e1", 0.9), create_test_entity("e2", 0.8)];

        let result = OperatorResult {
            entities_processed: 2,
            entities_changed: 0,
            operator_name: "Phi",
        };

        // Record first transition
        engine
            .record_transition(
                "Phi".to_string(),
                entities_before.clone(),
                entities_after.clone(),
                &result,
            )
            .expect("Failed to record transition");

        // Replay and verify exact match
        let replayed_state = engine.replay().expect("Failed to replay");
        assert_eq!(replayed_state.entities.len(), 2);
        assert_eq!(replayed_state.entities[0].id, "e1");
        assert_eq!(replayed_state.entities[0].confidence, 0.9);
        assert_eq!(replayed_state.entities[1].id, "e2");
        assert_eq!(replayed_state.entities[1].confidence, 0.8);

        // Cleanup
        let _ = fs::remove_file("test_replay.json");
    }

    #[test]
    fn test_confidence_decay_reproduces_exactly() {
        let mut engine =
            FileBasedReplayLog::new("test_decay.json").expect("Failed to create engine");

        // Initial state with high confidence
        let entities_before_1 = vec![create_test_entity("e1", 0.95)];
        let entities_after_1 = vec![create_test_entity("e1", 0.95)];

        engine
            .record_transition(
                "Phi".to_string(),
                entities_before_1.clone(),
                entities_after_1.clone(),
                &OperatorResult {
                    entities_processed: 1,
                    entities_changed: 0,
                    operator_name: "Phi",
                },
            )
            .expect("Failed to record transition 1");

        // Apply Gamma operator to simulate confidence decay/filtering
        let entities_before_2 = vec![create_test_entity("e1", 0.95)];
        let entities_after_2 = vec![create_test_entity("e1", 0.85)]; // Decay applied

        engine
            .record_transition(
                "Gamma".to_string(),
                entities_before_2.clone(),
                entities_after_2.clone(),
                &OperatorResult {
                    entities_processed: 1,
                    entities_changed: 0,
                    operator_name: "Gamma",
                },
            )
            .expect("Failed to record transition 2");

        // Replay and verify confidence was properly tracked
        let replayed = engine.replay().expect("Failed to replay");
        assert_eq!(replayed.entities[0].confidence, 0.85);
        assert_eq!(replayed.entities[0].id, "e1");

        // Cleanup
        let _ = fs::remove_file("test_decay.json");
    }

    #[test]
    fn test_operator_causality_preserved() {
        let mut engine =
            FileBasedReplayLog::new("test_causality.json").expect("Failed to create engine");

        let entity = vec![create_test_entity("e1", 0.9)];

        // Record in correct order: Phi → Delta → Gamma
        for op in &["Phi", "Delta", "Gamma"] {
            engine
                .record_transition(
                    op.to_string(),
                    entity.clone(),
                    entity.clone(),
                    &OperatorResult {
                        entities_processed: 1,
                        entities_changed: 0,
                        operator_name: op,
                    },
                )
                .expect(&format!("Failed to record {}", op));
        }

        // Validate causality
        let result = engine.validate_all();
        assert!(
            result.is_ok(),
            "Causality validation should pass for correct ordering"
        );

        // Cleanup
        let _ = fs::remove_file("test_causality.json");
    }

    #[test]
    fn test_replay_from_empty_to_final_state() {
        let mut engine =
            FileBasedReplayLog::new("test_full_replay.json").expect("Failed to create engine");

        // Build state incrementally
        let e1 = create_test_entity("e1", 0.9);
        let e2 = create_test_entity("e2", 0.8);
        let e3 = create_test_entity("e3", 0.7);

        // Transition 1: Add e1, e2
        engine
            .record_transition(
                "Phi".to_string(),
                vec![],
                vec![e1.clone(), e2.clone()],
                &OperatorResult {
                    entities_processed: 2,
                    entities_changed: 0,
                    operator_name: "Phi",
                },
            )
            .expect("Failed to record transition 1");

        // Transition 2: Add e3 via Delta
        engine
            .record_transition(
                "Delta".to_string(),
                vec![e1.clone(), e2.clone()],
                vec![e1.clone(), e2.clone(), e3.clone()],
                &OperatorResult {
                    entities_processed: 3,
                    entities_changed: 1,
                    operator_name: "Delta",
                },
            )
            .expect("Failed to record transition 2");

        // Transition 3: Filter via Gamma (remove e3)
        engine
            .record_transition(
                "Gamma".to_string(),
                vec![e1.clone(), e2.clone(), e3.clone()],
                vec![e1.clone(), e2.clone()],
                &OperatorResult {
                    entities_processed: 3,
                    entities_changed: 1,
                    operator_name: "Gamma",
                },
            )
            .expect("Failed to record transition 3");

        // Replay from empty and verify we get final state
        let replayed = engine.replay().expect("Failed to replay");
        assert_eq!(replayed.entities.len(), 2);
        assert_eq!(replayed.entities[0].id, "e1");
        assert_eq!(replayed.entities[1].id, "e2");

        // Also test replay to specific sequence
        let partial = engine
            .replay_to_sequence(1)
            .expect("Failed to replay to sequence 1");
        assert_eq!(partial.entities.len(), 3);
        assert_eq!(
            partial.entities.iter().map(|e| &e.id).collect::<Vec<_>>(),
            vec!["e1", "e2", "e3"]
        );

        // Cleanup
        let _ = fs::remove_file("test_full_replay.json");
    }

    #[test]
    fn test_merkle_dag_integrity() {
        let mut engine =
            FileBasedReplayLog::new("test_merkle.json").expect("Failed to create engine");

        let entity = vec![create_test_entity("e1", 0.9)];

        engine
            .record_transition(
                "Phi".to_string(),
                vec![],
                entity.clone(),
                &OperatorResult {
                    entities_processed: 1,
                    entities_changed: 0,
                    operator_name: "Phi",
                },
            )
            .expect("Failed to record transition 1");

        engine
            .record_transition(
                "Delta".to_string(),
                entity.clone(),
                entity.clone(),
                &OperatorResult {
                    entities_processed: 1,
                    entities_changed: 0,
                    operator_name: "Delta",
                },
            )
            .expect("Failed to record transition 2");

        // Validate Merkle DAG
        let result = engine.get_log().validate_merkle_dag();
        assert!(result.is_ok(), "Merkle DAG should be valid");

        // Cleanup
        let _ = fs::remove_file("test_merkle.json");
    }

    #[test]
    fn test_bitwise_equality_verification() {
        let mut engine =
            FileBasedReplayLog::new("test_bitwise.json").expect("Failed to create engine");

        let entity1 = OntologyEntity {
            id: "e1".to_string(),
            timestamp: 12345,
            confidence: 0.9123456789,
            data: json!({"test": "value", "nested": {"a": 1}}),
        };

        let entity2 = entity1.clone();

        engine
            .record_transition(
                "Phi".to_string(),
                vec![entity1.clone()],
                vec![entity2.clone()],
                &OperatorResult {
                    entities_processed: 1,
                    entities_changed: 0,
                    operator_name: "Phi",
                },
            )
            .expect("Failed to record transition");

        let replayed = engine.replay().expect("Failed to replay");

        // Verify bitwise equality
        assert_eq!(replayed.entities.len(), 1);
        let replayed_entity = &replayed.entities[0];
        assert_eq!(replayed_entity.id, entity1.id);
        assert_eq!(replayed_entity.timestamp, entity1.timestamp);
        assert_eq!(replayed_entity.confidence, entity1.confidence);
        assert_eq!(replayed_entity.data, entity1.data);

        // Cleanup
        let _ = fs::remove_file("test_bitwise.json");
    }
}
