//! L3 Input/Output Contracts: Type-safe permit gate interfaces
//! Replaces implicit JSON + String args with explicit trait boundaries

use crate::permit::{GateDecision, PermitGate};
use std::fmt;

/// Input contract for L3 (accepts L2Output via trait object)
pub trait L3Input: Send + Sync + fmt::Debug {
    fn request_id(&self) -> &str;
    fn results_count(&self) -> usize;
    fn requires_approval(&self) -> bool;
}

/// Tool argument contract (type-safe alternative to String args)
pub trait ToolArgs: Send + Sync + fmt::Debug {
    fn to_json(&self) -> String;
    fn arg_names(&self) -> Vec<&str>;
}

/// Output contract for L3 (gated decision)
pub trait L3Output: Send + Sync + fmt::Debug {
    fn request_id(&self) -> &str;
    fn gate_decision(&self) -> GateDecision;
    fn gate_id(&self) -> &str;
    fn approval_reason(&self) -> &str;
}

/// Concrete input adapter for L3
#[derive(Debug, Clone)]
pub struct GateRequest {
    request_id: String,
    results_count: usize,
    requires_approval: bool,
}

impl GateRequest {
    pub fn new(request_id: String, results_count: usize, requires_approval: bool) -> Self {
        Self {
            request_id,
            results_count,
            requires_approval,
        }
    }
}

impl L3Input for GateRequest {
    fn request_id(&self) -> &str {
        &self.request_id
    }

    fn results_count(&self) -> usize {
        self.results_count
    }

    fn requires_approval(&self) -> bool {
        self.requires_approval
    }
}

/// Strongly-typed tool invocation (replaces String arguments)
#[derive(Debug, Clone)]
pub struct TypedToolInvocation {
    tool_name: String,
    function_name: String,
    args: Vec<(String, String)>, // (key, value) pairs instead of raw JSON string
}

impl TypedToolInvocation {
    pub fn new(tool_name: String, function_name: String) -> Self {
        Self {
            tool_name,
            function_name,
            args: Vec::new(),
        }
    }

    pub fn add_arg(&mut self, key: String, value: String) {
        self.args.push((key, value));
    }

    pub fn tool_name(&self) -> &str {
        &self.tool_name
    }

    pub fn function_name(&self) -> &str {
        &self.function_name
    }

    pub fn args(&self) -> &[(String, String)] {
        &self.args
    }
}

impl ToolArgs for TypedToolInvocation {
    fn to_json(&self) -> String {
        use serde_json::json;
        let obj = self
            .args
            .iter()
            .fold(json!({}), |mut acc, (k, v)| {
                acc[k] = json!(v);
                acc
            });
        obj.to_string()
    }

    fn arg_names(&self) -> Vec<&str> {
        self.args.iter().map(|(k, _)| k.as_str()).collect()
    }
}

/// Concrete output for L3 (gated response)
#[derive(Debug, Clone)]
pub struct GatedDecision {
    request_id: String,
    gate: PermitGate,
    approval_reason: String,
}

impl GatedDecision {
    pub fn new(request_id: String, gate: PermitGate, approval_reason: String) -> Self {
        Self {
            request_id,
            gate,
            approval_reason,
        }
    }

    pub fn gate(&self) -> &PermitGate {
        &self.gate
    }
}

impl L3Output for GatedDecision {
    fn request_id(&self) -> &str {
        &self.request_id
    }

    fn gate_decision(&self) -> GateDecision {
        self.gate.decision
    }

    fn gate_id(&self) -> &str {
        &self.gate.id
    }

