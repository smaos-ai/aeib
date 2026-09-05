use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Modality {
    Text,
    Vision,
    Audio,
}

#[derive(Debug, Clone)]
pub struct PerModalityScores {
    pub modality: Modality,
    pub divergence: f64,
    pub f1_score: f64,
    pub robustness: f64,
    pub alignment: f64,
    pub corebench: f64,
}
