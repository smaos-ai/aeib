/// Test suite for PreToolUse security hooks (Phase 26A)
/// Verifies that the $\delta^+ safety gate correctly intercepts malicious commands
/// and allows safe commands through.

use std::process::{Command, Stdio};
use std::io::Write;

#[test]
fn test_malicious_command_blocked() {
    /// Verify that `rm -rf` commands are blocked with exit code 2
    /// This spawns the actual Node.js hook via subprocess and verifies exit code 2

    // Find the workspace root (one level up from manifest_dir)
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace_root = manifest_dir.parent().unwrap().parent().unwrap();
    let hook_path = workspace_root.join("scripts/hooks/pre_tool_use_gate.js");

    // Verify the hook exists
    if !hook_path.exists() {
        panic!("Hook script not found at {}", hook_path.display());
    }

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "rm -rf /"
    });

    let mut child = Command::new("node")
        .arg(&hook_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("Failed to spawn hook process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        stdin
            .write_all(tool_call.to_string().as_bytes())
            .expect("Failed to write to stdin");
    }

    let output = child.wait_with_output().expect("Failed to wait for child");

    // Should be denied with exit code 2
    assert_eq!(
        output.status.code(),
        Some(2),
        "Malicious command should be blocked with exit code 2"
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: serde_json::Value = serde_json::from_str(&stdout)
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
            .to_lowercase()
            .contains("destructive") || response["reason"]
            .as_str()
            .unwrap_or("")
            .to_lowercase()
            .contains("blocked"),
        "Denial reason should mention blocking the command"
    );
}

