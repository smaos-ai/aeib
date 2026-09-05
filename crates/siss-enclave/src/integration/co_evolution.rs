use crate::learning::{DistillationOrchestrator, GhostBranchBuffer};
use crate::memory::EphemeralBuffer;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// Orchestrates the complete Sovereign Co-Evolution Doctrine:
/// - Negative cascade: Quarantine → Trust decay → -1.0 GRPO → LoRA swap
/// - Positive loop: AP2 success → Trust elevation → +1.0 GRPO → LoRA swap
pub struct CoEvolutionOrchestrator {
    distillation: Arc<DistillationOrchestrator>,
    quarantine_log: Arc<RwLock<HashMap<Uuid, String>>>,
    lora_buffer_history: Arc<RwLock<Vec<String>>>,
    active_lora_id: Arc<RwLock<String>>,
}

impl CoEvolutionOrchestrator {
    pub fn new() -> Self {
        Self {
            distillation: Arc::new(DistillationOrchestrator::new()),
            quarantine_log: Arc::new(RwLock::new(HashMap::new())),
            lora_buffer_history: Arc::new(RwLock::new(vec!["lora-initial".to_string()])),
            active_lora_id: Arc::new(RwLock::new("lora-initial".to_string())),
        }
    }

    /// Process negative cascade: destructive command detection → quarantine → RL training
    pub async fn process_negative_cascade(
        &self,
        ephemeral: Arc<EphemeralBuffer>,
        agent_did: String,
        violation: String,
    ) -> Result<Uuid, String> {
        // Step 1: Extract trajectory from EphemeralBuffer
        tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
        let snapshot = ephemeral.snapshot().await;
        let ghost_branch = GhostBranchBuffer::from_trajectory(snapshot);

        // Step 2: Create quarantine event
        let _quarantine_event = crate::security::BehavioralEvent::QuarantineEntry {
            agent_did: agent_did.clone(),
            violation: violation.clone(),
        };

        // Step 3: Compute GRPO reward
        let reward_signal = crate::learning::BehavioralSignal::QuarantineEntry {
            agent_did,
            violation,
        };
        let reward_model = crate::learning::RewardModel::new();
        let reward = reward_model.compute_reward(&reward_signal).await;

        // Step 4: Queue distillation with negative reward
        let task_id = self
            .distillation
            .queue_distillation(ghost_branch, reward, Uuid::new_v4())
            .await?;

        Ok(task_id)
    }

    /// Process positive loop: AP2 transaction → trust elevation → RL training
    pub async fn process_positive_loop(
        &self,
        ephemeral: Arc<EphemeralBuffer>,
        agent_did: String,
    ) -> Result<Uuid, String> {
        // Step 1: Extract trajectory from EphemeralBuffer
        tokio::time::sleep(tokio::time::Duration::from_millis(50)).await;
        let snapshot = ephemeral.snapshot().await;
        let ghost_branch = GhostBranchBuffer::from_trajectory(snapshot);

        // Step 2: Create AP2 success event
        let _ap2_event = crate::security::BehavioralEvent::Ap2NonceBurn {
            agent_did: agent_did.clone(),
            success: true,
        };

        // Step 3: Compute GRPO reward
        let reward_signal = crate::learning::BehavioralSignal::Ap2NonceBurn {
            agent_did,
            success: true,
        };
        let reward_model = crate::learning::RewardModel::new();
        let reward = reward_model.compute_reward(&reward_signal).await;

        // Step 4: Queue distillation with positive reward
        let task_id = self
            .distillation
            .queue_distillation(ghost_branch, reward, Uuid::new_v4())
            .await?;

        Ok(task_id)
    }

    /// Get distillation status (async poll-safe)
    pub async fn get_distillation_status(&self, task_id: &Uuid) -> Result<bool, String> {
        match self.distillation.get_distillation_status(task_id).await {
            Ok(status) => Ok(status.is_complete),
            Err(_) => Ok(false),
        }
    }

    /// Get scheduled LoRA swap (atomic swap guarantee)
    pub async fn get_scheduled_swap(
        &self,
        task_id: &Uuid,
    ) -> Result<crate::learning::DistillationTask, String> {
        self.distillation.get_scheduled_swap(task_id).await
    }

    /// Queue depth for monitoring
    pub async fn queue_depth(&self) -> usize {
        self.distillation.queue_depth().await
    }

    /// Quarantine failed distillation batch with reason
    pub async fn quarantine_failed_distillation(
        &self,
        task_id: &Uuid,
        reason: &str,
    ) -> Result<(), String> {
        let mut log = self.quarantine_log.write().await;
        log.insert(*task_id, reason.to_string());
        Ok(())
    }

    /// Get audit log for quarantined distillation
    pub async fn get_quarantine_audit_log(&self, task_id: &Uuid) -> Result<String, String> {
        let log = self.quarantine_log.read().await;
        match log.get(task_id) {
            Some(reason) => Ok(format!("task_id: {}, reason: {}", task_id, reason)),
            None => Err("not found in quarantine".to_string()),
        }
    }

    /// Get current active LoRA buffer ID
    pub async fn get_active_lora_id(&self) -> Result<String, String> {
        Ok(self.active_lora_id.read().await.clone())
    }

    /// Rollback to previous LoRA buffer (restore on validation failure)
    pub async fn rollback_lora_buffer(&self, _failed_task_id: &Uuid) -> Result<bool, String> {
        let history = self.lora_buffer_history.read().await;

        if history.len() < 2 {
            return Err("no previous buffer available".to_string());
        }

        // Restore second-to-last buffer (undo latest swap)
        let previous_buffer = history[history.len() - 2].clone();

        drop(history);

        let mut active = self.active_lora_id.write().await;
        *active = previous_buffer;

        Ok(true)
    }

    /// Record successful LoRA swap in history
    pub async fn record_swap(&self, new_lora_id: String) -> Result<(), String> {
        let mut history = self.lora_buffer_history.write().await;
        let mut active = self.active_lora_id.write().await;

        history.push(new_lora_id.clone());
        *active = new_lora_id;

        Ok(())
    }
}

impl Default for CoEvolutionOrchestrator {
    fn default() -> Self {
        Self::new()
    }
}
