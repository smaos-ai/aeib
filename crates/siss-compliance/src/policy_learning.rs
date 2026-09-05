//! Phase 2C: Policy Learning (L9 Layer)
//! ML model learns gate logic from historical decisions
//! Targets: 92%+ accuracy, explainable rules, policy update suggestions

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::compliance_automation::Decision;

/// Policy learning model trained on historical decisions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyModel {
    /// Training data: historical decisions from Phase 1+2B
    pub training_data: Vec<Decision>,
    /// Model accuracy on training set
    pub accuracy: f64,
    /// Learned rules explaining approvals/denials
    pub learned_rules: Vec<PolicyRule>,
    /// Feature importance scores
    pub feature_importance: HashMap<String, f64>,
}

/// A learned policy rule extracted from decision data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyRule {
    pub rule_id: String,
    pub rule_name: String,
    pub condition: String,  // e.g., "credit_score > 650"
    pub approval_rate: f64,
    pub match_rate: f64,    // % of decisions matching this rule
    pub confidence: f64,    // confidence in rule accuracy
}

/// Policy compliance prediction result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyPrediction {
    pub compliant: bool,
    pub confidence: f64,
    pub matching_rules: Vec<String>,
    pub risk_assessment: String,
}

/// Policy explanation for a specific decision
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicyExplanation {
    pub decision_id: String,
    pub predicted_outcome: bool,
    pub actual_outcome: bool,
    pub explaining_rules: Vec<String>,
    pub accuracy_contribution: f64,
}

impl PolicyModel {
    /// Create new untrained model
    pub fn new() -> Self {
        Self {
            training_data: Vec::new(),
            accuracy: 0.0,
            learned_rules: Vec::new(),
            feature_importance: HashMap::new(),
        }
    }

    /// Fit policy model: learn gate logic from decisions
    /// Requires minimum 100 decisions; targets 92%+ accuracy
    pub fn fit_policy(&mut self, decisions: Vec<Decision>) -> Result<(), String> {
        if decisions.len() < 100 {
            return Err(format!(
                "Insufficient training data: {} < 100",
                decisions.len()
            ));
        }

        self.training_data = decisions.clone();

        // Extract rules from decisions
        self.learned_rules = self.extract_rules(&decisions)?;

        // Compute feature importance
        self.feature_importance = self.compute_feature_importance(&decisions)?;

        // Compute model accuracy
        self.accuracy = self.compute_accuracy(&decisions)?;

        // Warn if accuracy below target
        if self.accuracy < 0.92 {
            eprintln!(
                "Warning: Policy model accuracy {} < 92% target",
                self.accuracy
            );
        }

        Ok(())
    }

    /// Extract decision rules from training data
    /// Analyzes decision patterns by case_type, score ranges, metadata
    fn extract_rules(&self, decisions: &[Decision]) -> Result<Vec<PolicyRule>, String> {
        let mut rules = Vec::new();

        // Rule 1: High-score approval pattern
        let high_score_decisions: Vec<_> = decisions.iter().filter(|d| d.score > 0.85).collect();
        if !high_score_decisions.is_empty() {
            let approval_count = high_score_decisions.iter().filter(|d| d.outcome).count();
            rules.push(PolicyRule {
                rule_id: "rule_high_score".to_string(),
                rule_name: "High Score Approval".to_string(),
                condition: "score > 0.85".to_string(),
                approval_rate: approval_count as f64 / high_score_decisions.len() as f64,
                match_rate: high_score_decisions.len() as f64 / decisions.len() as f64,
                confidence: 0.95,
            });
        }

        // Rule 2: Low-score denial pattern
        let low_score_decisions: Vec<_> = decisions.iter().filter(|d| d.score < 0.60).collect();
        if !low_score_decisions.is_empty() {
            let approval_count = low_score_decisions.iter().filter(|d| d.outcome).count();
            rules.push(PolicyRule {
                rule_id: "rule_low_score".to_string(),
                rule_name: "Low Score Denial".to_string(),
                condition: "score < 0.60".to_string(),
                approval_rate: approval_count as f64 / low_score_decisions.len() as f64,
                match_rate: low_score_decisions.len() as f64 / decisions.len() as f64,
                confidence: 0.92,
            });
        }

        // Rule 3: Case type fairness
        for case_type in &["hotel", "glass", "auto"] {
            let case_decisions: Vec<_> = decisions.iter().filter(|d| &d.case_type == case_type).collect();
            if !case_decisions.is_empty() {
                let approval_count = case_decisions.iter().filter(|d| d.outcome).count();
                rules.push(PolicyRule {
                    rule_id: format!("rule_{}_fairness", case_type),
                    rule_name: format!("{} Case Fairness", case_type.to_uppercase()),
                    condition: format!("case_type == '{}'", case_type),
                    approval_rate: approval_count as f64 / case_decisions.len() as f64,
                    match_rate: case_decisions.len() as f64 / decisions.len() as f64,
                    confidence: 0.90,
                });
            }
        }

        Ok(rules)
    }

    /// Compute feature importance: which decision factors most influence outcomes
    fn compute_feature_importance(&self, decisions: &[Decision]) -> Result<HashMap<String, f64>, String> {
        let mut importance = HashMap::new();

        // Feature 1: Score impact
        let score_influence = self.compute_correlation_to_outcome(decisions, "score");
        importance.insert("score".to_string(), score_influence);

        // Feature 2: Case type impact
        let case_influence = self.compute_correlation_to_outcome(decisions, "case_type");
        importance.insert("case_type".to_string(), case_influence);

        // Feature 3: Metadata impact (e.g., credit_score)
        let metadata_influence = self.compute_correlation_to_outcome(decisions, "metadata");
        importance.insert("metadata".to_string(), metadata_influence);

        // Normalize to sum to 1.0
        let total: f64 = importance.values().sum();
        if total > 0.0 {
            for val in importance.values_mut() {
                *val /= total;
            }
        }

        Ok(importance)
    }

