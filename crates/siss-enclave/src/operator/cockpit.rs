use crate::integration::CoEvolutionOrchestrator;
use crate::memory::EphemeralBuffer;
use crate::operator::hitl::{CryptoApproval, HitlError, HitlGate};
use crate::operator::telemetry::{LoraSwapEvent, OperatorTelemetry, SwapEventKind};
use std::sync::Arc;
use tokio::sync::broadcast;
use uuid::Uuid;

pub struct ContextProjection {
    pub agent_id: Uuid,
    pub visible_field_entries: usize,
    pub gray_fog_summary: String,
    pub pending_approvals: Vec<Uuid>,
}

pub struct OperatorCockpit {
    telemetry: Arc<OperatorTelemetry>,
    hitl_gate: Arc<HitlGate>,
    orchestrator: Arc<CoEvolutionOrchestrator>,
}

impl OperatorCockpit {
    pub fn new(
        orchestrator: Arc<CoEvolutionOrchestrator>,
    ) -> (Self, broadcast::Receiver<LoraSwapEvent>) {
        let (telemetry, rx) = OperatorTelemetry::new();
        (
            Self {
                telemetry: Arc::new(telemetry),
                hitl_gate: Arc::new(HitlGate::new()),
                orchestrator,
            },
            rx,
        )
    }

    pub fn subscribe_telemetry(&self) -> broadcast::Receiver<LoraSwapEvent> {
        self.telemetry.subscribe()
    }

    pub async fn process_distillation_with_telemetry(
        &self,
        ephemeral: Arc<EphemeralBuffer>,
        agent_did: String,
    ) -> Result<Uuid, String> {
        // Emit Queued event as pre-queue sentinel
        let pre_queue_id = Uuid::new_v4();
        self.telemetry.emit(LoraSwapEvent {
            task_id: pre_queue_id,
            agent_id: agent_did.clone(),
            kind: SwapEventKind::Queued,
            timestamp_ms: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis() as u64,
        });

        // Queue distillation via orchestrator
        let task_id = self
            .orchestrator
            .process_positive_loop(ephemeral, agent_did.clone())
            .await?;

        // Poll for completion (up to 2000ms)
        let mut attempts = 0;
        let max_attempts = 200;
        let mut completed = false;
        let mut swap_token = String::new();
        let mut new_lora_id = String::new();

        while attempts < max_attempts && !completed {
            if let Ok(task) = self.orchestrator.get_scheduled_swap(&task_id).await {
                if task.is_complete {
                    completed = true;
                    swap_token = task.swap_token;
                    new_lora_id = task.new_lora_id.unwrap_or_default();
                }
            }
            attempts += 1;
            tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
        }

        // Emit Authorized event on completion
        if completed {
            self.telemetry.emit(LoraSwapEvent {
                task_id,
                agent_id: agent_did,
                kind: SwapEventKind::Authorized {
                    swap_token,
                    new_lora_id,
                },
                timestamp_ms: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis() as u64,
            });
        }

        Ok(task_id)
    }

    pub async fn project_agent_state(&self, agent_id: Uuid) -> Result<ContextProjection, String> {
        // Return a basic projection (can be extended to query Gray Fog, etc.)
        Ok(ContextProjection {
            agent_id,
            visible_field_entries: 0,
            gray_fog_summary: "agent_context_projection".to_string(),
            pending_approvals: vec![],
        })
    }

    pub async fn issue_operator_approval(&self, approval: CryptoApproval) -> Result<(), HitlError> {
        self.hitl_gate.issue_approval(approval).await
    }

    pub fn hitl_gate(&self) -> Arc<HitlGate> {
        self.hitl_gate.clone()
    }
}
