use serde::{Deserialize, Serialize};
use thiserror::Error;
use uuid::Uuid;

/// A log entry representing repeated task executions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskLog {
    pub session_id: Uuid,
    pub tool_name: String,
    pub repetitions: usize,
}

/// A synthesized SKILL.md file derived from consolidated task logs.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SynthesizedSkill {
    pub skill_name: String,
    pub content_markdown: String,
    pub repetition_count: usize,
}

/// Errors from the skill crystallizer.
#[derive(Debug, Error, PartialEq)]
pub enum CrystallizerError {
    #[error("Below threshold: {0} < {1}")]
    BelowThreshold(usize, usize),
}

/// Crystallizes repeated task logs into new SKILL.md files via Ebbinghaus consolidation.
pub struct SkillCrystallizer {
    repetition_threshold: usize,
}

impl SkillCrystallizer {
    /// Create a new SkillCrystallizer with a repetition threshold.
    pub fn new(repetition_threshold: usize) -> Self {
        SkillCrystallizer { repetition_threshold }
    }

    /// Crystallize a single task log into a synthesized skill if it meets the threshold.
    pub fn crystallize_skill(&self, log: &TaskLog) -> Result<SynthesizedSkill, CrystallizerError> {
        if log.repetitions < self.repetition_threshold {
            return Err(CrystallizerError::BelowThreshold(log.repetitions, self.repetition_threshold));
        }
        Ok(SynthesizedSkill {
            skill_name: log.tool_name.clone(),
            content_markdown: format!("# {}\n\nRepeated {} times.", log.tool_name, log.repetitions),
            repetition_count: log.repetitions,
        })
    }

    /// Crystallize a batch of task logs, filtering for those that meet the threshold.
    pub fn crystallize_batch(&self, logs: &[TaskLog]) -> Vec<SynthesizedSkill> {
        logs.iter().filter_map(|l| self.crystallize_skill(l).ok()).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// test_below_threshold_rejected: TaskLog with 2 repetitions, threshold=3 → BelowThreshold(2, 3)
    #[test]
    fn test_below_threshold_rejected() {
        let crystallizer = SkillCrystallizer::new(3);
        let log = TaskLog {
            session_id: Uuid::new_v4(),
            tool_name: "test_tool".to_string(),
            repetitions: 2,
        };
        let result = crystallizer.crystallize_skill(&log);
        assert_eq!(result, Err(CrystallizerError::BelowThreshold(2, 3)));
    }

    /// test_meets_threshold_synthesized: TaskLog with 3 repetitions, threshold=3 → Ok(SynthesizedSkill)
    #[test]
    fn test_meets_threshold_synthesized() {
        let crystallizer = SkillCrystallizer::new(3);
        let log = TaskLog {
            session_id: Uuid::new_v4(),
            tool_name: "test_tool".to_string(),
            repetitions: 3,
        };
        let result = crystallizer.crystallize_skill(&log);
        assert!(result.is_ok());
        let skill = result.unwrap();
        assert_eq!(skill.skill_name, "test_tool");
        assert_eq!(skill.repetition_count, 3);
        assert_eq!(skill.content_markdown, "# test_tool\n\nRepeated 3 times.");
    }

    /// test_batch_filters_below_threshold: Batch of logs [2,3,5] reps, threshold=3 → 2 synthesized
    #[test]
    fn test_batch_filters_below_threshold() {
        let crystallizer = SkillCrystallizer::new(3);
        let logs = vec![
            TaskLog {
                session_id: Uuid::new_v4(),
                tool_name: "tool_a".to_string(),
                repetitions: 2,
            },
            TaskLog {
                session_id: Uuid::new_v4(),
                tool_name: "tool_b".to_string(),
                repetitions: 3,
            },
            TaskLog {
                session_id: Uuid::new_v4(),
                tool_name: "tool_c".to_string(),
                repetitions: 5,
            },
        ];
        let results = crystallizer.crystallize_batch(&logs);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].skill_name, "tool_b");
        assert_eq!(results[1].skill_name, "tool_c");
    }
}
