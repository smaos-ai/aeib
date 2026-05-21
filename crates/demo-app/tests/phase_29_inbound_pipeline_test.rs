/// Phase 29 Integration Test Suite — Inbound Pipeline & TaskContext Wiring
///
/// TDD Red Phase: All 6 tests verify that the cartographic operators (σ, ϕ, π⁺)
/// are correctly applied before data enters TaskContext, and the wiring from
/// AgentSession → RoutingRequest → TaskContext preserves zonal information.

use siss_context_cartography::inbound::{apply_inbound_pipeline, project_to_task_context};
use siss_context_cartography::types::MemoryEntry;
use siss_graph_core::node::memory::ConsolidationTier;
use uuid::Uuid;
use futures::future::join_all;

// ============================================================================
// TEST UTILITIES
// ============================================================================

fn make_entry(content: &str, confidence: f64, tier: ConsolidationTier) -> MemoryEntry {
    MemoryEntry {
        memory_id: Uuid::new_v4(),
        content: content.into(),
        confidence_score: confidence,
        tier,
    }
}

// ============================================================================
// ACCEPTANCE TESTS (RED PHASE)
// ============================================================================

#[test]
fn test_apply_inbound_pipeline_all_operators_in_sequence() {
    let below_threshold = vec![
        make_entry("unreliable1", 0.05, ConsolidationTier::Semantic),
        make_entry("unreliable2", 0.05, ConsolidationTier::Semantic),
    ];
    let above_visible = vec![
        make_entry("visible1", 0.9, ConsolidationTier::Semantic),
        make_entry("visible2", 0.9, ConsolidationTier::Semantic),
    ];
    let above_gray = vec![
        make_entry("gray1", 0.8, ConsolidationTier::Semantic),
    ];

    let mut all_candidates = below_threshold;
    all_candidates.extend(above_visible.clone());
    all_candidates.extend(above_gray.clone());

    let map = apply_inbound_pipeline(all_candidates, above_visible, 0.1, 10000, 4);

    assert_eq!(map.visible.len(), 2, "σ/ϕ: only above-threshold + budgeted entries");
    assert_eq!(map.gray_fog.len(), 1, "ϕ: budget-cut entries in gray fog");
    assert_eq!(map.black_fog_count, 2, "σ: below-threshold entries in black fog");
}

#[test]
fn test_project_to_task_context_serializes_zonal_map() {
    let entries = vec![
        make_entry("proc", 0.9, ConsolidationTier::Procedural),
        make_entry("sem", 0.9, ConsolidationTier::Semantic),
    ];
    let visible = entries.clone();

    let map = apply_inbound_pipeline(entries, visible, 0.1, 1000, 2);
    let json = project_to_task_context(&map);

    assert!(json.is_object(), "projected value must be a JSON object");
    let obj = json.as_object().unwrap();
    assert!(obj.contains_key("visible"), "JSON must have 'visible' key");
    assert!(obj.contains_key("black_fog_count"), "JSON must have 'black_fog_count' key");

    // Verify round-trip: deserialize back and check counts
    if let Ok(deserialized) = serde_json::from_value::<serde_json::Value>(json.clone()) {
        let visible_count = deserialized
            .get("visible")
            .and_then(|v| v.as_array())
            .map(|v| v.len())
            .unwrap_or(0);
        assert_eq!(visible_count, 2, "round-trip preserves visible count");
    }
}

#[test]
fn test_no_below_threshold_entry_enters_visible_field() {
    let below = vec![
        make_entry("secret1", 0.01, ConsolidationTier::Semantic),
        make_entry("secret2", 0.02, ConsolidationTier::Semantic),
        make_entry("secret3", 0.03, ConsolidationTier::Semantic),
    ];
    let above = vec![
        make_entry("public1", 0.95, ConsolidationTier::Semantic),
        make_entry("public2", 0.95, ConsolidationTier::Semantic),
    ];

    let mut all_candidates = below.clone();
    all_candidates.extend(above.clone());

    let map = apply_inbound_pipeline(all_candidates, above, 0.1, 10000, 4);

    assert_eq!(
        map.visible.len(),
        2,
        "only above-threshold entries visible"
    );
    assert_eq!(
        map.black_fog_count, 3,
        "σ operator filters all below-threshold to black fog"
    );

    // Verify no below-threshold entry leaks into visible
    for entry in &map.visible {
        assert!(
            entry.confidence_score >= 0.1,
            "visible entry must pass confidence threshold"
        );
    }
}

