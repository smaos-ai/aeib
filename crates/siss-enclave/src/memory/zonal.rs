use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use uuid::Uuid;

use crate::memory::auto_dream::AutoDream;
use crate::memory::operators::CartographicOperators;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ObservationTier {
    Procedural,
    Semantic,
    Episodic,
    Working,
}

#[derive(Debug, Clone)]
pub struct RawObservation {
    pub id: Uuid,
    pub content: String,
    pub confidence: f64,
    pub tier: ObservationTier,
}

impl RawObservation {
    pub fn new(content: String, confidence: f64, tier: ObservationTier) -> Self {
        Self {
            id: Uuid::new_v4(),
            content,
            confidence: confidence.clamp(0.0, 1.0),
            tier,
        }
    }

    pub fn token_count(&self) -> i64 {
        (self.content.len() as f64 * 0.25).ceil() as i64
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConsolidatedEntry {
    pub id: Uuid,
    pub content: String,
    pub confidence: f64,
    pub tier: ObservationTier,
    pub token_count: i64,
}

impl ConsolidatedEntry {
    pub fn into_raw_obs(self) -> RawObservation {
        RawObservation::new(self.content, self.confidence, self.tier)
    }
}

pub type LayeredFog = HashMap<ObservationTier, Vec<ConsolidatedEntry>>;

#[derive(Debug, Clone)]
pub struct GrayFog {
    pub layers: LayeredFog,
}

impl GrayFog {
    pub fn new() -> Self {
        Self {
            layers: HashMap::new(),
        }
    }

    pub fn total_entries(&self) -> usize {
        self.layers.values().map(|v| v.len()).sum()
    }
}

impl Default for GrayFog {
    fn default() -> Self {
        Self::new()
    }
}

pub struct EphemeralBuffer {
    sender: tokio::sync::mpsc::Sender<RawObservation>,
}

impl EphemeralBuffer {
    pub fn new(sender: tokio::sync::mpsc::Sender<RawObservation>) -> Self {
        Self { sender }
    }

    pub fn write(&self, obs: RawObservation) -> bool {
        self.sender.try_send(obs).is_ok()
    }
}

pub struct ZonalMemory {
    buffer: EphemeralBuffer,
    fog: Arc<parking_lot::RwLock<GrayFog>>,
    _dream_handle: tokio::task::JoinHandle<()>,
}

impl ZonalMemory {
    pub fn new(
        buffer_capacity: usize,
        max_tokens_per_entry: i64,
        jaccard_threshold: f64,
        cycle_interval_ms: u64,
    ) -> Self {
        let (tx, rx) = tokio::sync::mpsc::channel(buffer_capacity);
        let buffer = EphemeralBuffer::new(tx);
        let fog = Arc::new(parking_lot::RwLock::new(GrayFog::new()));

        let ops = CartographicOperators::new(max_tokens_per_entry, jaccard_threshold);
        let dream_handle = AutoDream::spawn(rx, Arc::clone(&fog), ops, cycle_interval_ms);

        Self {
            buffer,
            fog,
            _dream_handle: dream_handle,
        }
    }

    pub fn write(&self, obs: RawObservation) -> bool {
        self.buffer.write(obs)
    }

    pub fn project(&self, token_budget: i64) -> Vec<ConsolidatedEntry> {
        let guard = self.fog.read();

        let mut entries: Vec<&ConsolidatedEntry> =
            guard.layers.values().flat_map(|v| v.iter()).collect();

        entries.sort_by(|a, b| {
            b.confidence
                .partial_cmp(&a.confidence)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        let mut result = Vec::new();
        let mut tokens_used = 0i64;

        for entry in entries {
            if tokens_used + entry.token_count <= token_budget {
                result.push(entry.clone());
                tokens_used += entry.token_count;
            }
        }

        result
    }

    pub fn fog_snapshot(&self) -> GrayFog {
        let guard = self.fog.read();
        GrayFog {
            layers: guard.layers.clone(),
        }
    }

    pub fn get_by_ids(&self, ids: &[Uuid]) -> Vec<ConsolidatedEntry> {
        let guard = self.fog.read();
        guard
            .layers
            .values()
            .flat_map(|v| v.iter())
            .filter(|e| ids.contains(&e.id))
            .cloned()
            .collect()
    }

    pub fn with_fog(gray_fog: GrayFog, buffer_capacity: usize) -> Self {
        let (tx, rx) = tokio::sync::mpsc::channel(buffer_capacity);
        let buffer = EphemeralBuffer::new(tx);
        let fog = Arc::new(parking_lot::RwLock::new(gray_fog));

        let ops = CartographicOperators::new(100, 0.9);
        let dream_handle = AutoDream::spawn(rx, Arc::clone(&fog), ops, 100);

        Self {
            buffer,
            fog,
            _dream_handle: dream_handle,
        }
    }
}
