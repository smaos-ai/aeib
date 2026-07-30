//! Mandate Verifier: Three-Phase Evaluation (ReBAC + AP2 + Temporal)
//!
//! This module defines the `MandateVerifier` trait and its implementation,
//! which orchestrates evaluation across ReBAC, AP2, and TemporalGuard phases.

use crate::rebac::{ReBAC, SovereignIdentity, PolicyAction, PolicyResource, DenyReason};
use crate::ap2::AP2Evaluator;
use crate::temporal::TemporalGuard;
use std::time::{SystemTime, Duration};
use uuid::Uuid;
use serde::{Deserialize, Serialize};

/// MandateV2 represents the final authorization decision with cache TTL.
/// (V2 to distinguish from legacy Mandate in policy_engine::Mandate)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Mandate {
    pub decision: MandateDecision,
    pub reasons: Vec<String>,
    pub audit_id: Uuid,
    pub cache_ttl: Duration,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MandateDecision {
    Allow,
    Deny,
}

// Backward-compat alias
pub use MandateDecision as AllowDeny;

/// Request context for mandate verification.
#[derive(Debug, Clone)]
pub struct RequestContext {
    pub requester: SovereignIdentity,
    pub action: PolicyAction,
    pub resource: PolicyResource,
    pub timestamp: SystemTime,
}

/// Trait for verifying mandates through three-phase evaluation.
pub trait MandateVerifier: Send + Sync {
    fn verify_mandate(
        &self,
        requester: &SovereignIdentity,
        action: &PolicyAction,
        resource: &PolicyResource,
        context: &RequestContext,
    ) -> Result<Mandate, DenyReason>;
}

/// Default MandateVerifier implementation composing ReBAC, AP2, and TemporalGuard.
pub struct DefaultMandateVerifier {
    rebac: ReBAC,
    ap2: AP2Evaluator,
    temporal: TemporalGuard,
}

impl DefaultMandateVerifier {
    pub fn new(
        rebac: ReBAC,
        ap2: AP2Evaluator,
        temporal: TemporalGuard,
    ) -> Self {
        Self { rebac, ap2, temporal }
    }
}

impl MandateVerifier for DefaultMandateVerifier {
    fn verify_mandate(
        &self,
        requester: &SovereignIdentity,
        action: &PolicyAction,
        resource: &PolicyResource,
        _context: &RequestContext,
    ) -> Result<Mandate, DenyReason> {
        let audit_id = Uuid::new_v4();
        let mut reasons = Vec::new();

        // Phase 1: ReBAC - Verify relationship exists and is active
        let rebac_result = self.rebac.verify_relationship(*requester, resource.clone(), action.clone());
        let rebac_ok = match rebac_result {
            Ok(msg) => {
                reasons.push(format!("ReBAC: {}", msg));
                true
            }
            Err(e) => {
                reasons.push(format!("ReBAC denied: {:?}", e));
                false
            }
        };

        if !rebac_ok {
            return Ok(Mandate {
                decision: MandateDecision::Deny,
                reasons,
                audit_id,
                cache_ttl: Duration::from_secs(60),
            });
        }

        // Phase 2: AP2 - Evaluate attribute predicates
        // Convert rebac::PolicyAction to ap2::PolicyAction
        let ap2_action = convert_policy_action(action.clone());
        let ap2_result = self.ap2.evaluate(requester.0, ap2_action);
        let ap2_ok = match ap2_result {
            Ok(msg) => {
                reasons.push(format!("AP2: {}", msg));
                true
            }
            Err(e) => {
                reasons.push(format!("AP2 denied: {:?}", e));
                false
            }
        };

        if !ap2_ok {
            return Ok(Mandate {
                decision: MandateDecision::Deny,
                reasons,
                audit_id,
                cache_ttl: Duration::from_secs(60),
            });
        }

        // Phase 3: TemporalGuard - Check rate limit, time windows, and blackout dates
        let now = chrono::Utc::now();
        match self.temporal.evaluate(requester.0, now) {
            Ok(crate::temporal::Decision::Allow) => {
                reasons.push("TemporalGuard: Rate limit + time window + blackout checks passed".to_string());
            }
            Ok(crate::temporal::Decision::Deny) => {
                reasons.push("TemporalGuard: Denied by rate limit, time window, or blackout date".to_string());
                return Ok(Mandate {
                    decision: MandateDecision::Deny,
                    reasons,
                    audit_id,
                    cache_ttl: Duration::from_secs(60),
                });
            }
            Err(e) => {
                reasons.push(format!("TemporalGuard error: {}", e));
                return Ok(Mandate {
                    decision: MandateDecision::Deny,
                    reasons,
                    audit_id,
                    cache_ttl: Duration::from_secs(60),
                });
            }
        }

        // All three phases passed
        Ok(Mandate {
            decision: MandateDecision::Allow,
            reasons,
            audit_id,
            cache_ttl: Duration::from_secs(60),
        })
    }
}

// Conversion helpers for PolicyAction across different modules
fn convert_policy_action(action: crate::rebac::PolicyAction) -> crate::ap2::PolicyAction {
    use crate::rebac::PolicyAction as RebacAction;
    use crate::ap2::PolicyAction as Ap2Action;

    match action {
        RebacAction::Spawn => Ap2Action::Spawn,
        RebacAction::Pause => Ap2Action::Pause,
        RebacAction::Resume => Ap2Action::Resume,
        RebacAction::Abort => Ap2Action::Abort,
        RebacAction::Terminate => Ap2Action::Terminate,
        RebacAction::AssignTask => Ap2Action::AssignTask,
        RebacAction::CancelTask => Ap2Action::CancelTask,
        RebacAction::FinalizeTask => Ap2Action::FinalizeTask,
        RebacAction::InitiateConsent => Ap2Action::InitiateConsent,
        RebacAction::VoteConsent => Ap2Action::VoteConsent,
        RebacAction::RevokeGrant => Ap2Action::RevokeGrant,
        RebacAction::ReadMetrics => Ap2Action::ReadMetrics,
        RebacAction::StreamEvents => Ap2Action::StreamEvents,
        RebacAction::CreatePolicy => Ap2Action::CreatePolicy,
        RebacAction::UpdatePolicy => Ap2Action::UpdatePolicy,
        RebacAction::DeletePolicy => Ap2Action::DeletePolicy,
    }
}


#[cfg(test)]
mod tests {
    use super::*;

    // Placeholder tests to satisfy compilation
    // Real tests are in the test file
    #[test]
    fn placeholder_test() {
        // This module is tested via integration tests in tests/
    }
}
