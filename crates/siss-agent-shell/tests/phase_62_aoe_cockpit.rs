/// Phase 62: Operator Cockpit & Swarm Orchestration — 27 TDD Tests

use siss_agent_shell::aoe_tmux_bridge::{
    AoeTmuxBridge, TmuxBridgeConfig, TmuxBridgeError, TmuxSessionDriver,
};
use siss_agent_shell::aoe_sandbox::{AoeSandboxGate, SandboxBoundary, SandboxViolation};
use siss_agent_shell::aoe_tui_monitor::AoeTuiMonitor;
use siss_agent_shell::ag_ui::AgentState;
use siss_agent_shell::hooks::{HookResult, LifecycleHook, ToolUseContext};
use siss_graph_core::node::NodeId;
use chrono::Utc;
use serde_json::json;
use uuid::Uuid;

// ============================================================================
// MOCK: TmuxSessionDriver for testing bridge behavior
// ============================================================================

struct MockTmuxDriver {
    spawn_should_fail: bool,
    kill_should_fail: bool,
}

#[async_trait::async_trait]
impl TmuxSessionDriver for MockTmuxDriver {
    async fn spawn(&self, _name: &str, _working_dir: &str) -> Result<(), TmuxBridgeError> {
        if self.spawn_should_fail {
            Err(TmuxBridgeError::SpawnFailed(
                "mock spawn failure".to_string(),
            ))
        } else {
            Ok(())
        }
    }

    async fn kill(&self, _name: &str) -> Result<(), TmuxBridgeError> {
        if self.kill_should_fail {
            Err(TmuxBridgeError::KillFailed("mock kill failure".to_string()))
        } else {
            Ok(())
        }
    }
}

// ============================================================================
// Module 1: AoeTmuxBridge — 9 Tests
// ============================================================================

#[tokio::test]
async fn test_bridge_bind_creates_session_token() {
    let driver = MockTmuxDriver {
        spawn_should_fail: false,
        kill_should_fail: false,
    };
    let config = TmuxBridgeConfig {
        session_prefix: "siss-agent".to_string(),
        detach_resilient: true,
    };
    let bridge = AoeTmuxBridge::new(driver, config);

    let agent_id = Uuid::new_v4();
    let working_dir = "/tmp/test";

    let result = bridge.bind(agent_id, working_dir).await;
    assert!(result.is_ok());

    let token = result.unwrap();
    assert_eq!(token.agent_id, agent_id);
    assert_eq!(token.working_dir, working_dir);
    assert!(token.session_name.contains("siss-agent"));
}

#[tokio::test]
async fn test_bridge_bind_second_bind_same_name_fails() {
    let driver = MockTmuxDriver {
        spawn_should_fail: false,
        kill_should_fail: false,
    };
    let config = TmuxBridgeConfig {
        session_prefix: "siss-agent".to_string(),
        detach_resilient: true,
    };
    let bridge = AoeTmuxBridge::new(driver, config);

    let agent_id = Uuid::new_v4();
    let working_dir = "/tmp/test";

    let first = bridge.bind(agent_id, working_dir).await;
    assert!(first.is_ok());

    let second = bridge.bind(agent_id, working_dir).await;
    assert!(second.is_err());
    assert!(matches!(second.unwrap_err(), TmuxBridgeError::AlreadyBound { .. }));
}

#[tokio::test]
async fn test_bridge_unbind_removes_from_registry() {
    let driver = MockTmuxDriver {
        spawn_should_fail: false,
        kill_should_fail: false,
    };
    let config = TmuxBridgeConfig {
        session_prefix: "siss-agent".to_string(),
        detach_resilient: true,
    };
    let bridge = AoeTmuxBridge::new(driver, config);

    let agent_id = Uuid::new_v4();
    let working_dir = "/tmp/test";

    let token = bridge.bind(agent_id, working_dir).await.unwrap();
    assert_eq!(bridge.list_bound().len(), 1);

    let result = bridge.unbind(token).await;
    assert!(result.is_ok());
    assert_eq!(bridge.list_bound().len(), 0);
}

