/// Example: SMAOS AG-UI event streaming server
///
/// Demonstrates SSE streaming for Phase 20 recovery events.
/// Run: cargo run --example sse_server --features axum
///
/// Test: curl -N http://localhost:3000/events

#[cfg(feature = "axum")]
#[tokio::main]
async fn main() {
    use axum::{Router, routing::get};
    use siss_agent_card::cockpit::cockpit_handler;
    use siss_agent_card::events::{EventBroadcaster, RecoveryEvent, events_stream};
    use std::sync::Arc;

    // Create event broadcaster (shared state)
    let broadcaster = Arc::new(EventBroadcaster::new());
    let broadcaster_clone = broadcaster.clone();

    // Build Axum router with SSE + cockpit endpoints
    let app = Router::new()
        .route("/cockpit", get(cockpit_handler))
        .route("/events", get(events_stream))
        .with_state(broadcaster_clone);

    // Bind to port 3000
    let listener = tokio::net::TcpListener::bind("127.0.0.1:3000")
        .await
        .unwrap();

    println!("SSE server listening on http://127.0.0.1:3000");
    println!("Cockpit:  http://127.0.0.1:3000/cockpit");
    println!("Events:   curl -N http://127.0.0.1:3000/events");

    // Spawn a background task that emits demo events every 5 seconds
    let broadcaster_demo = broadcaster.clone();
    tokio::spawn(async move {
        let mut count = 0;
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
            count += 1;

            let event = if count % 3 == 0 {
                RecoveryEvent::RecoveryProgressed {
                    sovereign_id: format!("sovereign-{}", count % 3),
                    weeks_elapsed: (count % 8) as u32,
                    current_score: (85 + (count % 15)) as i16,
                    timestamp: chrono::Utc::now().to_rfc3339(),
                }
            } else if count % 5 == 0 {
                RecoveryEvent::RecoveryEntered {
                    sovereign_id: format!("sovereign-{}", count % 3),
                    score_at_entry: 82,
                    timestamp: chrono::Utc::now().to_rfc3339(),
                }
            } else {
                RecoveryEvent::ScoringDecision {
                    sovereign_id: format!("sovereign-{}", count % 3),
                    score: (85 + (count % 15)) as i16,
                    weeks_elapsed: (count % 8) as u32,
                    slash_penalty: ((count % 3) * 5) as i16,
                    anomaly_penalty: 0,
                    settlement_bonus: 5,
                    timestamp: chrono::Utc::now().to_rfc3339(),
                }
            };

            broadcaster_demo.emit(event);
        }
    });

    // Run server
    axum::serve(listener, app).await.unwrap();
}

#[cfg(not(feature = "axum"))]
fn main() {
    eprintln!("This example requires the 'axum' feature.");
    eprintln!("Run: cargo run --example sse_server --features axum");
}