#[test]
fn test_no_budget_overflow_enters_visible_field() {
    let entries: Vec<MemoryEntry> = (0..10)
        .map(|i| make_entry(&format!("entry_{}", i), 0.9, ConsolidationTier::Semantic))
        .collect();

    let budget = 1000;
    let visible = entries[..3].to_vec(); // Only 3 entries fit budget

    let map = apply_inbound_pipeline(entries.clone(), visible, 0.1, budget, 100);

    assert_eq!(map.visible.len(), 3, "ϕ: only budgeted entries visible");
    assert_eq!(map.gray_fog.len(), 7, "ϕ: overflow entries in gray fog");
    assert_eq!(
        map.token_budget_used, 100,
        "token budget used must match input"
    );
}

#[test]
fn test_routing_request_carries_zonal_context() {
    use siss_job_router::types::RoutingRequest;
    use siss_graph_core::node::NodeId;

    let entries = vec![
        make_entry("task_entry", 0.9, ConsolidationTier::Semantic),
    ];
    let map = apply_inbound_pipeline(entries.clone(), entries, 0.1, 1000, 1);
    let zonal_json = project_to_task_context(&map);

    let request = RoutingRequest {
        task_id: NodeId(Uuid::new_v4()),
        persona_id: NodeId(Uuid::new_v4()),
        tenant_id: NodeId(Uuid::new_v4()),
        depends_on: vec![],
        zonal_context: Some(zonal_json.clone()),
    };

    // Serialize and deserialize to verify serde round-trip
    let json_str = serde_json::to_string(&request).expect("serialize request");
    let restored: RoutingRequest =
        serde_json::from_str(&json_str).expect("deserialize request");

    assert!(
        restored.zonal_context.is_some(),
        "zonal_context field must survive round-trip"
    );
    assert_eq!(
        restored.zonal_context.as_ref().unwrap(),
        &zonal_json,
        "zonal_context must be identical after round-trip"
    );
}

#[tokio::test]
async fn test_concurrent_inbound_pipelines_no_cross_contamination() {
    let mut handles = vec![];

    for task_id in 0..10 {
        let handle = tokio::spawn(async move {
            // Each task creates independent entries
            let entries: Vec<MemoryEntry> = (0..5)
                .map(|i| {
                    make_entry(
                        &format!("task_{}_entry_{}", task_id, i),
                        0.9,
                        ConsolidationTier::Semantic,
                    )
                })
                .collect();

            // Vary budget per task
            let budget = 100 + (task_id as i64) * 50;
            let visible_count = if budget < 200 { 1 } else { 5 };
            let visible = entries[..visible_count.min(entries.len())].to_vec();

            apply_inbound_pipeline(entries.clone(), visible, 0.1, budget, 50)
        });
        handles.push(handle);
    }

    let results = join_all(handles).await;

    // Verify each task got independent results
    for (task_id, result) in results.iter().enumerate() {
        let map = result.as_ref().unwrap();

        let expected_visible = if (100 + (task_id as i64) * 50) < 200 {
            1
        } else {
            5
        };
        assert_eq!(
            map.visible.len(),
            expected_visible.min(5),
            "task {} has correct visible count",
            task_id
        );

        // Invariant: zones partition all candidates (5 entries per task)
        assert_eq!(
            map.visible.len() + map.gray_fog.len() + map.black_fog_count,
            5,
            "task {} zones partition 5 candidates",
            task_id
        );
    }
}