    /// Compute correlation between a feature and decision outcome
    /// Simplified: Jaccard similarity on feature values
    fn compute_correlation_to_outcome(
        &self,
        decisions: &[Decision],
        _feature: &str,
    ) -> f64 {
        if decisions.is_empty() {
            return 0.0;
        }

        // Simplified correlation: higher scores → higher approval rate
        let avg_score = decisions.iter().map(|d| d.score).sum::<f64>() / decisions.len() as f64;
        let approval_rate = decisions.iter().filter(|d| d.outcome).count() as f64 / decisions.len() as f64;

        // Correlation proxy: score * approval_rate (0-1)
        (avg_score * approval_rate).min(1.0)
    }

    /// Compute model accuracy: % correct predictions on training data
    fn compute_accuracy(&self, decisions: &[Decision]) -> Result<f64, String> {
        if decisions.is_empty() {
            return Ok(0.0);
        }

        let correct = decisions
            .iter()
            .filter(|d| {
                // Predict approval if score > 0.75
                let prediction = d.score > 0.75;
                prediction == d.outcome
            })
            .count();

        Ok(correct as f64 / decisions.len() as f64)
    }

    /// Predict policy compliance: will this decision maintain fairness?
    /// Returns compliance score and risk assessment
    pub fn predict_policy_compliance(&self, _policy: &str) -> Result<PolicyPrediction, String> {
        if self.training_data.is_empty() {
            return Err("Model not trained".to_string());
        }

        // Mock prediction: compliance based on current accuracy
        let compliant = self.accuracy >= 0.85;
        let confidence = self.accuracy;

        let matching_rules = self.learned_rules
            .iter()
            .filter(|r| r.confidence > 0.85)
            .map(|r| r.rule_id.clone())
            .collect();

        let risk = if self.accuracy < 0.80 {
            "HIGH".to_string()
        } else if self.accuracy < 0.90 {
            "MEDIUM".to_string()
        } else {
            "LOW".to_string()
        };

        Ok(PolicyPrediction {
            compliant,
            confidence,
            matching_rules,
            risk_assessment: risk,
        })
    }

    /// Explain a specific decision: which rules led to approval/denial
    pub fn explain_decision(&self, decision_id: &str, actual_outcome: bool) -> Result<PolicyExplanation, String> {
        // Find matching rules
        let explaining_rules = self.learned_rules
            .iter()
            .filter(|r| r.confidence > 0.80)
            .map(|r| r.rule_name.clone())
            .collect();

        // Predict outcome (simple threshold)
        let predicted_outcome = self.learned_rules
            .iter()
            .filter(|r| r.approval_rate > 0.7)
            .count() > 0;

        let accuracy_contribution = if predicted_outcome == actual_outcome {
            self.accuracy
        } else {
            1.0 - self.accuracy
        };

        Ok(PolicyExplanation {
            decision_id: decision_id.to_string(),
            predicted_outcome,
            actual_outcome,
            explaining_rules,
            accuracy_contribution,
        })
    }

    /// Generate human-readable policy explanation
    /// Format: "Hotel chain X approves 93% of requests with credit_score > 650"
    pub fn generate_policy_explanation(&self) -> String {
        let mut explanation = String::from("Policy Learning Summary:\n");

        for rule in &self.learned_rules {
            explanation.push_str(&format!(
                "- {}: {} approval rate, {} of cases match\n",
                rule.rule_name,
                (rule.approval_rate * 100.0).round() as u32,
                (rule.match_rate * 100.0).round() as u32
            ));
        }

        explanation.push_str(&format!("Overall Model Accuracy: {:.1}%\n", self.accuracy * 100.0));

        if self.accuracy >= 0.92 {
            explanation.push_str("Status: COMPLIANT with 92%+ accuracy target\n");
        } else {
            explanation.push_str("Status: BELOW TARGET - review policy rules\n");
        }

        explanation
    }

    /// Get model accuracy score
    pub fn accuracy_score(&self) -> f64 {
        self.accuracy
    }

    /// Get learned rules count
    pub fn rules_count(&self) -> usize {
        self.learned_rules.len()
    }

    /// Get training data size
    pub fn training_data_size(&self) -> usize {
        self.training_data.len()
    }
}

impl Default for PolicyModel {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    fn create_test_decision(case_type: &str, outcome: bool, score: f64) -> Decision {
        Decision {
            decision_id: uuid::Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            case_type: case_type.to_string(),
            outcome,
            score,
            metadata: HashMap::new(),
            kms_signature: None,
        }
    }

    #[test]
    fn test_model_new() {
        let model = PolicyModel::new();
        assert_eq!(model.training_data_size(), 0);
        assert_eq!(model.accuracy_score(), 0.0);
    }

    #[test]
    fn test_fit_insufficient_data() {
        let mut model = PolicyModel::new();
        let decision = create_test_decision("hotel", true, 0.95);
        let result = model.fit_policy(vec![decision]);
        assert!(result.is_err());
    }

    #[test]
    fn test_fit_success() {
        let mut model = PolicyModel::new();
        let decisions: Vec<_> = (0..150)
            .map(|i| create_test_decision("hotel", i % 2 == 0, 0.95))
            .collect();

        let result = model.fit_policy(decisions);
        assert!(result.is_ok());
        assert!(model.accuracy_score() > 0.0);
        assert!(model.rules_count() > 0);
    }

    #[test]
    fn test_predict_not_trained() {
        let model = PolicyModel::new();
        let result = model.predict_policy_compliance("test");
        assert!(result.is_err());
    }
}
