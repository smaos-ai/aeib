pub mod inference_engine;
pub mod model_registry;
pub mod tensor_ops;

pub use inference_engine::{HardwareBackend, InferenceEngine, InferenceModel};
pub use model_registry::ModelMetadata;
pub use tensor_ops::Tensor;

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
