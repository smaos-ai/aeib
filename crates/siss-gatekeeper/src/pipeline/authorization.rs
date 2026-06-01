//! Wave 3A: Unified governance authorization pipeline.
//!
//! Composes the four AXIOM Protocol governance gates into a single
//! fail-closed membrane evaluated in deterministic order:
//!
//!   1. Covenant signature validation (Capsule 1%/99% split, Ed25519)
//!   2. AP2 intent mandate (predicate evaluation over SovereignAttributes)
//!   3. Policy composition decision (AND/OR/NOT boolean tree)
//!   4. Temporal constraint validation (rate limit + UTC window)
//!
//! The first gate to fail halts the pipeline; downstream gates are not
//! evaluated. On full success the caller receives an [`AuthorizationProof`]
//! whose Merkle root is the SHA-256 of the canonical proof body.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::SystemTime;

use sha2::{Digest, Sha256};
use uuid::Uuid;

use siss_behavioral_firewall::ap2::{AttributePredicate, SovereignAttributes};
use siss_behavioral_firewall::covenant_firewall::{CovenantFirewall, EconomicIntent};
use siss_behavioral_firewall::policy_engine::PolicyComposition;
use siss_behavioral_firewall::rebac::DenyReason;
use siss_behavioral_firewall::temporal::{PolicyAction, TemporalGuard};

use crate::types::GatekeeperError;

/// Inputs required to authorize a single task end-to-end.
///
/// Optional fields (`ap2_predicate`, `policy_composition`) let callers skip a
/// gate when the corresponding policy layer has nothing to evaluate. Skipping
/// a gate is equivalent to "no restriction applies" and does not record an
/// audit entry for that gate.
///
/// `Debug` is intentionally not derived because [`PolicyComposition`] is not
/// `Debug`. Callers that need to log requests should serialize the individual
/// fields they care about.
pub struct TaskAuthorizationRequest {
    pub task_id: Uuid,
    pub actor: Uuid,
    pub action: PolicyAction,
    pub capsule_merkle_root: [u8; 32],
    pub capsule_intent: EconomicIntent,
    pub capsule_signature: Vec<u8>,
    pub capsule_verifying_key: Vec<u8>,
    pub ap2_predicate: Option<AttributePredicate>,
    pub ap2_attributes: SovereignAttributes,
    pub policy_composition: Option<PolicyComposition>,
}

/// Merkle-rooted proof of a successful authorization.
///
/// `gate_decisions` maps each evaluated gate name → `"PASSED"`. Gates that
/// were skipped (no predicate / no composition supplied) do not appear in
/// the map. `merkle_root` is a hex-encoded SHA-256 of the canonical proof
/// body (`task_id || actor || sorted(gate_decisions) || timestamp_nanos`).
#[derive(Debug, Clone)]
pub struct AuthorizationProof {
    pub task_id: Uuid,
    pub actor: Uuid,
    pub approval_timestamp: SystemTime,
    pub gate_decisions: HashMap<String, String>,
    pub merkle_root: String,
}

/// Unified authorization pipeline. Cheap to clone (`Arc`-backed guard) and
/// safe to share across threads.
pub struct AuthorizationPipeline {
    temporal_guard: Arc<TemporalGuard>,
}

impl AuthorizationPipeline {
    pub fn new(temporal_guard: TemporalGuard) -> Self {
        Self {
            temporal_guard: Arc::new(temporal_guard),
        }
    }

