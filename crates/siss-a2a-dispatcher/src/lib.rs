pub mod packager;

pub use packager::{ContextPackager, A2APayload};

#[cfg(test)]
mod tests {
    use super::*;
    use siss_memory_plane::operators::{CartographicOperatorSet, AnnotatedEntry, ProjectedEntry};
    use siss_context_cartography::types::MemoryEntry;
    use siss_graph_core::node::memory::ConsolidationTier;
    use uuid::Uuid;

    #[test]
    fn test_lambda_layer_excludes_foreign_namespace() {
        let ops = CartographicOperatorSet::new(0.5, 0.7, 100);

        let projected = vec![
            ProjectedEntry {
                memory_id: Uuid::new_v4(),
                content: "entry 1".to_string(),
                confidence_score: 0.9,
                relational_links: vec![],
                namespace: Some("ns1".to_string()),
            },
            ProjectedEntry {
                memory_id: Uuid::new_v4(),
                content: "entry 2".to_string(),
                confidence_score: 0.8,
                relational_links: vec![],
                namespace: Some("ns2".to_string()),
            },
            ProjectedEntry {
                memory_id: Uuid::new_v4(),
                content: "entry 3".to_string(),
                confidence_score: 0.7,
                relational_links: vec![],
                namespace: None,
            },
        ];

        let filtered = ops.lambda_layer(projected, "ns1");

        assert_eq!(filtered.len(), 1);
        assert_eq!(filtered[0].namespace, Some("ns1".to_string()));
    }

    #[test]
    fn test_pi_project_preserves_relational_links() {
        let ops = CartographicOperatorSet::new(0.5, 0.7, 100);

        let link_id = Uuid::new_v4();
        let entry = AnnotatedEntry {
            entry: MemoryEntry {
                memory_id: Uuid::new_v4(),
                content: "test content".to_string(),
                confidence_score: 0.85,
                tier: ConsolidationTier::Semantic,
                affective_signature: None,
            },
            entity_links: vec![(link_id, "reference".to_string())],
            namespace: Some("test".to_string()),
            is_critical_constraint: false,
        };

        let projected = ops.pi_project(entry);

        assert_eq!(projected.relational_links.len(), 1);
        assert_eq!(projected.relational_links[0].0, link_id);
        assert_eq!(projected.relational_links[0].1, "reference".to_string());
    }

    #[test]
    fn test_package_respects_token_budget() {
        let ops = CartographicOperatorSet::new(0.5, 0.7, 100);
        let packager = ContextPackager::new(ops);

        let mut annotated = vec![];
        for i in 0..10 {
            annotated.push(AnnotatedEntry {
                entry: MemoryEntry {
                    memory_id: Uuid::new_v4(),
                    content: format!("entry {}", i),
                    confidence_score: 0.8,
                    tier: ConsolidationTier::Semantic,
                    affective_signature: None,
                },
                entity_links: vec![],
                namespace: Some("test".to_string()),
                is_critical_constraint: false,
            });
        }

        let payload = packager.package(annotated, "test", 5);

        assert_eq!(payload.token_budget_used, 5);
        assert_eq!(payload.entries.len(), 5);
        assert!(packager.is_within_budget(&payload, 5));
        assert!(!packager.is_within_budget(&payload, 4));
    }
}