#[test]
fn test_bridge_session_name_uses_prefix() {
    let driver = MockTmuxDriver {
        spawn_should_fail: false,
        kill_should_fail: false,
    };
    let config = TmuxBridgeConfig {
        session_prefix: "custom-prefix".to_string(),
        detach_resilient: true,
    };
    let bridge = AoeTmuxBridge::new(driver, config);

    let agent_id = Uuid::new_v4();
    let name = bridge.session_name_for(agent_id);
    assert!(name.starts_with("custom-prefix-"));
}

#[tokio::test]
async fn test_bridge_spawn_failure_leaves_registry_clean() {
    let driver = MockTmuxDriver {
        spawn_should_fail: true,
        kill_should_fail: false,
    };
    let config = TmuxBridgeConfig {
        session_prefix: "siss-agent".to_string(),
        detach_resilient: true,
    };
    let bridge = AoeTmuxBridge::new(driver, config);

    let agent_id = Uuid::new_v4();
    let result = bridge.bind(agent_id, "/tmp/test").await;

    assert!(result.is_err());
    assert_eq!(bridge.list_bound().len(), 0);
}

#[tokio::test]
async fn test_bridge_unbind_unknown_session_returns_not_found() {
    let driver = MockTmuxDriver {
        spawn_should_fail: false,
        kill_should_fail: false,
    };
    let config = TmuxBridgeConfig {
        session_prefix: "siss-agent".to_string(),
        detach_resilient: true,
    };
    let bridge = AoeTmuxBridge::new(driver, config);

    let agent_id = Uuid::new_v4();
    let fake_token = siss_agent_shell::aoe_tmux_bridge::TmuxSessionToken {
        session_name: "unknown-session".to_string(),
        agent_id,
        working_dir: "/tmp".to_string(),
    };

    let result = bridge.unbind(fake_token).await;
    assert!(result.is_err());
    assert!(matches!(result.unwrap_err(), TmuxBridgeError::SessionNotFound { .. }));
}

#[tokio::test]
async fn test_bridge_list_bound_returns_all_active() {
    let driver = MockTmuxDriver {
        spawn_should_fail: false,
        kill_should_fail: false,
    };
    let config = TmuxBridgeConfig {
        session_prefix: "siss-agent".to_string(),
        detach_resilient: true,
    };
    let bridge = AoeTmuxBridge::new(driver, config);

    for _ in 0..3 {
        let agent_id = Uuid::new_v4();
        bridge.bind(agent_id, "/tmp/test").await.ok();
    }

    assert_eq!(bridge.list_bound().len(), 3);
}

#[test]
fn test_bridge_detach_resilient_config_true_by_default() {
    let config = TmuxBridgeConfig::default();
    assert_eq!(config.detach_resilient, true);
}

#[tokio::test]
async fn test_bridge_kill_failure_leaves_registry_intact() {
    let driver = MockTmuxDriver {
        spawn_should_fail: false,
        kill_should_fail: true,
    };
    let config = TmuxBridgeConfig {
        session_prefix: "siss-agent".to_string(),
        detach_resilient: true,
    };
    let bridge = AoeTmuxBridge::new(driver, config);

    let agent_id = Uuid::new_v4();
    let token = bridge.bind(agent_id, "/tmp/test").await.unwrap();
    assert_eq!(bridge.list_bound().len(), 1);

    let result = bridge.unbind(token).await;
    assert!(result.is_err());
    assert_eq!(bridge.list_bound().len(), 1);
}

// ============================================================================
// Module 2: AoeSandboxGate — 9 Tests
// ============================================================================

