use crate::app::App;
use crossterm::event::{self, KeyCode, KeyEvent};
use std::io;
use std::time::Duration;

pub async fn run_app(app: &mut App) -> io::Result<()> {
    let tick_rate = Duration::from_millis(100);

    loop {
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
