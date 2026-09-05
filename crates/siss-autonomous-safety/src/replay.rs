use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::SystemTime;
use uuid::Uuid;

use crate::errors::{SafetyError, SafetyResult};

/// Event type for replay recording
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ReplayEventType {
    /// Sensor reading received
    SensorReading,
    /// Actuator command issued
    ActuatorCommand,
    /// Decision made
    Decision,
    /// Fault detected
    FaultDetected,
    /// System state change
    StateChange,
}

/// Single recorded event for replay
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplayEvent {
    pub id: Uuid,
    pub event_type: ReplayEventType,
    pub timestamp: SystemTime,
    pub sequence_number: u64,
    pub data: Vec<u8>,
    pub checksum: [u8; 32],
}

impl ReplayEvent {
    pub fn new(event_type: ReplayEventType, data: Vec<u8>) -> Self {
        let checksum = Self::compute_checksum(&data);
        Self {
            id: Uuid::new_v4(),
            event_type,
            timestamp: SystemTime::now(),
            sequence_number: 0,
            data,
            checksum,
        }
    }

    /// Compute SHA256 checksum of event data
    pub fn compute_checksum(data: &[u8]) -> [u8; 32] {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(data);
        let result = hasher.finalize();
        let mut checksum = [0u8; 32];
        checksum.copy_from_slice(&result);
        checksum
    }

    /// Verify event integrity
    pub fn verify_checksum(&self) -> bool {
        let computed = Self::compute_checksum(&self.data);
        computed == self.checksum
    }
}

/// Deterministic session recording for accident reconstruction
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplaySession {
    pub id: Uuid,
    pub vehicle_id: Uuid,
    pub start_time: SystemTime,
    pub end_time: Option<SystemTime>,
    pub duration_ms: u64,
    pub event_count: u64,
    pub session_checksum: [u8; 32],
}

impl ReplaySession {
    pub fn new(vehicle_id: Uuid) -> Self {
        Self {
            id: Uuid::new_v4(),
            vehicle_id,
            start_time: SystemTime::now(),
            end_time: None,
            duration_ms: 0,
            event_count: 0,
            session_checksum: [0u8; 32],
        }
    }
}

/// Deterministic replay recorder for autonomous safety audit trail
pub struct ReplayRecorder {
    current_session: Arc<parking_lot::RwLock<Option<ReplaySession>>>,
    events: Arc<DashMap<Uuid, Vec<ReplayEvent>>>,
    sequence_counter: Arc<parking_lot::RwLock<u64>>,
}

impl ReplayRecorder {
    pub fn new() -> Self {
        Self {
            current_session: Arc::new(parking_lot::RwLock::new(None)),
            events: Arc::new(DashMap::new()),
            sequence_counter: Arc::new(parking_lot::RwLock::new(0)),
        }
    }

    /// Start a new recording session
    pub fn start_session(&self, vehicle_id: Uuid) -> SafetyResult<Uuid> {
        let mut session_lock = self.current_session.write();

        if session_lock.is_some() {
            return Err(SafetyError::InternalError(
                "Session already active".to_string(),
            ));
        }

        let session = ReplaySession::new(vehicle_id);
        let session_id = session.id;
        *session_lock = Some(session);

        self.events.insert(session_id, Vec::new());
        *self.sequence_counter.write() = 0;

        Ok(session_id)
    }

    /// End current recording session
    pub fn end_session(&self) -> SafetyResult<ReplaySession> {
        let mut session_lock = self.current_session.write();
        let mut session = session_lock
            .take()
            .ok_or(SafetyError::InternalError("No session active".to_string()))?;

        session.end_time = Some(SystemTime::now());
        if let Ok(duration) = session.end_time.unwrap().duration_since(session.start_time) {
            session.duration_ms = duration.as_millis() as u64;
        }

        Ok(session)
    }

    /// Record an event in current session
    pub fn record_event(&self, event_type: ReplayEventType, data: Vec<u8>) -> SafetyResult<Uuid> {
        let session_lock = self.current_session.read();
        let session = session_lock
            .as_ref()
            .ok_or(SafetyError::InternalError("No session active".to_string()))?;

        let mut event = ReplayEvent::new(event_type, data);
        let mut seq_lock = self.sequence_counter.write();
        event.sequence_number = *seq_lock;
        *seq_lock += 1;

        let session_id = session.id;
        let event_id = event.id;

        drop(session_lock);
        drop(seq_lock);

        self.events
            .entry(session_id)
            .or_insert_with(Vec::new)
            .push(event);

        Ok(event_id)
    }

