use siss_gatekeeper::edge_actuation::{ActuationError, EdgeActuationCommand, EdgeActuationGuard};
use siss_gatekeeper::tokens::IntentMandate;
/// Phase 47: Edge Plane & OpenClaw Gateway Integration
/// 8 TDD tests covering three physical deployment waves:
/// - Wave 1: OpenClaw Loopback Membrane
/// - Wave 2: Deterministic Skill Execution
/// - Wave 3: AP2-Governed Edge Actuation
use siss_job_router::edge_gateway::{GatewayConfig, GatewayMembraneValidator, GatewayViolation};
use siss_job_router::edge_skills::{
    EdgeSkill, SkillError, SkillExecutor, SkillRegistry, ToolInvocation,
};
use uuid::Uuid;

// ============================================================================
// WAVE 1: OPENCLAW LOOPBACK MEMBRANE
// ============================================================================

// ============================================================================
// TEST 1: Gateway accepts loopback 127.0.0.1
// ============================================================================

#[test]
fn test_gateway_accepts_loopback_127() {
    let config = GatewayConfig {
        bind_address: "127.0.0.1",
        model_endpoint_env_var: "MODEL_ENDPOINT",
        auth_token_env_var: "AUTH_TOKEN",
        no_external_binding: true,
    };

    let result = GatewayMembraneValidator::validate(&config);
    assert!(result.is_ok(), "127.0.0.1 loopback should be accepted");
}

// ============================================================================
// TEST 2: Gateway rejects external 0.0.0.0
// ============================================================================

#[test]
fn test_gateway_rejects_external_0_0_0_0() {
    let config = GatewayConfig {
        bind_address: "0.0.0.0",
        model_endpoint_env_var: "MODEL_ENDPOINT",
        auth_token_env_var: "AUTH_TOKEN",
        no_external_binding: true,
    };

    let result = GatewayMembraneValidator::validate(&config);
    assert!(
        matches!(
            result,
            Err(GatewayViolation::ExternalBinding { address }) if address == "0.0.0.0"
        ),
        "0.0.0.0 should be rejected"
    );
}

// ============================================================================
// TEST 3: Gateway accepts loopback IPv6 ::1
// ============================================================================

#[test]
fn test_gateway_accepts_loopback_ipv6() {
    let config = GatewayConfig {
        bind_address: "::1",
        model_endpoint_env_var: "MODEL_ENDPOINT",
        auth_token_env_var: "AUTH_TOKEN",
        no_external_binding: true,
    };

    let result = GatewayMembraneValidator::validate(&config);
    assert!(result.is_ok(), "::1 loopback should be accepted");
}

// ============================================================================
// WAVE 2: DETERMINISTIC SKILL EXECUTION
// ============================================================================

// ============================================================================
// TEST 4: Skill registry validates known skill with known arg prefix
// ============================================================================

#[test]
fn test_skill_validates_known_skill_known_arg() {
    let registry = SkillRegistry {
        skills: &[
            EdgeSkill {
                name: "sensor_read",
                command_template: "sensor_read {device_id}",
                allowed_arg_prefixes: &["SENSOR_", "DEVICE_"],
            },
            EdgeSkill {
                name: "actuator_set",
                command_template: "actuator_set {device_id} {value}",
                allowed_arg_prefixes: &["ACT_"],
            },
        ],
    };

    let invocation = ToolInvocation {
        skill_name: "sensor_read".to_string(),
        args: vec!["SENSOR_042".to_string()],
    };

    let result = SkillExecutor::validate_invocation(&invocation, &registry);
    assert!(
        result.is_ok(),
        "known skill with valid arg prefix should pass"
    );

    let cmd = result.unwrap();
    assert_eq!(cmd.skill_name, "sensor_read");
    assert!(cmd.resolved_command.contains("SENSOR_042"));
}

// ============================================================================
// TEST 5: Skill registry rejects unknown skill
// ============================================================================

#[test]
fn test_skill_rejects_unknown_skill() {
    let registry = SkillRegistry {
        skills: &[EdgeSkill {
            name: "sensor_read",
            command_template: "sensor_read {device_id}",
            allowed_arg_prefixes: &["SENSOR_", "DEVICE_"],
        }],
    };

    let invocation = ToolInvocation {
        skill_name: "rm_rf".to_string(),
        args: vec![],
    };

    let result = SkillExecutor::validate_invocation(&invocation, &registry);
    assert!(
        matches!(
            result,
            Err(SkillError::SkillNotFound { name }) if name == "rm_rf"
        ),
        "unknown skill should be rejected"
    );
}

// ============================================================================
// TEST 6: Skill registry rejects hallucinated args
// ============================================================================

#[test]
fn test_skill_rejects_hallucinated_arg() {
    let registry = SkillRegistry {
        skills: &[EdgeSkill {
            name: "sensor_read",
            command_template: "sensor_read {device_id}",
            allowed_arg_prefixes: &["SENSOR_", "DEVICE_"],
        }],
    };

    let invocation = ToolInvocation {
        skill_name: "sensor_read".to_string(),
        args: vec!["rm -rf /data".to_string()],
    };

    let result = SkillExecutor::validate_invocation(&invocation, &registry);
    assert!(
        matches!(result, Err(SkillError::HallucinatedArgs { .. })),
        "arg not starting with allowed prefix should be rejected"
    );
}

// ============================================================================
// WAVE 3: AP2-GOVERNED EDGE ACTUATION
// ============================================================================

// ============================================================================
// TEST 7: Edge actuation within mandate budget
// ============================================================================

#[test]
fn test_edge_actuation_within_mandate_budget() {
    let device_tool_id = Uuid::new_v4();

    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 500,
        budget_spent: 100,
        risk_class: "low".to_string(),
        allowed_tools: vec![device_tool_id],
    };

    let command = EdgeActuationCommand {
        command_id: Uuid::new_v4(),
        device_id: "ACT_001".to_string(),
        action: "set_temp".to_string(),
        cost_ap2_units: 200,
    };

    let result = EdgeActuationGuard::authorize(&command, &mandate, device_tool_id);
    assert!(result.is_ok(), "command within budget should be authorized");

    let auth = result.unwrap();
    assert_eq!(auth.approved_budget, 400); // budget_remaining() = 500 - 100 = 400
}

// ============================================================================
// TEST 8: Edge actuation exceeds mandate budget
// ============================================================================

#[test]
fn test_edge_actuation_exceeds_mandate_budget() {
    let device_tool_id = Uuid::new_v4();

    let mandate = IntentMandate {
        id: Uuid::new_v4(),
        budget_limit: 1000,
        budget_spent: 950,
        risk_class: "low".to_string(),
        allowed_tools: vec![device_tool_id],
    };

    let command = EdgeActuationCommand {
        command_id: Uuid::new_v4(),
        device_id: "ACT_001".to_string(),
        action: "set_temp".to_string(),
        cost_ap2_units: 200,
    };

    let result = EdgeActuationGuard::authorize(&command, &mandate, device_tool_id);
    assert!(
        matches!(
            result,
            Err(ActuationError::InsufficientBudget {
                required: 200,
                available: 50
            })
        ),
        "command exceeding budget should be rejected"
    );
}
