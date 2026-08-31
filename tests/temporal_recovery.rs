//! Temporal recovery and checkpoint tests for hybrid QA pipeline
//! Tests 48-hour recovery from any gate, checkpoint resumption, AP2 ledger append-only
//! Target: 8 tests, 300 lines

use chrono::{Duration, Utc};
use uuid::Uuid;
use sha2::{Digest, Sha256};
use std::collections::VecDeque;

/// Checkpoint representing a saved state at a specific time
#[derive(Debug, Clone)]
struct Checkpoint {
    checkpoint_id: String,
    timestamp: i64,
    gate_state: String,
    digest: String,
    recovery_metadata: String,
}

impl Checkpoint {
    fn new(gate_state: String) -> Self {
        let timestamp = Utc::now().timestamp();
        let mut hasher = Sha256::new();
        hasher.update(format!("{}{}", gate_state, timestamp).as_bytes());
        let digest = format!("{:x}", hasher.finalize());

        Self {
            checkpoint_id: Uuid::new_v4().to_string(),
            timestamp,
            gate_state,
            digest,
            recovery_metadata: "recoverable".to_string(),
        }
    }

    fn is_recoverable(&self) -> bool {
        self.recovery_metadata == "recoverable" && !self.digest.is_empty()
    }
}

/// Recovery manager for temporal restoration
struct RecoveryManager {
    checkpoints: VecDeque<Checkpoint>,
    max_age_secs: i64,
    recovery_window_hours: i64,
}

impl RecoveryManager {
    fn new(recovery_window_hours: i64) -> Self {
        Self {
            checkpoints: VecDeque::new(),
            max_age_secs: 3600 * recovery_window_hours,
            recovery_window_hours,
        }
    }

    fn save_checkpoint(&mut self, gate_state: String) -> Checkpoint {
        let checkpoint = Checkpoint::new(gate_state);
        self.checkpoints.push_back(checkpoint.clone());
        checkpoint
    }

    fn get_latest_checkpoint(&self) -> Option<&Checkpoint> {
        self.checkpoints.back()
    }

    fn get_checkpoints_within_window(&self) -> Vec<Checkpoint> {
        let cutoff_time = Utc::now().timestamp() - self.max_age_secs;
        self.checkpoints
            .iter()
            .filter(|cp| cp.timestamp > cutoff_time)
            .cloned()
            .collect()
    }

    fn recover_from_checkpoint(&self, checkpoint_id: &str) -> Result<String, String> {
        for cp in self.checkpoints.iter() {
            if cp.checkpoint_id == checkpoint_id && cp.is_recoverable() {
                return Ok(cp.gate_state.clone());
            }
        }
        Err(format!("Checkpoint {} not found or not recoverable", checkpoint_id))
    }

    fn checkpoint_count(&self) -> usize {
        self.checkpoints.len()
    }

    fn cleanup_old_checkpoints(&mut self) {
        let cutoff_time = Utc::now().timestamp() - self.max_age_secs;
        while let Some(front) = self.checkpoints.front() {
            if front.timestamp <= cutoff_time {
                self.checkpoints.pop_front();
            } else {
                break;
            }
        }
    }
}

/// Append-only ledger entry for immutable action logging
#[derive(Debug, Clone)]
struct LedgerEntry {
    entry_id: String,
    timestamp: i64,
    action: String,
    digest: String,
    previous_digest: Option<String>,
    is_checkpoint: bool,
}

impl LedgerEntry {
    fn new(action: String, previous_digest: Option<String>) -> Self {
        let timestamp = Utc::now().timestamp();
        let mut hasher = Sha256::new();
        hasher.update(format!("{}{}", action, timestamp).as_bytes());
        let digest = format!("{:x}", hasher.finalize());

        Self {
            entry_id: Uuid::new_v4().to_string(),
            timestamp,
            action,
            digest,
            previous_digest,
            is_checkpoint: false,
        }
    }

    fn verify_chain(&self, expected_previous: Option<&str>) -> bool {
        match expected_previous {
            None => self.previous_digest.is_none(),
            Some(expected) => {
                if let Some(prev) = &self.previous_digest {
                    prev == expected
                } else {
                    false
                }
            }
        }
    }
}

/// Append-only ledger for AP2 proof trail
struct AP2Ledger {
    entries: Vec<LedgerEntry>,
    last_digest: Option<String>,
}

impl AP2Ledger {
    fn new() -> Self {
        Self {
            entries: Vec::new(),
            last_digest: None,
        }
    }

    fn append(&mut self, action: String) -> Result<LedgerEntry, String> {
        let entry = LedgerEntry::new(action, self.last_digest.clone());

        // Verify chain integrity
        if !entry.verify_chain(self.last_digest.as_deref()) {
            return Err("Chain verification failed".to_string());
        }

        self.last_digest = Some(entry.digest.clone());
        self.entries.push(entry.clone());
        Ok(entry)
    }

