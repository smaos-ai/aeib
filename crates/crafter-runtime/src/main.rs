use siss_agent_shell::crafter_runtime::{CrafterRuntime, RuntimeConfig};

#[tokio::main]
async fn main() {
    let runtime = CrafterRuntime::new(RuntimeConfig::default()).await;
    println!("CrafterRuntime online. Hooks: {}", runtime.hook_count());

    tokio::signal::ctrl_c()
        .await
        .expect("failed to listen for ctrl-c");

    println!("Shutting down gracefully...");
}
