use l3_permit_gates::{PermitGate, GateEnforcer};

#[test]
fn test_policy_to_permit_gate_flow() {
    let mut enforcer = GateEnforcer::new();

    let gate = PermitGate::new(
        "credit_scoring".to_string(),
        "Article50".to_string(),
        1,
    );

    enforcer.register_gate(gate.clone());

    assert_eq!(gate.approval_status(), "0/1 approvals required for credit_scoring");

    let enforce_result = enforcer.check_permit("credit_scoring", "evaluate");
    assert!(enforce_result.is_err());
}

#[test]
fn test_multi_layer_decision_flow() {
    let mut enforcer = GateEnforcer::new();

    let gate = PermitGate::new(
        "hotel_credit_decision".to_string(),
        "Article50".to_string(),
        2,
    );

    let gate_id = gate.id.clone();
    enforcer.register_gate(gate);

    enforcer.approve_gate(&gate_id).ok();
    enforcer.approve_gate(&gate_id).ok();

    let permit_check = enforcer.check_permit("hotel_credit_decision", "execute");
    assert!(permit_check.is_ok());
}

#[test]
fn test_escalation_when_gate_denied() {
    let mut enforcer = GateEnforcer::new();
    let gate = PermitGate::new(
        "sensitive_decision".to_string(),
        "Article50".to_string(),
        1,
    );

    let gate_id = gate.id.clone();
    enforcer.register_gate(gate);

    enforcer.deny_gate(&gate_id).ok();

    let result = enforcer.check_permit("sensitive_decision", "execute");
    assert!(result.is_err());
    assert!(result.unwrap_err().contains("denied"));
}

#[test]
fn test_audit_trail_from_gate_decisions() {
    let mut enforcer = GateEnforcer::new();

    let gate = PermitGate::new(
        "audit_test".to_string(),
        "Article50".to_string(),
        1,
    );

    let gate_id = gate.id.clone();
    enforcer.register_gate(gate);

    assert!(enforcer.get_gate(&gate_id).is_some());

    let initial_decision = enforcer.get_gate(&gate_id).unwrap().decision;
    enforcer.approve_gate(&gate_id).ok();
    let approved_decision = enforcer.get_gate(&gate_id).unwrap().decision;

    assert_ne!(
        format!("{:?}", initial_decision),
        format!("{:?}", approved_decision)
    );
}
