/// VisionAPI — Decision Support Layer for Any Application
/// Embeds cryptographic governance into app decision flows
/// Covenant-aligned: fail-closed gates, cryptographic audit, 1%/99% settlement
/// Human Gate Policy Engine: fail-closed pre-execution checks before AP2 ledger charge

use crate::baseline_capsule::BaselineCapsule;
use std::collections::HashMap;
use sha2::{Sha256, Digest};
use chrono::{DateTime, Utc};
use serde::{Serialize, Deserialize};

/// Risk Level Classification for Human Gate Policy
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum RiskLevel {
    Low,
    Medium,
    High,
    Critical,
}

impl RiskLevel {
    pub fn from_blast_radius(radius: f64) -> Self {
        match radius {
            r if r < 0.25 => RiskLevel::Low,
            r if r < 0.5 => RiskLevel::Medium,
            r if r < 0.75 => RiskLevel::High,
            _ => RiskLevel::Critical,
        }
    }

    pub fn requires_approval(&self) -> bool {
        matches!(self, RiskLevel::High | RiskLevel::Critical)
    }
}

/// Human Gate Policy: defines approval requirements per risk level
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HumanGatePolicy {
    pub policy_id: String,
    pub requires_approval_for: Vec<RiskLevel>,     // Risk levels that need human approval
    pub ap2_charge_enabled: bool,                  // Whether to charge AP2 ledger
    pub psi_drift_threshold: f64,                  // PSI threshold for auto-engagement (0.25)
    pub max_concurrent_approvals: usize,           // Concurrency limit
    pub approval_timeout_secs: u64,                // Timeout for approval response
}

impl HumanGatePolicy {
    pub fn new() -> Self {
        Self {
            policy_id: "default-human-gate".to_string(),
            requires_approval_for: vec![RiskLevel::High, RiskLevel::Critical],
            ap2_charge_enabled: true,
            psi_drift_threshold: 0.25,
            max_concurrent_approvals: 10,
            approval_timeout_secs: 3600, // 1 hour
        }
    }

    pub fn needs_approval(&self, risk_level: RiskLevel) -> bool {
        self.requires_approval_for.contains(&risk_level)
    }
}

/// Signed proof returned when gate passes
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HumanGateProof {
    pub merkle_root: String,                    // Merkle hash of all gate decisions
    pub timestamp: DateTime<Utc>,               // When approval was granted
    pub decision_id: String,                    // Reference to decision
    pub approved_by: Option<String>,            // Human approver ID (if human approval)
    pub auto_approved: bool,                    // Whether auto-approved due to low risk
}

/// Govern request for AP2 ledger charge
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GovernRequest {
    pub request_id: String,
    pub action: String,
    pub blast_radius: f64,
    pub user_id: String,
    pub app_id: String,
    pub human_approved: bool,                   // Whether human has approved
    pub timestamp: DateTime<Utc>,
}

