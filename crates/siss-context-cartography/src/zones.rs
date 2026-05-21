//! Tripartite Zonal Model for context governance
//!
//! Classifies memory entries into three zones:
//! - VisibleField: within budget, above confidence threshold, immediately accessible
//! - GrayFog: above confidence but cut by token budget (known-to-exist but obscured)
//! - BlackFog: below confidence threshold, permanently excluded (no content surfaced)

use crate::types::MemoryEntry;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ZoneClass {
    VisibleField,
    GrayFog,
    BlackFog,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZonalContextMap {
    pub visible: Vec<MemoryEntry>,
    pub gray_fog: Vec<MemoryEntry>,
    pub black_fog_count: usize,
    pub token_budget_used: i64,
    pub token_budget_total: i64,
}

/// Classify memory entries into zones based on confidence threshold and budget constraints.
///
/// Invariant: visible.len() + gray_fog.len() + black_fog_count == all_candidates.len()
pub fn classify_zones(
    all_candidates: Vec<MemoryEntry>,
    visible: Vec<MemoryEntry>,
    confidence_threshold: f64,
    token_budget: i64,
    budget_used: i64,
) -> ZonalContextMap {
    let visible_ids: HashSet<uuid::Uuid> = visible.iter().map(|e| e.memory_id).collect();

    let mut gray_fog = Vec::new();
    let mut black_fog_count = 0usize;

    for entry in all_candidates {
        if entry.confidence_score < confidence_threshold {
            black_fog_count += 1;
        } else if visible_ids.contains(&entry.memory_id) {
            // Entry is already in visible, skip (will be in visible vec)
        } else {
            gray_fog.push(entry);
        }
    }

    ZonalContextMap {
        visible,
        gray_fog,
        black_fog_count,
        token_budget_used: budget_used,
        token_budget_total: token_budget,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use siss_graph_core::node::memory::ConsolidationTier;
    use uuid::Uuid;

    fn make_entry(content: &str, confidence: f64, tier: ConsolidationTier) -> MemoryEntry {
        MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: content.into(),
            confidence_score: confidence,
            tier,
        }
    }

    #[test]
    fn test_entries_within_budget_above_threshold_land_in_visible_field() {
        let entries = vec![
            make_entry("proc", 0.9, ConsolidationTier::Procedural),
            make_entry("sem", 0.9, ConsolidationTier::Semantic),
            make_entry("epi", 0.9, ConsolidationTier::Episodic),
        ];
        let visible = entries.clone();

        let map = classify_zones(entries, visible, 0.1, 1000, 3);

        assert_eq!(map.visible.len(), 3);
        assert_eq!(map.gray_fog.len(), 0);
        assert_eq!(map.black_fog_count, 0);
    }

    #[test]
    fn test_budget_cut_entries_land_in_gray_fog() {
        let entries = vec![
            make_entry("a", 0.9, ConsolidationTier::Semantic),
            make_entry("b", 0.9, ConsolidationTier::Semantic),
            make_entry("c", 0.9, ConsolidationTier::Semantic),
            make_entry("d", 0.9, ConsolidationTier::Semantic),
            make_entry("e", 0.9, ConsolidationTier::Semantic),
        ];
        let visible = entries[..2].to_vec();

        let map = classify_zones(entries, visible, 0.1, 1000, 4);

        assert_eq!(map.visible.len(), 2);
        assert_eq!(map.gray_fog.len(), 3);
        assert_eq!(map.black_fog_count, 0);
    }

    #[test]
    fn test_below_threshold_entries_are_black_fog() {
        let below_threshold = vec![
            make_entry("x", 0.05, ConsolidationTier::Semantic),
            make_entry("y", 0.05, ConsolidationTier::Semantic),
            make_entry("z", 0.05, ConsolidationTier::Semantic),
        ];
        let above_threshold = vec![
            make_entry("a", 0.9, ConsolidationTier::Semantic),
            make_entry("b", 0.9, ConsolidationTier::Semantic),
        ];

        let mut all_candidates = below_threshold;
        all_candidates.extend(above_threshold.clone());

        let map = classify_zones(all_candidates, above_threshold, 0.1, 1000, 4);

        assert_eq!(map.visible.len(), 2);
        assert_eq!(map.gray_fog.len(), 0);
        assert_eq!(map.black_fog_count, 3);
    }

    #[test]
    fn test_invariant_zones_partition_all_candidates() {
        let below = vec![
            make_entry("b1", 0.05, ConsolidationTier::Semantic),
            make_entry("b2", 0.05, ConsolidationTier::Semantic),
            make_entry("b3", 0.05, ConsolidationTier::Semantic),
        ];
        let above_visible = vec![
            make_entry("v1", 0.9, ConsolidationTier::Semantic),
            make_entry("v2", 0.9, ConsolidationTier::Semantic),
            make_entry("v3", 0.9, ConsolidationTier::Semantic),
        ];
        let above_gray = vec![
            make_entry("g1", 0.8, ConsolidationTier::Semantic),
            make_entry("g2", 0.8, ConsolidationTier::Semantic),
            make_entry("g3", 0.8, ConsolidationTier::Semantic),
            make_entry("g4", 0.8, ConsolidationTier::Semantic),
        ];

        let mut all = below.clone();
        all.extend(above_visible.clone());
        all.extend(above_gray.clone());

        let map = classify_zones(all.clone(), above_visible, 0.1, 10000, 9);

        assert_eq!(
            map.visible.len() + map.gray_fog.len() + map.black_fog_count,
            all.len()
        );
        assert_eq!(map.visible.len(), 3);
        assert_eq!(map.gray_fog.len(), 4);
        assert_eq!(map.black_fog_count, 3);
    }

    #[test]
    fn test_black_fog_exposes_no_content() {
        let black = vec![make_entry("secret", 0.0, ConsolidationTier::Semantic)];
        let visible = vec![];

        let map = classify_zones(black, visible, 0.1, 1000, 0);

        assert_eq!(map.black_fog_count, 1);
        // Struct-level check: ZonalContextMap has no field that exposes black fog content
        assert!(map.visible.is_empty());
        assert!(map.gray_fog.is_empty());
    }
}
