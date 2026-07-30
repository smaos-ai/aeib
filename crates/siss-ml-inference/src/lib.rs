pub mod tensor_ops;
pub mod model_registry;
pub mod inference_engine;

pub use inference_engine::{InferenceEngine, InferenceModel, HardwareBackend};
pub use tensor_ops::Tensor;
pub use model_registry::ModelMetadata;

use thiserror::Error;

#[derive(Error, Debug)]
pub enum InferenceError {
    #[error("Model not found: {0}")]
    ModelNotFound(String),

    #[error("Tensor shape mismatch: expected {expected}, got {actual}")]
    ShapeMismatch { expected: String, actual: String },

    #[error("Hardware backend error: {0}")]
    HardwareError(String),

    #[error("Determinism verification failed")]
    DeterminismFailed,

    #[error("Inference failed: {0}")]
    InferenceFailed(String),

    #[error("Quantization error: {0}")]
    QuantizationError(String),
}

pub type Result<T> = std::result::Result<T, InferenceError>;
