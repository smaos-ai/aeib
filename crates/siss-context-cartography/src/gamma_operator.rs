use crate::llm_wiki_v2::EpistemicStatus;
use chrono::{DateTime, Utc};
use std::collections::HashSet;

pub struct GammaOperator {
    pub divergence_threshold: f64,
}

impl GammaOperator {
    pub fn new(divergence_threshold: f64) -> Self {
        GammaOperator { divergence_threshold }
    }

    pub fn check(
        &self,
        primary_path: &[&str],
        adversarial_path: &[&str],
        now: DateTime<Utc>,
    ) -> EpistemicStatus {
        let divergence = 1.0 - jaccard_words(primary_path, adversarial_path);

        if divergence > self.divergence_threshold {
            EpistemicStatus::Uncertain {
                divergence_score: divergence,
                flagged_at: now,
            }
        } else {
            EpistemicStatus::Verified {
                divergence_score: divergence,
            }
        }
    }
}

fn jaccard_words(a: &[&str], b: &[&str]) -> f64 {
    let set_a: HashSet<&str> = a.iter().copied().collect();
    let set_b: HashSet<&str> = b.iter().copied().collect();

    let intersection = set_a.intersection(&set_b).count() as f64;
    let union = set_a.union(&set_b).count() as f64;

    if union == 0.0 {
        0.0
    } else {
        intersection / union
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_jaccard_identical_lists() {
        let a = vec!["hello", "world"];
        let b = vec!["hello", "world"];
        let similarity = jaccard_words(&a, &b);
        assert_eq!(similarity, 1.0);
    }

    #[test]
    fn test_jaccard_disjoint_lists() {
        let a = vec!["a", "b"];
        let b = vec!["c", "d"];
        let similarity = jaccard_words(&a, &b);
        assert_eq!(similarity, 0.0);
    }

    #[test]
    fn test_jaccard_partial_overlap() {
        let a = vec!["a", "b", "c"];
        let b = vec!["b", "c", "d"];
        let similarity = jaccard_words(&a, &b);
        let expected = 2.0 / 4.0;
        assert!((similarity - expected).abs() < 0.001);
    }
}