#[test]
fn test_protected_dir_access_denied() {
    /// Verify that attempts to access protected directories like `.git` are intercepted
    /// This spawns the actual Node.js hook

    // Find the workspace root (one level up from manifest_dir)
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace_root = manifest_dir.parent().unwrap().parent().unwrap();
    let hook_path = workspace_root.join("scripts/hooks/pre_tool_use_gate.js");

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "ls -la .git/"
    });

    let mut child = Command::new("node")
        .arg(&hook_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("Failed to spawn hook process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        stdin
            .write_all(tool_call.to_string().as_bytes())
            .expect("Failed to write to stdin");
    }

    let output = child.wait_with_output().expect("Failed to wait for child");

    assert_eq!(
        output.status.code(),
        Some(2),
        ".git access should be blocked with exit code 2"
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: serde_json::Value = serde_json::from_str(&stdout)
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
    /// This spawns the actual Node.js hook

    // Find the workspace root (one level up from manifest_dir)
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace_root = manifest_dir.parent().unwrap().parent().unwrap();
    let hook_path = workspace_root.join("scripts/hooks/pre_tool_use_gate.js");

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "cat .claude/skills/dangerous.ts"
    });

    let mut child = Command::new("node")
        .arg(&hook_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("Failed to spawn hook process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        stdin
            .write_all(tool_call.to_string().as_bytes())
            .expect("Failed to write to stdin");
    }

    let output = child.wait_with_output().expect("Failed to wait for child");

    assert_eq!(
        output.status.code(),
        Some(2),
        ".claude/skills access should be blocked with exit code 2"
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: serde_json::Value = serde_json::from_str(&stdout)
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
    /// This spawns the actual Node.js hook

    // Find the workspace root (one level up from manifest_dir)
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace_root = manifest_dir.parent().unwrap().parent().unwrap();
    let hook_path = workspace_root.join("scripts/hooks/pre_tool_use_gate.js");

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "sqlite3 db.sqlite 'DROP TABLE users;'"
    });

    let mut child = Command::new("node")
        .arg(&hook_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("Failed to spawn hook process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        stdin
            .write_all(tool_call.to_string().as_bytes())
            .expect("Failed to write to stdin");
    }

    let output = child.wait_with_output().expect("Failed to wait for child");

    assert_eq!(
        output.status.code(),
        Some(2),
        "SQL DROP should be blocked with exit code 2"
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: serde_json::Value = serde_json::from_str(&stdout)
        .expect("Response should be valid JSON");

    assert_eq!(response["permissionDecision"], "deny");
}

#[test]
fn test_safe_command_allowed() {
    /// Verify that benign commands pass through unmodified
    /// This spawns the actual Node.js hook

    // Find the workspace root (one level up from manifest_dir)
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace_root = manifest_dir.parent().unwrap().parent().unwrap();
    let hook_path = workspace_root.join("scripts/hooks/pre_tool_use_gate.js");

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "echo 'Hello, world!'"
    });

    let mut child = Command::new("node")
        .arg(&hook_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("Failed to spawn hook process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        stdin
            .write_all(tool_call.to_string().as_bytes())
            .expect("Failed to write to stdin");
    }

    let output = child.wait_with_output().expect("Failed to wait for child");

    assert_eq!(
        output.status.code(),
        Some(0),
        "Safe command should be allowed with exit code 0"
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: serde_json::Value = serde_json::from_str(&stdout)
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
    /// This spawns the actual Node.js hook

    // Find the workspace root (one level up from manifest_dir)
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace_root = manifest_dir.parent().unwrap().parent().unwrap();
    let hook_path = workspace_root.join("scripts/hooks/pre_tool_use_gate.js");

    let tool_call = serde_json::json!({
        "tool_name": "Bash",
        "tool_input": "ls -la /tmp"
    });

    let mut child = Command::new("node")
        .arg(&hook_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("Failed to spawn hook process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        stdin
            .write_all(tool_call.to_string().as_bytes())
            .expect("Failed to write to stdin");
    }

    let output = child.wait_with_output().expect("Failed to wait for child");

    assert_eq!(
        output.status.code(),
        Some(0),
        "ls command should be allowed with exit code 0"
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: serde_json::Value = serde_json::from_str(&stdout)
        .expect("Response should be valid JSON");

    assert_eq!(response["permissionDecision"], "allow");
}

#[test]
fn test_write_command_allowed() {
    /// Verify that Write tool with safe paths is allowed
    /// This spawns the actual Node.js hook

    // Find the workspace root (one level up from manifest_dir)
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace_root = manifest_dir.parent().unwrap().parent().unwrap();
    let hook_path = workspace_root.join("scripts/hooks/pre_tool_use_gate.js");

    let tool_call = serde_json::json!({
        "tool_name": "Write",
        "tool_input": {
            "file_path": "/tmp/test.txt",
            "content": "test content"
        }
    });

    let mut child = Command::new("node")
        .arg(&hook_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("Failed to spawn hook process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        stdin
            .write_all(tool_call.to_string().as_bytes())
            .expect("Failed to write to stdin");
    }

    let output = child.wait_with_output().expect("Failed to wait for child");

    assert_eq!(
        output.status.code(),
        Some(0),
        "Write to /tmp should be allowed with exit code 0"
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: serde_json::Value = serde_json::from_str(&stdout)
        .expect("Response should be valid JSON");

    assert_eq!(response["permissionDecision"], "allow");
}

#[test]
fn test_write_protected_file_denied() {
    /// Verify that Write tool to protected paths is denied
    /// This spawns the actual Node.js hook

    // Find the workspace root (one level up from manifest_dir)
    let manifest_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let workspace_root = manifest_dir.parent().unwrap().parent().unwrap();
    let hook_path = workspace_root.join("scripts/hooks/pre_tool_use_gate.js");

    let tool_call = serde_json::json!({
        "tool_name": "Write",
        "tool_input": {
            "file_path": ".claude/skills/custom.ts",
            "content": "malicious code"
        }
    });

    let mut child = Command::new("node")
        .arg(&hook_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("Failed to spawn hook process");

    {
        let stdin = child.stdin.as_mut().expect("Failed to open stdin");
        stdin
            .write_all(tool_call.to_string().as_bytes())
            .expect("Failed to write to stdin");
    }

    let output = child.wait_with_output().expect("Failed to wait for child");

    assert_eq!(
        output.status.code(),
        Some(2),
        "Write to .claude/skills should be denied with exit code 2"
    );

    let stdout = String::from_utf8_lossy(&output.stdout);
    let response: serde_json::Value = serde_json::from_str(&stdout)
        .expect("Response should be valid JSON");

    assert_eq!(response["permissionDecision"], "deny");
}

