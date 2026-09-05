use super::AgentEvent;
use super::emitter::EventEmitter;

/// Emitter that calls a provided closure for each event.
/// AoE wires this to SSE serialization.
pub struct CallbackEmitter {
    callback: Box<dyn Fn(AgentEvent) + Send + Sync>,
}

impl CallbackEmitter {
    pub fn new<F>(callback: F) -> Self
    where
        F: Fn(AgentEvent) + Send + Sync + 'static,
    {
        Self {
            callback: Box::new(callback),
        }
    }
}

impl EventEmitter for CallbackEmitter {
    fn emit(&self, event: AgentEvent) {
        (self.callback)(event);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use std::sync::{Arc, Mutex};
    use uuid::Uuid;

    #[test]
    fn test_callback_emitter_calls_closure() {
        let received = Arc::new(Mutex::new(Vec::new()));
        let received_clone = Arc::clone(&received);
        let emitter = CallbackEmitter::new(move |event| {
            received_clone
                .lock()
                .unwrap()
                .push(event.event_type().to_string());
        });

        emitter.emit(AgentEvent::SessionStarted {
            session_id: Uuid::nil(),
            persona_id: Uuid::nil(),
            timestamp: Utc::now(),
        });
        emitter.emit(AgentEvent::IntentCompleted {
            task_id: Uuid::nil(),
            quality_score: 0.8,
            timestamp: Utc::now(),
        });

        let types = received.lock().unwrap().clone();
        assert_eq!(types, vec!["session_started", "intent_completed"]);
    }
}