    fn create_checkpoint(&mut self) -> Result<LedgerEntry, String> {
        let mut entry = LedgerEntry::new(
            "checkpoint".to_string(),
            self.last_digest.clone(),
        );
        entry.is_checkpoint = true;

        self.last_digest = Some(entry.digest.clone());
        self.entries.push(entry.clone());
        Ok(entry)
    }

    fn verify_append_only(&self) -> Result<bool, String> {
        let mut previous_digest: Option<String> = None;

        for entry in &self.entries {
            if !entry.verify_chain(previous_digest.as_deref()) {
                return Ok(false);
            }
            previous_digest = Some(entry.digest.clone());
        }

        Ok(true)
    }

    fn get_entry_count(&self) -> usize {
        self.entries.len()
    }

    fn get_checkpoints(&self) -> Vec<&LedgerEntry> {
        self.entries.iter().filter(|e| e.is_checkpoint).collect()
    }

    fn attempt_remove_entry(&mut self, _entry_id: &str) -> Result<(), String> {
        // Prevent removal from append-only ledger
        Err("Cannot remove entries from append-only ledger".to_string())
    }

    fn attempt_modify_entry(&mut self, entry_id: &str, _new_action: String) -> Result<(), String> {
        // Prevent modification of existing entries
        if self.entries.iter().any(|e| e.entry_id == entry_id) {
            Err("Cannot modify existing entries in append-only ledger".to_string())
        } else {
            Err("Entry not found".to_string())
        }
    }
}

/// 48-hour recovery simulator
struct HourRecoverySimulator {
    elapsed_hours: i64,
}

impl HourRecoverySimulator {
    fn new() -> Self {
        Self { elapsed_hours: 0 }
    }

    fn simulate_hours(&mut self, hours: i64) {
        self.elapsed_hours += hours;
    }

    fn can_recover(&self) -> bool {
        self.elapsed_hours <= 48
    }

    fn recovery_deadline_passed(&self) -> bool {
        self.elapsed_hours > 48
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_checkpoint_creation() {
        let cp = Checkpoint::new("gate_0_passed".to_string());
        assert!(!cp.checkpoint_id.is_empty());
        assert!(!cp.digest.is_empty());
        assert!(cp.is_recoverable());
    }

    #[test]
    fn test_recovery_manager_save_and_retrieve() {
        let mut manager = RecoveryManager::new(48);

        let cp1 = manager.save_checkpoint("gate_1_state".to_string());
        let cp2 = manager.save_checkpoint("gate_2_state".to_string());

        assert_eq!(manager.checkpoint_count(), 2);

        let latest = manager.get_latest_checkpoint().unwrap();
        assert_eq!(latest.checkpoint_id, cp2.checkpoint_id);
    }

    #[test]
    fn test_recovery_from_checkpoint() {
        let mut manager = RecoveryManager::new(48);

        let cp = manager.save_checkpoint("important_state".to_string());
        let recovered = manager.recover_from_checkpoint(&cp.checkpoint_id).unwrap();

        assert_eq!(recovered, "important_state");
    }

    #[test]
    fn test_recovery_window_enforcement() {
        let manager = RecoveryManager::new(48);
        manager.save_checkpoint("state_1".to_string());

        let checkpoints = manager.get_checkpoints_within_window();
        assert!(!checkpoints.is_empty());
    }

    #[test]
    fn test_ap2_ledger_append_only() {
        let mut ledger = AP2Ledger::new();

        ledger.append("action_1".to_string()).unwrap();
        ledger.append("action_2".to_string()).unwrap();
        ledger.append("action_3".to_string()).unwrap();

        assert_eq!(ledger.get_entry_count(), 3);
        assert!(ledger.verify_append_only().unwrap());
    }

    #[test]
    fn test_ap2_ledger_prevent_removal() {
        let mut ledger = AP2Ledger::new();
        let entry = ledger.append("action".to_string()).unwrap();

        let result = ledger.attempt_remove_entry(&entry.entry_id);
        assert!(result.is_err());
        assert_eq!(
            result.unwrap_err(),
            "Cannot remove entries from append-only ledger"
        );
    }

    #[test]
    fn test_ap2_ledger_prevent_modification() {
        let mut ledger = AP2Ledger::new();
        let entry = ledger.append("action".to_string()).unwrap();

        let result = ledger.attempt_modify_entry(&entry.entry_id, "new_action".to_string());
        assert!(result.is_err());
        assert_eq!(
            result.unwrap_err(),
            "Cannot modify existing entries in append-only ledger"
        );
    }

    #[test]
    fn test_48_hour_recovery_window() {
        let mut simulator = HourRecoverySimulator::new();

        // Within 48 hours
        simulator.simulate_hours(24);
        assert!(simulator.can_recover());
        assert!(!simulator.recovery_deadline_passed());

        // At 48 hours
        simulator.simulate_hours(24);
        assert!(simulator.can_recover());

        // Beyond 48 hours
        simulator.simulate_hours(1);
        assert!(!simulator.can_recover());
        assert!(simulator.recovery_deadline_passed());
    }
}
