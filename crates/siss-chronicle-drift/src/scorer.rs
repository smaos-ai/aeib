use crate::error::{DriftError, Result};
use crate::Decision;

/// RAGAS Scoring dimensions
#[derive(Clone, Debug)]
pub struct RAGASMetrics {
    pub faithfulness: f64,
    pub answer_relevancy: f64,
    pub context_precision: f64,
    pub context_recall: f64,
}

impl RAGASMetrics {
    /// Compute aggregate RAGAS score (harmonic mean)
    pub fn aggregate_score(&self) -> f64 {
        let scores = [
            self.faithfulness,
            self.answer_relevancy,
            self.context_precision,
            self.context_recall,
        ];
        let sum: f64 = scores.iter().sum();
        sum / scores.len() as f64
    }
}

/// RAGAS Scorer
pub struct RAGASScorer;

impl RAGASScorer {
    /// Score a decision based on quality metrics
    pub fn score_decision(decision: &Decision) -> Result<RAGASMetrics> {
        // Stub: In Jun 2027, integrate actual RAGAS evaluation
        // For now: use quality_score as proxy for all dimensions
        Ok(RAGASMetrics {
            faithfulness: decision.quality_score,
            answer_relevancy: decision.quality_score * 0.95,
            context_precision: decision.quality_score * 0.90,
            context_recall: decision.quality_score * 0.92,
        })
    }

    /// Score batch of decisions
    pub fn score_batch(decisions: &[Decision]) -> Result<Vec<RAGASMetrics>> {
        decisions
            .iter()
            .map(Self::score_decision)
            .collect()
    }

    /// Compute average metrics across decisions
    pub fn average_metrics(metrics: &[RAGASMetrics]) -> RAGASMetrics {
        if metrics.is_empty() {
            return RAGASMetrics {
                faithfulness: 0.0,
                answer_relevancy: 0.0,
                context_precision: 0.0,
                context_recall: 0.0,
            };
        }

        let n = metrics.len() as f64;
        RAGASMetrics {
            faithfulness: metrics.iter().map(|m| m.faithfulness).sum::<f64>() / n,
            answer_relevancy: metrics.iter().map(|m| m.answer_relevancy).sum::<f64>() / n,
            context_precision: metrics.iter().map(|m| m.context_precision).sum::<f64>() / n,
            context_recall: metrics.iter().map(|m| m.context_recall).sum::<f64>() / n,
        }
    }

    /// Detect sudden quality drop (RAGAS drift)
    pub fn detect_quality_drop(
        previous_avg: f64,
        current_avg: f64,
        threshold: f64,
    ) -> bool {
        (previous_avg - current_avg) > threshold
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ragas_metrics_aggregate() {
        let metrics = RAGASMetrics {
            faithfulness: 0.8,
            answer_relevancy: 0.85,
            context_precision: 0.75,
            context_recall: 0.90,
        };
        let score = metrics.aggregate_score();
        assert!((score - 0.825).abs() < 0.01);
    }

    #[test]
    fn test_ragas_score_decision() {
        let decision = Decision::new("test".to_string(), "test".to_string())
            .with_quality_score(0.8);

        let metrics = RAGASScorer::score_decision(&decision).unwrap();
        assert!(metrics.faithfulness > 0.0);
    }

    #[test]
    fn test_ragas_batch_scoring() {
        let decisions = vec![
            Decision::new("a".to_string(), "a".to_string())
                .with_quality_score(0.9),
            Decision::new("b".to_string(), "b".to_string())
                .with_quality_score(0.8),
        ];

        let scores = RAGASScorer::score_batch(&decisions).unwrap();
        assert_eq!(scores.len(), 2);
    }

    #[test]
    fn test_ragas_quality_drop_detection() {
        assert!(RAGASScorer::detect_quality_drop(0.9, 0.7, 0.15));
        assert!(!RAGASScorer::detect_quality_drop(0.9, 0.88, 0.05));
    }
}
