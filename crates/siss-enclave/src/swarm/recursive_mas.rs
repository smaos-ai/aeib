use crate::memory::{ConsolidatedEntry, ZonalMemory};
use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

use super::a2a_protocol::{A2ATaskStatus, A2ATaskUpdate, SwarmAgentCard};

pub struct SwarmWorker {
    pub card: SwarmAgentCard,
    pub handler: Arc<
        dyn Fn(Vec<ConsolidatedEntry>) -> Pin<Box<dyn Future<Output = WorkerResult> + Send>>
            + Send
            + Sync,
    >,
}

pub struct WorkerResult {
    pub artifact: Option<ConsolidatedEntry>,
    pub error: Option<String>,
}

#[derive(Debug, Clone, thiserror::Error)]
pub enum SwarmError {
    #[error("unknown skill: {0}")]
    UnknownSkill(String),
    #[error("dispatch failed: {0}")]
    DispatchFailed(String),
}

pub struct RecursiveMasDispatcher {
    zonal_memory: Arc<ZonalMemory>,
    workers: Arc<RwLock<HashMap<String, Arc<SwarmWorker>>>>,
    task_tx: tokio::sync::broadcast::Sender<A2ATaskUpdate>,
    #[allow(dead_code)]
    root_agent_id: Uuid,
}

impl RecursiveMasDispatcher {
    pub fn new(
        zonal_memory: Arc<ZonalMemory>,
        root_agent_id: Uuid,
    ) -> (Self, tokio::sync::broadcast::Receiver<A2ATaskUpdate>) {
        let (task_tx, task_rx) = tokio::sync::broadcast::channel(64);

        let dispatcher = Self {
            zonal_memory,
            workers: Arc::new(RwLock::new(HashMap::new())),
            task_tx,
            root_agent_id,
        };

        (dispatcher, task_rx)
    }

    pub async fn register_worker(&self, worker: SwarmWorker) {
        let skill_id = worker
            .card
            .skills
            .first()
            .map(|s| s.id.clone())
            .unwrap_or_else(|| "default".to_string());

        let mut workers = self.workers.write().await;
        workers.insert(skill_id, Arc::new(worker));
    }

    pub async fn dispatch(
        &self,
        skill_id: &str,
        context_refs: Vec<Uuid>,
        token_budget: i64,
    ) -> Result<Uuid, SwarmError> {
        let workers = self.workers.read().await;
        let worker = workers
            .get(skill_id)
            .cloned()
            .ok_or_else(|| SwarmError::UnknownSkill(skill_id.to_string()))?;
        drop(workers);

        let task_id = Uuid::new_v4();

        let _ = self.task_tx.send(A2ATaskUpdate {
            task_id,
            status: A2ATaskStatus::Pending,
            artifact_ref: None,
            reason: None,
        });

        let zonal = Arc::clone(&self.zonal_memory);
        let tx = self.task_tx.clone();
        let worker_clone = Arc::clone(&worker);

        tokio::spawn(async move {
            let _ = tx.send(A2ATaskUpdate {
                task_id,
                status: A2ATaskStatus::Running,
                artifact_ref: None,
                reason: None,
            });

            let mut materialized = zonal.get_by_ids(&context_refs);

            materialized.sort_by(|a, b| {
                b.confidence
                    .partial_cmp(&a.confidence)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });

            let mut budget_remaining = token_budget;
            let mut projected = Vec::new();
            for entry in materialized {
                if budget_remaining >= entry.token_count {
                    budget_remaining -= entry.token_count;
                    projected.push(entry);
                }
            }

            let result = (worker_clone.handler)(projected).await;

            if let Some(error) = result.error {
                let _ = tx.send(A2ATaskUpdate {
                    task_id,
                    status: A2ATaskStatus::Failed,
                    artifact_ref: None,
                    reason: Some(error),
                });
            } else {
                match result.artifact {
                    Some(artifact) => {
                        let artifact_id = artifact.id;
                        let raw_obs = artifact.into_raw_obs();
                        let _ = zonal.write(raw_obs);
                        let _ = tx.send(A2ATaskUpdate {
                            task_id,
                            status: A2ATaskStatus::Completed,
                            artifact_ref: Some(artifact_id),
                            reason: None,
                        });
                    }
                    None => {
                        let _ = tx.send(A2ATaskUpdate {
                            task_id,
                            status: A2ATaskStatus::Completed,
                            artifact_ref: None,
                            reason: None,
                        });
                    }
                }
            }
        });

        Ok(task_id)
    }

    pub fn subscribe(&self) -> tokio::sync::broadcast::Receiver<A2ATaskUpdate> {
        self.task_tx.subscribe()
    }
}
