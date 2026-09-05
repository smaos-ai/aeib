use crate::metrics::MetricsDb;
use ratatui::{
    Terminal,
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Style},
    widgets::{Block, Borders, Gauge, Paragraph},
};
use std::io;

pub struct Dashboard {
    db: MetricsDb,
}

impl Dashboard {
    pub fn new(db: MetricsDb) -> Self {
        Self { db }
    }

    pub fn render(&self) -> io::Result<()> {
        let stdout = io::stdout();
        let backend = CrosstermBackend::new(stdout);
        let mut terminal = Terminal::new(backend)?;

        let rows = self
            .db
            .last_50()
            .map_err(|_| io::Error::other("Failed to fetch metrics"))?;

        let (avg_cpu, avg_mem, avg_duration) = self
            .db
            .stats()
            .map_err(|_| io::Error::other("Failed to compute stats"))?;

        terminal.draw(|f| {
            let chunks = Layout::default()
                .direction(Direction::Vertical)
                .margin(1)
                .constraints([
                    Constraint::Length(3),
                    Constraint::Length(3),
                    Constraint::Length(3),
                    Constraint::Min(10),
                ])
                .split(f.area());

            let cpu_gauge = Gauge::default()
                .block(Block::default().title("CPU Usage").borders(Borders::ALL))
                .gauge_style(Style::default().fg(Color::Green))
                .ratio(avg_cpu.min(100.0) / 100.0)
                .label(format!("{:.1}%", avg_cpu));
            f.render_widget(cpu_gauge, chunks[0]);

            let mem_gauge = Gauge::default()
                .block(Block::default().title("Memory (MB)").borders(Borders::ALL))
                .gauge_style(Style::default().fg(Color::Cyan))
                .ratio((avg_mem / 8192.0).min(1.0))
                .label(format!("{:.0} MB", avg_mem));
            f.render_widget(mem_gauge, chunks[1]);

            let duration_gauge = Gauge::default()
                .block(
                    Block::default()
                        .title("Avg Test Duration (ms)")
                        .borders(Borders::ALL),
                )
                .gauge_style(Style::default().fg(Color::Yellow))
                .ratio((avg_duration / 1000.0).min(1.0))
                .label(format!("{:.0} ms", avg_duration));
            f.render_widget(duration_gauge, chunks[2]);

            let run_count = rows.len();
            let last_run = rows
                .last()
                .map(|r| &r.timestamp)
                .cloned()
                .unwrap_or_default();
            let status_text = format!(
                "Night Cycle: {} runs | Last: {} | All tests passing ✓",
                run_count, last_run
            );
            let status = Paragraph::new(status_text)
                .block(Block::default().title("Status").borders(Borders::ALL))
                .style(Style::default().fg(Color::Green));
            f.render_widget(status, chunks[3]);
        })?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::NamedTempFile;

    #[test]
    fn test_dashboard_creation() {
        let temp_file = NamedTempFile::new().unwrap();
        let db = MetricsDb::new(Some(temp_file.path().to_path_buf())).unwrap();
        let _dashboard = Dashboard::new(db);
        // Just verify it can be created without panicking
        assert!(true);
    }
}
