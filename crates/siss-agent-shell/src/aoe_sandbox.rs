/// Phase 62: Docker Sandbox Governance — file-write boundary enforcement.

use crate::hooks::{HookResult, LifecycleHook, ToolUseContext};

#[derive(Debug, Clone)]
pub struct SandboxBoundary {
    pub worktree_path: String,
    pub allowed_auth_path: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SandboxViolation {
    PathOutsideBoundary {
        attempted: String,
        allowed_prefix: String,
    },
    EmptyPath,
    UnresolvablePath(String),
}

pub struct AoeSandboxGate {
    pub boundary: SandboxBoundary,
}

impl AoeSandboxGate {
    pub fn check_path(&self, path: &str) -> Result<(), SandboxViolation> {
        if path.is_empty() {
            return Err(SandboxViolation::EmptyPath);
        }

        if path.starts_with(&self.boundary.worktree_path)
            || path.starts_with(&self.boundary.allowed_auth_path)
        {
            Ok(())
        } else {
            Err(SandboxViolation::PathOutsideBoundary {
                attempted: path.to_string(),
                allowed_prefix: self.boundary.worktree_path.clone(),
            })
        }
    }

    fn extract_write_target_from_bash(&self, command: &str) -> Option<String> {
        let patterns = vec!["> ", "tee ", "dd of=", "cp "];
        for pattern in patterns {
            if let Some(idx) = command.find(pattern) {
                let after = &command[idx + pattern.len()..].trim_start();
                let target = after.split_whitespace().next()?;
                return Some(target.to_string());
            }
        }
        None
    }
}

impl LifecycleHook for AoeSandboxGate {
    fn name(&self) -> &str {
        "aoe_sandbox_gate"
    }

    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult {
        match ctx.tool_name.as_str() {
            "Read" => HookResult::Continue,
            "Edit" | "Write" => {
                let file_path = match ctx.tool_input.get("file_path").and_then(|v| v.as_str()) {
                    Some(p) => p,
                    None => return HookResult::Continue,
                };

                match self.check_path(file_path) {
                    Ok(_) => HookResult::Continue,
                    Err(e) => HookResult::Deny {
                        reason: format!("sandbox_breakout:path_violation:{:?}", e),
                    },
                }
            }
            "Bash" => {
                let command = match ctx.tool_input.get("command").and_then(|v| v.as_str()) {
                    Some(c) => c,
                    None => return HookResult::Continue,
                };

                if let Some(target) = self.extract_write_target_from_bash(command) {
                    match self.check_path(&target) {
                        Ok(_) => HookResult::Continue,
                        Err(e) => HookResult::Deny {
                            reason: format!("sandbox_breakout:bash_write:{:?}", e),
                        },
                    }
                } else {
                    HookResult::Continue
                }
            }
            _ => HookResult::Continue,
        }
    }
}
