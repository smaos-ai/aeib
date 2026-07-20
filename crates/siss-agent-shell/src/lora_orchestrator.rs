/// Phase 53: LoRA Orchestrator — Memory Pressure Circuit Breaker
/// Enforces 85% unified memory limit before spawning training jobs.
use crate::distillation_gate::TrainingContract;

pub trait ResourceMonitor: Send + Sync {
    fn unified_memory_pct(&self) -> f64;
}

#[derive(Debug, Clone)]
pub struct LoraConfig {
    pub memory_pressure_limit: f64,
    pub base_model: String,
    pub adapter_output_dir: String,
}

impl Default for LoraConfig {
    fn default() -> Self {
        LoraConfig {
            memory_pressure_limit: 0.85,
            base_model: "mlx-community/Mistral-7B-Instruct".to_string(),
            adapter_output_dir: "/tmp/lora_adapters".to_string(),
        }
    }
}

#[derive(Debug, PartialEq, Clone)]
pub enum LoraJobState {
    Queued,
    Running { pid: u32 },
    Paused { reason: String },
    Completed { adapter_path: String },
    Failed { error: String },
}

#[derive(Debug, PartialEq, Eq)]
pub enum OrchestrationError {
    MemoryPressureTooHigh { actual_pct: i64, limit_pct: i64 },
    NoExamplesInContract,
    SpawnFailed(String),
}

pub struct LoraOrchestrator<R: ResourceMonitor> {
    pub config: LoraConfig,
    pub monitor: R,
}

impl<R: ResourceMonitor> LoraOrchestrator<R> {
    /// Attempt to queue a LoRA training job from a TrainingContract.
    /// RULE 1: contract.examples.is_empty() → Err(NoExamplesInContract)
    /// RULE 2: monitor.unified_memory_pct() > config.memory_pressure_limit
    ///         → Err(MemoryPressureTooHigh { actual_pct, limit_pct }) (values * 100)
    /// RULE 3: Ok(LoraJobState::Queued) — caller is responsible for spawning
    pub fn try_queue(
        &self,
        contract: &TrainingContract,
    ) -> Result<LoraJobState, OrchestrationError> {
        if contract.examples.is_empty() {
            return Err(OrchestrationError::NoExamplesInContract);
        }

        let memory_pct = self.monitor.unified_memory_pct();
        if memory_pct > self.config.memory_pressure_limit {
            let actual_pct = (memory_pct * 100.0) as i64;
            let limit_pct = (self.config.memory_pressure_limit * 100.0) as i64;
            return Err(OrchestrationError::MemoryPressureTooHigh {
                actual_pct,
                limit_pct,
            });
        }

        Ok(LoraJobState::Queued)
    }

    /// Determine if a running job should pause due to rising memory pressure.
    /// RULE A: state is Running AND monitor.unified_memory_pct() > limit → Some(Paused { reason })
    /// RULE B: any other state or pressure below limit → None
    pub fn should_pause(&self, state: &LoraJobState) -> Option<LoraJobState> {
        match state {
            LoraJobState::Running { pid } => {
                let memory_pct = self.monitor.unified_memory_pct();
                if memory_pct > self.config.memory_pressure_limit {
                    let reason = format!(
                        "memory pressure {:.0}% > {:.0}%",
                        memory_pct * 100.0,
                        self.config.memory_pressure_limit * 100.0
                    );
                    Some(LoraJobState::Paused { reason })
                } else {
                    None
                }
            }
            _ => None,
        }
    }
}