    fn approval_reason(&self) -> &str {
        &self.approval_reason
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gate_request_creation() {
        let req = GateRequest::new("req123".to_string(), 5, true);
        assert_eq!(req.request_id(), "req123");
        assert_eq!(req.results_count(), 5);
        assert!(req.requires_approval());
    }

    #[test]
    fn test_gate_request_no_approval() {
        let req = GateRequest::new("req456".to_string(), 2, false);
        assert!(!req.requires_approval());
    }

    #[test]
    fn test_gate_request_l3_input_trait() {
        let req: Box<dyn L3Input> = Box::new(GateRequest::new("id".to_string(), 3, true));
        assert_eq!(req.request_id(), "id");
        assert_eq!(req.results_count(), 3);
        assert!(req.requires_approval());
    }

    #[test]
    fn test_typed_tool_invocation_creation() {
        let inv = TypedToolInvocation::new("database".to_string(), "insert".to_string());
        assert_eq!(inv.tool_name(), "database");
        assert_eq!(inv.function_name(), "insert");
        assert_eq!(inv.args().len(), 0);
    }

    #[test]
    fn test_typed_tool_invocation_add_args() {
        let mut inv = TypedToolInvocation::new("api".to_string(), "post".to_string());
        inv.add_arg("endpoint".to_string(), "/users".to_string());
        inv.add_arg("method".to_string(), "POST".to_string());

        assert_eq!(inv.args().len(), 2);
        assert_eq!(inv.args()[0].0, "endpoint");
        assert_eq!(inv.args()[0].1, "/users");
    }

    #[test]
    fn test_typed_tool_invocation_to_json() {
        let mut inv = TypedToolInvocation::new("test".to_string(), "func".to_string());
        inv.add_arg("key1".to_string(), "value1".to_string());
        inv.add_arg("key2".to_string(), "value2".to_string());

        let json = inv.to_json();
        assert!(json.contains("key1"));
        assert!(json.contains("value1"));
        assert!(json.contains("key2"));
    }

    #[test]
    fn test_typed_tool_invocation_arg_names() {
        let mut inv = TypedToolInvocation::new("test".to_string(), "func".to_string());
        inv.add_arg("param1".to_string(), "val1".to_string());
        inv.add_arg("param2".to_string(), "val2".to_string());

        let names = inv.arg_names();
        assert_eq!(names.len(), 2);
        assert_eq!(names[0], "param1");
        assert_eq!(names[1], "param2");
    }

    #[test]
    fn test_gated_decision_creation() {
        let gate = PermitGate::new("test_gate".to_string(), "Article 50".to_string(), 1);
        let decision = GatedDecision::new(
            "req789".to_string(),
            gate,
            "Policy-approved".to_string(),
        );

        assert_eq!(decision.request_id(), "req789");
        assert_eq!(decision.approval_reason(), "Policy-approved");
    }

    #[test]
    fn test_gated_decision_approved_gate() {
        let mut gate =
            PermitGate::new("approval_test".to_string(), "Article 50".to_string(), 1);
        gate.add_approval();

        let decision = GatedDecision::new("r".to_string(), gate, "Approved".to_string());
        assert_eq!(decision.gate_decision(), GateDecision::Approved);
    }

    #[test]
    fn test_gated_decision_denied_gate() {
        let mut gate = PermitGate::new("denial_test".to_string(), "Article 6".to_string(), 1);
        gate.deny();

        let decision = GatedDecision::new("r".to_string(), gate, "Denied".to_string());
        assert_eq!(decision.gate_decision(), GateDecision::Denied);
    }

    #[test]
    fn test_gated_decision_pending_gate() {
        let gate = PermitGate::new("pending_test".to_string(), "Article 50".to_string(), 2);
        let decision = GatedDecision::new("r".to_string(), gate, "Pending".to_string());
        assert_eq!(decision.gate_decision(), GateDecision::PendingApproval);
    }

    #[test]
    fn test_gated_decision_l3_output_trait() {
        let gate = PermitGate::new("gate".to_string(), "Article".to_string(), 1);
        let decision = GatedDecision::new("r".to_string(), gate, "reason".to_string());
        let output: Box<dyn L3Output> = Box::new(decision);

        assert_eq!(output.request_id(), "r");
        assert_eq!(output.approval_reason(), "reason");
    }

    #[test]
    fn test_typed_tool_invocation_clone() {
        let mut inv1 = TypedToolInvocation::new("tool".to_string(), "func".to_string());
        inv1.add_arg("key".to_string(), "val".to_string());
        let inv2 = inv1.clone();

        assert_eq!(inv1.tool_name(), inv2.tool_name());
        assert_eq!(inv1.args().len(), inv2.args().len());
    }

    #[test]
    fn test_gate_request_clone() {
        let req1 = GateRequest::new("id".to_string(), 5, true);
        let req2 = req1.clone();

        assert_eq!(req1.request_id(), req2.request_id());
        assert_eq!(req1.results_count(), req2.results_count());
    }

    #[test]
    fn test_gated_decision_clone() {
        let gate = PermitGate::new("g".to_string(), "A".to_string(), 1);
        let dec1 = GatedDecision::new("r".to_string(), gate, "reason".to_string());
        let dec2 = dec1.clone();

        assert_eq!(dec1.request_id(), dec2.request_id());
        assert_eq!(dec1.approval_reason(), dec2.approval_reason());
    }

    #[test]
    fn test_typed_tool_invocation_empty_args_json() {
        let inv = TypedToolInvocation::new("test".to_string(), "func".to_string());
        let json = inv.to_json();
        assert_eq!(json, "{}");
    }

    #[test]
    fn test_typed_tool_invocation_single_arg_json() {
        let mut inv = TypedToolInvocation::new("test".to_string(), "func".to_string());
        inv.add_arg("status".to_string(), "active".to_string());

        let json = inv.to_json();
        assert!(json.contains("status"));
        assert!(json.contains("active"));
    }

    #[test]
    fn test_gate_request_results_count_zero() {
        let req = GateRequest::new("r".to_string(), 0, false);
        assert_eq!(req.results_count(), 0);
    }

    #[test]
    fn test_gate_request_results_count_large() {
        let req = GateRequest::new("r".to_string(), 10000, true);
        assert_eq!(req.results_count(), 10000);
    }

    #[test]
    fn test_l3_input_output_chain() {
        let input: Box<dyn L3Input> = Box::new(GateRequest::new("r".to_string(), 3, true));
        assert_eq!(input.request_id(), "r");

        let gate = PermitGate::new("g".to_string(), "A".to_string(), 1);
        let output: Box<dyn L3Output> = Box::new(GatedDecision::new(
            input.request_id().to_string(),
            gate,
            "approved".to_string(),
        ));
        assert_eq!(output.request_id(), input.request_id());
    }
}
