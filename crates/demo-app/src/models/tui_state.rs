use super::agent::AgentSession;
use super::agent::MemoryTierState;
use super::document::DocumentManifest;
use super::mandate::AnalysisMandate;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::path::PathBuf;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ActivePane {
    AlphaTmux,
    BetaTmux,
    DocumentQueue,
    AnalysisResults,
    MemoryMetrics,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    pub timestamp_ms: u64,
    pub agent: String,
    pub event: String,
    pub severity: LogLevel,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum LogLevel {
    Info,
    Warn,
    Error,
}

#[derive(Debug, Clone)]
pub struct TuiState {
    pub active_pane: ActivePane,
    pub agent_alpha: AgentSession,
    pub agent_beta: AgentSession,
    pub document_queue: Vec<DocumentManifest>,
    pub current_document: Option<String>,
    pub analysis_results: Vec<AnalysisMandate>,
    pub memory_pressure: f32,
    pub ttft_violation_count: u64,
    pub scroll_offset: usize,
    pub log_buffer: VecDeque<LogEntry>,
    pub violations: u64,
    pub l2_snippets: Vec<String>,
    pub ap2_logs: Vec<String>,
    pub branding_context: String,
}

impl TuiState {
    pub fn new() -> Self {
        let alpha_state = MemoryTierState {
            l2_visible_field_bytes: 0,
            l2_gray_fog_bytes: 0,
            l2_context_map_bytes: 0,
            l3_ledger_entries: 0,
            cache_hit_rate: 0.0,
            ttft_last_request_ms: 0,
        };

        let beta_state = MemoryTierState {
            l2_visible_field_bytes: 0,
            l2_gray_fog_bytes: 0,
            l2_context_map_bytes: 0,
            l3_ledger_entries: 0,
            cache_hit_rate: 0.0,
            ttft_last_request_ms: 0,
        };

        Self {
            active_pane: ActivePane::AlphaTmux,
            agent_alpha: AgentSession {
                agent_id: "alpha".to_string(),
                tmux_pane: "agent-alpha-session:0".to_string(),
                git_worktree: PathBuf::from("/worktrees/alpha"),
                current_document: None,
                active_mandates: vec![],
                inference_tokens_generated: 0,
                memory_tier_state: alpha_state,
                last_activity_ms: 0,
            },
            agent_beta: AgentSession {
                agent_id: "beta".to_string(),
                tmux_pane: "agent-beta-session:0".to_string(),
                git_worktree: PathBuf::from("/worktrees/beta"),
                current_document: None,
                active_mandates: vec![],
                inference_tokens_generated: 0,
                memory_tier_state: beta_state,
                last_activity_ms: 0,
            },
            document_queue: vec![],
            current_document: None,
            analysis_results: vec![],
            memory_pressure: 0.0,
            ttft_violation_count: 0,
            scroll_offset: 0,
            log_buffer: VecDeque::new(),
            violations: 0,
            l2_snippets: vec![],
            ap2_logs: vec![],
            branding_context: "SMAOS Offline Intelligence".to_string(),
        }
    }

    pub fn with_branding(mut self, branding: String) -> Self {
        self.branding_context = branding;
        self
    }

    pub fn push_log(&mut self, entry: LogEntry) {
        self.log_buffer.push_back(entry);
        if self.log_buffer.len() > 20 {
            self.log_buffer.pop_front();
        }
    }
}
