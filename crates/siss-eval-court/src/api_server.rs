use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConflictDisplay {
    pub capsule_a: String,
    pub capsule_b: String,
    pub affected_symbol: String,
    pub risk_a: String,
    pub risk_b: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConflictJSON {
    pub conflict_id: String,
    pub capsule_a: String,
    pub capsule_b: String,
    pub affected_symbol: String,
    pub risk_a: String,
    pub risk_b: String,
    pub action_required: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VetoSubmission {
    pub conflict_id: String,
    pub approve_a: bool,
    pub approve_b: bool,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VetoResponse {
    pub decision_id: String,
    pub status: String,
    pub capsule_a_status: String,
    pub capsule_b_status: String,
    pub signature: String,
    pub timestamp: u64,
}

pub struct VetoFlowAPI;

impl VetoFlowAPI {
    pub fn new() -> Self {
        VetoFlowAPI
    }

    pub fn render_conflict_json(&self, conflict: &ConflictDisplay) -> Result<String, String> {
        let conflict_json = ConflictJSON {
            conflict_id: Uuid::new_v4().to_string(),
            capsule_a: conflict.capsule_a.clone(),
            capsule_b: conflict.capsule_b.clone(),
            affected_symbol: conflict.affected_symbol.clone(),
            risk_a: conflict.risk_a.clone(),
            risk_b: conflict.risk_b.clone(),
            action_required: "Human veto required (φ+ Eval Court)".to_string(),
        };

        serde_json::to_string(&conflict_json)
            .map_err(|e| format!("JSON serialization error: {}", e))
    }

    pub fn render_veto_response(
        &self,
        submission: &VetoSubmission,
        signature: String,
    ) -> Result<String, String> {
        let capsule_a_status = if submission.approve_a {
            "APPROVED".to_string()
        } else {
            "REJECTED".to_string()
        };

        let capsule_b_status = if submission.approve_b {
            "APPROVED".to_string()
        } else {
            "REJECTED".to_string()
        };

        let response = VetoResponse {
            decision_id: Uuid::new_v4().to_string(),
            status: "VETO_DECISION_EXECUTED".to_string(),
            capsule_a_status,
            capsule_b_status,
            signature,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_err(|e| format!("Time error: {}", e))?
                .as_secs(),
        };

        serde_json::to_string(&response).map_err(|e| format!("JSON serialization error: {}", e))
    }

    pub fn validate_veto_submission(&self, submission: &VetoSubmission) -> Result<bool, String> {
        if submission.conflict_id.is_empty() {
            return Err("conflict_id required".to_string());
        }
        if submission.reason.is_empty() {
            return Err("reason required".to_string());
        }
        if !submission.approve_a && !submission.approve_b {
            // Both rejected is valid (fail-closed)
            return Ok(true);
        }
        Ok(true)
    }

    pub fn format_dashboard_status(
        &self,
        pending_conflicts: usize,
        resolved_decisions: usize,
    ) -> Result<String, String> {
        let status = serde_json::json!({
            "dashboard": "φ+ Eval Court",
            "pending_conflicts": pending_conflicts,
            "resolved_decisions": resolved_decisions,
            "status": if pending_conflicts > 0 { "WAITING_FOR_VETO" } else { "IDLE" },
            "last_update": std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_err(|e| format!("Time error: {}", e))?
                .as_secs()
        });

        serde_json::to_string(&status).map_err(|e| format!("JSON serialization error: {}", e))
    }
}

impl Default for VetoFlowAPI {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_veto_flow_api_returns_json_conflict_display() {
        let api = VetoFlowAPI::new();

        let conflict = ConflictDisplay {
            capsule_a: "Agent-001: add logging to validateUser".to_string(),
            capsule_b: "Agent-002: refactor validateUser return type".to_string(),
            affected_symbol: "validateUser".to_string(),
            risk_a: "Low".to_string(),
            risk_b: "High (15 callers)".to_string(),
        };

        let json = api.render_conflict_json(&conflict).unwrap();
        assert!(json.contains("validateUser"));
        assert!(json.contains("Agent-001"));
        assert!(json.contains("φ+ Eval Court"));
    }

    #[test]
    fn test_veto_response_approval() {
        let api = VetoFlowAPI::new();

        let submission = VetoSubmission {
            conflict_id: "conflict-123".to_string(),
            approve_a: true,
            approve_b: false,
            reason: "A is safe, B modifies too many callers".to_string(),
        };

        let signature = "hmac-sha256-signature-hex".to_string();
        let response_json = api.render_veto_response(&submission, signature).unwrap();

        assert!(response_json.contains("APPROVED"));
        assert!(response_json.contains("REJECTED"));
        assert!(response_json.contains("VETO_DECISION_EXECUTED"));
    }

    #[test]
    fn test_veto_response_reject_both_fail_closed() {
        let api = VetoFlowAPI::new();

        let submission = VetoSubmission {
            conflict_id: "conflict-456".to_string(),
            approve_a: false,
            approve_b: false,
            reason: "Both unsafe - fail-closed".to_string(),
        };

        let signature = "hmac-signature".to_string();
        let response_json = api.render_veto_response(&submission, signature).unwrap();

        assert!(response_json.contains("REJECTED"));
        assert!(response_json.contains("REJECTED"));
    }

    #[test]
    fn test_validate_veto_submission_requires_conflict_id() {
        let api = VetoFlowAPI::new();

        let submission = VetoSubmission {
            conflict_id: "".to_string(),
            approve_a: true,
            approve_b: false,
            reason: "test".to_string(),
        };

        let result = api.validate_veto_submission(&submission);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_veto_submission_requires_reason() {
        let api = VetoFlowAPI::new();

        let submission = VetoSubmission {
            conflict_id: "conflict-123".to_string(),
            approve_a: true,
            approve_b: false,
            reason: "".to_string(),
        };

        let result = api.validate_veto_submission(&submission);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_veto_submission_accepts_both_rejected() {
        let api = VetoFlowAPI::new();

        let submission = VetoSubmission {
            conflict_id: "conflict-123".to_string(),
            approve_a: false,
            approve_b: false,
            reason: "Both unsafe".to_string(),
        };

        let result = api.validate_veto_submission(&submission);
        assert!(result.is_ok());
        assert!(result.unwrap());
    }

    #[test]
    fn test_dashboard_status_shows_pending_conflicts() {
        let api = VetoFlowAPI::new();

        let status_json = api.format_dashboard_status(2, 5).unwrap();

        assert!(status_json.contains("pending_conflicts"));
        assert!(status_json.contains("2"));
        assert!(status_json.contains("WAITING_FOR_VETO"));
    }

    #[test]
    fn test_dashboard_status_shows_idle_when_no_conflicts() {
        let api = VetoFlowAPI::new();

        let status_json = api.format_dashboard_status(0, 10).unwrap();

        assert!(status_json.contains("IDLE"));
        assert!(status_json.contains("0"));
    }
}
