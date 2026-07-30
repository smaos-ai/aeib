//! Ollama local LLM integration for SISS
//!
//! This crate provides a client for interacting with Ollama local LLM inference.
//! Ollama enables zero-latency, offline-capable, cost-free inference for development.
//!
//! # Features
//!
//! - Local LLM inference via Ollama API
//! - Multiple model support (qwen2.5-coder:14b primary)
//! - Health checking and model listing
//! - Configurable temperature and sampling parameters
//! - Concurrent request handling
//! - Timeout and error handling
//!
//! # Example
//!
//! ```no_run
//! use siss_local_llm::OllamaClient;
//!
//! #[tokio::main]
//! async fn main() -> Result<(), Box<dyn std::error::Error>> {
//!     let client = OllamaClient::new("http://localhost:11434", "qwen2.5-coder:14b");
//!
//!     // Check if Ollama is running
//!     if client.health_check().await? {
//!         let response = client.generate("fn hello() { println!(\"Hello\"); }").await?;
//!         println!("Response: {}", response.response);
//!     }
//!
//!     Ok(())
//! }
//! ```

pub mod ollama_client;

pub use ollama_client::{OllamaClient, OllamaRequest, OllamaResponse};
