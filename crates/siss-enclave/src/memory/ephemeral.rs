use std::sync::Arc;
use super::zonal::RawObservation;

pub struct EphemeralBuffer {
    trajectory: Arc<tokio::sync::RwLock<Vec<String>>>,
}

impl EphemeralBuffer {
    pub fn new(sender: tokio::sync::mpsc::Sender<RawObservation>) -> Self {
        let _ = sender; // Suppress unused warning
        Self {
            trajectory: Arc::new(tokio::sync::RwLock::new(Vec::new())),
        }
    }

    pub async fn snapshot(&self) -> Vec<String> {
        self.trajectory.read().await.clone()
    }

    pub fn append_thought(&self, thought: String) {
        let trajectory = Arc::clone(&self.trajectory);
        tokio::spawn(async move {
            trajectory.write().await.push(thought);
        });
    }

    pub fn append_tool_call(&self, tool: String, _args: String) {
        let trajectory = Arc::clone(&self.trajectory);
        tokio::spawn(async move {
            trajectory.write().await.push(tool);
        });
    }

    pub fn append_action_result(&self, result: String) {
        let trajectory = Arc::clone(&self.trajectory);
        tokio::spawn(async move {
            trajectory.write().await.push(result);
        });
    }
}
