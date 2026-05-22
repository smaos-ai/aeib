/// Phase 37.5: RCE Execution Layer — Decision Webhook
/// POST /api/rce/decision — atomic state mutation, synchronized broadcast, audit-first

use axum::{
    extract::State,
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::Utc;

use crate::state::CockpitState;
use crate::handlers::schema_contracts::DecisionWebhookPayload;
use siss_graph_db::rce::ExecutionState;
use siss_graph_db::rce_event_broadcaster::RceEvent;
use siss_graph_db::repo::rce_checkpoint_repo;

#[derive(Debug, Serialize, Deserialize)]
pub struct DecisionResponse {
    pub status: String,
    pub workflow_id: String,
    pub new_state: String,
    pub decision: String,
    pub timestamp: String,
}

/// POST /api/rce/decision handler — Phase 37.5 execution layer
#[axum::debug_handler]
pub async fn post_rce_decision(
    State(state): State<CockpitState>,
    Json(payload): Json<DecisionWebhookPayload>,
) -> (StatusCode, Json<DecisionResponse>) {
    // Schema validation is pre-wired at the route layer
    // Parse workflow_id
    let Ok(workflow_id) = Uuid::parse_str(&payload.workflow_id) else {
        return (
            StatusCode::BAD_REQUEST,
            Json(DecisionResponse {
                status: "error".to_string(),
                workflow_id: payload.workflow_id.clone(),
                new_state: "".to_string(),
                decision: payload.decision.clone(),
                timestamp: Utc::now().to_rfc3339(),
            }),
        );
    };

    // MODIFY requires new_plan
    if payload.decision == "MODIFY" && payload.new_plan.is_none() {
        return (
            StatusCode::BAD_REQUEST,
            Json(DecisionResponse {
                status: "error_new_plan_required".to_string(),
                workflow_id: payload.workflow_id.clone(),
                new_state: "".to_string(),
                decision: "MODIFY".to_string(),
                timestamp: Utc::now().to_rfc3339(),
            }),
        );
    }

    // Acquire write lock on RCE engine
    let mut engine_guard = state.rce_engine.write().await;

    let engine = match engine_guard.as_mut() {
        None => {
            return (
                StatusCode::NOT_FOUND,
                Json(DecisionResponse {
                    status: "error_engine_not_wired".to_string(),
                    workflow_id: payload.workflow_id.clone(),
                    new_state: "".to_string(),
                    decision: payload.decision.clone(),
                    timestamp: Utc::now().to_rfc3339(),
                }),
            )
        }
        Some(e) => e,
    };

    // State guard: must be Paused
    if engine.get_state() != ExecutionState::Paused {
        return (
            StatusCode::CONFLICT,
            Json(DecisionResponse {
                status: "error_not_paused".to_string(),
                workflow_id: payload.workflow_id.clone(),
                new_state: format!("{:?}", engine.get_state()),
                decision: payload.decision.clone(),
                timestamp: Utc::now().to_rfc3339(),
            }),
        );
    }

    // [AUDIT-FIRST] Write audit before mutation
    let pool = {
        let pool_guard = state.pool.lock().expect("pool lock");
        match pool_guard.as_ref() {
            None => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(DecisionResponse {
                        status: "error_audit_required".to_string(),
                        workflow_id: payload.workflow_id.clone(),
                        new_state: "".to_string(),
                        decision: payload.decision.clone(),
                        timestamp: Utc::now().to_rfc3339(),
                    }),
                );
            }
            Some(p) => p.clone(),
        }
    };

    // Write audit trail BEFORE any state mutation
    if let Err(e) = rce_checkpoint_repo::append_audit_event(
        &pool,
        workflow_id,
        "decision",
        Some(payload.decision.as_str()),
        Some(payload.human_operator_id.as_str()),
        payload.reason.as_deref(),
        &serde_json::json!({
            "decision": payload.decision,
            "workflow_id": workflow_id.to_string(),
            "timestamp": payload.timestamp,
        }),
    )
    .await
    {
        eprintln!("[rce_decision] audit write failed (non-fatal): {e}");
        return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(DecisionResponse {
                status: "error_audit_failed".to_string(),
                workflow_id: payload.workflow_id.clone(),
                new_state: "".to_string(),
                decision: payload.decision.clone(),
                timestamp: Utc::now().to_rfc3339(),
            }),
        );
    }

    // Snapshot pre-mutation state for rollback
    let snapshot = (
        engine.get_state(),
        engine.checkpoint.clone(),
        engine.get_current_step_index(),
        engine.plan.clone(),
    );

    // Apply state mutation
    let (event, new_state_str) = match payload.decision.as_str() {
        "APPROVE" => {
            if let Err(e) = engine.resume_workflow_approve() {
                return (
                    StatusCode::UNPROCESSABLE_ENTITY,
                    Json(DecisionResponse {
                        status: format!("mutation_failed: {}", e),
                        workflow_id: payload.workflow_id.clone(),
                        new_state: "".to_string(),
                        decision: "APPROVE".to_string(),
                        timestamp: Utc::now().to_rfc3339(),
                    }),
                );
            }
            let step_index = engine.get_current_step_index();
            (
                Some(RceEvent::WorkflowResumed {
                    workflow_id,
                    timestamp: Utc::now(),
                    step_index,
                    decision: "approve".to_string(),
                }),
                "Resumed",
            )
        }
        "REJECT" => {
            let reason = payload.reason.clone().unwrap_or_default();
            if let Err(e) = engine.resume_workflow_reject(reason) {
                return (
                    StatusCode::UNPROCESSABLE_ENTITY,
                    Json(DecisionResponse {
                        status: format!("mutation_failed: {}", e),
                        workflow_id: payload.workflow_id.clone(),
                        new_state: "".to_string(),
                        decision: "REJECT".to_string(),
                        timestamp: Utc::now().to_rfc3339(),
                    }),
                );
            }
            (
                Some(RceEvent::WorkflowRejected {
                    workflow_id,
                    timestamp: Utc::now(),
                    reason: payload.reason.unwrap_or_default(),
                }),
                "Idle",
            )
        }
        "MODIFY" => {
            let new_plan = match payload.new_plan {
                Some(plan) => plan,
                None => {
                    return (
                        StatusCode::BAD_REQUEST,
                        Json(DecisionResponse {
                            status: "error_new_plan_required".to_string(),
                            workflow_id: payload.workflow_id.clone(),
                            new_state: "".to_string(),
                            decision: "MODIFY".to_string(),
                            timestamp: Utc::now().to_rfc3339(),
                        }),
                    )
                }
            };
            if let Err(e) = engine.resume_workflow_modify(new_plan) {
                return (
                    StatusCode::UNPROCESSABLE_ENTITY,
                    Json(DecisionResponse {
                        status: format!("mutation_failed: {}", e),
                        workflow_id: payload.workflow_id.clone(),
                        new_state: "".to_string(),
                        decision: "MODIFY".to_string(),
                        timestamp: Utc::now().to_rfc3339(),
                    }),
                );
            }
            let step_index = engine.get_current_step_index();
            (
                Some(RceEvent::WorkflowResumed {
                    workflow_id,
                    timestamp: Utc::now(),
                    step_index,
                    decision: "modify".to_string(),
                }),
                "Resumed",
            )
        }
        "PAUSE" => {
            engine.updated_at = Utc::now();
            (None, "Paused") // No event for PAUSE (no state change)
        }
        _ => {
            return (
                StatusCode::BAD_REQUEST,
                Json(DecisionResponse {
                    status: "error_invalid_decision".to_string(),
                    workflow_id: payload.workflow_id.clone(),
                    new_state: "".to_string(),
                    decision: payload.decision.clone(),
                    timestamp: Utc::now().to_rfc3339(),
                }),
            )
        }
    };

    // Broadcast event if one was created
    if let Some(evt) = event {
        match state.rce_broadcaster.emit_checked(evt) {
            Ok(_n) => {} // Success
            Err(_) => {
                // Rollback: no subscribers observing (Transaction Rollback on Broadcast Failure)
                engine.state = snapshot.0;
                engine.checkpoint = snapshot.1;
                engine.current_step_index = snapshot.2;
                engine.plan = snapshot.3;

                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(DecisionResponse {
                        status: "error_broadcast_required".to_string(),
                        workflow_id: payload.workflow_id.clone(),
                        new_state: "".to_string(),
                        decision: payload.decision.clone(),
                        timestamp: Utc::now().to_rfc3339(),
                    }),
                );
            }
        }
    }

    // Release write lock
    drop(engine_guard);

    // Return 200 OK
    (
        StatusCode::OK,
        Json(DecisionResponse {
            status: "accepted".to_string(),
            workflow_id: payload.workflow_id.clone(),
            new_state: new_state_str.to_string(),
            decision: payload.decision.clone(),
            timestamp: Utc::now().to_rfc3339(),
        }),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_decision_invalid_workflow_id() {
        let state = CockpitState::new();
        let payload = DecisionWebhookPayload {
            workflow_id: "not-uuid".to_string(),
            decision: "APPROVE".to_string(),
            reason: None,
            new_plan: None,
            timestamp: Utc::now().to_rfc3339(),
            human_operator_id: "op@example.com".to_string(),
        };

        let (status, _body) = post_rce_decision(State(state), Json(payload)).await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_decision_engine_not_wired() {
        let state = CockpitState::new();
        let payload = DecisionWebhookPayload {
            workflow_id: Uuid::new_v4().to_string(),
            decision: "APPROVE".to_string(),
            reason: None,
            new_plan: None,
            timestamp: Utc::now().to_rfc3339(),
            human_operator_id: "op@example.com".to_string(),
        };

        let (status, _body) = post_rce_decision(State(state), Json(payload)).await;
        assert_eq!(status, StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn test_decision_modify_requires_new_plan() {
        let state = CockpitState::new();
        let payload = DecisionWebhookPayload {
            workflow_id: Uuid::new_v4().to_string(),
            decision: "MODIFY".to_string(),
            reason: None,
            new_plan: None,
            timestamp: Utc::now().to_rfc3339(),
            human_operator_id: "op@example.com".to_string(),
        };

        let (status, _body) = post_rce_decision(State(state), Json(payload)).await;
        assert_eq!(status, StatusCode::BAD_REQUEST);
    }
}
