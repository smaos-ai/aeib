//! Tmux session orchestration for agent isolation
//! Thin wrapper around tmux CLI, fail-closed design

use crate::{DispatchError, Result};
use tokio::process::Command;
use uuid::Uuid;

/// Tmux session lifecycle management
pub struct TmuxSession {
    pub session_name: String,
}

#[derive(Debug)]
pub enum TmuxError {
    SpawnFailed(String),
    KillFailed(String),
}

impl TmuxSession {
    /// Create new tmux session identifier for a job
    pub fn new(job_id: Uuid) -> Self {
        Self {
            session_name: format!("siss-agent-{}", job_id),
        }
    }

    /// Spawn a new tmux session for the job (TDD stub)
    pub async fn spawn(&self, working_dir: &str) -> Result<()> {
        let output = Command::new("tmux")
            .args(&[
                "new-session",
                "-d",
                "-s",
                &self.session_name,
                "-c",
                working_dir,
            ])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(format!("tmux spawn failed: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            return Err(DispatchError::ProcessError(format!(
                "Failed to spawn tmux session: {}",
                stderr
            )));
        }

        Ok(())
    }

    /// Kill a tmux session (TDD stub)
    pub async fn kill(&self) -> Result<()> {
        let output = Command::new("tmux")
            .args(&["kill-session", "-t", &self.session_name])
            .output()
            .await
            .map_err(|e| DispatchError::ProcessError(format!("tmux kill failed: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            // Non-fatal: session may not exist; don't block cleanup
            eprintln!("Warning: tmux kill-session failed: {}", stderr);
        }

        Ok(())
    }

    /// Check if session is running (fail-closed: always false in tests)
    pub async fn is_running(&self) -> bool {
        let output = Command::new("tmux")
            .args(&["list-sessions", "-F", "#{session_name}"])
            .output()
            .await;

        match output {
            Ok(out) => {
                let stdout = String::from_utf8_lossy(&out.stdout);
                stdout.lines().any(|line| line == self.session_name)
            }
            Err(_) => false, // Fail-closed: assume not running if tmux not available
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tmux_session_name_format() {
        let job_id = Uuid::new_v4();
        let session = TmuxSession::new(job_id);
        assert_eq!(session.session_name, format!("siss-agent-{}", job_id));
    }

    #[test]
    fn test_tmux_session_names_unique() {
        let session_a = TmuxSession::new(Uuid::new_v4());
        let session_b = TmuxSession::new(Uuid::new_v4());
        assert_ne!(session_a.session_name, session_b.session_name);
    }
}
