use log::error;
use smaos_qa::run_qa_pipeline;

#[tokio::main]
async fn main() {
    env_logger::Builder::from_default_env()
        .filter_level(log::LevelFilter::Info)
        .init();

    match run_qa_pipeline().await {
        Ok(_) => {
            std::process::exit(0)
        }
        Err(e) => {
            error!("\n[ERROR] Pipeline failed: {}", e);
            std::process::exit(1)
        }
    }
}