    /// Get all events for a session
    pub fn get_session_events(&self, session_id: Uuid) -> SafetyResult<Vec<ReplayEvent>> {
        self.events
            .get(&session_id)
            .map(|entry| entry.clone())
            .ok_or(SafetyError::ReplayIntegrityError(
                "Session not found".to_string(),
            ))
    }

    /// Verify integrity of all events in session
    pub fn verify_session_integrity(&self, session_id: Uuid) -> SafetyResult<bool> {
        let events = self.get_session_events(session_id)?;

        if events.is_empty() {
            return Ok(true);
        }

        // Verify each event's checksum
        for event in &events {
            if !event.verify_checksum() {
                return Err(SafetyError::ReplayIntegrityError(format!(
                    "Event {} checksum failed",
                    event.id
                )));
            }
        }

        // Verify sequence numbers are monotonic
        for (i, event) in events.iter().enumerate() {
            if event.sequence_number != i as u64 {
                return Err(SafetyError::ReplayIntegrityError(format!(
                    "Sequence break at event {}",
                    event.id
                )));
            }
        }

        Ok(true)
    }

    /// Get current session info
    pub fn current_session_info(&self) -> SafetyResult<ReplaySession> {
        let session_lock = self.current_session.read();
        session_lock
            .clone()
            .ok_or(SafetyError::InternalError("No session active".to_string()))
    }

    /// Get event by ID (searches all sessions)
    pub fn get_event(&self, event_id: Uuid) -> Option<ReplayEvent> {
        for entry in self.events.iter() {
            for event in entry.value() {
                if event.id == event_id {
                    return Some(event.clone());
                }
            }
        }
        None
    }

    /// Count events in a session
    pub fn event_count(&self, session_id: Uuid) -> SafetyResult<usize> {
        Ok(self
            .events
            .get(&session_id)
            .map(|entry| entry.len())
            .unwrap_or(0))
    }

    /// Replay events in strict order (for accident reconstruction)
    pub fn replay_session(&self, session_id: Uuid) -> SafetyResult<Vec<ReplayEvent>> {
        let events = self.get_session_events(session_id)?;

        // Verify integrity before replay
        self.verify_session_integrity(session_id)?;

        // Return sorted by sequence number
        let mut sorted_events = events;
        sorted_events.sort_by_key(|e| e.sequence_number);

        Ok(sorted_events)
    }
}

impl Default for ReplayRecorder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_replay_event_creation() {
        let data = b"sensor_data".to_vec();
        let event = ReplayEvent::new(ReplayEventType::SensorReading, data.clone());

