use demo_app::app::App;
use demo_app::models::TuiState;
use demo_app::pipeline::IngestionPipeline;
use demo_app::storage::ConcurrentMemoryRepo;
use std::sync::{Arc, Mutex};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create shared TUI state that both watcher and event loop access
    let shared_state = Arc::new(Mutex::new(TuiState::new()));
    let mut app = App::new();

    // Initialize the Chaos Petri Quarantine watcher
    let pipeline = IngestionPipeline::new("http://127.0.0.1:8080", 256);
    let repo = ConcurrentMemoryRepo::new();

    // Spawn the background Chaos Petri watcher task
    let watcher_state = Arc::clone(&shared_state);
    tokio::spawn(demo_app::pipeline::spawn_chaos_petri_watcher(
        pipeline,
        repo,
        watcher_state,
    ));

    // Run the TUI event loop with shared state
    demo_app::tui::run_app_with_state(&mut app, Some(shared_state)).await?;

    Ok(())
}
