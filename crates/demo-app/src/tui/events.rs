use crate::app::App;
use crate::models::TuiState;
use crate::tui::ui::render;
use crossterm::{
    event::{self, KeyCode, KeyEvent},
    execute,
    terminal::{EnterAlternateScreen, LeaveAlternateScreen, disable_raw_mode, enable_raw_mode},
};
use ratatui::prelude::*;
use std::io;
use std::sync::{Arc, Mutex};
use std::time::Duration;

pub async fn run_app(app: &mut App) -> io::Result<()> {
    run_app_with_state(app, None).await
}

pub async fn run_app_with_state(
    app: &mut App,
    shared_state: Option<Arc<Mutex<TuiState>>>,
) -> io::Result<()> {
    // Setup terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let tick_rate = Duration::from_millis(100);
    let result = event_loop(&mut terminal, app, shared_state, tick_rate).await;

    // Restore terminal
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;

    result
}

async fn event_loop(
    terminal: &mut Terminal<CrosstermBackend<io::Stdout>>,
    app: &mut App,
    shared_state: Option<Arc<Mutex<TuiState>>>,
    tick_rate: Duration,
) -> io::Result<()> {
    loop {
        terminal.draw(|frame| {
            // Use shared state if available, otherwise use app.state
            if let Some(ref state) = shared_state {
                if let Ok(state_guard) = state.lock() {
                    render(frame, &*state_guard);
                } else {
                    render(frame, &app.state);
                }
            } else {
                render(frame, &app.state);
            }
        })?;

        if event::poll(tick_rate)? {
            if let event::Event::Key(KeyEvent { code, .. }) = event::read()? {
                match code {
                    KeyCode::Char(c) => {
                        app.on_key(c);
                    }
                    KeyCode::Esc => {
                        app.should_quit = true;
                    }
                    _ => {}
                }
            }
        }

        app.tick();

        if app.should_quit {
            break;
        }
    }

    Ok(())
}
