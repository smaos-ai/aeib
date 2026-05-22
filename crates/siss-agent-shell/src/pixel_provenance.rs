/// Phase 54: Pixel-Level Provenance & Audit Trail — AP2-Gated GUI Action Recording
/// Every pixel interaction is logged with mandate, screenshot delta, and token cost.

use crate::swarm_mcp_server::{SwarmMcpServer, SwarmStatePayload};
use crate::swarm_channel::{SwarmChannel, SwarmMessage};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PixelProvenanceRecord {
    pub provenance_id: Uuid,
    pub intent_mandate_id: Uuid,           // Uuid::nil() → rejected at record()
    pub task_id: Uuid,
    pub agent_id: String,
    pub phase: String,                     // "PHASE_54"
    pub action_type: String,               // "GuiClick" | "GuiType" | "GuiScroll"
    pub action_x: Option<f64>,
    pub action_y: Option<f64>,
    pub ui_element_selector: Option<String>,
    pub before_screenshot_path: Option<String>,
    pub after_screenshot_path: Option<String>,
    pub token_cost: i64,
    pub recorded_at: DateTime<Utc>,
    pub failure_reason: Option<String>,    // None = success (skip CIPO), Some("reason") = route to retraining
}

#[derive(Debug, PartialEq, Eq)]
pub enum ProvenanceError {
    MissingMandate,
    StoreFailed(String),
    DeserializationFailed(String),
}

pub struct PixelProvenanceRecorder {
    server: Arc<SwarmMcpServer>,
    channel: Option<Arc<SwarmChannel>>,
}

impl PixelProvenanceRecorder {
    pub fn new(server: Arc<SwarmMcpServer>) -> Self {
        PixelProvenanceRecorder { server, channel: None }
    }

    pub fn new_with_channel(server: Arc<SwarmMcpServer>, channel: Arc<SwarmChannel>) -> Self {
        PixelProvenanceRecorder { server, channel: Some(channel) }
    }

    /// RULE 1: record.intent_mandate_id == Uuid::nil() → Err(MissingMandate)
    /// RULE 2: Serialize record → SwarmStatePayload
    /// RULE 3: server.update_swarm_state(payload) → Ok(())
    /// RULE 4: If channel is Some, broadcast SwarmMessage::PixelProvenance (errors silently ignored)
    pub async fn record(&self, record: &PixelProvenanceRecord) -> Result<(), ProvenanceError> {
        if record.intent_mandate_id == Uuid::nil() {
            return Err(ProvenanceError::MissingMandate);
        }

        let payload_json = serde_json::to_string(record)
            .map_err(|e| ProvenanceError::StoreFailed(e.to_string()))?;

        let payload = SwarmStatePayload {
            idempotency_key: format!(
                "pixel_provenance:{}:{}",
                record.agent_id, record.provenance_id
            ),
            agent_id: record.agent_id.clone(),
            phase: "PIXEL_PROVENANCE".to_string(),
            status: record.action_type.clone(),
            payload_json: Some(payload_json),
        };

        self.server
            .update_swarm_state(payload)
            .await
            .map_err(|e| ProvenanceError::StoreFailed(e))?;

        if let Some(channel) = &self.channel {
            let msg = SwarmMessage::PixelProvenance {
                provenance_id: record.provenance_id,
                agent_id: record.agent_id.clone(),
                action_type: record.action_type.clone(),
                action_x: record.action_x,
                action_y: record.action_y,
                token_cost: record.token_cost,
                mandate_id: record.intent_mandate_id,
            };
            let _ = channel.broadcast(msg);
        }

        Ok(())
    }

    /// Filter phase="PIXEL_PROVENANCE", deserialize, match intent_mandate_id
    pub async fn query_by_mandate(
        &self,
        mandate_id: Uuid,
    ) -> Result<Vec<PixelProvenanceRecord>, ProvenanceError> {
        let payloads = self
            .server
            .get_global_state(crate::swarm_mcp_server::GlobalStateFilter {
                phase_filter: Some("PIXEL_PROVENANCE".to_string()),
            })
            .await
            .map_err(|e| ProvenanceError::StoreFailed(e))?;

        let mut results = Vec::new();
        for payload in payloads {
            if let Some(json_str) = &payload.payload_json {
                let record: PixelProvenanceRecord = serde_json::from_str(json_str)
                    .map_err(|e| ProvenanceError::DeserializationFailed(e.to_string()))?;
                if record.intent_mandate_id == mandate_id {
                    results.push(record);
                }
            }
        }

        Ok(results)
    }

    /// Filter phase="PIXEL_PROVENANCE", deserialize, match task_id
    pub async fn query_by_task(
        &self,
        task_id: Uuid,
    ) -> Result<Vec<PixelProvenanceRecord>, ProvenanceError> {
        let payloads = self
            .server
            .get_global_state(crate::swarm_mcp_server::GlobalStateFilter {
                phase_filter: Some("PIXEL_PROVENANCE".to_string()),
            })
            .await
            .map_err(|e| ProvenanceError::StoreFailed(e))?;

        let mut results = Vec::new();
        for payload in payloads {
            if let Some(json_str) = &payload.payload_json {
                let record: PixelProvenanceRecord = serde_json::from_str(json_str)
                    .map_err(|e| ProvenanceError::DeserializationFailed(e.to_string()))?;
                if record.task_id == task_id {
                    results.push(record);
                }
            }
        }

        Ok(results)
    }
}
