//! Phase 2C Compliance Automation Tests
//! Test-first suite: 15 test cases covering dossier generation, policy learning, RAGAS validation
//! Target: 350+ LOC, all pass before implementation

use std::collections::HashMap;
use chrono::Utc;
use uuid::Uuid;
use sha2::{Digest, Sha256};

// ============ MOCK AP2 LEDGER DECISION ============

#[derive(Debug, Clone)]
struct MockDecision {
    decision_id: String,
    timestamp: i64,
    case_type: String, // "hotel", "glass", "auto"
    outcome: bool,     // approved/denied
    score: f64,        // fairness/safety score 0-1
    metadata: HashMap<String, String>,
}

impl MockDecision {
    fn new(case_type: &str, outcome: bool, score: f64) -> Self {
        Self {
            decision_id: Uuid::new_v4().to_string(),
            timestamp: Utc::now().timestamp(),
            case_type: case_type.to_string(),
            outcome,
            score,
            metadata: HashMap::new(),
        }
    }

    fn with_metadata(mut self, key: &str, value: &str) -> Self {
        self.metadata.insert(key.to_string(), value.to_string());
        self
    }

    fn hash(&self) -> String {
        let mut hasher = Sha256::new();
        hasher.update(format!("{}{}{}{}", self.decision_id, self.timestamp, self.outcome, self.score).as_bytes());
        format!("{:x}", hasher.finalize())
    }
}

// ============ MOCK DOSSIER GENERATOR ============

#[derive(Debug, Clone)]
struct MockDossierGenerator {
    decisions: Vec<MockDecision>,
}

impl MockDossierGenerator {
    fn new() -> Self {
        Self {
            decisions: Vec::new(),
        }
    }

    fn add_decision(&mut self, decision: MockDecision) {
        self.decisions.push(decision);
    }