    /// Canonical gate ordering. Tests rely on this exact sequence to assert
    /// deterministic fail-closed behaviour.
    pub fn gate_execution_order() -> Vec<&'static str> {
        vec!["covenant", "ap2", "policy", "temporal"]
    }

    /// Run every gate in order. The first failure halts the pipeline.
    pub fn authorize(
        &self,
        req: &TaskAuthorizationRequest,
    ) -> Result<AuthorizationProof, GatekeeperError> {
        let mut decisions: HashMap<String, String> = HashMap::new();

        // Gate 1: Covenant
        Self::check_covenant(
            &req.capsule_merkle_root,
            &req.capsule_intent,
            &req.capsule_signature,
            &req.capsule_verifying_key,
        )?;
        decisions.insert("covenant".into(), "PASSED".into());

        // Gate 2: AP2 intent mandate
        if let Some(predicate) = &req.ap2_predicate {
            Self::check_ap2_intent(predicate, &req.ap2_attributes).map_err(|e| {
                if let GatekeeperError::IntentMismatch { reason, .. } = e {
                    GatekeeperError::IntentMismatch {
                        task_id: req.task_id.to_string(),
                        reason,
                    }
                } else {
                    e
                }
            })?;
            decisions.insert("ap2".into(), "PASSED".into());
        }

        // Gate 3: Policy composition
        if let Some(composition) = &req.policy_composition {
            Self::check_policy(composition, &HashMap::new())?;
            decisions.insert("policy".into(), "PASSED".into());
        }

        // Gate 4: Temporal
        self.check_temporal(req.actor, req.action)?;
        decisions.insert("temporal".into(), "PASSED".into());

        let approval_timestamp = SystemTime::now();
        let merkle_root = compute_merkle_root(
            req.task_id,
            req.actor,
            &decisions,
            approval_timestamp,
        );

        Ok(AuthorizationProof {
            task_id: req.task_id,
            actor: req.actor,
            approval_timestamp,
            gate_decisions: decisions,
            merkle_root,
        })
    }

    /// Standalone covenant check. Adapts [`CovenantFirewall::verify`] errors
    /// into a [`GatekeeperError::CovenantViolation`].
    pub fn check_covenant(
        merkle_root: &[u8; 32],
        intent: &EconomicIntent,
        signature: &[u8],
        verifying_key: &[u8],
    ) -> Result<(), GatekeeperError> {
        CovenantFirewall::verify(merkle_root, intent, signature, verifying_key).map_err(|e| {
            GatekeeperError::CovenantViolation {
                merkle_root: hex::encode(merkle_root),
                violation: e.to_string(),
            }
        })
    }

    /// Standalone AP2 intent check. Predicates are pure boolean expressions
    /// over [`SovereignAttributes`]; a `false` result becomes an
    /// [`GatekeeperError::IntentMismatch`].
    pub fn check_ap2_intent(
        predicate: &AttributePredicate,
        attributes: &SovereignAttributes,
    ) -> Result<(), GatekeeperError> {
        if evaluate_predicate(predicate, attributes) {
            Ok(())
        } else {
            Err(GatekeeperError::IntentMismatch {
                task_id: "unknown".into(),
                reason: "AP2 predicate evaluation returned false".into(),
            })
        }
    }

    /// Standalone policy composition check. A composition is satisfied when
    /// `evaluate` returns `Ok(true)`; anything else maps to
    /// [`GatekeeperError::PolicyViolation`].
    pub fn check_policy(
        composition: &PolicyComposition,
        attrs: &HashMap<String, String>,
    ) -> Result<(), GatekeeperError> {
        match composition.evaluate(attrs) {
            Ok(true) => Ok(()),
            Ok(false) => Err(GatekeeperError::PolicyViolation {
                policy_id: "composition".into(),
                reason: "policy composition evaluated to false".into(),
            }),
            Err(reason) => Err(GatekeeperError::PolicyViolation {
                policy_id: "composition".into(),
                reason,
            }),
        }
    }

    fn check_temporal(&self, actor: Uuid, action: PolicyAction) -> Result<(), GatekeeperError> {
        self.temporal_guard
            .check_rate_limit(actor)
            .map_err(deny_to_temporal)?;
        self.temporal_guard
            .check_time_window(action)
            .map_err(deny_to_temporal)?;
        Ok(())
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn deny_to_temporal(reason: DenyReason) -> GatekeeperError {
    match reason {
        DenyReason::TemporalViolation(msg) => GatekeeperError::TemporalViolation(msg),
        DenyReason::ReBAC(msg) | DenyReason::AP2(msg) => GatekeeperError::TemporalViolation(msg),
    }
}

/// Pure predicate evaluator. Mirrors `AP2Evaluator::evaluate_predicate` but
/// avoids constructing a full evaluator just to call a total function.
fn evaluate_predicate(predicate: &AttributePredicate, attrs: &SovereignAttributes) -> bool {
    match predicate {
        AttributePredicate::TrustLevel(min) => attrs.trust_level >= *min,
        AttributePredicate::ReputationScore(min) => attrs.reputation >= *min,
        AttributePredicate::SenioritySince(cutoff) => attrs.joined_at <= *cutoff,
        AttributePredicate::NotBlacklisted => !attrs.blacklisted,
        AttributePredicate::HasCertification(cert) => attrs.certifications.contains(cert),
        AttributePredicate::And(left, right) => {
            evaluate_predicate(left, attrs) && evaluate_predicate(right, attrs)
        }
        AttributePredicate::Or(left, right) => {
            evaluate_predicate(left, attrs) || evaluate_predicate(right, attrs)
        }
        AttributePredicate::Not(inner) => !evaluate_predicate(inner, attrs),
    }
}

fn compute_merkle_root(
    task_id: Uuid,
    actor: Uuid,
    decisions: &HashMap<String, String>,
    timestamp: SystemTime,
) -> String {
    let mut hasher = Sha256::new();
    hasher.update(task_id.as_bytes());
    hasher.update(actor.as_bytes());

    let mut sorted: Vec<_> = decisions.iter().collect();
    sorted.sort_by(|a, b| a.0.cmp(b.0));
    for (gate, decision) in sorted {
        hasher.update(gate.as_bytes());
        hasher.update(b":");
        hasher.update(decision.as_bytes());
        hasher.update(b"|");
    }

    let nanos = timestamp
        .duration_since(SystemTime::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    hasher.update(nanos.to_le_bytes());

    format!("sha256:{}", hex::encode(hasher.finalize()))
}
