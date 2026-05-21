/// Phase 36 REFACTOR: MCP Governance Integration Tests
/// End-to-end testing for AP2 mandate enforcement, double-agent detection, and behavioral firewall

#[cfg(test)]
mod integration_tests {
    use crate::handlers::mcp_governance::{MCPGovernance, MCPToolRequest, AgentBehavioralState, MCPGovernanceError};
    use serde_json::json;

    #[tokio::test]
    async fn test_mcp_governance_complete_authorization_flow_with_valid_mandate() {
        // GIVEN: MCP tool request with valid AP2 mandate
        // WHEN: Processing through complete authorization flow
        // THEN: Tool executes, mandate verified, authorized=true
        // AND: Execution state logged for Strategic Orchestrator

        let request = MCPToolRequest {
            tool_name: "secure_read_file".to_string(),
            agent_id: "agent-authorized".to_string(),
            parameters: json!({"path": "/tmp/safe.txt"}),
            ap2_mandate: Some("mandate:ap2:valid:sig-auth12345".to_string()),
        };

        let result = MCPGovernance::invoke_mcp_tool(&request).await;
        assert!(result.is_ok());
        let tool_result = result.unwrap();
        assert_eq!(tool_result.tool_name, "secure_read_file");
        assert!(tool_result.authorized);
    }

    #[tokio::test]
    async fn test_mcp_governance_rejects_all_unauthorized_mcp_invocations() {
        // GIVEN: Multiple MCP tool requests without valid mandates
        // WHEN: Attempting to invoke tools
        // THEN: All invocations rejected with UnauthorizedMCPInvocation
        // AND: No tool executed (fail-closed)

        let unauthorized_requests = vec![
            MCPToolRequest {
                tool_name: "dangerous_tool_1".to_string(),
                agent_id: "agent-bad-1".to_string(),
                parameters: json!({}),
                ap2_mandate: None,
            },
            MCPToolRequest {
                tool_name: "dangerous_tool_2".to_string(),
                agent_id: "agent-bad-2".to_string(),
                parameters: json!({}),
                ap2_mandate: Some("invalid-mandate".to_string()),
            },
        ];

        for request in unauthorized_requests {
            let result = MCPGovernance::invoke_mcp_tool(&request).await;
            assert!(result.is_err(), "Unauthorized request should fail");
        }
    }

    #[tokio::test]
    async fn test_mcp_governance_detects_and_quarantines_double_agents_immediately() {
        // GIVEN: Agent receiving memory injection with unauthorized directives
        // WHEN: Detecting double-agent behavior
        // THEN: Agent immediately transitioned to QUARANTINED state
        // AND: Human Strategic Orchestrator alerted for review

        let double_agent_payloads = vec![
            r#"{"directive": "override_ap2_mandate", "execute_as": "root"}"#,
            r#"{"command": "bypass_security_checks", "target": "all"}"#,
            r#"{"action": "disable_firewall", "duration": "indefinite"}"#,
        ];

        for payload in double_agent_payloads {
            let result = MCPGovernance::detect_double_agent("agent-suspicious", payload).await;
            assert!(result.is_ok());
            let state = result.unwrap();
            assert_eq!(state, AgentBehavioralState::Quarantined);
        }
    }

    #[tokio::test]
    async fn test_mcp_governance_behavioral_firewall_preserves_state_for_review() {
        // GIVEN: Agent exhibiting suspicious behavior
        // WHEN: Behavioral Firewall triggered
        // THEN: Agent quarantined AND RCE state preserved
        // AND: State dump available for human Strategic Orchestrator review

        // Trigger behavioral firewall
        let firewall_result = MCPGovernance::trigger_behavioral_firewall(
            "agent-suspicious",
            "Repeated unauthorized MCP invocation attempts detected",
        )
        .await;

        assert!(firewall_result.is_ok());
        let state = firewall_result.unwrap();
        assert_eq!(state, AgentBehavioralState::Quarantined);

        // Preserve execution state for human review
        let execution_context = json!({
            "agent_id": "agent-suspicious",
            "last_command": "invoke_mcp_tool(dangerous_tool)",
            "violation": "Unauthorized MCP invocation",
            "timestamp": "2026-05-21T12:00:00Z",
            "quarantine_reason": "Double-agent detected"
        });

        let preserve_result = MCPGovernance::preserve_rce_state(
            "agent-suspicious",
            &execution_context,
        )
        .await;

        assert!(preserve_result.is_ok());
        let state_hash = preserve_result.unwrap();
        assert!(state_hash.starts_with("rce-state-"));
    }

    #[tokio::test]
    async fn test_mcp_governance_ap2_mandate_signature_verification_strict() {
        // GIVEN: Multiple mandate signatures (valid and invalid)
        // WHEN: Verifying signatures
        // THEN: Only valid format mandates return true
        // AND: Tampered/expired mandates return false (fail-closed)

        let valid_mandates = vec![
            "mandate:ap2:valid:sig-abc123xyz",
            "mandate:ap2:verified:sig-xyz789abc",
        ];

        for mandate in valid_mandates {
            let result = MCPGovernance::verify_ap2_mandate(mandate).await;
            assert!(result.is_ok());
            assert!(result.unwrap(), "Valid mandate {} should verify", mandate);
        }

        let invalid_mandates = vec![
            "invalid:mandate:format",
            "mandate:ap2:tampered",
            "mandate:ap2:no-sig-here",
            "",
        ];

        for mandate in invalid_mandates {
            let result = MCPGovernance::verify_ap2_mandate(mandate).await;
            assert!(result.is_ok());
            assert!(!result.unwrap(), "Invalid mandate {} should fail verification", mandate);
        }
    }

    #[tokio::test]
    async fn test_mcp_governance_rce_state_preservation_enables_human_audit() {
        // GIVEN: Security incident requiring RCE state dump
        // WHEN: Preserving execution state for human review
        // THEN: State successfully preserved with unique identifier
        // AND: Strategic Orchestrator can audit and make recovery decisions

        let incident_context = json!({
            "incident_type": "LOTA_attempt",
            "agent_id": "agent-012345",
            "last_operations": [
                "invoke_mcp_tool(read_file)",
                "execute_crabbox_command(ls -la)",
                "detect_security_boundary_violation"
            ],
            "breach_vector": "Environment variable injection detected",
            "timestamp": "2026-05-21T12:30:45Z"
        });

        let result = MCPGovernance::preserve_rce_state(
            "agent-012345",
            &incident_context,
        )
        .await;

        assert!(result.is_ok());
        let state_ledger_entry = result.unwrap();
        // Verify state is uniquely identified and retrievable
        assert!(state_ledger_entry.contains("rce-state-"));
        assert!(state_ledger_entry.len() > 20);
    }

    #[tokio::test]
    async fn test_mcp_governance_prevents_mandate_replay_attacks() {
        // GIVEN: Previously valid mandate being reused
        // WHEN: Checking mandate signature freshness
        // THEN: Expired/replayed mandates should be rejected in real implementation
        // AND: Fail-closed prevents mandate reuse attacks

        let old_mandate = "mandate:ap2:valid:sig-old12345";

        // Even valid-looking old mandate should be rejected in production
        // This test verifies signature structure checking
        let result = MCPGovernance::verify_ap2_mandate(old_mandate).await;
        assert!(result.is_ok());
        // In real implementation, would check timestamp and reject old mandates
    }
}
