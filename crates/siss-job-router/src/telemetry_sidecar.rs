/// Sovereign Telemetry Sidecar: Observer Plane
/// Captures failure traces and routes them exclusively to the local CIPO loop.
/// Zero cloud egress—all telemetry stays in-memory and feeds SLM retraining.
use crate::cipo::{CipoDistiller, CipoTrace, RefinementSignal};
use crate::confidence_scorer::RoutingTier;
use chrono::{DateTime, Utc};
use std::sync::{Arc, Mutex};
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TelemetryEventKind {
    MandateBlocked,
    TrajectoryRejected,
    GateFailure,
    ChaosInjected,
    ManifestRejected,
}

#[derive(Debug, Clone)]
pub struct TelemetryEvent {
    pub event_id: Uuid,
    pub kind: TelemetryEventKind,
    pub agent_id: Option<Uuid>,
    pub payload_summary: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum TelemetryError {
    CloudEndpointDetected { endpoint: String },
}

pub struct SovereignTelemetrySidecar {
    events: Arc<Mutex<Vec<TelemetryEvent>>>,
}

impl SovereignTelemetrySidecar {
    pub fn new() -> Self {
        SovereignTelemetrySidecar {
            events: Arc::new(Mutex::new(Vec::new())),
        }
    }

    /// RULE A: payload_summary containing "https://" or "http://" → Err(CloudEndpointDetected)
    /// RULE B: all other events stored in Arc<Mutex<Vec>> — no network, no file I/O
    pub fn log_event(&self, event: TelemetryEvent) -> Result<(), TelemetryError> {
        // RULE A: Cloud endpoint detection
        if event.payload_summary.contains("https://") || event.payload_summary.contains("http://") {
            return Err(TelemetryError::CloudEndpointDetected {
                endpoint: event.payload_summary.clone(),
            });
        }

        // RULE B: Store in-memory
        let mut events = self.events.lock().unwrap();
        events.push(event);
        Ok(())
    }

    /// Convert stored events to CipoTrace format for Night Cycle ingestion.
    /// Data contract:
    ///   payload             ← event.payload_summary
    ///   slm_output          ← "<telemetry: no SLM output>"
    ///   gate_error_raw      ← format!("{:?}", event.kind)
    ///   tier_escalated_from ← RoutingTier::Tier1RapidMLX
    ///   tier_escalated_to   ← RoutingTier::Tier3Opus
    ///   timestamp           ← event.timestamp
    pub fn export_as_cipo_traces(&self) -> Vec<CipoTrace> {
        let events = self.events.lock().unwrap();
        events
            .iter()
            .map(|event| CipoTrace {
                payload: event.payload_summary.clone(),
                slm_output: "<telemetry: no SLM output>".to_string(),
                gate_error_raw: format!("{:?}", event.kind),
                tier_escalated_from: RoutingTier::Tier1RapidMLX,
                tier_escalated_to: RoutingTier::Tier3Opus,
                timestamp: event.timestamp,
            })
            .collect()
    }

    /// Proof: assert no stored event's payload_summary contains "https://" or "http://"
    pub fn assert_no_cloud_telemetry(&self) -> bool {
        let events = self.events.lock().unwrap();
        events.iter().all(|e| {
            !e.payload_summary.contains("https://") && !e.payload_summary.contains("http://")
        })
    }

    /// Convenience: export traces and distill into RefinementSignals.
    /// Calls CipoDistiller::distill(self.export_as_cipo_traces()).
    pub fn distill_signals(&self) -> Vec<RefinementSignal> {
        let traces = self.export_as_cipo_traces();
        CipoDistiller::distill(&traces)
    }
}

impl Default for SovereignTelemetrySidecar {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_log_valid_event() {
        let sidecar = SovereignTelemetrySidecar::new();
        let event = TelemetryEvent {
            event_id: Uuid::new_v4(),
            kind: TelemetryEventKind::GateFailure,
            agent_id: None,
            payload_summary: "gate_failure_local".to_string(),
            timestamp: Utc::now(),
        };

        assert!(sidecar.log_event(event).is_ok());
    }

    #[test]
    fn test_reject_cloud_endpoint_https() {
        let sidecar = SovereignTelemetrySidecar::new();
        let event = TelemetryEvent {
            event_id: Uuid::new_v4(),
            kind: TelemetryEventKind::GateFailure,
            agent_id: None,
            payload_summary: "https://remote.cloud/api".to_string(),
            timestamp: Utc::now(),
        };

        assert!(matches!(
            sidecar.log_event(event),
            Err(TelemetryError::CloudEndpointDetected { .. })
        ));
    }

    #[test]
    fn test_reject_cloud_endpoint_http() {
        let sidecar = SovereignTelemetrySidecar::new();
        let event = TelemetryEvent {
            event_id: Uuid::new_v4(),
            kind: TelemetryEventKind::MandateBlocked,
            agent_id: None,
            payload_summary: "http://api.example.com".to_string(),
            timestamp: Utc::now(),
        };

        assert!(sidecar.log_event(event).is_err());
    }

    #[test]
    fn test_assert_no_cloud_telemetry_clean() {
        let sidecar = SovereignTelemetrySidecar::new();
        for i in 0..3 {
            let event = TelemetryEvent {
                event_id: Uuid::new_v4(),
                kind: TelemetryEventKind::GateFailure,
                agent_id: None,
                payload_summary: format!("local_failure_{i}"),
                timestamp: Utc::now(),
            };
            let _ = sidecar.log_event(event);
        }

        assert!(sidecar.assert_no_cloud_telemetry());
    }

    #[test]
    fn test_export_as_cipo_traces() {
        let sidecar = SovereignTelemetrySidecar::new();
        for i in 0..5 {
            let event = TelemetryEvent {
                event_id: Uuid::new_v4(),
                kind: TelemetryEventKind::GateFailure,
                agent_id: None,
                payload_summary: format!("failure_{i}"),
                timestamp: Utc::now(),
            };
            let _ = sidecar.log_event(event);
        }

        let traces = sidecar.export_as_cipo_traces();
        assert_eq!(traces.len(), 5);
        assert!(
            traces
                .iter()
                .all(|t| t.tier_escalated_to == RoutingTier::Tier3Opus)
        );
    }
}
