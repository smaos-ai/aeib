/// Phase 62: TUI Status Aggregation — operator cockpit status matrix.

use crate::ag_ui::AgentState;
use chrono::{DateTime, Utc};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct AgentStatusEntry {
    pub agent_id: Uuid,
    pub state: AgentState,
    pub tmux_name: String,
    pub worktree_path: String,
    pub progress_pct: u8,
    pub last_updated: DateTime<Utc>,
}

#[derive(Debug, Clone)]
pub struct DiffEntry {
    pub file_path: String,
    pub insertions: usize,
    pub deletions: usize,
    pub summary: String,
}

#[derive(Debug, Clone)]
pub struct TuiMonitorReport {
    pub entries: Vec<AgentStatusEntry>,
    pub diff_entries: Vec<DiffEntry>,
    pub built_at: DateTime<Utc>,
    pub running_count: usize,
    pub waiting_count: usize,
    pub idle_count: usize,
}

pub struct AoeTuiMonitor {
    registry: HashMap<Uuid, AgentStatusEntry>,
}

impl AoeTuiMonitor {
    pub fn new() -> Self {
        AoeTuiMonitor {
            registry: HashMap::new(),
        }
    }

    pub fn update(
        &mut self,
        agent_id: Uuid,
        state: AgentState,
        tmux_name: &str,
        worktree_path: &str,
        progress_pct: u8,
        now: DateTime<Utc>,
    ) {
        self.registry.insert(
            agent_id,
            AgentStatusEntry {
                agent_id,
                state,
                tmux_name: tmux_name.to_string(),
                worktree_path: worktree_path.to_string(),
                progress_pct,
                last_updated: now,
            },
        );
    }

    pub fn remove(&mut self, agent_id: Uuid) -> Option<AgentStatusEntry> {
        self.registry.remove(&agent_id)
    }

    pub fn build_report(&self, now: DateTime<Utc>) -> TuiMonitorReport {
        let entries: Vec<AgentStatusEntry> = self.registry.values().cloned().collect();

        let running_count = entries.iter().filter(|e| e.state == AgentState::Running).count();
        let waiting_count = entries.iter().filter(|e| e.state == AgentState::Waiting).count();
        let idle_count = entries.iter().filter(|e| e.state == AgentState::Idle).count();

        TuiMonitorReport {
            entries,
            diff_entries: Vec::new(),
            built_at: now,
            running_count,
            waiting_count,
            idle_count,
        }
    }

    pub fn parse_diff(&self, diff_text: &str) -> Vec<DiffEntry> {
        if diff_text.is_empty() {
            return Vec::new();
        }

        let mut entries = Vec::new();
        let mut current_file: Option<String> = None;
        let mut insertions = 0;
        let mut deletions = 0;

        for line in diff_text.lines() {
            if line.starts_with("+++ b/") {
                if let Some(file) = current_file.take() {
                    entries.push(DiffEntry {
                        file_path: file,
                        insertions,
                        deletions,
                        summary: format!("+{} -{}", insertions, deletions),
                    });
                }

                let path = line[6..].to_string();
                current_file = Some(path);
                insertions = 0;
                deletions = 0;
            } else if line.starts_with('+') && !line.starts_with("+++") {
                insertions += 1;
            } else if line.starts_with('-') && !line.starts_with("---") {
                deletions += 1;
            }
        }

        if let Some(file) = current_file {
            entries.push(DiffEntry {
                file_path: file,
                insertions,
                deletions,
                summary: format!("+{} -{}", insertions, deletions),
            });
        }

        entries
    }
}
