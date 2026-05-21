/// Event bridge: converts siss-event-log SystemEvents to CockpitEvents for SSE streaming.
/// This module integrates the immutable event log into the real-time observability stream
/// WITHOUT modifying any A2UI schemas or Phase 32 components (read-only integration).

use crate::state::CockpitEvent;
use chrono::Utc;
use siss_event_log::SystemEvent;

/// Convert a SystemEvent from the immutable log into a CockpitEvent for SSE streaming.
pub fn system_event_to_cockpit(event: SystemEvent) -> CockpitEvent {
    match event {
        SystemEvent::JobDispatched { job_id, mandate_id } => CockpitEvent {
            event_type: "job_dispatched".to_string(),
            agent_id: Some(job_id.to_string()),
            payload: serde_json::json!({
                "job_id": job_id,
                "mandate_id": mandate_id,
            }),
            timestamp: Utc::now(),
        },
        SystemEvent::JobCompleted { job_id, result } => CockpitEvent {
            event_type: "job_completed".to_string(),
            agent_id: Some(job_id.to_string()),
            payload: serde_json::json!({
                "job_id": job_id,
                "result": result,
            }),
            timestamp: Utc::now(),
        },
        SystemEvent::JobFailed { job_id, error } => CockpitEvent {
            event_type: "job_failed".to_string(),
            agent_id: Some(job_id.to_string()),
            payload: serde_json::json!({
                "job_id": job_id,
                "error": error,
            }),
            timestamp: Utc::now(),
        },
        SystemEvent::AccessDecision { actor, decision } => CockpitEvent {
            event_type: "access_decision".to_string(),
            agent_id: Some(actor.to_string()),
            payload: serde_json::json!({
                "actor": actor,
                "decision": decision,
            }),
            timestamp: Utc::now(),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use uuid::Uuid;

    #[test]
    fn test_job_dispatched_conversion() {
        let job_id = Uuid::new_v4();
        let mandate_id = Uuid::new_v4();
        let event = SystemEvent::JobDispatched { job_id, mandate_id };

        let cockpit_event = system_event_to_cockpit(event);

        assert_eq!(cockpit_event.event_type, "job_dispatched");
        assert_eq!(cockpit_event.agent_id, Some(job_id.to_string()));
    }

    #[test]
    fn test_access_decision_conversion() {
        let actor = Uuid::new_v4();
        let decision = "authorized task with risk_class low".to_string();
        let event = SystemEvent::AccessDecision {
            actor,
            decision: decision.clone(),
        };

        let cockpit_event = system_event_to_cockpit(event);

        assert_eq!(cockpit_event.event_type, "access_decision");
        assert_eq!(cockpit_event.agent_id, Some(actor.to_string()));
    }
}
