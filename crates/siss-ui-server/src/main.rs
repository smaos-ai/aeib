use siss_ui_server::{create_router, AppState};
use std::net::SocketAddr;

#[tokio::main]
async fn main() {
    let state = AppState::new();
    let app = create_router(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    println!("Listening on http://0.0.0.0:8080");

    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .expect("Failed to bind to port 8080");

    axum::serve(listener, app).await.expect("Server error");
}
