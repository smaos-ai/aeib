pub mod episodic;

use uuid::Uuid;

use crate::types::CrystallizedMemory;

/// Context for crystallization.
pub struct CrystallizationContext {
    pub task_id: Uuid,
    pub intent: String,
    pub execution_output: serde_json::Value,
    pub quality_score: f64,
}

/// Trait for producing memory nodes from completed tasks.
pub trait Crystallizer: Send + Sync {
    fn crystallize(&self, context: &CrystallizationContext) -> Vec<CrystallizedMemory>;
}
