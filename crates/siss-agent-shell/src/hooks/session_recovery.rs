/// Phase 40: SessionRecoveryHook — on_session_start hook that detects suspended snapshots
/// Always returns Continue (fail-open): never blocks session startup.

use crate::hooks::{HookResult, LifecycleHook, SessionContext};
use uuid::Uuid;

/// Trait for reading session snapshots (abstracted for testing)
pub trait SnapshotReader: Send + Sync {
    fn read_snapshot(&self, session_id: Uuid) -> Option<serde_json::Value>;
}

/// SessionRecoveryHook: detects suspended snapshots and allows recovery
pub struct SessionRecoveryHook<R: SnapshotReader> {
    reader: R,
}

impl<R: SnapshotReader> SessionRecoveryHook<R> {
    pub fn new(reader: R) -> Self {
        Self { reader }
    }
}

impl<R: SnapshotReader> LifecycleHook for SessionRecoveryHook<R> {
    fn name(&self) -> &str {
        "session_recovery"
    }

    fn on_session_start(&self, ctx: &SessionContext) -> HookResult {
        // Try to read snapshot
        let snapshot = self.reader.read_snapshot(ctx.session_id.0);

        // If snapshot exists and status is suspended, log recovery (not shown in this impl)
        // If snapshot not found or DB error, session starts fresh
        // Either way, we return Continue — never block session startup (fail-open)

        if let Some(snap) = snapshot {
            if let Some(obj) = snap.as_object() {
                if let Some(status) = obj.get("status").and_then(|s| s.as_str()) {
                    if status == "suspended" {
                        // Session recovery from suspended state
                        // (actual logging would happen here)
                        return HookResult::Continue;
                    }
                }
            }
        }

        // DB error, None, or status != "suspended" → session starts fresh
        HookResult::Continue
    }
}
