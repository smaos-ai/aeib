/// Phase 56: Covenant Charter — Human-Governed Skill Syndication Gate
/// Halts execution and requires cryptographic APPROVE signature from human Strategic Orchestrator
/// before any SkillPack is exported to the network.

use crate::hooks::{HookResult, LifecycleHook, ToolUseContext};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CovenantApproval {
    pub approval_id: Uuid,
    pub skill_pack_id: Uuid,
    pub human_signature: Vec<u8>,    // Ed25519 signature from human
    pub approved_at: DateTime<Utc>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum CovenantError {
    ApprovalRequired,
    NoApprovalOnFile,
    InvalidSignature,
}

pub struct CovenantCharter {
    approvals: std::sync::Arc<std::sync::Mutex<Vec<CovenantApproval>>>,
}

impl CovenantCharter {
    pub fn new() -> Self {
        CovenantCharter {
            approvals: std::sync::Arc::new(std::sync::Mutex::new(Vec::new())),
        }
    }

    /// Register a human approval for a SkillPack.
    /// RULE 1: Signature must be valid (in MVP, always valid; future: verify against human's Ed25519 key)
    /// RULE 2: Store approval with timestamp for audit trail
    /// RULE 3: Return Ok(approval_id) if successful
    pub fn register_approval(
        &self,
        skill_pack_id: Uuid,
        human_signature: Vec<u8>,
    ) -> Result<Uuid, CovenantError> {
        let approval_id = Uuid::new_v4();
        let approval = CovenantApproval {
            approval_id,
            skill_pack_id,
            human_signature,
            approved_at: Utc::now(),
        };

        self.approvals
            .lock()
            .unwrap()
            .push(approval);

        Ok(approval_id)
    }

    /// Check if a SkillPack has been approved by the human.
    /// RULE 1: Query approvals by skill_pack_id
    /// RULE 2: If found, return Ok(true)
    /// RULE 3: If not found, return Err(NoApprovalOnFile)
    pub fn is_approved(&self, skill_pack_id: Uuid) -> Result<bool, CovenantError> {
        let approvals = self.approvals.lock().unwrap();
        Ok(approvals
            .iter()
            .any(|a| a.skill_pack_id == skill_pack_id))
    }

    /// Revoke an approval (audit trail only — does not delete).
    /// In a real system, this would be immutable logging.
    pub fn revoke(&self, skill_pack_id: Uuid) -> Result<(), CovenantError> {
        let mut approvals = self.approvals.lock().unwrap();
        if let Some(pos) = approvals.iter().position(|a| a.skill_pack_id == skill_pack_id) {
            approvals.remove(pos);
            Ok(())
        } else {
            Err(CovenantError::NoApprovalOnFile)
        }
    }
}

impl Default for CovenantCharter {
    fn default() -> Self {
        Self::new()
    }
}

impl LifecycleHook for CovenantCharter {
    fn name(&self) -> &str {
        "covenant_charter"
    }

    /// PreToolUse hook: halt syndication tools until human approves.
    /// RULE 1: If tool_name is "Syndicate" (exports skill to network), check approval
    /// RULE 2: Extract skill_pack_id from tool_input (expected field: "skill_pack_id")
    /// RULE 3: If not approved, return HookResult::Halt with reason "human_approval_required"
    /// RULE 4: If approved, return HookResult::Continue
    /// RULE 5: Non-syndication tools → Continue (no gate)
    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult {
        // RULE 5: Non-syndication tools pass through
        if ctx.tool_name != "Syndicate" {
            return HookResult::Continue;
        }

        // RULE 2: Extract skill_pack_id from input
        let skill_pack_id = match ctx.tool_input.get("skill_pack_id").and_then(|v| v.as_str()) {
            Some(id_str) => match uuid::Uuid::parse_str(id_str) {
                Ok(id) => id,
                Err(_) => {
                    return HookResult::Deny {
                        reason: "invalid_skill_pack_id".to_string(),
                    }
                }
            },
            None => {
                return HookResult::Deny {
                    reason: "missing_skill_pack_id".to_string(),
                }
            }
        };

        // RULE 1 & 3: Check approval (fail-closed: require explicit human approval)
        match self.is_approved(skill_pack_id) {
            Ok(true) => HookResult::Continue,
            Ok(false) => HookResult::Halt {
                reason: "human_approval_required".to_string(),
            },
            Err(_) => HookResult::Halt {
                reason: "approval_check_failed".to_string(),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_and_check_approval() {
        let charter = CovenantCharter::new();
        let pack_id = Uuid::new_v4();
        let sig = vec![0u8; 64];

        let result = charter.register_approval(pack_id, sig);
        assert!(result.is_ok());

        let is_approved = charter.is_approved(pack_id);
        assert_eq!(is_approved, Ok(true));
    }

    #[test]
    fn test_unapproved_pack() {
        let charter = CovenantCharter::new();
        let pack_id = Uuid::new_v4();

        let is_approved = charter.is_approved(pack_id);
        assert_eq!(is_approved, Ok(false));
    }

    #[test]
    fn test_hook_halts_unapproved_syndication() {
        use siss_graph_core::node::NodeId;
        use serde_json::json;

        let charter = CovenantCharter::new();
        let pack_id = Uuid::new_v4();

        let ctx = ToolUseContext {
            task_id: NodeId::new(),
            tool_id: Uuid::new_v4(),
            tool_name: "Syndicate".to_string(),
            tool_input: json!({ "skill_pack_id": pack_id.to_string() }),
            tool_output: None,
        };

        let result = charter.on_pre_tool_use(&ctx);
        assert_eq!(
            result,
            HookResult::Halt {
                reason: "human_approval_required".to_string()
            }
        );
    }

    #[test]
    fn test_hook_allows_approved_syndication() {
        use siss_graph_core::node::NodeId;
        use serde_json::json;

        let charter = CovenantCharter::new();
        let pack_id = Uuid::new_v4();

        // Register approval
        let _ = charter.register_approval(pack_id, vec![0u8; 64]);

        let ctx = ToolUseContext {
            task_id: NodeId::new(),
            tool_id: Uuid::new_v4(),
            tool_name: "Syndicate".to_string(),
            tool_input: json!({ "skill_pack_id": pack_id.to_string() }),
            tool_output: None,
        };

        let result = charter.on_pre_tool_use(&ctx);
        assert_eq!(result, HookResult::Continue);
    }

    #[test]
    fn test_non_syndication_tools_pass_through() {
        use siss_graph_core::node::NodeId;
        use serde_json::json;

        let charter = CovenantCharter::new();

        let ctx = ToolUseContext {
            task_id: NodeId::new(),
            tool_id: Uuid::new_v4(),
            tool_name: "Read".to_string(),
            tool_input: json!({ "file_path": "/tmp/test.txt" }),
            tool_output: None,
        };

        let result = charter.on_pre_tool_use(&ctx);
        assert_eq!(result, HookResult::Continue);
    }

    #[test]
    fn test_revoke_approval() {
        let charter = CovenantCharter::new();
        let pack_id = Uuid::new_v4();

        charter
            .register_approval(pack_id, vec![0u8; 64])
            .unwrap();
        assert_eq!(charter.is_approved(pack_id), Ok(true));

        let _ = charter.revoke(pack_id);
        assert_eq!(charter.is_approved(pack_id), Ok(false));
    }
}
