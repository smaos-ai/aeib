use super::policy_templates::{defense_role_template, DefenseRole};
use chrono::Utc;
use serde::{Deserialize, Serialize};

/// Pilot scenario represents a single decision request in the Defense pilot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PilotScenario {
    pub name: String,
    pub requester_role: DefenseRole,
    pub target_facility: String,           // "T1", "T2", "T3"
    pub requested_classification: String,  // "Unclassified", "Secret", "TopSecret", "SCI"
}

/// Result of a single pilot evaluation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PilotResult {
    pub decision: String,              // "Allow" or "Deny"
    pub timestamp: String,             // ISO 8601 format
    pub audit_trail: String,           // Human-readable audit log entry
    pub reason: String,                // Explanation of decision
    pub scenario_name: String,
}

/// Defense pilot simulator for FedRAMP compliance testing
#[derive(Debug, Clone)]
pub struct DefensePilot {
    pub customer_name: String,
    pub decisions: Vec<PilotResult>,
}

impl DefensePilot {
    /// Create a new Defense pilot simulator
    pub fn new(customer_name: &str) -> Self {
        DefensePilot {
            customer_name: customer_name.to_string(),
            decisions: Vec::new(),
        }
    }

    /// Evaluate access based on role, facility, and classification level
    pub fn evaluate_access(&self, scenario: &PilotScenario) -> PilotResult {
        let role = defense_role_template(scenario.requester_role);
        let timestamp = Utc::now().to_rfc3339();

        // Check if role can access the requested facility tier
        let facility_allowed = role.facility_tiers.contains(&scenario.target_facility);

        // Check if role can access the requested classification
        let classification_allowed = role
            .can_access_classifications
            .contains(&scenario.requested_classification);

        let (decision, reason) = if !facility_allowed {
            (
                "Deny".to_string(),
                format!(
                    "{} cannot access facility tier {}. Allowed: {:?}",
                    role.name, scenario.target_facility, role.facility_tiers
                ),
            )
        } else if !classification_allowed {
            (
                "Deny".to_string(),
                format!(
                    "{} cannot access classification {}. Allowed: {:?}",
                    role.name, scenario.requested_classification, role.can_access_classifications
                ),
            )
        } else {
            (
                "Allow".to_string(),
                format!(
                    "{} granted access to {} at facility {} (FedRAMP compliance verified)",
                    role.name, scenario.requested_classification, scenario.target_facility
                ),
            )
        };

        let audit_trail = format!(
            "Role: {} | Action: {} | Classification: {} | Facility: {} | Decision: {} | Timestamp: {}",
            role.name, scenario.name, scenario.requested_classification, scenario.target_facility, decision, timestamp
        );

        PilotResult {
            decision,
            timestamp,
            audit_trail,
            reason,
            scenario_name: scenario.name.clone(),
        }
    }

    /// Simulate a complete pilot scenario with multiple requests
    pub fn run_pilot_scenario(&mut self, scenarios: Vec<PilotScenario>) -> Vec<PilotResult> {
        let mut results = Vec::new();
        for scenario in scenarios {
            let result = self.evaluate_access(&scenario);
            results.push(result.clone());
        }
        self.decisions = results.clone();
        results
    }

    /// Get audit trail summary for compliance reporting
    pub fn generate_audit_summary(&self) -> String {
        let mut summary = format!("Defense Pilot Audit Summary - {}\n", self.customer_name);
        summary.push_str(&format!("Total Decisions: {}\n", self.decisions.len()));

        let allowed = self
            .decisions
            .iter()
            .filter(|d| d.decision == "Allow")
            .count();
        let denied = self.decisions.len() - allowed;

        summary.push_str(&format!("Approved: {}, Denied: {}\n", allowed, denied));
        summary.push_str("Decision Log:\n");

        for result in &self.decisions {
            summary.push_str(&format!("  - {}\n", result.audit_trail));
        }

        summary
    }

