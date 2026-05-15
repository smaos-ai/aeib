use anyhow::Result;
use tracing::{info, warn};

use crate::events::sse_emitter::{SseEmitter, SseEvent};

#[async_trait::async_trait]
pub trait Judge: Send + Sync {
    async fn evaluate_next(&self) -> Result<Verdict>;
}

#[derive(Debug)]
pub struct Verdict {
    pub pass: bool,
    pub reason: String,
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
