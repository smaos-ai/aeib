//! L7: RAGAS evaluation framework
//! Golden set (50Q compliance questions), accuracy tracking, LangSmith integration

pub mod error;
pub mod evaluator;
pub mod golden_set;

pub use error::{L7AuditEntry, L7Error};
pub use evaluator::{EvaluationResult, Evaluator};
pub use golden_set::{GoldenQuestion, GoldenSet};
