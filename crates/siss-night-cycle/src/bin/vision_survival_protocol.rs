use siss_night_cycle::VisionSurvivalProtocol;
use std::path::PathBuf;

#[tokio::main]
async fn main() {
    // Get workspace path from environment or use default
    let workspace_path = std::env::var("SISS_WORKSPACE")
        .unwrap_or_else(|_| ".".to_string());

    let mut protocol = VisionSurvivalProtocol::new(PathBuf::from(workspace_path));

    match protocol.execute().await {
        Ok(sync_capsule) => {
            println!("\n✓ Vision Survival Protocol completed successfully");
            println!("  Sync ID: {}", sync_capsule.sync_id);
            println!("  Timestamp: {}", sync_capsule.timestamp);
            println!("  Checksum: {}", &sync_capsule.workspace_checksum[..16]);
            std::process::exit(0);
        }
        Err(e) => {
            eprintln!("\n✗ Vision Survival Protocol failed: {}", e);
            std::process::exit(1);
        }
    }
}
