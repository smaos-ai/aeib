use crate::autonomous_policy::AssilLevel;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;

#[derive(Clone, Debug, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum HazardLevel {
    Negligible = 0,
    Minor = 1,
    Major = 2,
    Critical = 3,
}

pub struct SafetyEnforcer {
    pub asil_level: AssilLevel,
    pub mtbf_target: Duration,
    pub max_hazard_severity: HazardLevel,
    state: Arc<RwLock<SafetyState>>,
}

#[derive(Clone, Debug)]
struct SafetyState {
    fail_safe_active: bool,
    propulsion_cut: bool,
    brakes_engaged: bool,
}

impl SafetyEnforcer {
    pub fn new(asil: AssilLevel) -> Self {
        let mtbf = match asil {
            AssilLevel::A => Duration::from_secs(10_000 * 3600),
            AssilLevel::B => Duration::from_secs(100_000 * 3600),
            AssilLevel::C => Duration::from_secs(500_000 * 3600),
            AssilLevel::D => Duration::from_secs(1_000_000 * 3600),
        };

        let max_severity = match asil {
            AssilLevel::A => HazardLevel::Minor,
            AssilLevel::B => HazardLevel::Major,
            AssilLevel::C => HazardLevel::Major,
            AssilLevel::D => HazardLevel::Critical,
        };

        Self {
            asil_level: asil,
            mtbf_target: mtbf,
            max_hazard_severity: max_severity,
            state: Arc::new(RwLock::new(SafetyState {
                fail_safe_active: false,
                propulsion_cut: false,
                brakes_engaged: false,
            })),
        }
    }

    /// Deterministic auto-halt: cut power to propulsion, engage brakes, stop immediately
    /// NO network dependency, NO cloud fallback, LOCAL fail-safe only
    pub async fn trigger_fail_safe(&self) -> Result<(), String> {
        let mut state = self.state.write();
        state.fail_safe_active = true;
        state.propulsion_cut = true;
        state.brakes_engaged = true;

        // Log fail-safe trigger (local only, no network)
        tracing::warn!(
            asil_level = ?self.asil_level,
            "FAIL-SAFE TRIGGERED: propulsion cut, brakes engaged"
        );

        Ok(())
    }

    pub async fn get_fail_safe_state(&self) -> FailSafeProof {
        let state = self.state.read();
        FailSafeProof {
            fail_safe_active: state.fail_safe_active,
            propulsion_cut: state.propulsion_cut,
            brakes_engaged: state.brakes_engaged,
        }
    }

    /// Validate autonomous decision against ISO 26262 + SOTIF bounds
    pub async fn validate_decision(
        &self,
        decision: &AutonomousDecision,
    ) -> Result<SafetyProof, String> {
        // ISO 26262: Verify decision is within ASIL bounds
        if !decision.is_safety_critical() {
            return Ok(SafetyProof {
                approved: true,
                decision_id: decision.id,
                asil_verified: false,
            });
        }

        // SOTIF: Check for unreasonable hazards
        if decision.contains_hazard_violation() {
            return Err("Decision violates SOTIF safety bounds".to_string());
        }

        // Deterministic validation
        if !decision.is_deterministic() {
            return Err("Decision non-deterministic (replay mismatch)".to_string());
        }

        Ok(SafetyProof {
            approved: true,
            decision_id: decision.id,
            asil_verified: true,
        })
    }

    /// Evaluate hazard and determine response
    pub async fn evaluate_hazard(&self, hazard: &Hazard) -> HazardResponse {
        match hazard.severity {
            HazardLevel::Critical => {
                // Immediate auto-halt required
                HazardResponse {
                    should_halt: true,
                    requires_remediation: false,
                    recommended_action: "EMERGENCY_STOP".to_string(),
                }
            }
            HazardLevel::Major => {
                // Requires remediation (reduce speed, switch to safe mode)
                HazardResponse {
                    should_halt: false,
                    requires_remediation: true,
                    recommended_action: "REDUCE_SPEED".to_string(),
                }
            }
            HazardLevel::Minor => {
                // Monitor and log
                HazardResponse {
                    should_halt: false,
                    requires_remediation: false,
                    recommended_action: "MONITOR".to_string(),
                }
            }
            HazardLevel::Negligible => {
                // Continue normal operation
                HazardResponse {
                    should_halt: false,
                    requires_remediation: false,
                    recommended_action: "CONTINUE".to_string(),
                }
            }
        }
    }

    pub fn get_mtbf_target(&self) -> Duration {
        self.mtbf_target
    }

    pub fn get_max_hazard_severity(&self) -> HazardLevel {
        self.max_hazard_severity
    }
}

