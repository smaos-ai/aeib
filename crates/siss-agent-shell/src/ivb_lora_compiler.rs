/// Phase 60: IVB LoRA Compiler — Self-Improvement Harvest & Queue Pipeline

use crate::distillation_gate::{DistillationConfig, DistillationGate, TrainingContract};
use crate::lora_orchestrator::{LoraOrchestrator, LoraJobState, OrchestrationError, ResourceMonitor};
use crate::memory_crystallizer::{MemoryCrystal, SemanticCrystallizer};
use crate::swarm_knowledge::KnowledgeAtom;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IvbError {
    NoExamplesInContract,
    MemoryPressureTooHigh { actual_pct: i64, limit_pct: i64 },
    CrystallizationFailed(String),
}

pub struct IvbLoraCompiler;

impl IvbLoraCompiler {
    /// RULE 1: Filter atoms by effective_confidence(now) >= config.confidence_threshold
    /// RULE 2: Promote each via SemanticCrystallizer::promote(atom); silently drop CrystalError
    /// RULE 3: Crystals vec empty → Err(NoExamplesInContract)
    /// RULE 4: Delegate to DistillationGate::extract(crystals, config) → TrainingContract
    pub fn harvest(
        atoms: &[KnowledgeAtom],
        crystallizer: &SemanticCrystallizer,
        config: &DistillationConfig,
        now: DateTime<Utc>,
    ) -> Result<TrainingContract, IvbError> {
        let filtered: Vec<&KnowledgeAtom> = atoms
            .iter()
            .filter(|atom| atom.effective_confidence(now) >= config.confidence_threshold)
            .collect();

        if filtered.is_empty() {
            return Err(IvbError::NoExamplesInContract);
        }

        let crystals: Vec<MemoryCrystal> = filtered
            .iter()
            .filter_map(|atom| crystallizer.promote(atom).ok())
            .collect();

        if crystals.is_empty() {
            return Err(IvbError::NoExamplesInContract);
        }

        let contract = DistillationGate::extract(&crystals, config);

        if contract.examples.is_empty() {
            return Err(IvbError::NoExamplesInContract);
        }

        Ok(contract)
    }

    /// RULE 5: LoraOrchestrator::try_queue(contract):
    ///   Err(MemoryPressureTooHigh) → Err(IvbError::MemoryPressureTooHigh)
    ///   Err(NoExamplesInContract) → Err(IvbError::NoExamplesInContract)
    ///   Ok(LoraJobState::Queued) → Ok(LoraJobState::Queued)
    pub fn queue_compilation<R: ResourceMonitor>(
        contract: &TrainingContract,
        orchestrator: &LoraOrchestrator<R>,
    ) -> Result<LoraJobState, IvbError> {
        match orchestrator.try_queue(contract) {
            Ok(state) => Ok(state),
            Err(OrchestrationError::MemoryPressureTooHigh {
                actual_pct,
                limit_pct,
            }) => Err(IvbError::MemoryPressureTooHigh {
                actual_pct,
                limit_pct,
            }),
            Err(OrchestrationError::NoExamplesInContract) => Err(IvbError::NoExamplesInContract),
            Err(OrchestrationError::SpawnFailed(s)) => Err(IvbError::CrystallizationFailed(s)),
        }
    }
}
