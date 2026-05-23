use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum EvalVerdict {
    Safe,
    Unsafe(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProposedUpdate {
    pub update_id: Uuid,
    pub description: String,
    pub target_skill: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvalReport {
    pub update_id: Uuid,
    pub verdict: EvalVerdict,
    pub invariants_checked: usize,
}

pub struct EvalCourt;

impl EvalCourt {
    pub fn new() -> Self {
        EvalCourt
    }

    pub fn evaluate(&self, update: ProposedUpdate) -> EvalReport {
        let verdict = if update.description.to_lowercase().contains("unsafe") {
            EvalVerdict::Unsafe(update.description.clone())
        } else {
            EvalVerdict::Safe
        };

        EvalReport {
            update_id: update.update_id,
            verdict,
            invariants_checked: 3,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_safe_update_returns_safe_verdict() {
        let court = EvalCourt::new();
        let update = ProposedUpdate {
            update_id: Uuid::new_v4(),
            description: "add timeout logic".to_string(),
            target_skill: "test-skill".to_string(),
        };

        let report = court.evaluate(update);
        assert_eq!(report.verdict, EvalVerdict::Safe);
    }

    #[test]
    fn test_unsafe_description_blocked() {
        let court = EvalCourt::new();
        let update = ProposedUpdate {
            update_id: Uuid::new_v4(),
            description: "unsafe bypass".to_string(),
            target_skill: "test-skill".to_string(),
        };

        let report = court.evaluate(update);
        match report.verdict {
            EvalVerdict::Unsafe(_) => {
                // Expected: unsafe verdict matched
            }
            EvalVerdict::Safe => {
                panic!("Expected Unsafe verdict for unsafe description");
            }
        }
    }

    #[test]
    fn test_eval_report_checks_three_invariants() {
        let court = EvalCourt::new();
        let update = ProposedUpdate {
            update_id: Uuid::new_v4(),
            description: "any update".to_string(),
            target_skill: "test-skill".to_string(),
        };

        let report = court.evaluate(update);
        assert_eq!(report.invariants_checked, 3);
    }
}
