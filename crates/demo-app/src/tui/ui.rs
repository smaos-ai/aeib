use crate::models::tui_state::TuiState;
use ratatui::{
    prelude::*,
    widgets::{Block, Borders, List, ListItem, Paragraph, Wrap},
};

/// The pure projection function: mapping the proven state machine to the Terminal Visible Field.
pub fn render(frame: &mut Frame, state: &TuiState) {
    // 1. Architect the 5-Panel Layout constraints
    let main_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // Panel 1: Sovereign Header
            Constraint::Min(15),   // Panels 2, 3, 4: Agents & Cartography
            Constraint::Length(8), // Panel 5: AP2 Audit Log
        ])
        .split(frame.area());

    let middle_layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(50), // Left: Agent Swarm
            Constraint::Percentage(50), // Right: Cartography Visualizer
        ])
        .split(main_layout[1]);

    let agent_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Percentage(50), // Top-Left: Agent Alpha
            Constraint::Percentage(50), // Bottom-Left: Agent Beta
        ])
        .split(middle_layout[0]);

    // ========================================================================
    // PANEL 1: The Sovereign Header
    // ========================================================================
    let header_text = format!(
        " {} - SMAOS SECURE ENCLAVE | Mem: {:.0}% | TTFT: {}ms | Violations: {} ",
        state.branding_context,
        state.memory_pressure,
        state.agent_alpha.memory_tier_state.ttft_last_request_ms,
        state.ttft_violation_count
    );
    let header_block = Paragraph::new(Text::styled(
        header_text,
        Style::default()
            .fg(Color::Cyan)
            .add_modifier(Modifier::BOLD),
    ))
    .block(Block::default().borders(Borders::ALL).title("Telemetry"))
    .alignment(Alignment::Center);

    frame.render_widget(header_block, main_layout[0]);

    // ========================================================================
    // PANEL 2: Agent Alpha Pane (Mirrored tmux execution)
    // ========================================================================
    let alpha_worktree = state.agent_alpha.git_worktree.display().to_string();
    let alpha_current_doc = state.agent_alpha.current_document.as_deref().unwrap_or("—");
    let alpha_tokens = state.agent_alpha.inference_tokens_generated;
    let alpha_content = format!(
        "Worktree: {}\nCurrent Document: {}\nTokens Generated: {}\nActive Mandates: {}",
        alpha_worktree,
        alpha_current_doc,
        alpha_tokens,
        state.agent_alpha.active_mandates.len()
    );
    let alpha_pane = Paragraph::new(alpha_content)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Agent Alpha [Pane: agent-alpha-session:0]"),
        )
        .wrap(Wrap { trim: true })
        .style(Style::default().fg(Color::Green));

    frame.render_widget(alpha_pane, agent_layout[0]);

    // ========================================================================
    // PANEL 3: Agent Beta Pane (Mirrored tmux execution)
    // ========================================================================
    let beta_worktree = state.agent_beta.git_worktree.display().to_string();
    let beta_current_doc = state.agent_beta.current_document.as_deref().unwrap_or("—");
    let beta_tokens = state.agent_beta.inference_tokens_generated;
    let beta_content = format!(
        "Worktree: {}\nCurrent Document: {}\nTokens Generated: {}\nActive Mandates: {}",
        beta_worktree,
        beta_current_doc,
        beta_tokens,
        state.agent_beta.active_mandates.len()
    );
    let beta_pane = Paragraph::new(beta_content)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Agent Beta [Pane: agent-beta-session:0]"),
        )
        .wrap(Wrap { trim: true })
        .style(Style::default().fg(Color::Yellow));

    frame.render_widget(beta_pane, agent_layout[1]);

    // ========================================================================
    // PANEL 4: Context Cartography / L2 Visualizer
    // ========================================================================
    let cartography_items: Vec<ListItem> = state
        .analysis_results
        .iter()
        .take(10)
        .enumerate()
        .map(|(i, mandate)| {
            ListItem::new(format!(
                "[φ-Compressed] Task {}: {:?}",
                i + 1,
                mandate.analysis_type
            ))
            .style(Style::default().fg(Color::Magenta))
        })
        .collect();

    let cartography_pane = if cartography_items.is_empty() {
        List::new(vec![
            ListItem::new("(No L2 snippets in transit)")
                .style(Style::default().fg(Color::DarkGray)),
        ])
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Context Cartography (G -> V)"),
        )
    } else {
        List::new(cartography_items).block(
            Block::default()
                .borders(Borders::ALL)
                .title("Context Cartography (G -> V)"),
        )
    };

    frame.render_widget(cartography_pane, middle_layout[1]);

    // ========================================================================
    // PANEL 5: AP2 Audit Log
    // ========================================================================
    let audit_items: Vec<ListItem> = state
        .log_buffer
        .iter()
        .rev()
        .take(6)
        .map(|log| {
            let level_indicator = match log.severity {
                crate::models::tui_state::LogLevel::Error => "🔴",
                crate::models::tui_state::LogLevel::Warn => "🟡",
                crate::models::tui_state::LogLevel::Info => "🟢",
            };
            let style = match log.severity {
                crate::models::tui_state::LogLevel::Error => {
                    Style::default().fg(Color::Red).add_modifier(Modifier::BOLD)
                }
                crate::models::tui_state::LogLevel::Warn => Style::default().fg(Color::Yellow),
                crate::models::tui_state::LogLevel::Info => Style::default().fg(Color::DarkGray),
            };
            ListItem::new(format!("{} [{}] {}", level_indicator, log.agent, log.event)).style(style)
        })
        .collect();

    let audit_pane = List::new(audit_items).block(
        Block::default()
            .borders(Borders::ALL)
            .title("AP2 Ledger & Collision Firewall"),
    );

    frame.render_widget(audit_pane, main_layout[2]);
}
