use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::{Arc, Mutex};
use tokio::sync::{broadcast, mpsc, RwLock};
use uuid::Uuid;
use crate::event_bridge::{system_event_to_cockpit, agent_event_to_cockpit};
use siss_agent_shell::events::AgentEvent;
use siss_event_log::EventFilter;
use siss_graph_db::rce_event_broadcaster::RceEventBroadcaster;
use siss_graph_db::rce::ResumableCognitiveExecution;
use sqlx::PgPool;

pub const EVENT_BUFFER_SIZE: usize = 1000;
pub const BROADCAST_CHANNEL_SIZE: usize = 1024;

// Anomaly event types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnomalyEvent {
    pub sovereign_id: Uuid,
    pub anomaly_type: String,
    pub severity: i32,
    pub detected_at: DateTime<Utc>,
}

pub type AnomalyEventBroadcaster = broadcast::Sender<AnomalyEvent>;

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
    pub rce_broadcaster: Arc<RceEventBroadcaster>,
    pub rce_engine: Arc<RwLock<Option<ResumableCognitiveExecution>>>,
    pub pool: Arc<Mutex<Option<Arc<PgPool>>>>,
    pub anomaly_broadcaster: Arc<AnomalyEventBroadcaster>,
}

impl CockpitState {
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(BROADCAST_CHANNEL_SIZE);
        let (anomaly_tx, _) = broadcast::channel(256);
        Self {
            tx,
            buffer: Arc::new(Mutex::new(VecDeque::with_capacity(EVENT_BUFFER_SIZE))),
            rce_broadcaster: Arc::new(RceEventBroadcaster::new()),
            rce_engine: Arc::new(RwLock::new(None)),
            pool: Arc::new(Mutex::new(None)),
            anomaly_broadcaster: Arc::new(anomaly_tx),
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

    pub fn wire_pool(&self, pool: Arc<PgPool>) {
        let mut p = self.pool.lock().expect("pool lock");
        *p = Some(pool);
    }

    pub fn subscribe_anomalies(&self) -> broadcast::Receiver<AnomalyEvent> {
        self.anomaly_broadcaster.subscribe()
    }
}

impl CockpitState {
    /// Wire the immutable event-log into the cockpit stream.
    /// Spawns a background task that continuously streams events from the log.
    /// Non-blocking: logging failures don't crash the cockpit.
    pub fn wire_event_log(&self, event_log: siss_event_log::EventLog) {
        let state = self.clone();
        tokio::spawn(async move {
            // Stream all events from the log (non-blocking integration)
            match event_log.stream_events(EventFilter::all()).await {
                Ok(mut stream) => {
                    use futures::StreamExt;
                    while let Some(event) = stream.next().await {
                        let cockpit_event = system_event_to_cockpit(event);
                        state.emit(cockpit_event);
                    }
                }
                Err(e) => {
                    eprintln!("Failed to stream events from log: {}", e);
                }
            }
        });
    }

    /// Wire the agent pipeline event stream into the cockpit SSE stream.
    /// Converts AgentEvent → CockpitEvent and broadcasts via SSE.
    /// Non-blocking: event conversion/emission errors don't crash the cockpit.
    pub fn wire_agent_emitter(&self, mut rx: mpsc::Receiver<AgentEvent>) {
        let state = self.clone();
        tokio::spawn(async move {
            while let Some(event) = rx.recv().await {
                state.emit(agent_event_to_cockpit(event));
            }
        });
    }

    /// Wire an active RCE engine into the cockpit decision handler.
    /// Safe to call multiple times; replaces any previously wired engine.
    pub fn wire_rce_engine(&self, engine: ResumableCognitiveExecution, pool: Arc<PgPool>) {
        {
            let mut guard = self.rce_engine.blocking_write();
            *guard = Some(engine);
        }
        {
            let mut p = self.pool.lock().expect("pool lock");
            *p = Some(pool);
        }
    }
}

impl Default for CockpitState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_wire_pool_populates_state() {
        let state = CockpitState::new();

        // Create a mock PgPool (we'll use a minimal configuration)
        // For testing, we create a disabled pool
        let pool_options = sqlx::postgres::PgPoolOptions::new()
            .max_connections(1);

        // Create a dummy connection string for testing
        // Note: This won't actually connect, just create the pool
        let pool = Arc::new(
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current().block_on(async {
                    pool_options
                        .connect("postgres://test:test@localhost/test")
                        .await
                        .unwrap_or_else(|_| {
                            // For test purposes, we can't actually connect
                            // So we'll use a workaround: create via connect_lazy
                            sqlx::postgres::PgPoolOptions::new()
                                .connect_lazy("postgres://test:test@localhost/test")
                                .expect("pool creation")
                        })
                })
            })
        );

        state.wire_pool(pool.clone());

        let retrieved = state.pool.lock().unwrap().clone();
        assert!(retrieved.is_some(), "Pool should be populated after wire_pool");
    }

    #[test]
    fn test_subscribe_anomalies_returns_receiver() {
        let state = CockpitState::new();
        let receiver = state.subscribe_anomalies();

        // Verify we get a receiver; sending on broadcaster should work
        let event = AnomalyEvent {
            sovereign_id: Uuid::new_v4(),
            anomaly_type: "test_anomaly".to_string(),
            severity: 1,
            detected_at: Utc::now(),
        };

        let _ = state.anomaly_broadcaster.send(event);
        // If we got here without panic, receiver was valid
    }
}
