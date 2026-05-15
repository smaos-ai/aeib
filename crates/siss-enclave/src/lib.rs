pub mod eval;
pub mod events;
pub mod model;
pub mod orchestrator;
pub mod routing;

/// Enclave v2.1: Safe Model Evolution with Chaos Petri Validation Gate
///
/// Teacher-Forcing enclave implements safe LoRA policy evolution via:
/// - Canary routing: Shadow 1-5% live traffic to new Policy Ledger delta
/// - Agent-as-a-Judge: Evaluate logprob divergence, tool-call F1, golden trajectories
/// - Double-buffered LoRA swap: Atomic pointer swap without KV cache flush
/// - RCE integration: Pause evolution workflows during evaluation, resume on approval
pub use model::lora_swap;

#[derive(Debug, Clone)]
pub struct EnclaveConfig {
    /// Maximum unified memory utilization (0.0-1.0, typically 0.25)
    pub max_memory_utilization: f64,
    /// Latency SLA for LoRA swap (milliseconds, must be <50ms)
    pub swap_latency_sla_ms: u64,
    /// Canary traffic percentage (1-5)
    pub canary_traffic_percent: u8,
    /// Logprob divergence rejection threshold
    pub logprob_divergence_threshold: f64,
    /// Tool-call F1 score rejection threshold
    pub tool_f1_threshold: f64,
}

impl Default for EnclaveConfig {
    fn default() -> Self {
        Self {
            max_memory_utilization: 0.25,
            swap_latency_sla_ms: 50,
            canary_traffic_percent: 3,
            logprob_divergence_threshold: 0.15,
            tool_f1_threshold: 0.85,
        }
    }
}