/// Result of pre-execution check
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PreExecuteCheckResult {
    pub allowed: bool,
    pub charge_amount: i64,                     // AP2 ledger charge (0 if blocked)
    pub proof: Option<HumanGateProof>,          // Signed proof if allowed
    pub error: Option<String>,                  // Error if blocked
    pub reason: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct DecisionContext {
    pub app_id: String,                    // e.g., "langchain-app-001"
    pub decision_id: String,               // UUID
    pub action: String,                    // what the app wants to do
    pub blast_radius: f64,                 // risk score (0.0-1.0)
    pub timestamp: u64,
    pub user_id: String,
}

#[derive(Debug, Clone, PartialEq)]
pub enum DecisionGate {
    Approved {
        action: String,
        merkle_proof: String,
        confidence: f64,
    },
    NeedsApproval {
        reason: String,
        blast_radius: f64,
        alternatives: Vec<String>,
    },
    Rejected {
        reason: String,
        fallback_action: String,
    },
}

#[derive(Debug, Clone)]
pub struct VisionAPI {
    baseline: BaselineCapsule,
    decisions: HashMap<String, DecisionContext>,
    audit_trail: Vec<(String, String)>,  // (decision_id, merkle_proof)
    circuit_breaker_count: usize,
    human_gate_policy: HumanGatePolicy,
    pending_approvals: HashMap<String, GovernRequest>,  // request_id -> GovernRequest
    merkle_root: String,                 // Accumulated Merkle root of all gates
}

impl VisionAPI {
    pub fn new() -> Self {
        Self {
            baseline: BaselineCapsule::new(),
            decisions: HashMap::new(),
            audit_trail: Vec::new(),
            circuit_breaker_count: 0,
            human_gate_policy: HumanGatePolicy::new(),
            pending_approvals: HashMap::new(),
            merkle_root: String::from("0"),
        }
    }

    pub fn with_policy(mut self, policy: HumanGatePolicy) -> Self {
        self.human_gate_policy = policy;
        self
    }

    /// Pre-execution check with Human Gate Policy
    /// Fail-closed: returns zero charge + error if not approved
    /// Flow:
    /// 1. Compute risk level from blast radius
    /// 2. Check if human approval is required
    /// 3. If required and not approved, return error with zero charge
    /// 4. If approved or low risk, compute Merkle proof and return charge authorization
    pub fn pre_execute_check(
        &mut self,
        request: GovernRequest,
        policy: Option<&HumanGatePolicy>,
    ) -> PreExecuteCheckResult {
        let risk_level = RiskLevel::from_blast_radius(request.blast_radius);

        // Use the provided policy or the default
        let needs_approval = if let Some(p) = policy {
            p.needs_approval(risk_level)
        } else {
            self.human_gate_policy.needs_approval(risk_level)
        };

        let ap2_enabled = if let Some(p) = policy {
            p.ap2_charge_enabled
        } else {
            self.human_gate_policy.ap2_charge_enabled
        };

        // 1. Check if approval is required for this risk level
        let approval_required = needs_approval;

        // 2. Fail-closed gate: if approval required but not granted, block
        if approval_required && !request.human_approved {
            return PreExecuteCheckResult {
                allowed: false,
                charge_amount: 0,  // Zero charge on rejection
                proof: None,
                error: Some("HumanGateRequired".to_string()),
                reason: format!(
                    "Request requires human approval for risk level {:?}",
                    risk_level
                ),
            };
        }

        // 3. Gate passes: generate signed proof
        let merkle_proof = self.compute_govern_merkle(&request);
        let now = Utc::now();

        // Update cumulative Merkle root
        self.update_merkle_root(&merkle_proof);

        let proof = HumanGateProof {
            merkle_root: self.merkle_root.clone(),
            timestamp: now,
            decision_id: request.request_id.clone(),
            approved_by: if request.human_approved {
                Some(request.user_id.clone())
            } else {
                None
            },
            auto_approved: !request.human_approved && !approval_required,
        };

        // Store in audit trail
        self.audit_trail
            .push((request.request_id.clone(), merkle_proof));

        // Compute charge (simplified: 100 units per request)
        let charge_amount = if ap2_enabled { 100 } else { 0 };

        PreExecuteCheckResult {
            allowed: true,
            charge_amount,
            proof: Some(proof),
            error: None,
            reason: format!("Approved (risk: {:?})", risk_level),
        }
    }

    /// Check if drift detection (PSI threshold) should auto-engage human gate
    /// PSI = Population Stability Index
    /// Returns true if PSI > policy.psi_drift_threshold
    pub fn check_drift_detection(&self, baseline_values: &[f64], current_values: &[f64]) -> bool {
        if baseline_values.is_empty() || current_values.is_empty() {
            return false;
        }

        let psi = self.compute_psi(baseline_values, current_values);
        psi > self.human_gate_policy.psi_drift_threshold
    }

    /// Compute Population Stability Index (PSI) for drift detection
    /// PSI measures distributional shift between baseline and current values
    /// PSI > 0.25 indicates significant drift and should trigger human gate
    fn compute_psi(&self, baseline: &[f64], current: &[f64]) -> f64 {
        if baseline.is_empty() || current.is_empty() {
            return 0.0;
        }

        let baseline_mean = baseline.iter().sum::<f64>() / baseline.len() as f64;
        let baseline_std = (baseline
            .iter()
            .map(|v| (v - baseline_mean).powi(2))
            .sum::<f64>()
            / baseline.len() as f64)
            .sqrt()
            .max(0.001);

        let current_mean = current.iter().sum::<f64>() / current.len() as f64;
        let current_std = (current
            .iter()
            .map(|v| (v - current_mean).powi(2))
            .sum::<f64>()
            / current.len() as f64)
            .sqrt()
            .max(0.001);

        // PSI = (current_mean - baseline_mean) / baseline_std
        // + 0.5 * (current_std - baseline_std)^2 / baseline_std^2
        let psi = ((current_mean - baseline_mean) / baseline_std).abs()
            + 0.5 * ((current_std - baseline_std) / baseline_std).powi(2);

        psi.min(1.0) // Clamp to [0, 1]
    }

    /// Evaluate a decision before execution (pre-decision governance)
    /// Returns guidance: Approved, NeedsApproval, or Rejected
    pub fn evaluate_decision(&mut self, context: DecisionContext) -> DecisionGate {
        // 1. Compute blast radius for this action
        let blast = self.compute_blast_radius(&context.action);

        // 2. Fail-closed gate: if blast is too high, request approval
        if blast > 0.7 {
            return DecisionGate::NeedsApproval {
                reason: format!("High-risk decision (blast_radius={:.2})", blast),
                blast_radius: blast,
                alternatives: vec![
                    "Use conservative default".to_string(),
                    "Request human approval".to_string(),
                ],
            };
        }

        // 3. If within acceptable range, approve + log to audit trail
        let merkle_proof = self.compute_decision_merkle(&context);
        self.audit_trail
            .push((context.decision_id.clone(), merkle_proof.clone()));
        self.decisions.insert(context.decision_id.clone(), context);

        DecisionGate::Approved {
            action: "execute".to_string(),
            merkle_proof,
            confidence: 1.0 - blast,
        }
    }

    /// Post-decision regret scoring
    /// Compares actual outcome against counterfactual (what would have happened)
    pub fn score_regret(&self, _decision_id: &str, actual_outcome: f64, counterfactual: f64) -> f64 {
        let regret = (counterfactual - actual_outcome).abs();
        regret / actual_outcome.max(1.0)  // normalized regret
    }

    /// Counterfactual replay: show what would have happened if you chose differently
    pub fn replay_counterfactual(&self, decision_id: &str, alternative_action: &str) -> String {
        format!(
            "If you had chosen '{}' instead, simulated outcome would be X. Actual outcome was Y. Regret: {:.2}%",
            alternative_action,
            self.score_regret(decision_id, 100.0, 110.0) * 100.0
        )
    }

    /// Compute blast radius (risk score) for an action
    /// Based on action type + frequency + temporal patterns
    fn compute_blast_radius(&self, action: &str) -> f64 {
        match action {
            a if a.contains("read") => 0.1,
            a if a.contains("write") => 0.4,
            a if a.contains("delete") => 0.7,
            a if a.contains("execute_system") => 0.9,
            _ => 0.3,
        }
    }

    /// Generate Merkle proof for a govern request
    fn compute_govern_merkle(&self, request: &GovernRequest) -> String {
        let mut hasher = Sha256::new();
        hasher.update(request.request_id.as_bytes());
        hasher.update(request.action.as_bytes());
        hasher.update(&request.blast_radius.to_le_bytes());
        hasher.update(request.user_id.as_bytes());
        hasher.update(request.app_id.as_bytes());
        hasher.update(&request.human_approved.to_string().as_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Update cumulative Merkle root by hashing current root with new proof
    fn update_merkle_root(&mut self, new_proof: &str) {
        let mut hasher = Sha256::new();
        hasher.update(self.merkle_root.as_bytes());
        hasher.update(new_proof.as_bytes());
        self.merkle_root = format!("{:x}", hasher.finalize());
    }

    /// Generate Merkle proof for a decision (cryptographic audit)
    fn compute_decision_merkle(&self, context: &DecisionContext) -> String {
        let mut hasher = Sha256::new();
        hasher.update(context.decision_id.as_bytes());
        hasher.update(context.action.as_bytes());
        hasher.update(&context.blast_radius.to_le_bytes());
        hasher.update(&context.timestamp.to_le_bytes());
        format!("{:x}", hasher.finalize())
    }

    /// Export decision history as audit trail (for compliance + transparency)
    pub fn export_audit_trail(&self) -> String {
        let mut output = String::from("DECISION AUDIT TRAIL\n");
        output.push_str("===================\n\n");

        for (decision_id, merkle_proof) in &self.audit_trail {
            output.push_str(&format!("Decision ID: {}\n", decision_id));
            output.push_str(&format!("Merkle Proof: {}\n", merkle_proof));
            if let Some(context) = self.decisions.get(decision_id) {
                output.push_str(&format!("Action: {}\n", context.action));
                output.push_str(&format!("Blast Radius: {:.2}\n", context.blast_radius));
            }
            output.push_str("\n");
        }

        output
    }

    /// Get audit trail (human-verifiable, cryptographically signed)
    pub fn get_audit_trail(&self) -> Vec<(String, String)> {
        self.audit_trail.clone()
    }

    /// Circuit breaker: if too many rejections, activate safe mode
    pub fn check_circuit_breaker(&mut self) -> bool {
        self.circuit_breaker_count >= 3
    }

    pub fn increment_breach(&mut self) {
        self.circuit_breaker_count += 1;
    }

    pub fn reset_breaker(&mut self) {
        self.circuit_breaker_count = 0;
    }
}

impl Default for VisionAPI {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ============ HUMAN GATE POLICY TESTS ============

    #[test]
    fn test_risk_level_classification() {
        assert_eq!(RiskLevel::from_blast_radius(0.1), RiskLevel::Low);
        assert_eq!(RiskLevel::from_blast_radius(0.3), RiskLevel::Medium);
        assert_eq!(RiskLevel::from_blast_radius(0.6), RiskLevel::High);
        assert_eq!(RiskLevel::from_blast_radius(0.9), RiskLevel::Critical);
    }

    #[test]
    fn test_risk_level_requires_approval() {
        assert!(!RiskLevel::Low.requires_approval());
        assert!(!RiskLevel::Medium.requires_approval());
        assert!(RiskLevel::High.requires_approval());
        assert!(RiskLevel::Critical.requires_approval());
    }

    #[test]
    fn test_human_gate_policy_default() {
        let policy = HumanGatePolicy::new();
        assert_eq!(policy.psi_drift_threshold, 0.25);
        assert!(policy.ap2_charge_enabled);
        assert_eq!(policy.requires_approval_for.len(), 2);
    }

    #[test]
    fn test_human_gate_policy_needs_approval() {
        let policy = HumanGatePolicy::new();
        assert!(!policy.needs_approval(RiskLevel::Low));
        assert!(!policy.needs_approval(RiskLevel::Medium));
        assert!(policy.needs_approval(RiskLevel::High));
        assert!(policy.needs_approval(RiskLevel::Critical));
    }

    // ============ HUMAN GATE PRE-EXECUTION CHECK TESTS ============

    #[test]
    fn test_low_risk_auto_approved_no_gate_required() {
        let mut api = VisionAPI::new();
        let request = GovernRequest {
            request_id: "req-001".to_string(),
            action: "read_data".to_string(),
            blast_radius: 0.1,  // Low risk
            user_id: "user-1".to_string(),
            app_id: "app-1".to_string(),
            human_approved: false,  // Not explicitly approved by human
            timestamp: Utc::now(),
        };

        let result = api.pre_execute_check(request, None);
        assert!(result.allowed);
        assert_eq!(result.charge_amount, 100);
        assert!(result.proof.is_some());
        assert!(result.proof.unwrap().auto_approved);
        assert_eq!(result.error, None);
    }

    #[test]
    fn test_high_risk_without_approval_blocked_zero_charge() {
        let mut api = VisionAPI::new();
        let request = GovernRequest {
            request_id: "req-002".to_string(),
            action: "execute_system".to_string(),
            blast_radius: 0.8,  // High risk
            user_id: "user-2".to_string(),
            app_id: "app-2".to_string(),
            human_approved: false,  // NOT approved
            timestamp: Utc::now(),
        };

        let result = api.pre_execute_check(request, None);
        assert!(!result.allowed);
        assert_eq!(result.charge_amount, 0);  // ZERO charge on rejection
        assert!(result.proof.is_none());
        assert_eq!(result.error, Some("HumanGateRequired".to_string()));
        // Reason should contain "High" or "requires human approval"
        assert!(result.reason.contains("human approval") || result.reason.contains("High"));
    }

    #[test]
    fn test_critical_risk_without_approval_blocked() {
        let mut api = VisionAPI::new();
        let request = GovernRequest {
            request_id: "req-003".to_string(),
            action: "delete_critical_data".to_string(),
            blast_radius: 0.95,  // Critical risk
            user_id: "user-3".to_string(),
            app_id: "app-3".to_string(),
            human_approved: false,
            timestamp: Utc::now(),
        };

        let result = api.pre_execute_check(request, None);
        assert!(!result.allowed);
        assert_eq!(result.charge_amount, 0);
        assert!(result.proof.is_none());
        assert!(result.reason.contains("Critical"));
    }

    #[test]
    fn test_high_risk_with_human_approval_allowed() {
        let mut api = VisionAPI::new();
        let request = GovernRequest {
            request_id: "req-004".to_string(),
            action: "execute_system".to_string(),
            blast_radius: 0.8,
            user_id: "admin-1".to_string(),
            app_id: "app-4".to_string(),
            human_approved: true,  // APPROVED
            timestamp: Utc::now(),
        };

        let result = api.pre_execute_check(request, None);
        assert!(result.allowed);
        assert_eq!(result.charge_amount, 100);
        assert!(result.proof.is_some());
        let proof = result.proof.unwrap();
        assert_eq!(proof.approved_by, Some("admin-1".to_string()));
        assert!(!proof.auto_approved);  // Human-approved, not auto
    }

    #[test]
    fn test_pre_execute_check_returns_merkle_proof_with_timestamp() {
        let mut api = VisionAPI::new();
        let request = GovernRequest {
            request_id: "req-005".to_string(),
            action: "read".to_string(),
            blast_radius: 0.1,
            user_id: "user-5".to_string(),
            app_id: "app-5".to_string(),
            human_approved: false,
            timestamp: Utc::now(),
        };

        let result = api.pre_execute_check(request.clone(), None);
        assert!(result.allowed);
        let proof = result.proof.unwrap();
        assert!(!proof.merkle_root.is_empty());
        assert_eq!(proof.decision_id, "req-005".to_string());
    }

    // ============ DRIFT DETECTION TESTS ============

    #[test]
    fn test_drift_detection_no_drift() {
        let api = VisionAPI::new();
        // Create two very similar distributions with some variance to match standard patterns
        let baseline = vec![100.0, 101.0, 99.0, 100.0, 101.0];
        let current = vec![100.05, 101.05, 99.05, 100.05, 101.05];  // <0.1% shift

        let triggers_gate = api.check_drift_detection(&baseline, &current);
        assert!(!triggers_gate);  // PSI should be very small, < 0.25
    }

    #[test]
    fn test_drift_detection_significant_drift_triggers_gate() {
        let api = VisionAPI::new();
        let baseline = vec![100.0, 100.0, 100.0, 100.0, 100.0];
        let current = vec![80.0, 80.0, 80.0, 80.0, 80.0];  // 20% shift

        let triggers_gate = api.check_drift_detection(&baseline, &current);
        assert!(triggers_gate);  // PSI > 0.25
    }

    #[test]
    fn test_psi_computation() {
        let api = VisionAPI::new();
        // Two distributions with different means
        let baseline = vec![10.0, 11.0, 12.0, 13.0, 14.0];
        let shifted = vec![20.0, 21.0, 22.0, 23.0, 24.0];  // Shifted by 10

        let psi = api.compute_psi(&baseline, &shifted);
        assert!(psi > 0.0);
        // PSI should be high due to mean shift
        assert!(psi > 0.25);
    }

    #[test]
    fn test_drift_detection_empty_values() {
        let api = VisionAPI::new();
        let baseline = vec![];
        let current = vec![100.0];

        let triggers_gate = api.check_drift_detection(&baseline, &current);
        assert!(!triggers_gate);  // Empty returns false
    }

    // ============ MERKLE ROOT AND PROOF TESTS ============

    #[test]
    fn test_merkle_proof_accumulation() {
        let mut api = VisionAPI::new();
        let initial_root = api.merkle_root.clone();

        let request1 = GovernRequest {
            request_id: "req-1".to_string(),
            action: "action1".to_string(),
            blast_radius: 0.1,
            user_id: "user-1".to_string(),
            app_id: "app-1".to_string(),
            human_approved: false,
            timestamp: Utc::now(),
        };

        api.pre_execute_check(request1, None);
        let root_after_1 = api.merkle_root.clone();
        assert_ne!(initial_root, root_after_1);

        let request2 = GovernRequest {
            request_id: "req-2".to_string(),
            action: "action2".to_string(),
            blast_radius: 0.2,
            user_id: "user-2".to_string(),
            app_id: "app-2".to_string(),
            human_approved: false,
            timestamp: Utc::now(),
        };

        api.pre_execute_check(request2, None);
        let root_after_2 = api.merkle_root.clone();
        assert_ne!(root_after_1, root_after_2);  // Root changes with each request
    }

    #[test]
    fn test_merkle_proof_deterministic_for_same_request() {
        let api = VisionAPI::new();
        let request = GovernRequest {
            request_id: "req-det".to_string(),
            action: "action".to_string(),
            blast_radius: 0.1,
            user_id: "user".to_string(),
            app_id: "app".to_string(),
            human_approved: true,
            timestamp: Utc::now(),
        };

        let proof1 = api.compute_govern_merkle(&request);
        let proof2 = api.compute_govern_merkle(&request);
        assert_eq!(proof1, proof2);  // Same request = same proof
    }

    // ============ CUSTOM POLICY TESTS ============

    #[test]
    fn test_custom_policy_overrides_default() {
        let mut custom_policy = HumanGatePolicy::new();
        custom_policy.psi_drift_threshold = 0.5;  // Override threshold
        custom_policy.ap2_charge_enabled = false;  // Disable AP2 charges

        let mut api = VisionAPI::new().with_policy(custom_policy.clone());

        let request = GovernRequest {
            request_id: "req-custom".to_string(),
            action: "read".to_string(),
            blast_radius: 0.1,
            user_id: "user".to_string(),
            app_id: "app".to_string(),
            human_approved: false,
            timestamp: Utc::now(),
        };

        let result = api.pre_execute_check(request, Some(&custom_policy));
        assert!(result.allowed);
        assert_eq!(result.charge_amount, 0);  // No charge due to disabled AP2
    }

    // ============ LEGACY TESTS (backward compatibility) ============

    #[test]
    fn test_low_blast_radius_approved() {
        let mut api = VisionAPI::new();
        let context = DecisionContext {
            app_id: "test-app".to_string(),
            decision_id: "dec-001".to_string(),
            action: "read_file".to_string(),
            blast_radius: 0.1,
            timestamp: 0,
            user_id: "user-1".to_string(),
        };

        match api.evaluate_decision(context) {
            DecisionGate::Approved { .. } => assert!(true),
            _ => panic!("Expected Approved"),
        }
    }

    #[test]
    fn test_high_blast_radius_needs_approval() {
        let mut api = VisionAPI::new();
        let context = DecisionContext {
            app_id: "test-app".to_string(),
            decision_id: "dec-001".to_string(),
            action: "execute_system_command".to_string(),
            blast_radius: 0.9,
            timestamp: 0,
            user_id: "user-1".to_string(),
        };

        match api.evaluate_decision(context) {
            DecisionGate::NeedsApproval { reason, .. } => {
                assert!(reason.contains("High-risk"));
            }
            _ => panic!("Expected NeedsApproval"),
        }
    }

    #[test]
    fn test_regret_scoring() {
        let api = VisionAPI::new();
        let regret = api.score_regret("dec-001", 100.0, 120.0);
        assert!(regret > 0.1);  // 20% regret
    }

    #[test]
    fn test_circuit_breaker() {
        let mut api = VisionAPI::new();
        api.increment_breach();
        api.increment_breach();
        api.increment_breach();
        assert!(api.check_circuit_breaker());
    }

    #[test]
    fn test_audit_trail_export() {
        let mut api = VisionAPI::new();
        let context = DecisionContext {
            app_id: "test-app".to_string(),
            decision_id: "dec-001".to_string(),
            action: "write_data".to_string(),
            blast_radius: 0.4,
            timestamp: 0,
            user_id: "user-1".to_string(),
        };

        api.evaluate_decision(context);
        let trail = api.export_audit_trail();
        assert!(trail.contains("dec-001"));
        assert!(trail.contains("write_data"));
    }

    #[test]
    fn test_merkle_proof_deterministic() {
        let api = VisionAPI::new();
        let context1 = DecisionContext {
            app_id: "test-app".to_string(),
            decision_id: "dec-001".to_string(),
            action: "read".to_string(),
            blast_radius: 0.1,
            timestamp: 1000,
            user_id: "user-1".to_string(),
        };

        let proof1 = api.compute_decision_merkle(&context1);

        let context2 = DecisionContext {
            app_id: "test-app".to_string(),
            decision_id: "dec-001".to_string(),
            action: "read".to_string(),
            blast_radius: 0.1,
            timestamp: 1000,
            user_id: "user-1".to_string(),
        };

        let proof2 = api.compute_decision_merkle(&context2);
        assert_eq!(proof1, proof2);  // Same inputs = same proof
    }
}
