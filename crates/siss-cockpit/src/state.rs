use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::{Arc, Mutex};
use tokio::sync::broadcast;

pub const EVENT_BUFFER_SIZE: usize = 1000;
pub const BROADCAST_CHANNEL_SIZE: usize = 1024;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CockpitEvent {
    pub event_type: String,
    pub agent_id: Option<String>,
    pub payload: serde_json::Value,
    pub timestamp: DateTime<Utc>,
}

#[derive(Clone)]
pub struct CockpitState {
    tx: broadcast::Sender<CockpitEvent>,
    buffer: Arc<Mutex<VecDeque<CockpitEvent>>>,
}

impl CockpitState {
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(BROADCAST_CHANNEL_SIZE);
        Self {
            tx,
            buffer: Arc::new(Mutex::new(VecDeque::with_capacity(EVENT_BUFFER_SIZE))),
        }
    }

    pub fn emit(&self, event: CockpitEvent) {
        let _ = self.tx.send(event.clone());

        let mut buf = self.buffer.lock().expect("buffer lock");
        if buf.len() >= EVENT_BUFFER_SIZE {
            buf.pop_front();
        }
        buf.push_back(event);
    }

    pub fn subscribe(&self) -> broadcast::Receiver<CockpitEvent> {
        self.tx.subscribe()
    }

    pub fn buffered_events(&self) -> Vec<CockpitEvent> {
        let buf = self.buffer.lock().expect("buffer lock");
        buf.iter().cloned().collect()
    }
}

impl Default for CockpitState {
    fn default() -> Self {
        Self::new()
    }
}
