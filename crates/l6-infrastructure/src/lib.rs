//! L6: FreeToken edge inference + hardware detection
//! Validates 39.3 tok/s on 8GB, integrates CanIRun.ai

pub mod benchmark;
pub mod error;
pub mod freetoken;
pub mod hardware;
pub mod langchain_ollama;

pub use benchmark::{Benchmark, BenchmarkConfig};
pub use error::{L6AuditEntry, L6Error};
pub use freetoken::{FreeTokenValidator, InferenceResult, QwenInferenceConfig};
pub use hardware::{HardwareDetector, HardwareTier};
pub use langchain_ollama::{LLMRequest, LLMResponse, LangChainOllamaAdapter, OllamaConfig};
