/// Phase 54: Visual Action Membrane — Click-Zone Validation Gate
/// Validates spatial coordinates against restricted zones before execution.
use crate::hooks::{HookResult, LifecycleHook, ToolUseContext};

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub enum ZonePolicy {
    Allow,
    Warn,
    Defer,
    Deny,
}

#[derive(Debug, Clone)]
pub struct BoundingBox {
    pub x_min: f64,
    pub y_min: f64,
    pub x_max: f64,
    pub y_max: f64,
}

impl BoundingBox {
    /// Returns true if (x, y) falls within the box (inclusive)
    pub fn contains(&self, x: f64, y: f64) -> bool {
        x >= self.x_min && x <= self.x_max && y >= self.y_min && y <= self.y_max
    }
}

#[derive(Debug, Clone)]
pub struct RestrictedZone {
    pub name: String,
    pub bounds: BoundingBox,
    pub policy: ZonePolicy,
}

#[derive(Debug, Clone)]
pub struct ZoneReport {
    pub matched_zone: Option<RestrictedZone>,
    pub policy: ZonePolicy,
}

pub trait ZoneAnalyzer: Send + Sync {
    fn check_point(&self, x: f64, y: f64) -> ZoneReport;
}

pub struct VisualActionMembrane<A: ZoneAnalyzer> {
    pub analyzer: A,
}

impl<A: ZoneAnalyzer> LifecycleHook for VisualActionMembrane<A> {
    fn name(&self) -> &str {
        "visual_action_membrane"
    }

    fn on_pre_tool_use(&self, ctx: &ToolUseContext) -> HookResult {
        // RULE 1: tool_name not in {"GuiClick","GuiType","GuiScroll"} → Continue
        match ctx.tool_name.as_str() {
            "GuiClick" | "GuiType" | "GuiScroll" => {}
            _ => return HookResult::Continue,
        }

        // RULE 2: x or y missing from tool_input → Deny
        let x = match ctx.tool_input.get("x").and_then(|v| v.as_f64()) {
            Some(val) => val,
            None => {
                return HookResult::Deny {
                    reason: "missing_coords".to_string(),
                };
            }
        };

        let y = match ctx.tool_input.get("y").and_then(|v| v.as_f64()) {
            Some(val) => val,
            None => {
                return HookResult::Deny {
                    reason: "missing_coords".to_string(),
                };
            }
        };

        // RULE 3: analyzer.check_point(x, y)
        let report = self.analyzer.check_point(x, y);

        // RULE 4: ZonePolicy::Deny → HookResult::Deny
        if report.policy == ZonePolicy::Deny {
            let reason = if let Some(zone) = &report.matched_zone {
                format!("restricted_zone:{}", zone.name)
            } else {
                "restricted_zone:unknown".to_string()
            };
            return HookResult::Deny { reason };
        }

        // RULE 5: ZonePolicy::Defer → HookResult::Defer
        if report.policy == ZonePolicy::Defer {
            let reason = if let Some(zone) = &report.matched_zone {
                format!("approval_zone:{}", zone.name)
            } else {
                "approval_zone:unknown".to_string()
            };
            return HookResult::Defer {
                reason,
                severity: "HIGH".to_string(),
            };
        }

        // RULE 6: ZonePolicy::Allow | Warn → HookResult::Continue
        HookResult::Continue
    }
}

pub struct MockZoneAnalyzer {
    pub zones: Vec<RestrictedZone>,
}

impl ZoneAnalyzer for MockZoneAnalyzer {
    fn check_point(&self, x: f64, y: f64) -> ZoneReport {
        for zone in &self.zones {
            if zone.bounds.contains(x, y) {
                return ZoneReport {
                    matched_zone: Some(zone.clone()),
                    policy: zone.policy.clone(),
                };
            }
        }

        ZoneReport {
            matched_zone: None,
            policy: ZonePolicy::Allow,
        }
    }
}
