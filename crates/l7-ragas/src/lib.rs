//! L7: RAGAS evaluation framework
//! Golden set (50Q compliance questions), accuracy tracking, LangSmith integration

pub mod golden_set;
pub mod evaluator;

pub use golden_set::{GoldenQuestion, GoldenSet};
pub use evaluator::{EvaluationResult, Evaluator};
