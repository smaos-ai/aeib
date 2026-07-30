use serde::{Deserialize, Serialize};
use siss_context_cartography::types::MemoryEntry;
use siss_context_cartography::zones::ZonalContextMap;
use std::collections::HashSet;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectedEntry {
    pub memory_id: Uuid,
    pub content: String,
    pub confidence_score: f64,
    pub relational_links: Vec<(Uuid, String)>,
    pub namespace: Option<String>,
}

pub struct AnnotatedEntry {
    pub entry: MemoryEntry,
    pub entity_links: Vec<(Uuid, String)>,
    pub namespace: Option<String>,
    pub is_critical_constraint: bool,
}

pub struct CartographicOperatorSet {
    pub confidence_threshold: f64,
    pub jaccard_threshold: f64,
    pub max_tokens_per_entry: usize,
}

impl CartographicOperatorSet {
    pub fn new(
        confidence_threshold: f64,
        jaccard_threshold: f64,
        max_tokens_per_entry: usize,
    ) -> Self {
        CartographicOperatorSet {
            confidence_threshold,
            jaccard_threshold,
            max_tokens_per_entry,
        }
    }

    pub fn rho_reconnaissance(&self, map: &ZonalContextMap, limit: usize) -> Vec<Uuid> {
        let mut result: Vec<Uuid> = map.gray_fog.iter().map(|entry| entry.memory_id).collect();
        result.sort_by(|a, b| {
            let conf_a = map
                .gray_fog
                .iter()
                .find(|e| e.memory_id == *a)
                .map(|e| e.confidence_score)
                .unwrap_or(0.0);
            let conf_b = map
                .gray_fog
                .iter()
                .find(|e| e.memory_id == *b)
                .map(|e| e.confidence_score)
                .unwrap_or(0.0);
            conf_b
                .partial_cmp(&conf_a)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        result.truncate(limit);
        result
    }

    pub fn sigma_selection(&self, entries: Vec<MemoryEntry>) -> Vec<MemoryEntry> {
        entries
            .into_iter()
            .filter(|e| e.confidence_score >= self.confidence_threshold)
            .collect()
    }

    pub fn phi_simplify(&self, entries: Vec<MemoryEntry>) -> Vec<MemoryEntry> {
        entries
            .into_iter()
            .map(|mut e| {
                // Check affective bypass: high valence + high arousal + high sovereign_relevance
                let should_bypass_truncation = e
                    .affective_signature
                    .as_ref()
                    .map(|sig| sig.arousal > 0.8 && sig.sovereign_relevance >= 0.7)
                    .unwrap_or(false);

                if !should_bypass_truncation {
                    let max_chars = self.max_tokens_per_entry * 4; // ~1 token = 4 chars
                    if e.content.len() > max_chars {
                        e.content.truncate(max_chars);
                    }
                }
                e
            })
            .collect()
    }

    pub fn alpha_aggregate(&self, entries: Vec<MemoryEntry>) -> Vec<MemoryEntry> {
        let mut result: Vec<MemoryEntry> = Vec::new();
        for entry in entries {
            let mut found_similar = false;
            for existing in &mut result {
                if jaccard(&entry.content, &existing.content) >= self.jaccard_threshold {
                    if entry.confidence_score > existing.confidence_score {
                        *existing = entry.clone();
                    }
                    found_similar = true;
                    break;
                }
            }
            if !found_similar {
                result.push(entry);
            }
        }
        result
    }

    pub fn pi_project(&self, entry: AnnotatedEntry) -> ProjectedEntry {
        ProjectedEntry {
            memory_id: entry.entry.memory_id,
            content: entry.entry.content,
            confidence_score: entry.entry.confidence_score,
            relational_links: entry.entity_links,
            namespace: entry.namespace,
        }
    }

    pub fn delta_displace(
        &self,
        entries: Vec<MemoryEntry>,
        constraint_id: Uuid,
    ) -> Vec<MemoryEntry> {
        let mut result = entries;
        if let Some(pos) = result.iter().position(|e| e.memory_id == constraint_id) {
            let constraint_entry = result.remove(pos);
            result.insert(0, constraint_entry);
        }
        result
    }

    pub fn lambda_layer(
        &self,
        entries: Vec<ProjectedEntry>,
        namespace: &str,
    ) -> Vec<ProjectedEntry> {
        entries
            .into_iter()
            .filter(|e| e.namespace.as_deref() == Some(namespace))
            .collect()
    }

    pub fn omega_resonate(
        &self,
        _visible: Vec<MemoryEntry>,
        gray_fog: Vec<MemoryEntry>,
        limit: usize,
    ) -> Vec<MemoryEntry> {
        // ω operator: rescue high-arousal facts from GrayFog back to VisibleField
        let mut candidates: Vec<MemoryEntry> = gray_fog
            .into_iter()
            .filter(|e| {
                e.affective_signature
                    .as_ref()
                    .map(|sig| sig.arousal > 0.8)
                    .unwrap_or(false)
            })
            .collect();

        // Sort by arousal (descending)
        candidates.sort_by(|a, b| {
            let arousal_a = a
                .affective_signature
                .as_ref()
                .map(|s| s.arousal)
                .unwrap_or(0.0);
            let arousal_b = b
                .affective_signature
                .as_ref()
                .map(|s| s.arousal)
                .unwrap_or(0.0);
            arousal_b
                .partial_cmp(&arousal_a)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        candidates.truncate(limit);
        candidates
    }
}

// Helper Jaccard function (word-level intersection / union)
fn jaccard(a: &str, b: &str) -> f64 {
    let words_a: HashSet<&str> = a.split_whitespace().collect();
    let words_b: HashSet<&str> = b.split_whitespace().collect();
    let intersection = words_a.intersection(&words_b).count() as f64;
    let union = words_a.union(&words_b).count() as f64;
    if union == 0.0 {
        0.0
    } else {
        intersection / union
    }
}
