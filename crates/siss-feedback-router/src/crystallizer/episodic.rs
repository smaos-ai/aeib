use siss_graph_core::node::memory::ConsolidationTier;
use uuid::Uuid;

use crate::types::CrystallizedMemory;
use super::{Crystallizer, CrystallizationContext};

/// Default crystallizer: produces one Episodic memory per completed task.
pub struct EpisodicCrystallizer;

impl Crystallizer for EpisodicCrystallizer {
    fn crystallize(&self, context: &CrystallizationContext) -> Vec<CrystallizedMemory> {
        let output_summary = summarize_output(&context.execution_output, 500);

        let content = format!(
            "Task: {}\nOutput: {}\nQuality: {:.2}",
            context.intent, output_summary, context.quality_score,
        );

        vec![CrystallizedMemory {
            memory_id: Uuid::new_v4(),
            tier: ConsolidationTier::Episodic,
            content,
        }]
    }
}

/// Summarize JSON output to at most `max_chars` characters.
fn summarize_output(output: &serde_json::Value, max_chars: usize) -> String {
    let s = output.to_string();
    if s.len() <= max_chars {
        s
    } else {
        format!("{}...", &s[..max_chars])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_produces_one_episodic_memory() {
        let crystallizer = EpisodicCrystallizer;
        let ctx = CrystallizationContext {
            task_id: Uuid::new_v4(),
            intent: "Summarize document".into(),
            execution_output: serde_json::json!({"result": "done"}),
            quality_score: 0.75,
        };
        let memories = crystallizer.crystallize(&ctx);
        assert_eq!(memories.len(), 1);
        assert_eq!(memories[0].tier, ConsolidationTier::Episodic);
        assert!(memories[0].content.contains("Summarize document"));
        assert!(memories[0].content.contains("0.75"));
    }

    #[test]
    fn test_long_output_truncated() {
        let crystallizer = EpisodicCrystallizer;
        let long_output = "x".repeat(1000);
        let ctx = CrystallizationContext {
            task_id: Uuid::new_v4(),
            intent: "test".into(),
            execution_output: serde_json::json!({"data": long_output}),
            quality_score: 0.5,
        };
        let memories = crystallizer.crystallize(&ctx);
        // Output is truncated in the content
        assert!(memories[0].content.len() < 1500);
    }

    #[test]
    fn test_memory_id_is_unique() {
        let crystallizer = EpisodicCrystallizer;
        let ctx = CrystallizationContext {
            task_id: Uuid::new_v4(),
            intent: "test".into(),
            execution_output: serde_json::json!({}),
            quality_score: 1.0,
        };
        let m1 = crystallizer.crystallize(&ctx);
        let m2 = crystallizer.crystallize(&ctx);
        assert_ne!(m1[0].memory_id, m2[0].memory_id);
    }
}