        assert_eq!(event.event_type, ReplayEventType::SensorReading);
        assert_eq!(event.data, data);
        assert!(event.verify_checksum());
    }

    #[test]
    fn test_replay_event_checksum_verification() {
        let data = b"test_data".to_vec();
        let event = ReplayEvent::new(ReplayEventType::SensorReading, data);

        assert!(event.verify_checksum());

        // Create tampered event
        let mut tampered_event = event.clone();
        tampered_event.data.push(0xFF);

        assert!(!tampered_event.verify_checksum());
    }

    #[test]
    fn test_replay_event_all_types() {
        let types = vec![
            ReplayEventType::SensorReading,
            ReplayEventType::ActuatorCommand,
            ReplayEventType::Decision,
            ReplayEventType::FaultDetected,
            ReplayEventType::StateChange,
        ];

        for event_type in types {
            let event = ReplayEvent::new(event_type.clone(), vec![1, 2, 3]);
            assert_eq!(event.event_type, event_type);
        }
    }

    #[test]
    fn test_replay_session_creation() {
        let vehicle_id = Uuid::new_v4();
        let session = ReplaySession::new(vehicle_id);

        assert_eq!(session.vehicle_id, vehicle_id);
        assert_eq!(session.event_count, 0);
        assert!(session.end_time.is_none());
    }

    #[test]
    fn test_replay_recorder_start_session() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        let session_id = recorder.start_session(vehicle_id).expect("Session start failed");
        assert!(!session_id.as_bytes().iter().all(|&b| b == 0));
    }

    #[test]
    fn test_replay_recorder_end_session() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("Session start failed");
        let session = recorder.end_session().expect("Session end failed");

        assert!(session.end_time.is_some());
        assert!(session.duration_ms >= 0);
    }

    #[test]
    fn test_replay_recorder_cannot_start_multiple_sessions() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("First session failed");
        let result = recorder.start_session(vehicle_id);

        assert!(result.is_err());
    }

    #[test]
    fn test_replay_recorder_record_event() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("Session start failed");
        let event_id = recorder
            .record_event(ReplayEventType::SensorReading, vec![1, 2, 3])
            .expect("Record event failed");

        assert!(!event_id.as_bytes().iter().all(|&b| b == 0));
    }

    #[test]
    fn test_replay_recorder_sequence_numbers() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("Session start failed");

        for i in 0..5 {
            recorder
                .record_event(ReplayEventType::SensorReading, vec![i as u8])
                .expect("Record failed");
        }

        let session_info = recorder.current_session_info().expect("Session info failed");
        let session_id = session_info.id;

        let events = recorder.get_session_events(session_id).expect("Get events failed");
        assert_eq!(events.len(), 5);

        for (i, event) in events.iter().enumerate() {
            assert_eq!(event.sequence_number, i as u64);
        }
    }

    #[test]
    fn test_replay_recorder_verify_session_integrity() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("Session start failed");
        let session_info = recorder.current_session_info().expect("Session info failed");
        let session_id = session_info.id;

        recorder
            .record_event(ReplayEventType::SensorReading, vec![1, 2, 3])
            .expect("Record failed");

        let is_valid = recorder
            .verify_session_integrity(session_id)
            .expect("Integrity check failed");
        assert!(is_valid);
    }

    #[test]
    fn test_replay_recorder_get_event() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("Session start failed");
        let event_id = recorder
            .record_event(ReplayEventType::ActuatorCommand, vec![99])
            .expect("Record failed");

        let event = recorder.get_event(event_id);
        assert!(event.is_some());
        assert_eq!(event.unwrap().event_type, ReplayEventType::ActuatorCommand);
    }

    #[test]
    fn test_replay_recorder_event_count() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("Session start failed");
        let session_info = recorder.current_session_info().expect("Session info failed");
        let session_id = session_info.id;

        for _ in 0..10 {
            recorder
                .record_event(ReplayEventType::Decision, vec![1])
                .expect("Record failed");
        }

        let count = recorder.event_count(session_id).expect("Count failed");
        assert_eq!(count, 10);
    }

    #[test]
    fn test_replay_session_replay_deterministic() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("Session start failed");
        let session_info = recorder.current_session_info().expect("Session info failed");
        let session_id = session_info.id;

        // Record events in order
        for i in 0..5 {
            recorder
                .record_event(ReplayEventType::SensorReading, vec![i as u8])
                .expect("Record failed");
        }

        // Replay
        let replayed = recorder.replay_session(session_id).expect("Replay failed");
        assert_eq!(replayed.len(), 5);

        // Verify sequence is preserved
        for (i, event) in replayed.iter().enumerate() {
            assert_eq!(event.sequence_number, i as u64);
            assert_eq!(event.data[0], i as u8);
        }
    }

    #[test]
    fn test_replay_recorder_no_active_session_errors() {
        let recorder = ReplayRecorder::new();
        let result = recorder.record_event(ReplayEventType::SensorReading, vec![1]);

        assert!(result.is_err());
    }

    #[test]
    fn test_replay_event_checksum_computation() {
        let data1 = b"test1".to_vec();
        let data2 = b"test2".to_vec();

        let checksum1 = ReplayEvent::compute_checksum(&data1);
        let checksum2 = ReplayEvent::compute_checksum(&data2);

        assert_ne!(checksum1, checksum2);

        // Same data = same checksum
        let checksum1_again = ReplayEvent::compute_checksum(&data1);
        assert_eq!(checksum1, checksum1_again);
    }

    #[test]
    fn test_replay_recorder_empty_session_integrity() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("Session start failed");
        let session_info = recorder.current_session_info().expect("Session info failed");
        let session_id = session_info.id;

        // Empty session should be valid
        let is_valid = recorder
            .verify_session_integrity(session_id)
            .expect("Integrity check failed");
        assert!(is_valid);
    }

    #[test]
    fn test_replay_recorder_all_event_types_recorded() {
        let recorder = ReplayRecorder::new();
        let vehicle_id = Uuid::new_v4();

        recorder.start_session(vehicle_id).expect("Session start failed");
        let session_info = recorder.current_session_info().expect("Session info failed");
        let session_id = session_info.id;

        let types = vec![
            ReplayEventType::SensorReading,
            ReplayEventType::ActuatorCommand,
            ReplayEventType::Decision,
            ReplayEventType::FaultDetected,
            ReplayEventType::StateChange,
        ];

        for event_type in &types {
            recorder
                .record_event(event_type.clone(), vec![1])
                .expect("Record failed");
        }

        let events = recorder.get_session_events(session_id).expect("Get events failed");
        assert_eq!(events.len(), types.len());

        for (i, event_type) in types.iter().enumerate() {
            assert_eq!(&events[i].event_type, event_type);
        }
    }
}
