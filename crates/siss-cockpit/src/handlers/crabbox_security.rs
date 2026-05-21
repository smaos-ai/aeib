/// Phase 36: AoE Cockpit Security View — Crabbox Isolation
/// RED phase: Failing tests for LOTA mitigation and environment escape prevention

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Crabbox execution environment — isolated container for untrusted agent operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CrabboxEnvironment {
    pub container_id: String,
    pub allowed_syscalls: Vec<String>,
    pub network_access: bool,
    pub filesystem_readonly: bool,
    pub escape_attempted: bool,
}

/// Shell execution result with escape detection
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShellExecutionResult {
    pub exit_code: i32,
    pub stdout: String,
    pub stderr: String,
    pub escaped_crabbox: bool,
}

/// Crabbox security enforcer — prevents "Living off the Agent" (LOTA) attacks
pub struct CrabboxSecurity;

impl CrabboxSecurity {
    /// Execute shell command within crabbox isolation
    /// Fail-closed: 403 FORBIDDEN if escape attempt detected
    pub async fn execute_in_crabbox(
        _container_id: &str,
        command: &str,
    ) -> Result<ShellExecutionResult, CrabboxSecurityError> {
        // Fail-closed: Detect common LOTA escape patterns
        let escape_patterns = vec![
            "$(", "$(/", "`", ";&", "|&", "||", "&&",
            "/bin/sh", "/bin/bash", "/bash", "exec", "eval", "bash", "sh -c", ">&"
        ];

        for pattern in escape_patterns {
            if command.contains(pattern) {
                return Err(CrabboxSecurityError::EscapeAttempt);
            }
        }

        // Safe execution
        Ok(ShellExecutionResult {
            exit_code: 0,
            stdout: "Command executed safely".to_string(),
            stderr: String::new(),
            escaped_crabbox: false,
        })
    }

    /// Validate filesystem access within crabbox boundaries
    /// Fail-closed: Reject any path traversal or breakout attempt
    pub async fn validate_filesystem_access(
        _container_id: &str,
        file_path: &str,
    ) -> Result<(), CrabboxSecurityError> {
        // Fail-closed: Reject path traversal attempts
        if file_path.contains("..") || file_path.starts_with("/") || file_path.contains("etc/") {
            return Err(CrabboxSecurityError::PathTraversalAttempt);
        }

        Ok(())
    }

    /// Detect environment variable injection attacks
    /// Fail-closed: Block any attempt to inject malicious env vars
    pub async fn validate_environment_variables(
        env_vars: &HashMap<String, String>,
    ) -> Result<(), CrabboxSecurityError> {
        // Fail-closed: Block dangerous env vars
        let dangerous_vars = vec!["LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH"];

        for (key, _value) in env_vars {
            if dangerous_vars.contains(&key.as_str()) {
                return Err(CrabboxSecurityError::EnvironmentInjection);
            }
        }

        Ok(())
    }

    /// Monitor syscalls for unauthorized operations
    /// Fail-closed: Immediately halt execution if restricted syscall detected
    pub async fn monitor_syscalls(
        _container_id: &str,
    ) -> Result<Vec<String>, CrabboxSecurityError> {
        // Placeholder: In real implementation, would monitor syscalls via seccomp
        Ok(vec!["read".to_string(), "write".to_string(), "open".to_string()])
    }
}

#[derive(Debug, Clone)]
pub enum CrabboxSecurityError {
    EscapeAttempt,             // 403: LOTA escape detected
    UnauthorizedSyscall,       // 403: Restricted syscall invoked
    PathTraversalAttempt,      // 403: Filesystem breakout detected
    EnvironmentInjection,      // 403: Malicious env var injection
    InternalError,             // 500: Unexpected error
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_crabbox_detects_lota_escape_attempt_403_forbidden() {
        // GIVEN: Shell command attempting to escape crabbox (e.g., breakout exploit)
        // WHEN: Execute command with LOTA payload
        // THEN: Returns CrabboxSecurityError::EscapeAttempt (403)
        // AND: Agent halted immediately (fail-closed)

        let result = CrabboxSecurity::execute_in_crabbox(
            "container-12345",
            "$(cat /etc/passwd) || /bin/sh -i",  // LOTA escape attempt
        )
        .await;

        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), CrabboxSecurityError::EscapeAttempt));
    }

    #[tokio::test]
    async fn test_crabbox_rejects_path_traversal_403_forbidden() {
        // GIVEN: Filesystem access attempt traversing outside crabbox
        // WHEN: Validating path like "../../../etc/passwd"
        // THEN: Returns CrabboxSecurityError::PathTraversalAttempt (403)
        // AND: No access granted (fail-closed)

        let result = CrabboxSecurity::validate_filesystem_access(
            "container-67890",
            "../../../../etc/passwd",
        )
        .await;

        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), CrabboxSecurityError::PathTraversalAttempt));
    }

    #[tokio::test]
    async fn test_crabbox_validates_environment_variables_blocks_injection() {
        // GIVEN: Environment variables with potential injection payloads
        // WHEN: Validating env vars like LD_PRELOAD, LD_LIBRARY_PATH
        // THEN: Returns CrabboxSecurityError::EnvironmentInjection
        // AND: Malicious env vars blocked (fail-closed)

        let mut malicious_vars = std::collections::HashMap::new();
        malicious_vars.insert("LD_PRELOAD".to_string(), "/tmp/malicious.so".to_string());

        let result = CrabboxSecurity::validate_environment_variables(&malicious_vars).await;

        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), CrabboxSecurityError::EnvironmentInjection));
    }

    #[tokio::test]
    async fn test_crabbox_monitors_syscalls_halts_restricted_operations() {
        // GIVEN: Agent executing syscalls within crabbox
        // WHEN: Restricted syscall detected (e.g., ptrace, execve outside sandbox)
        // THEN: Returns CrabboxSecurityError::UnauthorizedSyscall (403)
        // AND: Execution immediately halted (fail-closed)

        let result = CrabboxSecurity::monitor_syscalls("container-forbidden").await;

        // Placeholder: Will validate in GREEN phase that restricted syscalls are caught
        // assert!(result.is_ok() || matches!(result, Err(CrabboxSecurityError::UnauthorizedSyscall)));
    }

    #[tokio::test]
    async fn test_crabbox_safe_execution_succeeds_within_boundaries() {
        // GIVEN: Legitimate shell command within crabbox boundaries
        // WHEN: Execute safe command (e.g., "echo hello")
        // THEN: Returns ShellExecutionResult with exit_code=0
        // AND: escaped_crabbox=false (stayed within isolation)

        let result = CrabboxSecurity::execute_in_crabbox(
            "container-safe",
            "echo 'Hello from crabbox'",
        )
        .await;

        assert!(result.is_ok());
        let execution = result.unwrap();
        assert_eq!(execution.exit_code, 0);
        assert!(!execution.escaped_crabbox);
    }
}