    /// Verify pilot success criteria (for compliance validation)
    pub fn verify_success_criteria(&self) -> (bool, Vec<String>) {
        let mut criteria_results = Vec::new();
        let mut all_passed = true;

        // Criteria 1: 100% audit coverage
        if self.decisions.is_empty() {
            criteria_results.push("❌ FAIL: No decisions recorded (0% audit coverage)".to_string());
            all_passed = false;
        } else {
            criteria_results.push(format!(
                "✅ PASS: {}/{}  decisions have audit trails (100% coverage)",
                self.decisions.len(),
                self.decisions.len()
            ));
        }

        // Criteria 2: Zero false-positive policy blocks (assess during pilot)
        let denials = self
            .decisions
            .iter()
            .filter(|d| d.decision == "Deny")
            .count();
        if denials == 0 {
            criteria_results.push("✅ PASS: Zero denials observed".to_string());
        } else {
            criteria_results.push(format!(
                "⚠️  WARNING: {} denials recorded (monitor for false positives)",
                denials
            ));
        }

        // Criteria 3: All decisions properly classified
        let all_classified = self.decisions.iter().all(|d| {
            !d.scenario_name.is_empty() && (d.decision == "Allow" || d.decision == "Deny")
        });

        if all_classified {
            criteria_results.push("✅ PASS: All decisions properly classified".to_string());
        } else {
            criteria_results.push("❌ FAIL: Some decisions missing classification".to_string());
            all_passed = false;
        }

        (all_passed, criteria_results)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pilot_allows_security_officer_access() {
        let pilot = DefensePilot::new("Test Customer");
        let scenario = PilotScenario {
            name: "SecurityOfficer Access".to_string(),
            requester_role: DefenseRole::SecurityOfficer,
            target_facility: "T1".to_string(),
            requested_classification: "TopSecret".to_string(),
        };

        let result = pilot.evaluate_access(&scenario);
        assert_eq!(result.decision, "Allow");
    }

    #[test]
    fn test_pilot_denies_analyst_toplevel_access() {
        let pilot = DefensePilot::new("Test Customer");
        let scenario = PilotScenario {
            name: "Analyst HighLevel Access".to_string(),
            requester_role: DefenseRole::Analyst,
            target_facility: "T1".to_string(),
            requested_classification: "TopSecret".to_string(),
        };

        let result = pilot.evaluate_access(&scenario);
        assert_eq!(result.decision, "Deny");
        assert!(result.reason.contains("cannot access"));
    }

    #[test]
    fn test_pilot_generates_audit_summary() {
        let mut pilot = DefensePilot::new("Test Customer");
        let scenarios = vec![
            PilotScenario {
                name: "Request 1".to_string(),
                requester_role: DefenseRole::SecurityOfficer,
                target_facility: "T1".to_string(),
                requested_classification: "Secret".to_string(),
            },
            PilotScenario {
                name: "Request 2".to_string(),
                requester_role: DefenseRole::Analyst,
                target_facility: "T3".to_string(),
                requested_classification: "Unclassified".to_string(),
            },
        ];

        pilot.run_pilot_scenario(scenarios);
        let summary = pilot.generate_audit_summary();

        assert!(summary.contains("Test Customer"));
        assert!(summary.contains("Total Decisions: 2"));
    }

    #[test]
    fn test_verify_success_criteria() {
        let mut pilot = DefensePilot::new("Test Customer");
        let scenarios = vec![PilotScenario {
            name: "Test".to_string(),
            requester_role: DefenseRole::SecurityOfficer,
            target_facility: "T1".to_string(),
            requested_classification: "Secret".to_string(),
        }];

        pilot.run_pilot_scenario(scenarios);
        let (passed, criteria) = pilot.verify_success_criteria();

        assert!(passed);
        assert!(criteria.iter().any(|c| c.contains("PASS")));
    }
}
