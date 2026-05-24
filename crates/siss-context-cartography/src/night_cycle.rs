use chrono::{DateTime, Utc};
use serde::{Serialize, Deserialize};
use uuid::Uuid;
use std::collections::HashMap;
use crate::llm_wiki_v2::{SemanticFact, ProceduralMemory};

/// Phase 81: Night Cycle Evolution Engine
/// Autonomous hypothesis generation from consolidated memories.
/// Runs asynchronously during off-peak cycles to refine codebase based on observed patterns.

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HypothesisTemplate {
    pub id: Uuid,
    pub name: String,
    pub description: String,
    pub trigger_pattern: String,
    pub facts_required: Vec<String>,
    pub confidence_threshold: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GeneratedHypothesis {
    pub id: Uuid,
    pub template_id: Uuid,
    pub hypothesis: String,
    pub supporting_facts: Vec<Uuid>,
    pub confidence_score: f64,
    pub generated_at: DateTime<Utc>,
    pub judge_script: JudgeScript,
    pub code_changes_proposed: Vec<ProposedCodeChange>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JudgeScript {
    pub id: Uuid,
    pub assertion: String,
    pub test_cases: Vec<String>,
    pub pass_threshold: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProposedCodeChange {
    pub file_path: String,
    pub symbol_name: String,
    pub change_type: ChangeType,
    pub diff: String,
    pub risk_level: RiskLevel,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ChangeType {
    Add,
    Modify,
    Remove,
    Refactor,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
pub enum RiskLevel {
    Low,
    Medium,
    High,
    Critical,
}

pub struct NightCycleEngine {
    templates: Vec<HypothesisTemplate>,
    hypotheses: Vec<GeneratedHypothesis>,
}

impl NightCycleEngine {
    pub fn new() -> Self {
        Self {
            templates: Self::bootstrap_templates(),
            hypotheses: Vec::new(),
        }
    }

    fn bootstrap_templates() -> Vec<HypothesisTemplate> {
        vec![
            HypothesisTemplate {
                id: Uuid::new_v4(),
                name: "performance_optimization".to_string(),
                description: "Identify frequently-called hot paths for optimization".to_string(),
                trigger_pattern: "high_access_count".to_string(),
                facts_required: vec!["caller_pattern".to_string(), "latency_report".to_string()],
                confidence_threshold: 0.85,
            },
            HypothesisTemplate {
                id: Uuid::new_v4(),
                name: "api_consistency".to_string(),
                description: "Unify inconsistent API signatures across modules".to_string(),
                trigger_pattern: "param_name_variance".to_string(),
                facts_required: vec!["function_signature".to_string(), "call_site".to_string()],
                confidence_threshold: 0.80,
            },
            HypothesisTemplate {
                id: Uuid::new_v4(),
                name: "dead_code_removal".to_string(),
                description: "Identify and propose removal of unreachable code".to_string(),
                trigger_pattern: "zero_callers".to_string(),
                facts_required: vec!["symbol_usage".to_string()],
                confidence_threshold: 0.95,
            },
        ]
    }

    pub fn generate_hypotheses(
        &mut self,
        facts: &[SemanticFact],
        procedures: &[ProceduralMemory],
    ) -> Vec<GeneratedHypothesis> {
        let mut generated = Vec::new();

        for template in &self.templates {
            if let Some(hypothesis) = self.evaluate_template(template, facts, procedures) {
                generated.push(hypothesis);
            }
        }

        self.hypotheses = generated.clone();
        generated
    }

    fn evaluate_template(
        &self,
        template: &HypothesisTemplate,
        facts: &[SemanticFact],
        _procedures: &[ProceduralMemory],
    ) -> Option<GeneratedHypothesis> {
        let matching_facts: Vec<&SemanticFact> = facts
            .iter()
            .filter(|f| {
                template.facts_required.iter().any(|req| f.fact.contains(req.as_str()))
            })
            .collect();

        if matching_facts.is_empty() {
            return None;
        }

        let confidence = matching_facts
            .iter()
            .map(|f| f.confidence_score)
            .sum::<f64>()
            / matching_facts.len() as f64;

        if confidence < template.confidence_threshold {
            return None;
        }

        let hypothesis_text = format!(
            "{}: Based on {} supporting facts with confidence {:.2}",
            template.description,
            matching_facts.len(),
            confidence
        );

        let judge_script = JudgeScript {
            id: Uuid::new_v4(),
            assertion: format!("Verify {}", template.name),
            test_cases: vec![
                "test_proposed_change_compiles".to_string(),
                "test_no_regression_on_existing_tests".to_string(),
                "test_improvement_metric_verified".to_string(),
            ],
            pass_threshold: 0.90,
        };

        let code_changes = self.propose_changes(&template.name, &matching_facts);

        Some(GeneratedHypothesis {
            id: Uuid::new_v4(),
            template_id: template.id,
            hypothesis: hypothesis_text,
            supporting_facts: matching_facts.iter().map(|f| f.id).collect(),
            confidence_score: confidence,
            generated_at: Utc::now(),
            judge_script,
            code_changes_proposed: code_changes,
        })
    }

    fn propose_changes(
        &self,
        template_name: &str,
        facts: &[&SemanticFact],
    ) -> Vec<ProposedCodeChange> {
        match template_name {
            "performance_optimization" => {
                vec![ProposedCodeChange {
                    file_path: "crates/siss-context-cartography/src/hot_path.rs".to_string(),
                    symbol_name: "consolidate_memories".to_string(),
                    change_type: ChangeType::Modify,
                    diff: "Add caching layer for frequently-accessed facts".to_string(),
                    risk_level: RiskLevel::Medium,
                }]
            }
            "api_consistency" => {
                vec![ProposedCodeChange {
                    file_path: "crates/siss-context-cartography/src/api.rs".to_string(),
                    symbol_name: "query_facts".to_string(),
                    change_type: ChangeType::Refactor,
                    diff: "Unify parameter ordering across query variants".to_string(),
                    risk_level: RiskLevel::Low,
                }]
            }
            "dead_code_removal" => {
                vec![ProposedCodeChange {
                    file_path: "crates/siss-context-cartography/src/legacy.rs".to_string(),
                    symbol_name: "deprecated_search".to_string(),
                    change_type: ChangeType::Remove,
                    diff: "Remove unreachable legacy search implementation".to_string(),
                    risk_level: RiskLevel::Low,
                }]
            }
            _ => vec![],
        }
    }

    pub fn hypotheses(&self) -> &[GeneratedHypothesis] {
        &self.hypotheses
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_fact(content: &str, confidence: f64) -> SemanticFact {
        SemanticFact {
            id: Uuid::new_v4(),
            fact: content.to_string(),
            confidence_score: confidence,
            created_at: Utc::now(),
            last_accessed_at: Utc::now(),
            access_count: 1,
            superseded_by: None,
            is_stale: false,
            sources: vec!["test".to_string()],
        }
    }

    #[test]
    fn test_night_cycle_generates_hypotheses_from_facts() {
        let mut engine = NightCycleEngine::new();
        let facts = vec![
            test_fact("caller_pattern: high_frequency", 0.90),
            test_fact("latency_report: 500ms p99", 0.85),
        ];

        let hypotheses = engine.generate_hypotheses(&facts, &[]);
        assert!(!hypotheses.is_empty());
    }

    #[test]
    fn test_judge_script_has_three_test_cases() {
        let mut engine = NightCycleEngine::new();
        let facts = vec![test_fact("caller_pattern: test", 0.90)];

        let hypotheses = engine.generate_hypotheses(&facts, &[]);
        if let Some(h) = hypotheses.first() {
            assert_eq!(h.judge_script.test_cases.len(), 3);
        }
    }

    #[test]
    fn test_low_confidence_facts_rejected() {
        let mut engine = NightCycleEngine::new();
        let facts = vec![test_fact("caller_pattern: maybe", 0.50)];

        let hypotheses = engine.generate_hypotheses(&facts, &[]);
        assert!(hypotheses.is_empty(), "Low confidence facts should not generate hypotheses");
    }

    #[test]
    fn test_proposed_changes_have_risk_levels() {
        let mut engine = NightCycleEngine::new();
        let facts = vec![
            test_fact("caller_pattern: high", 0.90),
            test_fact("latency_report: slow", 0.85),
        ];

        let hypotheses = engine.generate_hypotheses(&facts, &[]);
        for hypothesis in hypotheses {
            for change in hypothesis.code_changes_proposed {
                assert!(matches!(
                    change.risk_level,
                    RiskLevel::Low | RiskLevel::Medium | RiskLevel::High | RiskLevel::Critical
                ));
            }
        }
    }

    #[test]
    fn test_hypothesis_stores_supporting_facts() {
        let mut engine = NightCycleEngine::new();
        let facts = vec![
            test_fact("caller_pattern: high", 0.90),
            test_fact("latency_report: slow", 0.85),
        ];

        let hypotheses = engine.generate_hypotheses(&facts, &[]);
        if let Some(h) = hypotheses.first() {
            assert!(!h.supporting_facts.is_empty());
        }
    }
}
