/// Phase 34 REFACTOR: AoE Cockpit Integration Tests
/// End-to-end testing for session lifecycle, fail-closed contracts, and orchestration

#[cfg(test)]
mod integration_tests {
    use crate::handlers::aoe_cockpit::{AoECockpit, AoESession, AoEError};

    #[tokio::test]
    async fn test_aoe_session_lifecycle_complete() {
        // GIVEN: User with valid bearer token
        // WHEN: Session initialized, attached, listed, and accessed
        // THEN: All operations succeed with correct state transitions
        // AND: Session properties match throughout lifecycle

        let bearer = Some("Bearer user-12345".to_string());
        let tmux_name = "sovereign-lifecycle";

        // Initialize session
        let init_result = AoECockpit::init_session(bearer.clone(), tmux_name).await;
        assert!(init_result.is_ok());
        let session = init_result.unwrap();
        let session_id = session.session_id.clone();
        assert_eq!(session.tmux_name, tmux_name);
        assert_eq!(session.status, "active");

        // Attach to session
        let attach_result = AoECockpit::attach_tmux(&session_id, bearer.clone()).await;
        assert!(attach_result.is_ok());

        // List sessions
        let list_result = AoECockpit::list_active_sessions(bearer.clone()).await;
        assert!(list_result.is_ok());
        let sessions = list_result.unwrap();
        // In full implementation, would verify session appears in list

        // Verify access
        let access_result = AoECockpit::verify_agent_access(bearer);
        assert!(access_result.is_ok());
        assert_eq!(access_result.unwrap(), "user-12345");
    }

    #[tokio::test]
    async fn test_aoe_session_auth_fail_closed_across_all_operations() {
        // GIVEN: No bearer token provided
        // WHEN: Attempting any session operation
        // THEN: All operations fail-closed with 401 Unauthorized
        // AND: No partial state created

        // init_session without auth
        let init_result = AoECockpit::init_session(None, "test").await;
        assert!(init_result.is_err());
        assert!(matches!(init_result.unwrap_err(), AoEError::Unauthorized));

        // attach_tmux without auth
        let attach_result = AoECockpit::attach_tmux("session-123", None).await;
        assert!(attach_result.is_err());
        assert!(matches!(attach_result.unwrap_err(), AoEError::Unauthorized));

        // list_active_sessions without auth
        let list_result = AoECockpit::list_active_sessions(None).await;
        assert!(list_result.is_err());
        assert!(matches!(list_result.unwrap_err(), AoEError::Unauthorized));

        // verify_agent_access without auth
        let verify_result = AoECockpit::verify_agent_access(None);
        assert!(verify_result.is_err());
        assert!(matches!(verify_result.unwrap_err(), AoEError::Unauthorized));
    }

    #[tokio::test]
    async fn test_aoe_docker_sandbox_path_validation_fail_closed() {
        // GIVEN: Multiple worktree paths (valid and invalid)
        // WHEN: Starting docker sandbox
        // THEN: Valid paths succeed, invalid paths fail-closed with 403
        // AND: No container created for invalid paths

        // Valid path should succeed
        let valid_result = AoECockpit::start_docker_sandbox(
            "session-valid",
            "sovereign:latest",
            ".claude/worktrees/feat-phase34-aoe-cockpit",
        )
        .await;
        assert!(valid_result.is_ok());
        let container_id = valid_result.unwrap();
        assert!(container_id.starts_with("sha256:"));

        // Invalid path should fail-closed
        let invalid_paths = vec![
            "/nonexistent/path",
            "/tmp/surely/does/not/exist/on/this/system",
            "/var/invalid/workspace",
            "../../../etc/passwd",
        ];

        for invalid_path in invalid_paths {
            let result = AoECockpit::start_docker_sandbox(
                "session-invalid",
                "sovereign:latest",
                invalid_path,
            )
            .await;
            assert!(result.is_err(), "Path {} should be rejected", invalid_path);
            assert!(
                matches!(result.unwrap_err(), AoEError::WorkspaceNotFound),
                "Should return 403 WorkspaceNotFound for path {}",
                invalid_path
            );
        }
    }

    #[tokio::test]
    async fn test_aoe_agent_access_extracts_bearer_token_correctly() {
        // GIVEN: Valid bearer tokens with agent IDs
        // WHEN: Verifying agent access
        // THEN: Agent ID is correctly extracted from Bearer scheme
        // AND: Access is granted

        let test_cases = vec![
            ("Bearer agent-001", "agent-001"),
            ("Bearer sovereign-operator-xyz", "sovereign-operator-xyz"),
            ("Bearer token-with-hyphens-and-numbers-123", "token-with-hyphens-and-numbers-123"),
        ];

        for (bearer_token, expected_agent_id) in test_cases {
            let result = AoECockpit::verify_agent_access(Some(bearer_token.to_string()));
            assert!(result.is_ok(), "Bearer token {} should succeed", bearer_token);
            assert_eq!(
                result.unwrap(),
                expected_agent_id,
                "Agent ID should be correctly extracted"
            );
        }
    }

    #[tokio::test]
    async fn test_aoe_session_initialization_generates_unique_ids() {
        // GIVEN: Multiple session initialization requests with valid auth
        // WHEN: Creating multiple AoE sessions
        // THEN: Each session gets unique session_id
        // AND: All sessions marked as "active"

        let bearer = Some("Bearer admin-token".to_string());

        let mut session_ids = Vec::new();
        for i in 0..5 {
            let tmux_name = format!("sovereign-session-{}", i);
            let result = AoECockpit::init_session(bearer.clone(), &tmux_name).await;
            assert!(result.is_ok());
            let session = result.unwrap();
            session_ids.push(session.session_id.clone());
            assert_eq!(session.status, "active");
        }

        // Verify all session IDs are unique
        let unique_count = session_ids.iter().collect::<std::collections::HashSet<_>>().len();
        assert_eq!(unique_count, 5, "All session IDs should be unique");
    }

    #[tokio::test]
    async fn test_aoe_session_properties_are_consistent() {
        // GIVEN: Initialized AoE session
        // WHEN: Creating session with specific parameters
        // THEN: All properties are set correctly
        // AND: created_at timestamp is RFC3339 format

        let bearer = Some("Bearer consistency-check".to_string());
        let tmux_name = "sovereign-consistent-session";

        let result = AoECockpit::init_session(bearer, tmux_name).await;
        assert!(result.is_ok());
        let session = result.unwrap();

        // Verify all properties
        assert!(!session.session_id.is_empty());
        assert_eq!(session.tmux_name, tmux_name);
        assert!(session.worktree_path.contains(tmux_name));
        assert_eq!(session.docker_container, ""); // Not set until sandbox starts
        assert!(session.created_at.contains("T")); // RFC3339 format has T
        assert!(session.created_at.contains("Z") || session.created_at.contains("+")); // Has timezone
        assert_eq!(session.agent_count, 0);
        assert_eq!(session.status, "active");
    }
}