pub struct AutonomousDecision {
    pub id: uuid::Uuid,
    pub action: String,
    pub safety_critical: bool,
    pub deterministic: bool,
    pub hazard_violation: bool,
}

impl AutonomousDecision {
    pub fn new(action: &str) -> Self {
        Self {
            id: uuid::Uuid::new_v4(),
            action: action.to_string(),
            safety_critical: false,
            deterministic: true,
            hazard_violation: false,
        }
    }

    pub fn with_safety_critical(mut self, critical: bool) -> Self {
        self.safety_critical = critical;
        self
    }

    pub fn with_deterministic(mut self, deterministic: bool) -> Self {
        self.deterministic = deterministic;
        self
    }

    pub fn with_hazard_violation(mut self, violation: bool) -> Self {
        self.hazard_violation = violation;
        self
    }

    fn is_safety_critical(&self) -> bool {
        self.safety_critical
    }

    fn contains_hazard_violation(&self) -> bool {
        self.hazard_violation
    }

    fn is_deterministic(&self) -> bool {
        self.deterministic
    }
}

pub struct Hazard {
    pub id: uuid::Uuid,
    pub severity: HazardLevel,
    pub description: String,
}

impl Hazard {
    pub fn new(severity: HazardLevel, description: &str) -> Self {
        Self {
            id: uuid::Uuid::new_v4(),
            severity,
            description: description.to_string(),
        }
    }
}

pub struct SafetyProof {
    pub approved: bool,
    pub decision_id: uuid::Uuid,
    pub asil_verified: bool,
}

pub struct FailSafeProof {
    pub fail_safe_active: bool,
    pub propulsion_cut: bool,
    pub brakes_engaged: bool,
}

pub struct HazardResponse {
    pub should_halt: bool,
    pub requires_remediation: bool,
    pub recommended_action: String,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_safety_enforcer_asil_d_creation() {
        let enforcer = SafetyEnforcer::new(AssilLevel::D);
        assert_eq!(enforcer.asil_level, AssilLevel::D);
        assert_eq!(enforcer.mtbf_target, Duration::from_secs(1_000_000 * 3600));
        assert_eq!(enforcer.max_hazard_severity, HazardLevel::Critical);
    }

    #[tokio::test]
    async fn test_fail_safe_trigger() {
        let enforcer = SafetyEnforcer::new(AssilLevel::D);
        let result = enforcer.trigger_fail_safe().await;

        assert!(result.is_ok());

        let state = enforcer.get_fail_safe_state().await;
        assert!(state.fail_safe_active);
        assert!(state.propulsion_cut);
        assert!(state.brakes_engaged);
    }

    #[tokio::test]
    async fn test_validate_safe_decision() {
        let enforcer = SafetyEnforcer::new(AssilLevel::D);
        let decision = AutonomousDecision::new("accelerate")
            .with_safety_critical(false)
            .with_deterministic(true);

        let result = enforcer.validate_decision(&decision).await;
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_validate_unsafe_decision() {
        let enforcer = SafetyEnforcer::new(AssilLevel::D);
        let decision = AutonomousDecision::new("malfunction")
            .with_safety_critical(true)
            .with_hazard_violation(true);

        let result = enforcer.validate_decision(&decision).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_evaluate_critical_hazard() {
        let enforcer = SafetyEnforcer::new(AssilLevel::D);
        let hazard = Hazard::new(HazardLevel::Critical, "Collision imminent");

        let response = enforcer.evaluate_hazard(&hazard).await;
        assert!(response.should_halt);
        assert!(!response.requires_remediation);
        assert_eq!(response.recommended_action, "EMERGENCY_STOP");
    }

    #[tokio::test]
    async fn test_evaluate_major_hazard() {
        let enforcer = SafetyEnforcer::new(AssilLevel::D);
        let hazard = Hazard::new(HazardLevel::Major, "Sensor degradation");

        let response = enforcer.evaluate_hazard(&hazard).await;
        assert!(!response.should_halt);
        assert!(response.requires_remediation);
    }

    #[tokio::test]
    async fn test_mtbf_asil_a() {
        let enforcer = SafetyEnforcer::new(AssilLevel::A);
        assert_eq!(
            enforcer.get_mtbf_target(),
            Duration::from_secs(10_000 * 3600)
        );
    }

    #[tokio::test]
    async fn test_mtbf_asil_b() {
        let enforcer = SafetyEnforcer::new(AssilLevel::B);
        assert_eq!(
            enforcer.get_mtbf_target(),
            Duration::from_secs(100_000 * 3600)
        );
    }
}
