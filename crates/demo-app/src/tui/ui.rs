use crate::app::App;
use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Paragraph};

pub fn render(frame: &mut Frame, _app: &App) {
    let layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3),
            Constraint::Min(20),
            Constraint::Min(10),
        ])
        .split(frame.area());

    // Header
    let header = Paragraph::new("SMAOS Offline Intelligence")
        .block(Block::default().borders(Borders::BOTTOM));
    frame.render_widget(header, layout[0]);

    // Agent panes (placeholder)
    let content = Paragraph::new("Content area").block(Block::default().borders(Borders::ALL));
    frame.render_widget(content, layout[1]);

    // Log buffer
    let log = Paragraph::new("Log area").block(Block::default().borders(Borders::ALL));
    frame.render_widget(log, layout[2]);
}
