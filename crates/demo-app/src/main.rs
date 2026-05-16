use demo_app::app::App;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut app = App::new();

    // For now, just run the event loop
    demo_app::tui::run_app(&mut app).await?;

    Ok(())
}
