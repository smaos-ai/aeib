//! L7 Error Handling: RAGAS evaluation metrics and golden set validation
//! Accuracy measurement, question evaluation, citation verification

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug, Clone, Serialize, Deserialize)]
pub enum L7Error {
    #[error("Question validation failed: {reason}. Recovery: {recovery}")]
    QuestionValidationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Answer parsing failed: {reason}. Recovery: {recovery}")]
    AnswerParsingFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Citation verification failed: {reason}. Recovery: {recovery}")]
    CitationVerificationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Accuracy calculation failed: {reason}. Recovery: {recovery}")]
    AccuracyCalculationFailed {
        reason: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Golden set lookup failed: {category}. Recovery: {recovery}")]
    GoldenSetNotFound {
        category: String,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Evaluation timeout: exceeded {timeout_ms}ms. Recovery: {recovery}")]
    EvaluationTimeout {
        timeout_ms: u64,
        recovery: String,
        timestamp: DateTime<Utc>,
    },

    #[error("Accuracy below target: {actual}% < {target}%. Recovery: {recovery}")]
    AccuracyBelowTarget {
        actual: f32,
        target: f32,
        recovery: String,
        timestamp: DateTime<Utc>,
    },
}

impl L7Error {
    pub fn reason(&self) -> String {
        match self {
            Self::QuestionValidationFailed { reason, .. } => reason.clone(),
            Self::AnswerParsingFailed { reason, .. } => reason.clone(),
            Self::CitationVerificationFailed { reason, .. } => reason.clone(),
            Self::AccuracyCalculationFailed { reason, .. } => reason.clone(),
            Self::GoldenSetNotFound { category, .. } => {
                format!("Category {} not in golden set", category)
            }
            Self::EvaluationTimeout { timeout_ms, .. } => {
                format!("Evaluation exceeded {}ms", timeout_ms)
            }
            Self::AccuracyBelowTarget { actual, target, .. } => {
                format!("Accuracy {}% < target {}%", actual, target)
            }
        }
    }

    pub fn timestamp(&self) -> DateTime<Utc> {
        match self {
            Self::QuestionValidationFailed { timestamp, .. }
            | Self::AnswerParsingFailed { timestamp, .. }
            | Self::CitationVerificationFailed { timestamp, .. }
            | Self::AccuracyCalculationFailed { timestamp, .. }
            | Self::GoldenSetNotFound { timestamp, .. }
            | Self::EvaluationTimeout { timestamp, .. }
            | Self::AccuracyBelowTarget { timestamp, .. } => *timestamp,
        }
    }

    pub fn recovery(&self) -> String {
        match self {
            Self::QuestionValidationFailed { recovery, .. }
            | Self::AnswerParsingFailed { recovery, .. }
            | Self::CitationVerificationFailed { recovery, .. }
            | Self::AccuracyCalculationFailed { recovery, .. }
            | Self::GoldenSetNotFound { recovery, .. }
            | Self::EvaluationTimeout { recovery, .. }
            | Self::AccuracyBelowTarget { recovery, .. } => recovery.clone(),
        }
    }
}

/// AuditEntry for evaluation in L7
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct L7AuditEntry {
    pub timestamp: DateTime<Utc>,
    pub event_id: String,
    pub question_id: String,
    pub category: String,
    pub answer_correctness: bool,
    pub citations_verified: bool,
    pub accuracy_score: f32,
    pub error: Option<String>,
}

impl L7AuditEntry {
    pub fn new(
        question_id: String,
        category: String,
        answer_correctness: bool,
        citations_verified: bool,
    ) -> Self {
        Self {
            timestamp: Utc::now(),
            event_id: uuid::Uuid::new_v4().to_string(),
            question_id,
            category,
            answer_correctness,
            citations_verified,
            accuracy_score: 0.0,
            error: None,
        }
    }

    pub fn with_accuracy(mut self, score: f32) -> Self {
        self.accuracy_score = score;
        self
    }

    pub fn with_error(mut self, error: L7Error) -> Self {
        self.error = Some(format!("{:?}", error));
        self
    }
}

/// Input validation for L7
pub fn validate_question(question: &str) -> Result<(), L7Error> {
    if question.is_empty() {
        return Err(L7Error::QuestionValidationFailed {
            reason: "Question cannot be empty".to_string(),
            recovery: "Provide non-empty question text".to_string(),
            timestamp: Utc::now(),
        });
    }
    if question.len() > 5000 {
        return Err(L7Error::QuestionValidationFailed {
            reason: "Question exceeds 5000 characters".to_string(),
            recovery: "Shorten question or split into multiple questions".to_string(),
            timestamp: Utc::now(),
        });
    }
    if !question.contains('?') {
        return Err(L7Error::QuestionValidationFailed {
            reason: "Question must contain '?' character".to_string(),
            recovery: "Rephrase as question (end with '?')".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_answer(answer: &str) -> Result<(), L7Error> {
    if answer.is_empty() {
        return Err(L7Error::AnswerParsingFailed {
            reason: "Answer cannot be empty".to_string(),
            recovery: "Provide expected answer text".to_string(),
            timestamp: Utc::now(),
        });
    }
    if answer.len() > 10_000 {
        return Err(L7Error::AnswerParsingFailed {
            reason: "Answer exceeds 10000 characters".to_string(),
            recovery: "Summarize answer or provide shorter version".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_category(category: &str) -> Result<(), L7Error> {
    if category.is_empty() {
        return Err(L7Error::GoldenSetNotFound {
            category: category.to_string(),
            recovery: "Provide valid category (e.g., 'hotel', 'glass', 'school')".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_accuracy_score(score: f32) -> Result<(), L7Error> {
    if !(0.0..=100.0).contains(&score) {
        return Err(L7Error::AccuracyCalculationFailed {
            reason: format!("Accuracy {} outside 0-100 range", score),
            recovery: "Ensure accuracy is between 0 and 100 percent".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

pub fn validate_article_reference(article: &str) -> Result<(), L7Error> {
    if article.is_empty() {
        return Err(L7Error::CitationVerificationFailed {
            reason: "Article reference cannot be empty".to_string(),
            recovery: "Provide article number or name".to_string(),
            timestamp: Utc::now(),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_question_empty() {
        let result = validate_question("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_question_too_long() {
        let long_question = "What is".to_string() + &"a".repeat(5000);
        let result = validate_question(&long_question);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_question_no_question_mark() {
        let result = validate_question("Tell me about Article 50");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_question_valid() {
        let result = validate_question("What is Article 50?");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_answer_empty() {
        let result = validate_answer("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_answer_too_long() {
        let long_answer = "a".repeat(10_001);
        let result = validate_answer(&long_answer);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_answer_valid() {
        let result = validate_answer("Article 50 is about transparency in EU AI Act");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_category_empty() {
        let result = validate_category("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_category_valid() {
        let result = validate_category("hotel");
        assert!(result.is_ok());
    }

    #[test]
    fn test_validate_accuracy_score_below_zero() {
        let result = validate_accuracy_score(-5.0);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_accuracy_score_above_100() {
        let result = validate_accuracy_score(150.0);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_accuracy_score_valid() {
        assert!(validate_accuracy_score(87.5).is_ok());
        assert!(validate_accuracy_score(0.0).is_ok());
        assert!(validate_accuracy_score(100.0).is_ok());
    }

    #[test]
    fn test_validate_article_reference_empty() {
        let result = validate_article_reference("");
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_article_reference_valid() {
        let result = validate_article_reference("Article 50");
        assert!(result.is_ok());
    }

    #[test]
    fn test_audit_entry_with_accuracy() {
        let entry = L7AuditEntry::new("q1".to_string(), "hotel".to_string(), true, true);
        let entry = entry.with_accuracy(87.5);
        assert_eq!(entry.accuracy_score, 87.5);
    }

    #[test]
    fn test_audit_entry_with_error() {
        let entry = L7AuditEntry::new("q1".to_string(), "hotel".to_string(), false, false);
        let error = L7Error::CitationVerificationFailed {
            reason: "citation not found".to_string(),
            recovery: "add citation".to_string(),
            timestamp: Utc::now(),
        };
        let entry = entry.with_error(error);
        assert!(entry.error.is_some());
    }
}
