/// Event bridge: converts agent events and system events to CockpitEvents for SSE streaming.
/// Integrates the immutable event log and real-time agent pipeline into the SSE stream.

use crate::state::CockpitEvent;
use chrono::Utc;
use serde_json::json;
use siss_agent_shell::events::AgentEvent;
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

/// Convert an AgentEvent from the agent pipeline into a CockpitEvent for SSE streaming.
pub fn agent_event_to_cockpit(event: AgentEvent) -> CockpitEvent {
    let event_type = event.event_type().to_string();
    let timestamp = Utc::now();

    let (agent_id, payload) = match event {
        AgentEvent::SessionStarted { session_id, persona_id, .. } => (
            Some(session_id.to_string()),
            json!({ "session_id": session_id, "persona_id": persona_id }),
        ),
        AgentEvent::SessionClosed { session_id, .. } => (
            Some(session_id.to_string()),
            json!({ "session_id": session_id }),
        ),
        AgentEvent::HookFired { hook_name, hook_point, result, .. } => (
            None,
            json!({ "hook_name": hook_name, "hook_point": format!("{:?}", hook_point), "result": format!("{:?}", result) }),
        ),
        AgentEvent::TaskCreated { task_id, intent, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "intent": intent }),
        ),
        AgentEvent::Authorized { task_id, mandate_id, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "mandate_id": mandate_id }),
        ),
        AgentEvent::Routed { task_id, hardware_target, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "hardware_target": format!("{:?}", hardware_target) }),
        ),
        AgentEvent::OutputChunk { task_id, chunk, index, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "chunk": chunk, "index": index }),
        ),
        AgentEvent::Executing { task_id, token_cost, duration_ms, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "token_cost": token_cost, "duration_ms": duration_ms }),
        ),
        AgentEvent::FirewallInspected { task_id, verdict, violation_count, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "verdict": format!("{:?}", verdict), "violation_count": violation_count }),
        ),
        AgentEvent::Scored { task_id, quality_score, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "quality_score": quality_score }),
        ),
        AgentEvent::Crystallized { task_id, memory_count, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "memory_count": memory_count }),
        ),
        AgentEvent::IntentCompleted { task_id, quality_score, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "quality_score": quality_score }),
        ),
        AgentEvent::IntentMandateRequested { task_id, mandate_id, reason, required_budget, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "mandate_id": mandate_id, "reason": reason, "required_budget": required_budget }),
        ),
        AgentEvent::Error { message, .. } => (
            None,
            json!({ "message": message }),
        ),
        AgentEvent::UIRequested { task_id, components, form_id, .. } => (
            Some(task_id.to_string()),
            json!({ "task_id": task_id, "components": components, "form_id": form_id }),
        ),
    };

    CockpitEvent { event_type, agent_id, payload, timestamp }
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
