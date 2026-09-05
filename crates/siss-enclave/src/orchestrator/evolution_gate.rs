use anyhow::Result;
use tracing::{info, warn};

use crate::events::sse_emitter::{SseEmitter, SseEvent};
use crate::model::modality::Modality;
use crate::routing::omni_router::OmniRoute;

#[async_trait::async_trait]
pub trait Judge: Send + Sync {
    async fn evaluate_next(&self) -> Result<Verdict>;
}

#[derive(Debug)]
pub struct Verdict {
    pub pass: bool,
    pub reason: String,
    pub approved_for_modalities: Vec<Modality>,
}

#[async_trait::async_trait]
pub trait DoubleBufferedSwap: Send + Sync {
    async fn execute_swap(&self, version: u64) -> Result<()>;
    async fn discard(&self, version: u64) -> Result<()>;
}

#[async_trait::async_trait]
pub trait RceStateMachine: Send + Sync {
    async fn pause_workflow_with_persistence(&self) -> Result<()>;
    async fn resume_workflow_approve_with_persistence(&self, version: u64) -> Result<()>;
    async fn resume_workflow_rollback(&self) -> Result<()>;
}

pub struct EvolutionGate {
    pub judge: Box<dyn Judge>,
    pub swap: Box<dyn DoubleBufferedSwap>,
    pub rce: Box<dyn RceStateMachine>,
    pub emitter: SseEmitter,
}

impl EvolutionGate {
    pub async fn process_evolution(&self, version: u64) -> Result<()> {
        info!(%version, "Evolution gate: pausing RCE for evaluation");
        self.rce.pause_workflow_with_persistence().await?;

        let verdict = self.judge.evaluate_next().await?;

        // Compute per-modality routing decisions
        let omni = OmniRoute::new();
        let decisions = omni.route(&verdict);
        let decision_vec: Vec<(String, String)> = decisions
            .iter()
            .map(|(modality, target)| {
                let modality_str = match modality {
                    Modality::Text => "Text".to_string(),
                    Modality::Vision => "Vision".to_string(),
                    Modality::Audio => "Audio".to_string(),
                };
                let target_str = match target {
                    crate::routing::omni_router::RouteTarget::Shadow => "shadow".to_string(),
                    crate::routing::omni_router::RouteTarget::Baseline => "baseline".to_string(),
                };
                (modality_str, target_str)
            })
            .collect();
        self.emitter.broadcast(SseEvent::ModalityRouted {
            version,
            decisions: decision_vec,
        })?;

        if verdict.pass {
            // CRITICAL BARRIER: Swap -> Persist -> SSE (fire-and-forget)
            info!(%version, "Judge passed. Executing atomic swap barrier...");

            // 1. Atomic Swap (Double-Buffered in-memory CAS)
            self.swap.execute_swap(version).await?;

            // 2. Resume RCE with DB persistence (blocks until durable)
            self.rce
                .resume_workflow_approve_with_persistence(version)
                .await?;

            // 3. Notify Operator Cockpit (fire-and-forget async)
            self.emitter.broadcast(SseEvent::LedgerCommit { version })?;
        } else {
            warn!(%version, "Judge failed: {}", verdict.reason);
            self.swap.discard(version).await?;
            self.rce.resume_workflow_rollback().await?;
            // SSE broadcast on failure (fire-and-forget)
            self.emitter.broadcast(SseEvent::CanaryFail {
                version,
                reason: verdict.reason,
            })?;
        }
        Ok(())
    }
}
