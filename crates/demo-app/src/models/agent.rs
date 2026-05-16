use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSession {
    pub agent_id: String,
    pub tmux_pane: String,
    pub git_worktree: PathBuf,
    pub current_document: Option<String>,
    pub active_mandates: Vec<String>,
    pub inference_tokens_generated: u64,
    pub memory_tier_state: MemoryTierState,
    pub last_activity_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryTierState {
    pub l2_visible_field_bytes: u64,
    pub l2_gray_fog_bytes: u64,
    pub l2_context_map_bytes: u64,
    pub l3_ledger_entries: usize,
    pub cache_hit_rate: f32,
    pub ttft_last_request_ms: u64,
}
