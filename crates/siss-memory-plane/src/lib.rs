//! SISS Memory Plane: Memory zone governance and access control
//!
//! Implements the tripartite zonal model with enforcement mechanisms
//! for BlackFog, GrayFog, and VisibleField memory classifications.

pub mod consolidation;
pub mod hybrid_search;
pub mod operators;
pub mod zone_guard;

pub use consolidation::{ConsolidationPipeline, SupersessionRecord, WorkingObservation};
pub use hybrid_search::{BM25Scorer, Corpus, HybridSearchEngine, RrfFuser, SearchResult};
pub use operators::{AnnotatedEntry, CartographicOperatorSet, ProjectedEntry};
pub use zone_guard::{ZoneAccessGuard, ZoneTransition, ZoneViolation};

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use uuid::Uuid;

    #[test]
    fn test_black_fog_raw_data_rejected_from_visible_field() {
        let guard = ZoneAccessGuard::new(0.1);
        let result = guard.check_transition(ZoneTransition::BlackFogToVisible);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err(), ZoneViolation::BlackFogBypass);
    }

    #[test]
    fn test_gray_fog_below_confidence_threshold_blocked() {
        let guard = ZoneAccessGuard::new(0.1);
        let result = guard.check_transition(ZoneTransition::GrayFogToVisible { confidence: 0.05 });
        assert!(result.is_err());
        assert_eq!(
            result.unwrap_err(),
            ZoneViolation::BelowThreshold(0.05, 0.1)
        );
    }

    #[test]
    fn test_valid_gray_fog_above_threshold_allowed() {
        let guard = ZoneAccessGuard::new(0.1);
        let result = guard.check_transition(ZoneTransition::GrayFogToVisible { confidence: 0.85 });
        assert!(result.is_ok());
    }

    #[test]
    fn test_displacement_moves_critical_constraint_to_index_zero() {
        use siss_context_cartography::types::MemoryEntry;
        use siss_graph_core::node::memory::ConsolidationTier;

        let constraint_id = Uuid::new_v4();
        let ops = CartographicOperatorSet::new(0.5, 0.7, 100);

        let entries = vec![
            MemoryEntry {
                memory_id: Uuid::new_v4(),
                content: "entry 0".to_string(),
                confidence_score: 0.8,
                tier: ConsolidationTier::Semantic,
                affective_signature: None,
            },
            MemoryEntry {
                memory_id: Uuid::new_v4(),
                content: "entry 1".to_string(),
                confidence_score: 0.8,
                tier: ConsolidationTier::Semantic,
                affective_signature: None,
            },
            MemoryEntry {
                memory_id: Uuid::new_v4(),
                content: "entry 2".to_string(),
                confidence_score: 0.8,
                tier: ConsolidationTier::Semantic,
                affective_signature: None,
            },
            MemoryEntry {
                memory_id: constraint_id,
                content: "constraint".to_string(),
                confidence_score: 0.95,
                tier: ConsolidationTier::Semantic,
                affective_signature: None,
            },
            MemoryEntry {
                memory_id: Uuid::new_v4(),
                content: "entry 4".to_string(),
                confidence_score: 0.8,
                tier: ConsolidationTier::Semantic,
                affective_signature: None,
            },
        ];

        let displaced = ops.delta_displace(entries, constraint_id);

        assert_eq!(displaced.len(), 5);
        assert_eq!(displaced[0].memory_id, constraint_id);
    }

    #[test]
    fn test_projection_preserves_relational_edges_across_boundary() {
        use siss_context_cartography::types::MemoryEntry;
        use siss_graph_core::node::memory::ConsolidationTier;

        let related_id = Uuid::new_v4();
        let ops = CartographicOperatorSet::new(0.5, 0.7, 100);

        let memory_entry = MemoryEntry {
            memory_id: Uuid::new_v4(),
            content: "test content".to_string(),
            confidence_score: 0.9,
            tier: ConsolidationTier::Semantic,
            affective_signature: None,
        };

        let annotated = AnnotatedEntry {
            entry: memory_entry,
            entity_links: vec![(related_id, "Supports".to_string())],
            namespace: Some("test".to_string()),
            is_critical_constraint: false,
        };

        let projected = ops.pi_project(annotated);

        assert_eq!(projected.relational_links.len(), 1);
        assert_eq!(
            projected.relational_links[0],
            (related_id, "Supports".to_string())
        );
    }

    #[test]
    fn test_layering_prevents_namespace_bleed() {
        let ops = CartographicOperatorSet::new(0.5, 0.7, 100);

        let entries = vec![
            ProjectedEntry {
                memory_id: Uuid::new_v4(),
                content: "audit 1".to_string(),
                confidence_score: 0.9,
                relational_links: vec![],
                namespace: Some("audit".to_string()),
            },
            ProjectedEntry {
                memory_id: Uuid::new_v4(),
                content: "reasoning 1".to_string(),
                confidence_score: 0.9,
                relational_links: vec![],
                namespace: Some("reasoning".to_string()),
            },
            ProjectedEntry {
                memory_id: Uuid::new_v4(),
                content: "audit 2".to_string(),
                confidence_score: 0.9,
                relational_links: vec![],
                namespace: Some("audit".to_string()),
            },
        ];

        let filtered = ops.lambda_layer(entries, "audit");

        assert_eq!(filtered.len(), 2);
        for entry in filtered {
            assert_eq!(entry.namespace, Some("audit".to_string()));
        }
    }

    #[test]
    fn test_working_observations_compress_to_episodic_summaries() {
        let pipeline = ConsolidationPipeline::new(0.5, 0.3);
        let observations = vec![
            WorkingObservation::new("obs1", 0.5),
            WorkingObservation::new("obs2", 0.6),
            WorkingObservation::new("obs3", 0.4),
            WorkingObservation::new("obs4", 0.7),
            WorkingObservation::new("obs5", 0.55),
            WorkingObservation::new("obs6", 0.65),
            WorkingObservation::new("obs7", 0.45),
            WorkingObservation::new("obs8", 0.75),
            WorkingObservation::new("obs9", 0.5),
            WorkingObservation::new("obs10", 0.6),
        ];
        let result = pipeline.compress_to_episodic(observations);
        assert!(
            result.len() <= 5,
            "Expected at most 5 compressed summaries, got {}",
            result.len()
        );
    }

    #[test]
    fn test_supersession_marks_contradicting_fact_deprecated() {
        use siss_graph_core::node::NodeId;

        let mut existing = vec![siss_graph_core::node::memory::EpisodicMemory::new(
            "old fact".to_string(),
            0.8,
            NodeId::new(),
        )];
        let old_node_id = existing[0].id;
        let old_uuid = old_node_id.0;

        let new_obs = vec![WorkingObservation::new("new fact", 0.9).with_contradiction(old_uuid)];

        let pipeline = ConsolidationPipeline::new(0.5, 0.3);
        let records = pipeline.apply_supersession(&new_obs, &mut existing);

        assert_eq!(records.len(), 1);
        assert!(
            (records[0].deprecated_confidence_after - 0.4).abs() < 0.01,
            "Expected deprecated_confidence_after ≈ 0.4, got {}",
            records[0].deprecated_confidence_after
        );
    }

    #[test]
    fn test_ebbinghaus_gc_eligibility_at_30_days_episodic() {
        let pipeline = ConsolidationPipeline::new(0.5, 0.3);
        let thirty_days_ago = Utc::now() - chrono::Duration::days(30);
        let is_eligible = pipeline.is_gc_eligible_episodic(0.9, thirty_days_ago);
        assert!(
            is_eligible,
            "Expected 30-day-old episodic memory to be GC eligible"
        );
    }

    #[test]
    fn test_bm25_ranks_exact_keyword_match_above_noise() {
        let doc_a = Uuid::new_v4();
        let doc_b = Uuid::new_v4();
        let corpus = Corpus::new(vec![
            (doc_a, "sovereign agent overview".to_string()),
            (doc_b, "unrelated topic noise".to_string()),
        ]);

        let scorer = BM25Scorer::build(&corpus);
        let results = scorer.score("sovereign");

        assert!(!results.is_empty());
        assert_eq!(results[0].0, doc_a);
        assert!(results[0].1 > results[1].1);
    }

    #[test]
    fn test_rrf_fusion_of_three_rankers_returns_consistent_ordering() {
        let top_doc = Uuid::new_v4();
        let doc_b = Uuid::new_v4();
        let doc_c = Uuid::new_v4();

        let ranked_list_1 = vec![top_doc, doc_b, doc_c];
        let ranked_list_2 = vec![top_doc, doc_c, doc_b];
        let ranked_list_3 = vec![top_doc, doc_b, doc_c];

        let fuser = RrfFuser::new(60);
        let results = fuser.fuse(vec![ranked_list_1, ranked_list_2, ranked_list_3]);

        assert!(!results.is_empty());
        assert_eq!(results[0].id, top_doc);
        assert!(results[0].rrf_score > results[1].rrf_score);
    }

    #[test]
    fn test_graph_traversal_extends_results_through_supports_edge() {
        let id_a = Uuid::new_v4();
        let id_b = Uuid::new_v4();

        let mut reachability = siss_graph_core::reachability::ReachabilityCache::new();
        reachability.add_edge(id_a, id_b);

        let corpus = Corpus::new(vec![
            (id_a, "test a".to_string()),
            (id_b, "test b".to_string()),
        ]);
        let mut engine = HybridSearchEngine::new(corpus, reachability);
        let expanded = engine.expand_via_graph(&[id_a], &[id_a, id_b]);

        assert!(expanded.contains(&id_a));
        assert!(expanded.contains(&id_b));
    }
}
