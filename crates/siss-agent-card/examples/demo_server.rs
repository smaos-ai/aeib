/// Demo server for Phase 20 + Phase 21 cockpit verification
/// Runs at localhost:3000/cockpit
/// Emits simulated recovery and trust events via GET /events

use axum::{
    extract::State,
    http::StatusCode,
    response::{sse::Event, Sse, IntoResponse},
    routing::{get, post},
    Json, Router,
};
use futures::stream::Stream;
use serde_json::json;
use std::convert::Infallible;
use std::sync::Arc;
use tokio::sync::broadcast;
use chrono::Utc;
use uuid::Uuid;

#[derive(Debug, Clone, serde::Serialize)]
#[serde(tag = "type")]
enum TestEvent {
    RecoveryEntered {
        sovereign_id: String,
        score_at_entry: i16,
        timestamp: String,
    },
    ScoringDecision {
        sovereign_id: String,
        score: i16,
        weeks_elapsed: u32,
        slash_penalty: i16,
        settlement_bonus: i16,
        timestamp: String,
    },
    TrustScoreUpdated {
        source_id: String,
        target_id: String,
        new_score: i16,
        explicit_component: i16,
        implicit_component: i16,
        decay_component: i16,
        transitive_component: Option<i16>,
        timestamp: String,
    },
    TrustEntered {
        source_id: String,
        target_id: String,
        initial_score: i16,
        timestamp: String,
    },
}

struct EventBroadcaster {
    tx: broadcast::Sender<TestEvent>,
}

impl EventBroadcaster {
    fn new() -> Self {
        let (tx, _) = broadcast::channel(256);
        EventBroadcaster { tx }
    }

    fn emit(&self, event: TestEvent) {
        let _ = self.tx.send(event);
    }

    fn subscribe(&self) -> broadcast::Receiver<TestEvent> {
        self.tx.subscribe()
    }
}

/// GET /cockpit - Serve HTML
async fn cockpit_handler() -> impl IntoResponse {
    const COCKPIT_HTML: &str = include_str!("../static/cockpit.html");
    (
        StatusCode::OK,
        [("content-type", "text/html")],
        COCKPIT_HTML,
    )
}

/// GET /events - SSE stream
async fn events_stream(
    State(broadcaster): State<Arc<EventBroadcaster>>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let mut rx = broadcaster.subscribe();

    let stream = async_stream::stream! {
        loop {
            match rx.recv().await {
                Ok(event) => {
                    if let Ok(json_str) = serde_json::to_string(&event) {
                        yield Ok(Event::default().data(json_str));
                    }
                }
                Err(broadcast::error::RecvError::Lagged(_)) => continue,
                Err(broadcast::error::RecvError::Closed) => break,
            }
        }
    };

    Sse::new(stream)
}

/// POST /emit/recovery-entered - Emit test recovery event
async fn emit_recovery_entered(
    State(broadcaster): State<Arc<EventBroadcaster>>,
) -> impl IntoResponse {
    let sovereign_id = Uuid::new_v4().to_string();
    broadcaster.emit(TestEvent::RecoveryEntered {
        sovereign_id: sovereign_id.clone(),
        score_at_entry: 82,
        timestamp: Utc::now().to_rfc3339(),
    });
    (StatusCode::OK, Json(json!({ "sovereign_id": sovereign_id, "event": "RecoveryEntered" })))
}

/// POST /emit/slashing-penalty - Emit test slashing event (Phase 20 signal)
async fn emit_slashing_penalty(
    State(broadcaster): State<Arc<EventBroadcaster>>,
) -> impl IntoResponse {
    let sovereign_id = Uuid::new_v4().to_string();
    broadcaster.emit(TestEvent::ScoringDecision {
        sovereign_id: sovereign_id.clone(),
        score: 65,
        weeks_elapsed: 2,
        slash_penalty: 30,
        settlement_bonus: 5,
        timestamp: Utc::now().to_rfc3339(),
    });
    (
        StatusCode::OK,
        Json(json!({ "sovereign_id": sovereign_id, "event": "ScoringDecision", "penalty": 30 })),
    )
}

/// POST /emit/trust-decay - Emit Phase 21 trust decay event
async fn emit_trust_decay(
    State(broadcaster): State<Arc<EventBroadcaster>>,
) -> impl IntoResponse {
    let source_id = Uuid::new_v4().to_string();
    let target_id = Uuid::new_v4().to_string();
    broadcaster.emit(TestEvent::TrustScoreUpdated {
        source_id: source_id.clone(),
        target_id: target_id.clone(),
        new_score: 45,
        explicit_component: 80,
        implicit_component: -20,
        decay_component: -15,
        transitive_component: None,
        timestamp: Utc::now().to_rfc3339(),
    });
    (
        StatusCode::OK,
        Json(json!({
            "source_id": source_id,
            "target_id": target_id,
            "event": "TrustScoreUpdated",
            "decay_penalty": -15
        })),
    )
}

#[tokio::main]
async fn main() {
    let broadcaster = Arc::new(EventBroadcaster::new());

    let app = Router::new()
        .route("/cockpit", get(cockpit_handler))
        .route("/events", get(events_stream))
        .route("/emit/recovery-entered", post(emit_recovery_entered))
        .route("/emit/slashing-penalty", post(emit_slashing_penalty))
        .route("/emit/trust-decay", post(emit_trust_decay))
        .with_state(broadcaster);

    let listener = tokio::net::TcpListener::bind("127.0.0.1:3000")
        .await
        .unwrap();

    println!("🚀 Demo server running at http://localhost:3000/cockpit");
    println!("   SSE stream: http://localhost:3000/events");
    println!();
    println!("Emit test events:");
    println!("   curl -X POST http://localhost:3000/emit/recovery-entered");
    println!("   curl -X POST http://localhost:3000/emit/slashing-penalty");
    println!("   curl -X POST http://localhost:3000/emit/trust-decay");
    println!();

    axum::serve(listener, app).await.unwrap();
}
