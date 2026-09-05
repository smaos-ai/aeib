/// Phase 53: Distillation Extraction Gate — MemoryCrystal → SFT JSONL (no cloud egress)
/// Pure synchronous transformation: high-confidence crystals → training data.
use crate::memory_crystallizer::MemoryCrystal;
use chrono::{DateTime, Utc};
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct DistillationConfig {
    pub confidence_threshold: f64,
    pub max_examples: usize,
}

impl Default for DistillationConfig {
    fn default() -> Self {
        DistillationConfig {
            confidence_threshold: 0.95,
            max_examples: 100,
        }
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct TrainingExample {
    pub prompt: String,
    pub completion: String,
}

#[derive(Debug, Clone)]
pub struct TrainingContract {
    pub contract_id: Uuid,
    pub examples: Vec<TrainingExample>,
    pub source_crystal_ids: Vec<Uuid>,
    pub created_at: DateTime<Utc>,
}

pub struct DistillationGate;

impl DistillationGate {
    /// Filter MemoryCrystals by confidence and format as TrainingContract.
    /// RULE 1: Only crystals with confidence >= config.confidence_threshold are included
    /// RULE 2: Each crystal's source_content becomes a prompt/completion pair:
    ///         prompt = format!("Encode procedural knowledge:\n{}", crystal.source_content)
    ///         completion = format!("Procedural fact: {}", crystal.source_content)
    /// RULE 3: Output capped at config.max_examples (first N after filtering)
    /// RULE 4: All processing is pure (no I/O, no network) — deterministic
    pub fn extract(crystals: &[MemoryCrystal], config: &DistillationConfig) -> TrainingContract {
        let mut examples = Vec::new();
        let mut source_crystal_ids = Vec::new();

        for crystal in crystals {
            if crystal.confidence >= config.confidence_threshold {
                let prompt = format!("Encode procedural knowledge:\n{}", crystal.source_content);
                let completion = format!("Procedural fact: {}", crystal.source_content);

                examples.push(TrainingExample { prompt, completion });
                source_crystal_ids.push(crystal.crystal_id);

                if examples.len() >= config.max_examples {
                    break;
                }
            }
        }

        TrainingContract {
            contract_id: Uuid::new_v4(),
            examples,
            source_crystal_ids,
            created_at: Utc::now(),
        }
    }

    /// Serialize TrainingContract as JSONL (one JSON object per line).
    /// Each line: {"prompt": "...", "completion": "..."}
    /// RULE: Each line must be valid JSON; empty contract → empty string (not an error)
    pub fn to_jsonl(contract: &TrainingContract) -> String {
        contract
            .examples
            .iter()
            .filter_map(|ex| serde_json::to_string(ex).ok())
            .collect::<Vec<_>>()
            .join("\n")
    }
}