#[test]
fn test_sandbox_write_inside_worktree_continues() {
    let boundary = SandboxBoundary {
        worktree_path: "/workspace/project".to_string(),
        allowed_auth_path: "/auth".to_string(),
    };
    let gate = AoeSandboxGate { boundary };

    let ctx = ToolUseContext {
        task_id: NodeId(Uuid::new_v4()),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: json!({ "file_path": "/workspace/project/src/lib.rs" }),
        tool_output: None,
    };

    let result = gate.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

#[test]
fn test_sandbox_write_outside_worktree_denies() {
    let boundary = SandboxBoundary {
        worktree_path: "/workspace/project".to_string(),
        allowed_auth_path: "/auth".to_string(),
    };
    let gate = AoeSandboxGate { boundary };

    let ctx = ToolUseContext {
        task_id: NodeId(Uuid::new_v4()),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: json!({ "file_path": "/etc/passwd" }),
        tool_output: None,
    };

    let result = gate.on_pre_tool_use(&ctx);
    assert!(matches!(result, HookResult::Deny { .. }));
}

#[test]
fn test_sandbox_write_to_auth_path_continues() {
    let boundary = SandboxBoundary {
        worktree_path: "/workspace/project".to_string(),
        allowed_auth_path: "/auth/shared".to_string(),
    };
    let gate = AoeSandboxGate { boundary };

    let ctx = ToolUseContext {
        task_id: NodeId(Uuid::new_v4()),
        tool_id: Uuid::new_v4(),
        tool_name: "Write".to_string(),
        tool_input: json!({ "file_path": "/auth/shared/token.txt" }),
        tool_output: None,
    };

    let result = gate.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

#[test]
fn test_sandbox_empty_path_denies() {
    let boundary = SandboxBoundary {
        worktree_path: "/workspace".to_string(),
        allowed_auth_path: "/auth".to_string(),
    };
    let gate = AoeSandboxGate { boundary };

    let ctx = ToolUseContext {
        task_id: NodeId(Uuid::new_v4()),
        tool_id: Uuid::new_v4(),
        tool_name: "Edit".to_string(),
        tool_input: json!({ "file_path": "" }),
        tool_output: None,
    };

    let result = gate.on_pre_tool_use(&ctx);
    assert!(matches!(result, HookResult::Deny { .. }));
}

#[test]
fn test_sandbox_non_write_tool_passes_through() {
    let boundary = SandboxBoundary {
        worktree_path: "/workspace".to_string(),
        allowed_auth_path: "/auth".to_string(),
    };
    let gate = AoeSandboxGate { boundary };

    let ctx = ToolUseContext {
        task_id: NodeId(Uuid::new_v4()),
        tool_id: Uuid::new_v4(),
        tool_name: "Bash".to_string(),
        tool_input: json!({ "command": "cat /etc/passwd" }),
        tool_output: None,
    };

    let result = gate.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

#[test]
fn test_sandbox_bash_write_outside_worktree_denies() {
    let boundary = SandboxBoundary {
        worktree_path: "/workspace".to_string(),
        allowed_auth_path: "/auth".to_string(),
    };
    let gate = AoeSandboxGate { boundary };

    let ctx = ToolUseContext {
        task_id: NodeId(Uuid::new_v4()),
        tool_id: Uuid::new_v4(),
        tool_name: "Bash".to_string(),
        tool_input: json!({ "command": "echo x > /tmp/evil" }),
        tool_output: None,
    };

    let result = gate.on_pre_tool_use(&ctx);
    assert!(matches!(result, HookResult::Deny { .. }));
}

#[test]
fn test_sandbox_check_path_inside_worktree_ok() {
    let boundary = SandboxBoundary {
        worktree_path: "/workspace".to_string(),
        allowed_auth_path: "/auth".to_string(),
    };
    let gate = AoeSandboxGate { boundary };

    let result = gate.check_path("/workspace/src/lib.rs");
    assert!(result.is_ok());
}

#[test]
fn test_sandbox_check_path_outside_both_roots_fails() {
    let boundary = SandboxBoundary {
        worktree_path: "/workspace".to_string(),
        allowed_auth_path: "/auth".to_string(),
    };
    let gate = AoeSandboxGate { boundary };

    let result = gate.check_path("/home/other/file");
    assert!(result.is_err());
    assert!(matches!(
        result.unwrap_err(),
        SandboxViolation::PathOutsideBoundary { .. }
    ));
}

#[test]
fn test_sandbox_read_tool_not_intercepted() {
    let boundary = SandboxBoundary {
        worktree_path: "/workspace".to_string(),
        allowed_auth_path: "/auth".to_string(),
    };
    let gate = AoeSandboxGate { boundary };

    let ctx = ToolUseContext {
        task_id: NodeId(Uuid::new_v4()),
        tool_id: Uuid::new_v4(),
        tool_name: "Read".to_string(),
        tool_input: json!({ "file_path": "/etc/passwd" }),
        tool_output: None,
    };

    let result = gate.on_pre_tool_use(&ctx);
    assert_eq!(result, HookResult::Continue);
}

// ============================================================================
// Module 3: AoeTuiMonitor — 9 Tests
// ============================================================================

#[test]
fn test_tui_update_adds_entry() {
    let mut monitor = AoeTuiMonitor::new();
    let agent_id = Uuid::new_v4();

    monitor.update(
        agent_id,
        AgentState::Running,
        "tmux-session",
        "/workspace",
        50,
        Utc::now(),
    );

    let report = monitor.build_report(Utc::now());
    assert_eq!(report.entries.len(), 1);
}

#[test]
fn test_tui_update_overwrites_same_agent() {
    let mut monitor = AoeTuiMonitor::new();
    let agent_id = Uuid::new_v4();

    monitor.update(
        agent_id,
        AgentState::Running,
        "tmux-1",
        "/workspace",
        50,
        Utc::now(),
    );
    monitor.update(
        agent_id,
        AgentState::Idle,
        "tmux-2",
        "/workspace",
        100,
        Utc::now(),
    );

    let report = monitor.build_report(Utc::now());
    assert_eq!(report.entries.len(), 1);
    assert_eq!(report.entries[0].state, AgentState::Idle);
}

#[test]
fn test_tui_build_report_counts_running() {
    let mut monitor = AoeTuiMonitor::new();

    for _ in 0..2 {
        monitor.update(
            Uuid::new_v4(),
            AgentState::Running,
            "tmux",
            "/workspace",
            50,
            Utc::now(),
        );
    }
    monitor.update(
        Uuid::new_v4(),
        AgentState::Idle,
        "tmux",
        "/workspace",
        100,
        Utc::now(),
    );

    let report = monitor.build_report(Utc::now());
    assert_eq!(report.running_count, 2);
}

#[test]
fn test_tui_build_report_counts_waiting() {
    let mut monitor = AoeTuiMonitor::new();

    monitor.update(
        Uuid::new_v4(),
        AgentState::Waiting,
        "tmux",
        "/workspace",
        0,
        Utc::now(),
    );
    for _ in 0..2 {
        monitor.update(
            Uuid::new_v4(),
            AgentState::Running,
            "tmux",
            "/workspace",
            50,
            Utc::now(),
        );
    }

    let report = monitor.build_report(Utc::now());
    assert_eq!(report.waiting_count, 1);
}

#[test]
fn test_tui_remove_deletes_entry() {
    let mut monitor = AoeTuiMonitor::new();
    let agent_id = Uuid::new_v4();

    monitor.update(
        agent_id,
        AgentState::Running,
        "tmux",
        "/workspace",
        50,
        Utc::now(),
    );
    assert_eq!(monitor.build_report(Utc::now()).entries.len(), 1);

    monitor.remove(agent_id);
    assert_eq!(monitor.build_report(Utc::now()).entries.len(), 0);
}

#[test]
fn test_tui_remove_unknown_returns_none() {
    let mut monitor = AoeTuiMonitor::new();
    let result = monitor.remove(Uuid::new_v4());
    assert!(result.is_none());
}

#[test]
fn test_tui_multiple_agents_tracked_independently() {
    let mut monitor = AoeTuiMonitor::new();
    let id1 = Uuid::new_v4();
    let id2 = Uuid::new_v4();
    let id3 = Uuid::new_v4();

    monitor.update(id1, AgentState::Running, "tmux1", "/workspace", 50, Utc::now());
    monitor.update(id2, AgentState::Idle, "tmux2", "/workspace", 100, Utc::now());
    monitor.update(id3, AgentState::Error, "tmux3", "/workspace", 0, Utc::now());

    let report = monitor.build_report(Utc::now());
    assert_eq!(report.entries.len(), 3);
    assert_eq!(report.running_count, 1);
    assert_eq!(report.idle_count, 1);
}

#[test]
fn test_tui_parse_diff_extracts_file_entries() {
    let monitor = AoeTuiMonitor::new();
    let diff_text = r#"
diff --git a/src/lib.rs b/src/lib.rs
index abc..def 100644
--- a/src/lib.rs
+++ b/src/lib.rs
@@ -1,5 +1,6 @@
 fn main() {
+    println!("hello");
     let x = 42;
 }
"#;

    let entries = monitor.parse_diff(diff_text);
    assert!(!entries.is_empty());
    assert!(entries.iter().any(|e| e.file_path.contains("lib.rs")));
}

#[test]
fn test_tui_parse_diff_empty_input_returns_empty() {
    let monitor = AoeTuiMonitor::new();
    let entries = monitor.parse_diff("");
    assert_eq!(entries.len(), 0);
}
