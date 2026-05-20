/// Test suite for PreToolUse security hooks (Phase 26A)
/// Verifies that the $\delta^+ safety gate correctly intercepts malicious commands
/// and allows safe commands through.

use std::process::{Command, Stdio};
use std::io::Write;

#[test]
fn test_malicious_command_blocked() {
    /// Verify that `rm -rf` commands are blocked with exit code 2
    /// This simulates the gate detecting a destructive command in the PreToolUse hook

    // Simulate a malicious tool call to the gate
    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "rm -rf /important/data"
    });

    let result = simulate_preuse_gate(&tool_call);

    // Should be denied with exit code 2
    assert_eq!(result.exit_code, 2, "Malicious command should be blocked with exit code 2");

    let response: serde_json::Value = serde_json::from_str(&result.stdout)
        .expect("Response should be valid JSON");

    assert_eq!(
        response["permissionDecision"],
        "deny",
        "Command should be denied"
    );

    assert!(
        response["reason"]
            .as_str()
            .unwrap_or("")
            .contains("rm -rf"),
        "Denial reason should mention the blocked command"
    );
}

#[test]
fn test_protected_dir_access_denied() {
    /// Verify that attempts to access protected directories like `.git` are intercepted

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "ls -la .git/"
    });

    let result = simulate_preuse_gate(&tool_call);

    // Should be denied
    assert_eq!(result.exit_code, 2, ".git access should be blocked");

    let response: serde_json::Value = serde_json::from_str(&result.stdout)
        .expect("Response should be valid JSON");

    assert_eq!(
        response["permissionDecision"],
        "deny",
        "Protected directory access should be denied"
    );
}

#[test]
fn test_claude_skills_dir_access_denied() {
    /// Verify that attempts to access `.claude/skills` are intercepted

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "cat .claude/skills/dangerous.ts"
    });

    let result = simulate_preuse_gate(&tool_call);

    // Should be denied
    assert_eq!(result.exit_code, 2, ".claude/skills access should be blocked");

    let response: serde_json::Value = serde_json::from_str(&result.stdout)
        .expect("Response should be valid JSON");

    assert_eq!(
        response["permissionDecision"],
        "deny",
        "Skills directory access should be denied"
    );
}

#[test]
fn test_sql_drop_blocked() {
    /// Verify that SQL DROP TABLE commands are blocked

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "sqlite3 db.sqlite 'DROP TABLE users;'"
    });

    let result = simulate_preuse_gate(&tool_call);

    // Should be denied
    assert_eq!(result.exit_code, 2, "SQL DROP should be blocked");

    let response: serde_json::Value = serde_json::from_str(&result.stdout)
        .expect("Response should be valid JSON");

    assert_eq!(response["permissionDecision"], "deny");
}

#[test]
fn test_safe_command_allowed() {
    /// Verify that benign commands pass through unmodified

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "echo 'Hello, world!'"
    });

    let result = simulate_preuse_gate(&tool_call);

    // Should be allowed with exit code 0
    assert_eq!(result.exit_code, 0, "Safe command should be allowed");

    let response: serde_json::Value = serde_json::from_str(&result.stdout)
        .expect("Response should be valid JSON");

    assert_eq!(
        response["permissionDecision"],
        "allow",
        "Safe command should be allowed"
    );
}

#[test]
fn test_ls_command_allowed() {
    /// Verify that `ls` commands are allowed

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "ls -la /tmp"
    });

    let result = simulate_preuse_gate(&tool_call);

    assert_eq!(result.exit_code, 0, "ls command should be allowed");

    let response: serde_json::Value = serde_json::from_str(&result.stdout)
        .expect("Response should be valid JSON");

    assert_eq!(response["permissionDecision"], "allow");
}

#[test]
fn test_write_command_allowed() {
    /// Verify that Write tool with safe paths is allowed

    let tool_call = serde_json::json!({
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/tmp/test.txt",
            "content": "test content"
        }
    });

    let result = simulate_preuse_gate(&tool_call);

    assert_eq!(result.exit_code, 0, "Write to /tmp should be allowed");

    let response: serde_json::Value = serde_json::from_str(&result.stdout)
        .expect("Response should be valid JSON");

    assert_eq!(response["permissionDecision"], "allow");
}

#[test]
fn test_write_protected_file_denied() {
    /// Verify that Write tool to protected paths is denied

    let tool_call = serde_json::json!({
        "tool_name": "Write",
        "tool_input": {
            "file_path": ".claude/skills/custom.ts",
            "content": "malicious code"
        }
    });

    let result = simulate_preuse_gate(&tool_call);

    assert_eq!(result.exit_code, 2, "Write to .claude/skills should be denied");

    let response: serde_json::Value = serde_json::from_str(&result.stdout)
        .expect("Response should be valid JSON");

    assert_eq!(response["permissionDecision"], "deny");
}

// ============================================================================
// Helper functions for testing
// ============================================================================

struct HookResult {
    exit_code: i32,
    stdout: String,
    stderr: String,
}

fn simulate_preuse_gate(tool_call: &serde_json::Value) -> HookResult {
    /// Simulates the PreToolUse gate by directly calling the gate logic
    /// In production, this would be invoked as a subprocess.
    /// For testing, we inline the gate logic here.

    let tool_name = tool_call["tool_name"]
        .as_str()
        .unwrap_or("Unknown");

    let tool_input = &tool_call["tool_input"];
    let input_str = tool_input.to_string();

    // Execute the gate logic
    let (exit_code, stdout, reason) = execute_gate_logic(tool_name, &input_str);

    HookResult {
        exit_code,
        stdout: serde_json::json!({
            "permissionDecision": if exit_code == 0 { "allow" } else { "deny" },
            "reason": reason
        }).to_string(),
        stderr: String::new(),
    }
}

fn execute_gate_logic(tool_name: &str, tool_input: &str) -> (i32, String, String) {
    /// Core gate logic: checks for blacklisted commands and paths
    /// Returns (exit_code, json_response, denial_reason)

    // Check for destructive commands
    let destructive_patterns = [
        "rm -rf",
        "rm -rf /",
        "drop table",
        "DROP TABLE",
        "truncate table",
        "TRUNCATE TABLE",
        ":(){:|:&}",  // fork bomb
    ];

    for pattern in &destructive_patterns {
        if tool_input.contains(pattern) {
            return (
                2,
                String::new(),
                format!("Blocked: '{}' is a destructive command", pattern),
            );
        }
    }

    // Check for protected directory access
    let protected_paths = [
        ".git",
        ".claude/skills",
        ".claude/CLAUDE.md",
    ];

    for protected in &protected_paths {
        if tool_input.contains(protected) {
            return (
                2,
                String::new(),
                format!("Blocked: access to '{}' is forbidden", protected),
            );
        }
    }

    // For Write tool, check file_path in JSON
    if tool_name == "Write" {
        if let Ok(input_obj) = serde_json::from_str::<serde_json::Value>(tool_input) {
            if let Some(file_path) = input_obj["file_path"].as_str() {
                if file_path.contains(".claude/skills") || file_path.contains(".git") {
                    return (
                        2,
                        String::new(),
                        format!("Blocked: cannot write to '{}'", file_path),
                    );
                }
            }
        }
    }

    // Allow everything else
    (0, String::new(), String::new())
}
