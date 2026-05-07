use super::AgentEvent;

/// Trait for receiving AG-UI events from the agent shell.
pub trait EventEmitter: Send + Sync {
    fn emit(&self, event: AgentEvent);
}

/// Default emitter that discards all events. Zero overhead.
pub struct NoOpEmitter;

impl EventEmitter for NoOpEmitter {
    fn emit(&self, _event: AgentEvent) {
        // Intentionally empty
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use uuid::Uuid;

    #[test]
    fn test_noop_emitter_does_not_panic() {
        let emitter = NoOpEmitter;
        emitter.emit(AgentEvent::SessionStarted {
            session_id: Uuid::nil(),
            persona_id: Uuid::nil(),
            timestamp: Utc::now(),
        });
        // No assertion needed — just verifying it doesn't panic
    }
}
