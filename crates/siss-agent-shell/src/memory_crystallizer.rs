/// Phase 52: Memory Crystallizers — Episodic→Semantic→Procedural promotion
/// Complete the 4-tier crystallization pipeline with confidence-based thresholds.

use crate::swarm_knowledge::KnowledgeAtom;
use chrono::Utc;
use siss_graph_core::node::memory::ConsolidationTier;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct MemoryCrystal {
    pub crystal_id: Uuid,
    pub source_content: String,
    pub tier: ConsolidationTier,
    pub confidence: f64,
    pub promoted_at: chrono::DateTime<Utc>,
}

#[derive(Debug, PartialEq, Eq)]
pub enum CrystalError {
    ConfidenceTooLow { required: i64, actual: i64 },
    InsufficientReinforcement { required: u32, actual: u32 },
}

pub struct SemanticCrystallizer {
    pub min_confidence: f64,
    pub min_reinforcements: u32,
}

impl Default for SemanticCrystallizer {
    fn default() -> Self {
        SemanticCrystallizer {
            min_confidence: 0.90,
            min_reinforcements: 2,
        }
    }
}

impl SemanticCrystallizer {
    pub fn new(min_confidence: f64, min_reinforcements: u32) -> Self {
        SemanticCrystallizer {
            min_confidence,
            min_reinforcements,
        }
    }

    /// Episodic → Semantic promotion.
    /// RULE 1: atom.confidence >= min_confidence → Err(ConfidenceTooLow) if not
    /// RULE 2: atom.reinforcement_count >= min_reinforcements → Err(InsufficientReinforcement) if not
    /// RULE 3: Ok(MemoryCrystal { tier: Semantic })
    pub fn promote(&self, atom: &KnowledgeAtom) -> Result<MemoryCrystal, CrystalError> {
        if atom.confidence < self.min_confidence {
            return Err(CrystalError::ConfidenceTooLow {
                required: (self.min_confidence * 100.0) as i64,
                actual: (atom.confidence * 100.0) as i64,
            });
        }

        if atom.reinforcement_count < self.min_reinforcements {
            return Err(CrystalError::InsufficientReinforcement {
                required: self.min_reinforcements,
                actual: atom.reinforcement_count,
            });
        }

        Ok(MemoryCrystal {
            crystal_id: Uuid::new_v4(),
            source_content: atom.content.clone(),
            tier: ConsolidationTier::Semantic,
            confidence: atom.confidence,
            promoted_at: Utc::now(),
        })
    }
}

pub struct ProceduralCrystallizer {
    pub min_confidence: f64,
    pub min_reinforcements: u32,
}

impl Default for ProceduralCrystallizer {
    fn default() -> Self {
        ProceduralCrystallizer {
            min_confidence: 0.95,
            min_reinforcements: 5,
        }
    }
}

impl ProceduralCrystallizer {
    pub fn new(min_confidence: f64, min_reinforcements: u32) -> Self {
        ProceduralCrystallizer {
            min_confidence,
            min_reinforcements,
        }
    }

    /// Semantic → Procedural promotion (higher thresholds).
    pub fn promote(&self, atom: &KnowledgeAtom) -> Result<MemoryCrystal, CrystalError> {
        if atom.confidence < self.min_confidence {
            return Err(CrystalError::ConfidenceTooLow {
                required: (self.min_confidence * 100.0) as i64,
                actual: (atom.confidence * 100.0) as i64,
            });
        }

        if atom.reinforcement_count < self.min_reinforcements {
            return Err(CrystalError::InsufficientReinforcement {
                required: self.min_reinforcements,
                actual: atom.reinforcement_count,
            });
        }

        Ok(MemoryCrystal {
            crystal_id: Uuid::new_v4(),
            source_content: atom.content.clone(),
            tier: ConsolidationTier::Procedural,
            confidence: atom.confidence,
            promoted_at: Utc::now(),
        })
    }
}
