use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FailoverState {
    Primary,
    Replica,
    Failed,
}

pub struct FailoverTracker {
    state: Arc<Mutex<FailoverState>>,
    last_failover: Arc<Mutex<u64>>,
}

impl FailoverTracker {
    pub fn new() -> Self {
        Self {
            state: Arc::new(Mutex::new(FailoverState::Primary)),
            last_failover: Arc::new(Mutex::new(0)),
        }
    }

    pub fn get_state(&self) -> FailoverState {
        *self.state.lock().unwrap()
    }

    pub fn set_state(&self, state: FailoverState) {
        let mut s = self.state.lock().unwrap();
        *s = state;
        let mut lf = self.last_failover.lock().unwrap();
        *lf = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis() as u64;
    }

    pub fn get_last_failover_ms(&self) -> u64 {
        *self.last_failover.lock().unwrap()
    }
}

impl Default for FailoverTracker {
    fn default() -> Self {
        Self::new()
    }
}
