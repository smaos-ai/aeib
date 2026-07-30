use siss_graph_db::api::create_router;
use demo_app::production::{ProductionConfig, startup_with_validations, create_production_router};
use std::net::SocketAddr;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing with structured logging
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .with_target(false)
        .with_thread_ids(true)
        .with_file(true)
        .with_line_number(true)
        .init();

    tracing::info!("=== Production Server Startup ===");

    // Load and validate configuration
    let config = ProductionConfig::from_env()
        .expect("Failed to load configuration");

    tracing::info!(
        "Configuration loaded: bind={}:{}, pool_size={}, timeout={}s",
        config.bind_address,
        config.bind_port,
        config.pool_size,
        config.connection_timeout_seconds
    );

    // Run all startup validations (checklist items 1, 2, 3, 4, 6)
    let (_pool, state) = startup_with_validations(&config)
        .await
        .expect("Failed startup validations");

    // Create the application router with:
    // - Original graph DB routes
    // - Production health check endpoint (checklist item 1)
    // - Production metrics endpoint (checklist item 5)
    let pool = state.pool.clone();
    let graph_router = create_router(pool.clone());
    let production_router = create_production_router(state.clone());

    // Merge routers
    let app = production_router.merge(graph_router);

    // Bind to configured address
    let bind_addr = format!("{}:{}", config.bind_address, config.bind_port);
    let addr: SocketAddr = bind_addr.parse()?;

    tracing::info!(
        "Starting HTTP server on {} with {} worker threads",
        addr,
        num_cpus::get()
    );

    let listener = tokio::net::TcpListener::bind(addr).await?;

    tracing::info!("Server listening on {}", addr);
    tracing::info!("Health check: GET /health");
    tracing::info!("Metrics export: GET /metrics");

    // Serve requests (graceful shutdown handled by signal in production.rs)
    axum::serve(listener, app).await?;

    Ok(())
}
