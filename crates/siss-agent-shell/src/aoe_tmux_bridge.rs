/// Phase 62: Tmux Session Isolation — 1:1 session-to-agent binding with detach resilience.
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

#[async_trait::async_trait]
pub trait TmuxSessionDriver: Send + Sync {
    async fn spawn(&self, name: &str, working_dir: &str) -> Result<(), TmuxBridgeError>;
    async fn kill(&self, name: &str) -> Result<(), TmuxBridgeError>;
}

#[derive(Debug)]
pub struct TmuxSessionToken {
    pub session_name: String,
    pub agent_id: Uuid,
    pub working_dir: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TmuxBridgeError {
    AlreadyBound { session_name: String, held_by: Uuid },
    SpawnFailed(String),
    SessionNotFound { session_name: String },
    KillFailed(String),
}

#[derive(Debug, Clone)]
pub struct TmuxBridgeConfig {
    pub session_prefix: String,
    pub detach_resilient: bool,
}

impl Default for TmuxBridgeConfig {
    fn default() -> Self {
        TmuxBridgeConfig {
            session_prefix: "siss-agent".to_string(),
            detach_resilient: true,
        }
    }
}

pub struct AoeTmuxBridge<D: TmuxSessionDriver> {
    pub driver: D,
    pub config: TmuxBridgeConfig,
    registry: Arc<tokio::sync::Mutex<HashMap<String, Uuid>>>,
}

impl<D: TmuxSessionDriver> AoeTmuxBridge<D> {
    pub fn new(driver: D, config: TmuxBridgeConfig) -> Self {
        Self {
            driver,
            config,
            registry: Arc::new(tokio::sync::Mutex::new(HashMap::new())),
        }
    }

    pub async fn bind(
        &self,
        agent_id: Uuid,
        working_dir: &str,
    ) -> Result<TmuxSessionToken, TmuxBridgeError> {
        let session_name = self.session_name_for(agent_id);

        let reg = self.registry.lock().await;
        if let Some(&existing_id) = reg.get(&session_name) {
            return Err(TmuxBridgeError::AlreadyBound {
                session_name,
                held_by: existing_id,
            });
        }

        drop(reg);

        if let Err(e) = self.driver.spawn(&session_name, working_dir).await {
            return Err(e);
        }

        let mut reg = self.registry.lock().await;
        reg.insert(session_name.clone(), agent_id);

        Ok(TmuxSessionToken {
            session_name,
            agent_id,
            working_dir: working_dir.to_string(),
        })
    }

    pub async fn unbind(&self, token: TmuxSessionToken) -> Result<(), TmuxBridgeError> {
        let reg = self.registry.lock().await;

        if !reg.contains_key(&token.session_name) {
            return Err(TmuxBridgeError::SessionNotFound {
                session_name: token.session_name,
            });
        }

        drop(reg);

        if let Err(e) = self.driver.kill(&token.session_name).await {
            return Err(e);
        }

        let mut reg = self.registry.lock().await;
        reg.remove(&token.session_name);

        Ok(())
    }

    pub fn list_bound(&self) -> Vec<(String, Uuid)> {
        match self.registry.try_lock() {
            Ok(reg) => reg.iter().map(|(name, id)| (name.clone(), *id)).collect(),
            Err(_) => Vec::new(),
        }
    }

    pub fn session_name_for(&self, agent_id: Uuid) -> String {
        format!("{}-{}", self.config.session_prefix, agent_id)
    }
}
