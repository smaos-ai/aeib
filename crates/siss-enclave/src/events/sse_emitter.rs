use anyhow::Result;
use axum::response::sse::Event;
use serde_json::json;
use tokio::sync::mpsc;

#[derive(Debug, Clone)]
pub enum SseEvent {
    CanaryFail {
        version: u64,
        reason: String,
    },
    LedgerCommit {
        version: u64,
    },
    ModalityRouted {
        version: u64,
        decisions: Vec<(String, String)>,
    },
}

#[derive(Clone)]
pub struct SseEmitter {
    tx: mpsc::UnboundedSender<Event>,
}

impl SseEmitter {
    pub fn new(tx: mpsc::UnboundedSender<Event>) -> Self {
        Self { tx }
    }

    pub fn broadcast(&self, event: SseEvent) -> Result<()> {
        let sse_event = match event {
            SseEvent::CanaryFail { version, reason } => Event::default()
                .event("CANARY_FAIL")
                .json_data(&json!({ "version": version, "reason": reason }))?,
            SseEvent::LedgerCommit { version } => Event::default()
                .event("LEDGER_COMMIT")
                .json_data(&json!({ "version": version }))?,
            SseEvent::ModalityRouted { version, decisions } => {
                let decision_objects: Vec<_> = decisions
                    .into_iter()
                    .map(|(modality, target)| json!({ "modality": modality, "target": target }))
                    .collect();
                Event::default()
                    .event("MODALITY_ROUTED")
                    .json_data(&json!({ "version": version, "decisions": decision_objects }))?
            }
        };
        // Fire-and-forget: ignore send errors (channel closed/no subscribers)
        let _ = self.tx.send(sse_event);
        Ok(())
    }
}
