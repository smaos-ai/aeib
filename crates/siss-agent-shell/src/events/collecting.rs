use std::sync::{Arc, Mutex};

use super::AgentEvent;
use super::emitter::EventEmitter;

/// Test emitter that collects all events in a thread-safe Vec.
pub struct CollectingEmitter {
    events: Arc<Mutex<Vec<AgentEvent>>>,
}

impl CollectingEmitter {
    pub fn new() -> Self {
        Self {
            events: Arc::new(Mutex::new(Vec::new())),
        }
    }

    /// Get a clone of the events handle for assertions.
    pub fn events(&self) -> Arc<Mutex<Vec<AgentEvent>>> {
        Arc::clone(&self.events)
    }

    /// Get the count of collected events.
    pub fn count(&self) -> usize {
        self.events.lock().unwrap().len()
    }

    /// Get all collected event type names.
    pub fn event_types(&self) -> Vec<String> {
        self.events
            .lock()
            .unwrap()
            .iter()
            .map(|e| e.event_type().to_string())
            .collect()
    }
}

impl Default for CollectingEmitter {
    fn default() -> Self {
        Self::new()
    }
}

impl EventEmitter for CollectingEmitter {
    fn emit(&self, event: AgentEvent) {
        self.events.lock().unwrap().push(event);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use uuid::Uuid;

    #[test]
    fn test_collecting_emitter_captures_events() {
        let emitter = CollectingEmitter::new();
        emitter.emit(AgentEvent::SessionStarted {
            session_id: Uuid::nil(),
            persona_id: Uuid::nil(),
            timestamp: Utc::now(),
        });
        emitter.emit(AgentEvent::SessionClosed {
            session_id: Uuid::nil(),
            timestamp: Utc::now(),
        });
        assert_eq!(emitter.count(), 2);
    }

    #[test]
    fn test_collecting_emitter_event_types() {
        let emitter = CollectingEmitter::new();
        emitter.emit(AgentEvent::TaskCreated {
            task_id: Uuid::nil(),
            intent: "test".into(),
            timestamp: Utc::now(),
        });
        emitter.emit(AgentEvent::Authorized {
            task_id: Uuid::nil(),
            mandate_id: Uuid::nil(),
            timestamp: Utc::now(),
        });
        let types = emitter.event_types();
        assert_eq!(types, vec!["task_created", "authorized"]);
    }

    #[test]
    fn test_collecting_emitter_shared_access() {
        let emitter = CollectingEmitter::new();
        let events = emitter.events();
        emitter.emit(AgentEvent::Error {
            message: "test".into(),
            timestamp: Utc::now(),
        });
        assert_eq!(events.lock().unwrap().len(), 1);
    }
}