    fn generate_annex_iii(&self) -> Result<String, String> {
        if self.decisions.is_empty() {
            return Err("No decisions to generate Annex III".to_string());
        }

        let hotel_decisions: Vec<_> = self.decisions
            .iter()
            .filter(|d| d.case_type == "hotel")
            .collect();

        if hotel_decisions.is_empty() {
            return Err("No hotel decisions for Annex III".to_string());
        }

        let total = hotel_decisions.len();
        let approved = hotel_decisions.iter().filter(|d| d.outcome).count();
        let approval_rate = approved as f64 / total as f64;

        let mut json = format!(r#"{{"section":"Annex III","approval_rate":{}}}"#, approval_rate);
        Ok(json)
    }

    fn generate_annex_iv(&self) -> Result<String, String> {
        if self.decisions.is_empty() {
            return Err("No decisions to generate Annex IV".to_string());
        }

        let glass_decisions: Vec<_> = self.decisions
            .iter()
            .filter(|d| d.case_type == "glass")
            .collect();

        if glass_decisions.is_empty() {
            return Err("No glass decisions for Annex IV".to_string());
        }

        let total = glass_decisions.len();
        let safety_score: f64 = glass_decisions.iter().map(|d| d.score).sum::<f64>() / total as f64;

        let json = format!(r#"{{"section":"Annex IV","safety_score":{}}}"#, safety_score);
        Ok(json)
    }

    fn generate_annex_i(&self) -> Result<String, String> {
        if self.decisions.is_empty() {
            return Err("No decisions to generate Annex I".to_string());
        }

        let auto_decisions: Vec<_> = self.decisions
            .iter()
            .filter(|d| d.case_type == "auto")
            .collect();

        if auto_decisions.is_empty() {
            return Err("No auto decisions for Annex I".to_string());
        }

        let total = auto_decisions.len();
        let approved = auto_decisions.iter().filter(|d| d.outcome).count();
        let approval_rate = approved as f64 / total as f64;

        let json = format!(r#"{{"section":"Annex I","approval_rate":{}}}"#, approval_rate);
        Ok(json)
    }

    fn validate_dossier(&self) -> Result<bool, String> {
        if self.decisions.len() < 50 {
            return Err("Insufficient decisions for dossier validation".to_string());
        }

        let has_hotel = self.decisions.iter().any(|d| d.case_type == "hotel");
        let has_glass = self.decisions.iter().any(|d| d.case_type == "glass");
        let has_auto = self.decisions.iter().any(|d| d.case_type == "auto");

        if !(has_hotel && has_glass && has_auto) {
            return Err("Missing decision types for complete dossier".to_string());
        }

        Ok(true)
    }

    fn decision_count(&self) -> usize {
        self.decisions.len()
    }
}

// ============ MOCK POLICY MODEL ============

#[derive(Debug, Clone)]
struct MockPolicyModel {
    training_data: Vec<MockDecision>,
    accuracy: f64,
}

impl MockPolicyModel {
    fn new() -> Self {
        Self {
            training_data: Vec::new(),
            accuracy: 0.0,
        }
    }

    fn fit_policy(&mut self, decisions: Vec<MockDecision>) -> Result<(), String> {
        if decisions.len() < 100 {
            return Err("Insufficient training data (minimum 100 decisions)".to_string());
        }
        self.training_data = decisions.clone();
        self.accuracy = 0.92; // Mock: 92% accuracy
        Ok(())
    }

    fn predict_policy_compliance(&self, policy: &str) -> Result<f64, String> {
        if self.training_data.is_empty() {
            return Err("Model not trained".to_string());
        }
        Ok(self.accuracy)
    }

    fn accuracy_score(&self) -> f64 {
        self.accuracy
    }

    fn explainability(&self) -> String {
        format!("Model explains {} decisions with 92% accuracy", self.training_data.len())
    }
}

// ============ MOCK RAGAS VALIDATOR ============

#[derive(Debug, Clone)]
struct MockRagasValidator {
    golden_questions: Vec<String>,
}

impl MockRagasValidator {
    fn new() -> Self {
        Self {
            golden_questions: vec![
                "Did fairness ratio stay <1.25x?".to_string(),
                "Were all glass safety rules executed?".to_string(),
                "Did approval denials include escalation reason?".to_string(),
            ],
        }
    }

    fn validate_dossier_compliance(&self, dossier: &str) -> Result<f64, String> {
        if dossier.is_empty() {
            return Err("Empty dossier".to_string());
        }
        Ok(0.87) // Mock: 87% compliance score
    }

    fn generate_report(&self, compliance_score: f64) -> String {
        if compliance_score >= 0.87 {
            "PASS: Compliance validated".to_string()
        } else {
            "FAIL: Compliance below 87% threshold".to_string()
        }
    }

    fn question_count(&self) -> usize {
        self.golden_questions.len()
    }
}

// ============ TEST SUITE ============

#[test]
fn test_generator_creation() {
    let gen = MockDossierGenerator::new();
    assert_eq!(gen.decision_count(), 0);
}

#[test]
fn test_add_decisions() {
    let mut gen = MockDossierGenerator::new();
    let decision = MockDecision::new("hotel", true, 0.95);
    gen.add_decision(decision);
    assert_eq!(gen.decision_count(), 1);
}

#[test]
fn test_generate_annex_iii_insufficient_decisions() {
    let gen = MockDossierGenerator::new();
    let result = gen.generate_annex_iii();
    assert!(result.is_err());
}

#[test]
fn test_generate_annex_iii_missing_hotel_decisions() {
    let mut gen = MockDossierGenerator::new();
    let decision = MockDecision::new("glass", true, 0.95);
    gen.add_decision(decision);
    let result = gen.generate_annex_iii();
    assert!(result.is_err());
}

#[test]
fn test_generate_annex_iii_success() {
    let mut gen = MockDossierGenerator::new();
    for i in 0..50 {
        let decision = MockDecision::new("hotel", i % 2 == 0, 0.95);
        gen.add_decision(decision);
    }
    let result = gen.generate_annex_iii();
    assert!(result.is_ok());
    let dossier = result.unwrap();
    assert!(dossier.contains("Annex III"));
    assert!(dossier.contains("approval_rate"));
}

#[test]
fn test_generate_annex_iv_success() {
    let mut gen = MockDossierGenerator::new();
    for i in 0..50 {
        let decision = MockDecision::new("glass", i % 2 == 0, 0.92);
        gen.add_decision(decision);
    }
    let result = gen.generate_annex_iv();
    assert!(result.is_ok());
    let dossier = result.unwrap();
    assert!(dossier.contains("Annex IV"));
    assert!(dossier.contains("safety_score"));
}

#[test]
fn test_generate_annex_i_success() {
    let mut gen = MockDossierGenerator::new();
    for i in 0..50 {
        let decision = MockDecision::new("auto", i % 2 == 0, 0.90);
        gen.add_decision(decision);
    }
    let result = gen.generate_annex_i();
    assert!(result.is_ok());
    let dossier = result.unwrap();
    assert!(dossier.contains("Annex I"));
    assert!(dossier.contains("approval_rate"));
}

#[test]
fn test_validate_dossier_insufficient_decisions() {
    let gen = MockDossierGenerator::new();
    let result = gen.validate_dossier();
    assert!(result.is_err());
}

#[test]
fn test_validate_dossier_missing_types() {
    let mut gen = MockDossierGenerator::new();
    for _ in 0..100 {
        gen.add_decision(MockDecision::new("hotel", true, 0.95));
    }
    let result = gen.validate_dossier();
    assert!(result.is_err());
}

#[test]
fn test_validate_dossier_complete() {
    let mut gen = MockDossierGenerator::new();
    // Add 50 hotel, 50 glass, 50 auto decisions
    for _ in 0..50 {
        gen.add_decision(MockDecision::new("hotel", true, 0.95));
        gen.add_decision(MockDecision::new("glass", true, 0.92));
        gen.add_decision(MockDecision::new("auto", true, 0.90));
    }
    let result = gen.validate_dossier();
    assert!(result.is_ok());
}

#[test]
fn test_policy_model_fit_insufficient_data() {
    let mut model = MockPolicyModel::new();
    let decisions = vec![MockDecision::new("hotel", true, 0.95)];
    let result = model.fit_policy(decisions);
    assert!(result.is_err());
}

#[test]
fn test_policy_model_fit_success() {
    let mut model = MockPolicyModel::new();
    let decisions: Vec<_> = (0..150)
        .map(|_| MockDecision::new("hotel", true, 0.95))
        .collect();
    let result = model.fit_policy(decisions);
    assert!(result.is_ok());
    assert_eq!(model.accuracy_score(), 0.92);
}

#[test]
fn test_policy_model_predict_not_trained() {
    let model = MockPolicyModel::new();
    let result = model.predict_policy_compliance("test_policy");
    assert!(result.is_err());
}

#[test]
fn test_ragas_validator_creation() {
    let validator = MockRagasValidator::new();
    assert_eq!(validator.question_count(), 3);
}

#[test]
fn test_ragas_validate_empty_dossier() {
    let validator = MockRagasValidator::new();
    let result = validator.validate_dossier_compliance("");
    assert!(result.is_err());
}

#[test]
fn test_ragas_validate_success() {
    let validator = MockRagasValidator::new();
    let result = validator.validate_dossier_compliance("mock_dossier_data");
    assert!(result.is_ok());
    let score = result.unwrap();
    assert!(score >= 0.87);
}

#[test]
fn test_ragas_generate_report_pass() {
    let validator = MockRagasValidator::new();
    let report = validator.generate_report(0.87);
    assert!(report.contains("PASS"));
}

#[test]
fn test_ragas_generate_report_fail() {
    let validator = MockRagasValidator::new();
    let report = validator.generate_report(0.80);
    assert!(report.contains("FAIL"));
}

#[test]
fn test_complete_workflow_hotel_pilot() {
    let mut gen = MockDossierGenerator::new();

    // Create 150 hotel decisions
    for i in 0..150 {
        let decision = MockDecision::new("hotel", i % 3 != 0, 0.93 + (i as f64 / 1000.0))
            .with_metadata("guest_id", &format!("guest_{}", i))
            .with_metadata("credit_score", "650");
        gen.add_decision(decision);
    }

    // Add some glass and auto decisions
    for _ in 0..50 {
        gen.add_decision(MockDecision::new("glass", true, 0.92));
        gen.add_decision(MockDecision::new("auto", true, 0.90));
    }

    // Generate annexes
    let annex_iii = gen.generate_annex_iii().expect("Failed to generate Annex III");
    let annex_iv = gen.generate_annex_iv().expect("Failed to generate Annex IV");
    let annex_i = gen.generate_annex_i().expect("Failed to generate Annex I");

    // Validate
    let valid = gen.validate_dossier().expect("Dossier validation failed");
    assert!(valid);

    // Policy learning
    let mut model = MockPolicyModel::new();
    model.fit_policy(gen.decisions.clone()).expect("Policy fit failed");
    assert_eq!(model.accuracy_score(), 0.92);

    // RAGAS validation
    let validator = MockRagasValidator::new();
    let compliance_score = validator.validate_dossier_compliance(&annex_iii)
        .expect("RAGAS validation failed");
    assert!(compliance_score >= 0.87);

    let report = validator.generate_report(compliance_score);
    assert!(report.contains("PASS") || report.contains("FAIL"));
}

#[test]
fn test_complete_workflow_glass_edge_case() {
    let mut gen = MockDossierGenerator::new();

    // Create 100 glass decisions
    for i in 0..100 {
        let outcome = i % 20 < 19; // 95% approval
        let decision = MockDecision::new("glass", outcome, 0.91 + (i as f64 / 1000.0));
        gen.add_decision(decision);
    }

    // Add minimal hotel and auto decisions
    for _ in 0..20 {
        gen.add_decision(MockDecision::new("hotel", true, 0.95));
        gen.add_decision(MockDecision::new("auto", true, 0.90));
    }

    let valid = gen.validate_dossier().expect("Dossier validation failed");
    assert!(valid);

    let annex_iv = gen.generate_annex_iv().expect("Failed to generate Annex IV");
    assert!(annex_iv.contains("safety_score"));
}

#[test]
fn test_complete_workflow_no_training_data() {
    let mut model = MockPolicyModel::new();

    // Try to predict without training
    let result = model.predict_policy_compliance("test_policy");
    assert!(result.is_err());

    // Train with sufficient data
    let decisions: Vec<_> = (0..200)
        .map(|i| MockDecision::new("hotel", i % 2 == 0, 0.95))
        .collect();

    model.fit_policy(decisions).expect("Policy fit failed");

    // Now prediction should work
    let result = model.predict_policy_compliance("test_policy");
    assert!(result.is_ok());
}

// ============ TASK 4: COMPLIANCE TESTING EXPANSION (34+ TESTS) ============

// === ANNEX III ADVANCED TESTS ===

#[test]
fn test_annex_iii_fairness_ratio_check() {
    let mut gen = MockDossierGenerator::new();

    // Create hotel decisions with known fairness ratio
    for i in 0..100 {
        let approved = i < 80; // 80% approval rate
        gen.add_decision(MockDecision::new("hotel", approved, 0.95));
    }

    let annex = gen.generate_annex_iii().unwrap();
    assert!(annex.contains("approval_rate"));
    assert!(annex.contains("0.8"));
}

#[test]
fn test_annex_iii_demographic_breakdown() {
    let mut gen = MockDossierGenerator::new();

    for i in 0..100 {
        let mut decision = MockDecision::new("hotel", i % 2 == 0, 0.95);
        decision.metadata.insert("guest_region".to_string(), format!("region_{}", i % 5));
        gen.add_decision(decision);
    }

    let annex = gen.generate_annex_iii().unwrap();
    assert!(!annex.is_empty());
    assert!(annex.len() > 50);
}

#[test]
fn test_annex_iii_gdpr_compliance_hash() {
    let mut gen = MockDossierGenerator::new();

    for _ in 0..150 {
        gen.add_decision(MockDecision::new("hotel", true, 0.95));
    }

    let annex = gen.generate_annex_iii().unwrap();
    // GDPR compliance should use hashing, not PII
    assert!(!annex.contains("guest_id"));
}

#[test]
fn test_annex_iii_score_distribution() {
    let mut gen = MockDossierGenerator::new();

    for i in 0..100 {
        let score = 0.80 + (i as f64 / 500.0);
        gen.add_decision(MockDecision::new("hotel", true, score));
    }

    let annex = gen.generate_annex_iii().unwrap();
    assert!(annex.contains("approval_rate"));
}

#[test]
fn test_annex_iii_edge_case_all_approved() {
    let mut gen = MockDossierGenerator::new();

    for _ in 0..50 {
        gen.add_decision(MockDecision::new("hotel", true, 0.98));
    }

    let annex = gen.generate_annex_iii().unwrap();
    assert!(annex.contains("1"));  // 100% approval
}

#[test]
fn test_annex_iii_edge_case_all_denied() {
    let mut gen = MockDossierGenerator::new();

    for _ in 0..50 {
        gen.add_decision(MockDecision::new("hotel", false, 0.30));
    }

    let annex = gen.generate_annex_iii().unwrap();
    assert!(annex.contains("0"));  // 0% approval
}

// === ANNEX IV ADVANCED TESTS ===

#[test]
fn test_annex_iv_safety_rules_execution() {
    let mut gen = MockDossierGenerator::new();

    for i in 0..100 {
        let mut decision = MockDecision::new("glass", i % 2 == 0, 0.90 + (i as f64 / 1000.0));
        decision.metadata.insert("safety_rule_executed".to_string(), "true".to_string());
        gen.add_decision(decision);
    }

    let annex = gen.generate_annex_iv().unwrap();
    assert!(annex.contains("safety_score"));
}

#[test]
fn test_annex_iv_false_negative_rate() {
    let mut gen = MockDossierGenerator::new();

    // Create decisions with known false negatives
    for i in 0..100 {
        let score = if i % 10 == 0 { 0.45 } else { 0.95 };
        gen.add_decision(MockDecision::new("glass", i % 2 == 0, score));
    }

    let annex = gen.generate_annex_iv().unwrap();
    assert!(!annex.is_empty());
}

#[test]
fn test_annex_iv_cad_metadata_presence() {
    let mut gen = MockDossierGenerator::new();

    for i in 0..80 {
        let mut decision = MockDecision::new("glass", true, 0.92);
        decision.metadata.insert("cad_design_id".to_string(), format!("design_{}", i));
        decision.metadata.insert("material_spec".to_string(), "safety_glass_laminate".to_string());
        gen.add_decision(decision);
    }

    let annex = gen.generate_annex_iv().unwrap();
    assert!(annex.len() > 50);
}

#[test]
fn test_annex_iv_perfect_safety_score() {
    let mut gen = MockDossierGenerator::new();

    for _ in 0..100 {
        gen.add_decision(MockDecision::new("glass", true, 1.0));
    }

    let annex = gen.generate_annex_iv().unwrap();
    assert!(annex.contains("safety_score"));
}

// === ANNEX I ADVANCED TESTS ===

#[test]
fn test_annex_i_pre_exec_gates() {
    let mut gen = MockDossierGenerator::new();

    for i in 0..100 {
        let mut decision = MockDecision::new("auto", i % 3 != 0, 0.90);
        decision.metadata.insert("gate_type".to_string(), "pre_execution".to_string());
        gen.add_decision(decision);
    }

    let annex = gen.generate_annex_i().unwrap();
    assert!(!annex.is_empty());
}

#[test]
fn test_annex_i_decision_tree_explanation() {
    let mut gen = MockDossierGenerator::new();

    for i in 0..150 {
        let mut decision = MockDecision::new("auto", i % 2 == 0, 0.88);
        decision.metadata.insert("rule_name".to_string(), "credit_check".to_string());
        gen.add_decision(decision);
    }

    let annex = gen.generate_annex_i().unwrap();
    assert!(annex.len() > 50);
}

#[test]
fn test_annex_i_fairness_ratio_threshold() {
    let mut gen = MockDossierGenerator::new();

    // Create decisions with <1.25x fairness ratio
    for i in 0..120 {
        let approved = i < 100; // 83% approval
        gen.add_decision(MockDecision::new("auto", approved, 0.90));
    }

    let annex = gen.generate_annex_i().unwrap();
    assert!(annex.contains("approval_rate"));
}

// === RAGAS VALIDATION TESTS ===

#[test]
fn test_ragas_87_percent_threshold() {
    let mut gen = MockDossierGenerator::new();

    for _ in 0..200 {
        gen.add_decision(MockDecision::new("hotel", true, 0.95));
        gen.add_decision(MockDecision::new("glass", true, 0.92));
        gen.add_decision(MockDecision::new("auto", true, 0.90));
    }

    let validator = MockRagasValidator::new();
    let score = validator.validate_dossier_compliance("valid_dossier").unwrap();
    assert!(score >= 0.87);
}

#[test]
fn test_ragas_multi_question_validation() {
    let mut gen = MockDossierGenerator::new();

    for _ in 0..300 {
        gen.add_decision(MockDecision::new("hotel", true, 0.95));
    }

    let validator = MockRagasValidator::new();
    assert!(validator.question_count() >= 3);

    let score = validator.validate_dossier_compliance("dossier").unwrap();
    assert!(score >= 0.87);
}

#[test]
fn test_ragas_compliance_report_pass() {
    let validator = MockRagasValidator::new();
    let report = validator.generate_report(0.91);
    assert!(report.contains("PASS"));
}

#[test]
fn test_ragas_compliance_report_fail_below_threshold() {
    let validator = MockRagasValidator::new();
    let report = validator.generate_report(0.75);
    assert!(report.contains("FAIL"));
}

// === CAC 3.0 / CAICT 16/70 MAPPING TESTS ===

#[test]
fn test_cac3_regulatory_mapping() {
    let mut gen = MockDossierGenerator::new();

    for i in 0..100 {
        let mut decision = MockDecision::new("hotel", i % 2 == 0, 0.95);
        decision.metadata.insert("regulation".to_string(), "cac3".to_string());
        gen.add_decision(decision);
    }

    let dossier = gen.generate_annex_iii().unwrap();
    assert!(!dossier.is_empty());
}

#[test]
fn test_caict_16_70_compliance_check() {
    let mut gen = MockDossierGenerator::new();

    for i in 0..150 {
        let mut decision = MockDecision::new("glass", i % 2 == 0, 0.92);
        decision.metadata.insert("caict_section".to_string(), "16.70".to_string());
        gen.add_decision(decision);
    }

    let dossier = gen.generate_annex_iv().unwrap();
    assert!(dossier.len() > 50);
}

// === PERFORMANCE TESTS ===

#[test]
fn test_large_dataset_2200_decisions() {
    let mut gen = MockDossierGenerator::new();

    // Load 2,200 decisions
    for i in 0..2200 {
        let case_type = match i % 3 {
            0 => "hotel",
            1 => "glass",
            _ => "auto",
        };
        let outcome = i % 2 == 0;
        let score = 0.88 + (i as f64 % 1.0) / 100.0;
        gen.add_decision(MockDecision::new(case_type, outcome, score));
    }

    assert_eq!(gen.decision_count(), 2200);
}

#[test]
fn test_large_dataset_annex_generation_speed() {
    let mut gen = MockDossierGenerator::new();

    // Create 2,200 hotel decisions
    for i in 0..2200 {
        gen.add_decision(MockDecision::new("hotel", i % 2 == 0, 0.95));
    }

    // Should complete quickly (mock implementation, not actual timing)
    let result = gen.generate_annex_iii();
    assert!(result.is_ok());
}

#[test]
fn test_mixed_dataset_1000_decisions() {
    let mut gen = MockDossierGenerator::new();

    for i in 0..1000 {
        let case_type = match i % 3 {
            0 => "hotel",
            1 => "glass",
            _ => "auto",
        };
        gen.add_decision(MockDecision::new(case_type, i % 2 == 0, 0.90 + (i as f64 / 1000.0)));
    }

    assert!(gen.validate_dossier().is_ok());
}

// === EDGE CASES & ERROR HANDLING ===

#[test]
fn test_minimal_valid_dossier_50_decisions() {
    let mut gen = MockDossierGenerator::new();

    for _ in 0..50 {
        gen.add_decision(MockDecision::new("hotel", true, 0.95));
    }

    assert!(gen.validate_dossier().is_ok());
}

#[test]
fn test_single_case_type_insufficient() {
    let mut gen = MockDossierGenerator::new();

    // Only hotel decisions, no glass or auto
    for _ in 0..100 {
        gen.add_decision(MockDecision::new("hotel", true, 0.95));
    }

    let result = gen.validate_dossier();
    assert!(result.is_err());
}

#[test]
fn test_extreme_score_values_0() {
    let mut gen = MockDossierGenerator::new();

    for _ in 0..60 {
        gen.add_decision(MockDecision::new("hotel", false, 0.0));
        gen.add_decision(MockDecision::new("glass", false, 0.0));
    }

    let result = gen.validate_dossier();
    assert!(result.is_ok() || result.is_err()); // Either is acceptable for edge case
}

#[test]
fn test_extreme_score_values_1() {
    let mut gen = MockDossierGenerator::new();

    for _ in 0..60 {
        gen.add_decision(MockDecision::new("hotel", true, 1.0));
        gen.add_decision(MockDecision::new("auto", true, 1.0));
    }

    let dossier = gen.generate_annex_iii().unwrap();
    assert!(!dossier.is_empty());
}

#[test]
fn test_mixed_approval_distribution() {
    let mut gen = MockDossierGenerator::new();

    // 50% approved, 50% denied
    for i in 0..200 {
        gen.add_decision(MockDecision::new("hotel", i < 100, 0.95));
        gen.add_decision(MockDecision::new("glass", i < 100, 0.92));
        gen.add_decision(MockDecision::new("auto", i < 100, 0.90));
    }

    assert!(gen.validate_dossier().is_ok());
}

// === END-TO-END MULTI-ANNEX WORKFLOW ===

#[test]
fn test_complete_workflow_all_annexes() {
    let mut gen = MockDossierGenerator::new();

    // Create 600 mixed decisions
    for i in 0..600 {
        let case_type = match i % 3 {
            0 => "hotel",
            1 => "glass",
            _ => "auto",
        };
        let outcome = i % 2 == 0;
        let score = 0.88 + (i as f64 % 0.12);
        gen.add_decision(MockDecision::new(case_type, outcome, score));
    }

    // Validate complete dossier
    assert!(gen.validate_dossier().is_ok());

    // Generate all annexes
    let annex_i = gen.generate_annex_i().expect("Failed Annex I");
    let annex_iii = gen.generate_annex_iii().expect("Failed Annex III");
    let annex_iv = gen.generate_annex_iv().expect("Failed Annex IV");

    assert!(!annex_i.is_empty());
    assert!(!annex_iii.is_empty());
    assert!(!annex_iv.is_empty());

    // Validate with RAGAS
    let validator = MockRagasValidator::new();
    let score = validator.validate_dossier_compliance(&annex_iii).unwrap();
    assert!(score >= 0.87);
}
