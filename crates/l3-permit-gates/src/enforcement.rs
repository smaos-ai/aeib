use crate::permit::{GateDecision, PermitGate};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolInvocation {
    pub tool_name: String,
    pub function_name: String,
    pub arguments: String,
}

pub struct GateEnforcer {
    gates: HashMap<String, PermitGate>,
}

impl GateEnforcer {
    pub fn new() -> Self {
        Self {
            gates: HashMap::new(),
        }
    }

    pub fn register_gate(&mut self, gate: PermitGate) {
        self.gates.insert(gate.id.clone(), gate);
    }

    pub fn check_permit(&self, tool_name: &str, _function_name: &str) -> Result<bool, String> {
        if let Some(gate) = self.gates.values().find(|g| g.gate_name == tool_name) {
            match gate.decision {
                GateDecision::Approved => Ok(true),
                GateDecision::Denied => Err(format!("Tool {} is denied by permit gate", tool_name)),
                GateDecision::PendingApproval => {
                    Err(format!("Tool {} is pending approval", tool_name))
                }
            }
        } else {
            Ok(true)
        }
    }

    pub fn enforce_invocation(&self, invocation: &ToolInvocation) -> Result<(), String> {
        self.check_permit(&invocation.tool_name, &invocation.function_name)?;
        Ok(())
    }

    pub fn get_gate(&self, gate_id: &str) -> Option<&PermitGate> {
        self.gates.get(gate_id)
    }

    pub fn get_pending_gates(&self) -> Vec<&PermitGate> {
        self.gates
            .values()
            .filter(|g| g.decision == GateDecision::PendingApproval)
            .collect()
    }

    pub fn approve_gate(&mut self, gate_id: &str) -> Result<(), String> {
        if let Some(gate) = self.gates.get_mut(gate_id) {
            gate.add_approval();
            Ok(())
        } else {
            Err(format!("Gate not found: {}", gate_id))
        }
    }

    pub fn deny_gate(&mut self, gate_id: &str) -> Result<(), String> {
        if let Some(gate) = self.gates.get_mut(gate_id) {
            gate.deny();
            Ok(())
        } else {
            Err(format!("Gate not found: {}", gate_id))
        }
    }
}

impl Default for GateEnforcer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_and_check_gate() {
        let mut enforcer = GateEnforcer::new();
        let gate = PermitGate::new("database_write".to_string(), "Article50".to_string(), 1);

        let _gate_id = gate.id.clone();
        enforcer.register_gate(gate);

        let result = enforcer.check_permit("database_write", "insert");
        assert!(result.is_err());
    }

    #[test]
    fn test_enforce_invocation() {
        let mut enforcer = GateEnforcer::new();
        let gate = PermitGate::new("api_call".to_string(), "Article50".to_string(), 1);

        enforcer.register_gate(gate);

        let invocation = ToolInvocation {
            tool_name: "api_call".to_string(),
            function_name: "post".to_string(),
            arguments: "{}".to_string(),
        };

        let result = enforcer.enforce_invocation(&invocation);
        assert!(result.is_err());
    }

    #[test]
    fn test_approve_gate() {
        let mut enforcer = GateEnforcer::new();
        let gate = PermitGate::new("test_gate".to_string(), "Article50".to_string(), 1);

        let gate_id = gate.id.clone();
        enforcer.register_gate(gate);

        assert!(enforcer.approve_gate(&gate_id).is_ok());

        let approved_gate = enforcer.get_gate(&gate_id).unwrap();
        assert!(approved_gate.is_approved());
    }

    #[test]
    fn test_get_pending_gates() {
        let mut enforcer = GateEnforcer::new();
        enforcer.register_gate(PermitGate::new(
            "gate1".to_string(),
            "Article50".to_string(),
            1,
        ));
        enforcer.register_gate(PermitGate::new(
            "gate2".to_string(),
            "Article50".to_string(),
            1,
        ));

        let pending = enforcer.get_pending_gates();
        assert_eq!(pending.len(), 2);
    }

    #[test]
    fn test_enforce_invocation_denied_gate() {
        let mut enforcer = GateEnforcer::new();
        let mut gate = PermitGate::new("dangerous_op".to_string(), "Article6".to_string(), 1);
        gate.deny();

        enforcer.register_gate(gate);

        let invocation = ToolInvocation {
            tool_name: "dangerous_op".to_string(),
            function_name: "execute".to_string(),
            arguments: "{}".to_string(),
        };

        let result = enforcer.enforce_invocation(&invocation);
        assert!(result.is_err());
    }

    #[test]
    fn test_approve_nonexistent_gate() {
        let mut enforcer = GateEnforcer::new();
        let result = enforcer.approve_gate("nonexistent_gate_id");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not found"));
    }

    #[test]
    fn test_deny_nonexistent_gate() {
        let mut enforcer = GateEnforcer::new();
        let result = enforcer.deny_gate("nonexistent_gate_id");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("not found"));
    }

    #[test]
    fn test_check_permit_multiple_gates_all_denied() {
        let mut enforcer = GateEnforcer::new();
        let mut gate1 = PermitGate::new("tool_a".to_string(), "Article6".to_string(), 1);
        let mut gate2 = PermitGate::new("tool_b".to_string(), "Article13".to_string(), 1);
        gate1.deny();
        gate2.deny();

        enforcer.register_gate(gate1);
        enforcer.register_gate(gate2);

        let result = enforcer.check_permit("tool_a", "action");
        assert!(result.is_err());
    }

    #[test]
    fn test_enforce_with_approved_gate() {
        let mut enforcer = GateEnforcer::new();
        let mut gate = PermitGate::new("safe_op".to_string(), "Article50".to_string(), 1);
        gate.add_approval();

        enforcer.register_gate(gate);

        let invocation = ToolInvocation {
            tool_name: "safe_op".to_string(),
            function_name: "read".to_string(),
            arguments: "{}".to_string(),
        };

        let result = enforcer.enforce_invocation(&invocation);
        assert!(result.is_ok());
    }
}
