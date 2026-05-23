use chrono::{DateTime, Utc};
use siss_graph_core::node::memory::EpisodicMemory;
use uuid::Uuid;

pub struct WorkingObservation {
    pub id: Uuid,
    pub content: String,
    pub confidence: f64,
    pub observed_at: DateTime<Utc>,
    pub contradicts_id: Option<Uuid>,
}

impl WorkingObservation {
    pub fn new(content: impl Into<String>, confidence: f64) -> Self {
        WorkingObservation {
            id: Uuid::new_v4(),
            content: content.into(),
            confidence,
            observed_at: Utc::now(),
            contradicts_id: None,
        }
    }

    pub fn with_contradiction(mut self, id: Uuid) -> Self {
        self.contradicts_id = Some(id);
        self
    }
}

pub struct SupersessionRecord {
    pub superseding_id: Uuid,
    pub deprecated_id: Uuid,
    pub deprecated_confidence_after: f64,
}

pub struct ConsolidationPipeline {
    pub compression_ratio: f64,
    pub gc_threshold: f64,
}

impl ConsolidationPipeline {
    pub fn new(compression_ratio: f64, gc_threshold: f64) -> Self {
        ConsolidationPipeline { compression_ratio, gc_threshold }
    }

    pub fn compress_to_episodic(
        &self,
        observations: Vec<WorkingObservation>,
    ) -> Vec<EpisodicMemory> {
        if observations.is_empty() {
            return Vec::new();
        }

        let target_groups = ((observations.len() as f64 * self.compression_ratio).ceil()) as usize;
        let group_size = (observations.len() as f64 / target_groups as f64).ceil() as usize;
        let mut result = Vec::new();
        let tenant = siss_graph_core::node::NodeId::new();

        for chunk in observations.chunks(group_size) {
            if let Some(best) = chunk.iter().max_by(|a, b| a.confidence.partial_cmp(&b.confidence).unwrap()) {
                result.push(siss_graph_core::node::memory::EpisodicMemory::new(
                    best.content.clone(),
                    best.confidence,
                    tenant,
                ));
            }
        }
        result
    }

    pub fn apply_supersession(
        &self,
        new_obs: &[WorkingObservation],
        existing: &mut Vec<EpisodicMemory>,
    ) -> Vec<SupersessionRecord> {
        let mut records = Vec::new();
        for obs in new_obs {
            if let Some(contradicts_id) = obs.contradicts_id {
                for entry in existing.iter_mut() {
                    if entry.id.0 == contradicts_id {
                        let deprecated_confidence_after = entry.confidence_score * 0.5;
                        records.push(SupersessionRecord {
                            superseding_id: obs.id,
                            deprecated_id: contradicts_id,
                            deprecated_confidence_after,
                        });
                        entry.confidence_score = deprecated_confidence_after;
                        break;
                    }
                }
            }
        }
        records
    }

    pub fn is_gc_eligible_episodic(
        &self,
        initial_confidence: f64,
        last_reinforced_at: DateTime<Utc>,
    ) -> bool {
        let decayed = siss_graph_core::node::memory::compute_decay(
            initial_confidence,
            last_reinforced_at,
            siss_graph_core::node::memory::ConsolidationTier::Episodic,
        );
        siss_graph_core::node::memory::is_gc_eligible(decayed, self.gc_threshold)
    }

    pub fn run(
        &self,
        observations: Vec<WorkingObservation>,
        _existing: &mut Vec<EpisodicMemory>,
    ) -> (Vec<EpisodicMemory>, Vec<SupersessionRecord>) {
        let compressed = self.compress_to_episodic(observations);
        let mut result = compressed;
        let supersessions = self.apply_supersession(&[], &mut result);
        (result, supersessions)
    }
}
