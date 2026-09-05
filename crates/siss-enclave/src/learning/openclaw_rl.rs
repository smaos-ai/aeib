use crate::security::BehavioralEvent;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

use super::ghost_branch::GhostBranchBuffer;

/// Behavioral signal extracted from agent events for reward computation.
#[derive(Debug, Clone)]
pub enum BehavioralSignal {
    Ap2NonceBurn {
        agent_did: String,
        success: bool,
    },
    GitNexusBlastRadiusBlock {
        agent_did: String,
        affected_files: usize,
        critical_modules: usize,
    },
    QuarantineEntry {
        agent_did: String,
        violation: String,
    },
    Neutral,
}

impl BehavioralSignal {
    pub fn from_event(event: &BehavioralEvent) -> Self {
        match event {
            BehavioralEvent::Ap2NonceBurn { agent_did, success } => Self::Ap2NonceBurn {
                agent_did: agent_did.clone(),
                success: *success,
            },
            BehavioralEvent::GitNexusBlastRadiusBlock {
                agent_did,
                affected_files,
                critical_modules,
            } => Self::GitNexusBlastRadiusBlock {
                agent_did: agent_did.clone(),
                affected_files: *affected_files,
                critical_modules: *critical_modules,
            },
            BehavioralEvent::QuarantineEntry {
                agent_did,
                violation,
            } => Self::QuarantineEntry {
                agent_did: agent_did.clone(),
                violation: violation.clone(),
            },
        }
    }
}

/// Maps behavioral signals to normalized scalar rewards [-1.0, +1.0].
pub struct RewardModel;

impl RewardModel {
    pub fn new() -> Self {
        Self
    }

    pub async fn compute_reward(&self, signal: &BehavioralSignal) -> f32 {
        match signal {
            // AP2 success: +0.05 trust delta → normalize to [+0.9, +1.0]
            BehavioralSignal::Ap2NonceBurn {
                agent_did: _,
                success: true,
            } => 0.95,

            // AP2 failure: -0.05 trust delta → normalize to [-0.5, -0.3]
            BehavioralSignal::Ap2NonceBurn {
                agent_did: _,
                success: false,
            } => -0.4,

            // GitNexus block: -0.10 trust delta → normalize to [-1.0, -0.9]
            BehavioralSignal::GitNexusBlastRadiusBlock {
                agent_did: _,
                affected_files: _,
                critical_modules: _,
            } => -0.95,

            // Quarantine: -0.15 trust delta → normalize to [-1.0, -0.9]
            BehavioralSignal::QuarantineEntry {
                agent_did: _,
                violation: _,
            } => -0.95,

            // Neutral: no change → map to [-0.05, +0.05]
            BehavioralSignal::Neutral => 0.0,
        }
    }
}

impl Default for RewardModel {
    fn default() -> Self {
        Self::new()
    }
}

/// Status of a distillation task in the queue.
#[derive(Debug, Clone)]
pub struct DistillationTask {
    pub task_id: Uuid,
    pub ghost_branch: GhostBranchBuffer,
    pub reward: f32,
    pub agent_id: Uuid,
    pub is_complete: bool,
    pub swap_token: String,
    pub new_lora_id: Option<String>,
}

/// Non-blocking async queue for GRPO distillation with LoRA swap scheduling.
pub struct DistillationOrchestrator {
    queue: Arc<RwLock<Vec<DistillationTask>>>,
    completed: Arc<RwLock<HashMap<Uuid, DistillationTask>>>,
}

impl DistillationOrchestrator {
    pub fn new() -> Self {
        Self {
            queue: Arc::new(RwLock::new(Vec::new())),
            completed: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Queue distillation task. Returns immediately (non-blocking).
    pub async fn queue_distillation(
        &self,
        ghost_branch: GhostBranchBuffer,
        reward: f32,
        agent_id: Uuid,
    ) -> Result<Uuid, String> {
        let task_id = Uuid::new_v4();
        let task = DistillationTask {
            task_id,
            ghost_branch,
            reward,
            agent_id,
            is_complete: false,
            swap_token: String::new(),
            new_lora_id: None,
        };

        let mut queue = self.queue.write().await;
        queue.push(task);

        // Spawn async background processor (fire-and-forget)
        let queue_clone = Arc::clone(&self.queue);
        let completed_clone = Arc::clone(&self.completed);
        tokio::spawn(async move {
            // Simulate distillation processing
            tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;

            let mut q = queue_clone.write().await;
            if let Some(pos) = q.iter().position(|t| t.task_id == task_id) {
                let mut task = q.remove(pos);
                task.is_complete = true;
                task.swap_token = format!("swap-token-{}", uuid::Uuid::new_v4());
                task.new_lora_id = Some(format!("lora-{}", uuid::Uuid::new_v4()));

                let mut completed = completed_clone.write().await;
                completed.insert(task_id, task);
            }
        });

        Ok(task_id)
    }

    pub async fn queue_depth(&self) -> usize {
        self.queue.read().await.len()
    }

    pub async fn get_distillation_status(
        &self,
        task_id: &Uuid,
    ) -> Result<DistillationTask, String> {
        let completed = self.completed.read().await;
        if let Some(task) = completed.get(task_id) {
            return Ok(task.clone());
        }

        let queue = self.queue.read().await;
        if let Some(task) = queue.iter().find(|t| t.task_id == *task_id) {
            return Ok(task.clone());
        }

        Err(format!("task {} not found", task_id))
    }

    pub async fn get_scheduled_swap(&self, task_id: &Uuid) -> Result<DistillationTask, String> {
        let completed = self.completed.read().await;
        if let Some(task) = completed.get(task_id) {
            if task.is_complete {
                return Ok(task.clone());
            }
        }
        Err(format!("swap not scheduled for task {}", task_id))
    }
}

impl Default for DistillationOrchestrator {
    fn default() -> Self {
        Self::new()
    }
}

/// GRPO loss computation from scalar rewards.
pub struct GRPOLoss {
    _batch_size: usize,
}

impl GRPOLoss {
    pub fn new(batch_size: usize) -> Self {
        Self {
            _batch_size: batch_size,
        }
    }

    /// Compute GRPO loss from logits and rewards.
    pub fn compute_loss(
        &self,
        _logits: &[f32],
        logits_shape: &[usize],
        rewards: &[f32],
    ) -> Result<f32, String> {
        if logits_shape.is_empty() {
            return Err("logits_shape must not be empty".to_string());
        }

        let batch_size = logits_shape[0];
        if batch_size != rewards.len() {
            return Err(format!(
                "batch_size {} != rewards.len() {}",
                batch_size,
                rewards.len()
            ));
        }

        // Simplified GRPO loss: mean of squared rewards (proxy for policy gradient loss)
        let loss = rewards.iter().map(|r| r * r).sum::<f32>() / batch_size as f32;

        Ok(loss)
    }
}
