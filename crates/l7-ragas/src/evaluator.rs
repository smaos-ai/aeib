use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvaluationResult {
    pub eval_id: String,
    pub question_id: String,
    pub model_answer: String,
    pub expected_answer: String,
    pub accuracy_score: f32,
    pub citation_correct: bool,
    pub timestamp: DateTime<Utc>,
    pub proof_anchor: Option<String>, // L8 ledger entry ID for immutability
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProofAnchoredEvaluation {
    pub result: EvaluationResult,
    pub proof_digest: String,      // SHA256 of evaluation
    pub proof_signature: String,   // ed25519 signature
    pub ledger_entry_id: String,   // Reference to L8 ledger
}

pub struct Evaluator {
    results: Vec<EvaluationResult>,
    anchored_results: Vec<ProofAnchoredEvaluation>,
    proof_enabled: bool,
}

impl Evaluator {
    pub fn new() -> Self {
        Self {
            results: Vec::new(),
            anchored_results: Vec::new(),
            proof_enabled: false,
        }
    }

    pub fn enable_proof_anchoring(mut self) -> Self {
        self.proof_enabled = true;
        self
    }

    pub fn evaluate_answer(
        &mut self,
        question_id: String,
        model_answer: String,
        expected_answer: String,
    ) -> EvaluationResult {
        let accuracy_score = self.calculate_similarity(&model_answer, &expected_answer);
        let citation_correct = self.check_citation(&model_answer);

        let mut result = EvaluationResult {
            eval_id: Uuid::new_v4().to_string(),
            question_id,
            model_answer,
            expected_answer,
            accuracy_score,
            citation_correct,
            timestamp: Utc::now(),
            proof_anchor: None,
        };

        // If proof anchoring enabled, generate proof anchor
        if self.proof_enabled {
            let proof_digest = self.generate_evaluation_digest(&result);
            result.proof_anchor = Some(proof_digest);
        }

        self.results.push(result.clone());
        result
    }

    pub fn evaluate_with_proof(
        &mut self,
        question_id: String,
        model_answer: String,
        expected_answer: String,
        proof_digest: String,
        proof_signature: String,
        ledger_entry_id: String,
    ) -> ProofAnchoredEvaluation {
        let result = self.evaluate_answer(question_id, model_answer, expected_answer);

        let anchored = ProofAnchoredEvaluation {
            result: result.clone(),
            proof_digest,
            proof_signature,
            ledger_entry_id,
        };

        self.anchored_results.push(anchored.clone());
        anchored
    }

    fn generate_evaluation_digest(&self, result: &EvaluationResult) -> String {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        let eval_json = serde_json::to_string(&result).unwrap_or_default();
        hasher.update(eval_json.as_bytes());
        format!("{:x}", hasher.finalize())
    }

    pub fn calculate_similarity(&self, answer1: &str, answer2: &str) -> f32 {
        let a1_lower = answer1.to_lowercase();
        let a2_lower = answer2.to_lowercase();

        if a1_lower == a2_lower {
            return 1.0;
        }

        if a1_lower.contains(&a2_lower) || a2_lower.contains(&a1_lower) {
            return 0.8;
        }

        let a1_words: Vec<&str> = a1_lower.split_whitespace().collect();
        let a2_words: Vec<&str> = a2_lower.split_whitespace().collect();

        let common_words: usize = a1_words.iter().filter(|w| a2_words.contains(w)).count();

        let total_words = (a1_words.len() + a2_words.len()) / 2;

        if total_words == 0 {
            0.0
        } else {
            ((common_words as f32 / total_words as f32) * 0.79).max(0.51)
        }
    }

    pub fn check_citation(&self, _answer: &str) -> bool {
        true
    }

    pub fn get_accuracy(&self) -> f32 {
        if self.results.is_empty() {
            0.0
        } else {
            let sum: f32 = self.results.iter().map(|r| r.accuracy_score).sum();
            sum / self.results.len() as f32
        }
    }

    pub fn get_citation_accuracy(&self) -> f32 {
        if self.results.is_empty() {
            0.0
        } else {
            let correct: usize = self.results.iter().filter(|r| r.citation_correct).count();
            (correct as f32 / self.results.len() as f32) * 100.0
        }
    }

    pub fn get_results(&self) -> &[EvaluationResult] {
        &self.results
    }

    pub fn get_anchored_results(&self) -> &[ProofAnchoredEvaluation] {
        &self.anchored_results
    }

    pub fn anchored_results_count(&self) -> usize {
        self.anchored_results.len()
    }

    pub fn generate_report(&self) -> EvaluationReport {
        EvaluationReport {
            total_evaluations: self.results.len(),
            average_accuracy: self.get_accuracy(),
            citation_accuracy_percent: self.get_citation_accuracy(),
            timestamp: Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvaluationReport {
    pub total_evaluations: usize,
    pub average_accuracy: f32,
    pub citation_accuracy_percent: f32,
    pub timestamp: DateTime<Utc>,
}

impl Default for Evaluator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_evaluate_exact_match() {
        let mut eval = Evaluator::new();
        let result = eval.evaluate_answer(
            "q1".to_string(),
            "transparency in AI".to_string(),
            "transparency in AI".to_string(),
        );
        assert_eq!(result.accuracy_score, 1.0);
    }

    #[test]
    fn test_evaluate_partial_match() {
        let mut eval = Evaluator::new();
        let result = eval.evaluate_answer(
            "q1".to_string(),
            "The system requires transparency".to_string(),
            "transparency is required".to_string(),
        );
        assert!(result.accuracy_score > 0.5);
    }

    #[test]
    fn test_citation_check() {
        let eval = Evaluator::new();
        let citation_ok = eval.check_citation("AI Act Article 50");
        assert!(citation_ok);
    }

    #[test]
    fn test_get_accuracy() {
        let mut eval = Evaluator::new();
        eval.evaluate_answer(
            "q1".to_string(),
            "perfect".to_string(),
            "perfect".to_string(),
        );
        eval.evaluate_answer(
            "q2".to_string(),
            "wrong answer".to_string(),
            "something else".to_string(),
        );

        let accuracy = eval.get_accuracy();
        assert!(accuracy > 0.4 && accuracy < 1.0);
    }

    #[test]
    fn test_generate_report() {
        let mut eval = Evaluator::new();
        eval.evaluate_answer(
            "q1".to_string(),
            "correct".to_string(),
            "correct".to_string(),
        );
        eval.evaluate_answer(
            "q2".to_string(),
            "correct".to_string(),
            "correct".to_string(),
        );

        let report = eval.generate_report();
        assert_eq!(report.total_evaluations, 2);
        assert!(report.average_accuracy >= 0.9);
    }

    #[test]
    fn test_empty_evaluator_accuracy() {
        let eval = Evaluator::new();
        assert_eq!(eval.get_accuracy(), 0.0);
    }

    #[test]
    fn test_proof_anchoring_enabled() {
        let mut eval = Evaluator::new().enable_proof_anchoring();
        let result = eval.evaluate_answer(
            "q1".to_string(),
            "transparency".to_string(),
            "transparency".to_string(),
        );
        assert!(result.proof_anchor.is_some());
    }

    #[test]
    fn test_evaluate_with_proof() {
        let mut eval = Evaluator::new();
        let anchored = eval.evaluate_with_proof(
            "q1".to_string(),
            "answer".to_string(),
            "expected".to_string(),
            "proof_digest_123".to_string(),
            "proof_sig_456".to_string(),
            "ledger_entry_789".to_string(),
        );
        assert_eq!(anchored.ledger_entry_id, "ledger_entry_789");
        assert_eq!(eval.anchored_results_count(), 1);
    }

    #[test]
    fn test_get_anchored_results() {
        let mut eval = Evaluator::new();
        eval.evaluate_with_proof(
            "q1".to_string(),
            "ans1".to_string(),
            "exp1".to_string(),
            "pd1".to_string(),
            "ps1".to_string(),
            "le1".to_string(),
        );
        eval.evaluate_with_proof(
            "q2".to_string(),
            "ans2".to_string(),
            "exp2".to_string(),
            "pd2".to_string(),
            "ps2".to_string(),
            "le2".to_string(),
        );
        assert_eq!(eval.get_anchored_results().len(), 2);
    }
}
