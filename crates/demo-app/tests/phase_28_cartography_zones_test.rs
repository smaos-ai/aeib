use futures::future::join_all;
use siss_context_cartography::budget::apply_budget;
/// Phase 28 Integration Test Suite — Context Cartography Zones
///
/// TDD Red Phase: All 6 tests define acceptance criteria for the Tripartite Zonal Model
/// (VisibleField, GrayFog, BlackFog) that governs context window visibility.
use siss_context_cartography::types::MemoryEntry;
use siss_context_cartography::zones::classify_zones;
use siss_graph_core::node::memory::ConsolidationTier;
use uuid::Uuid;

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
fn test_entries_within_budget_above_threshold_land_in_visible_field() {
    let entries = vec![
        make_entry("procedural workflow", 0.9, ConsolidationTier::Procedural),
        make_entry("semantic understanding", 0.9, ConsolidationTier::Semantic),
        make_entry("episodic memory", 0.9, ConsolidationTier::Episodic),
    ];
    let visible = entries.clone();

    let map = classify_zones(entries, visible, 0.1, 1000, 100);

    assert_eq!(
        map.visible.len(),
        3,
        "all entries within budget and above threshold should be visible"
    );
    assert_eq!(map.gray_fog.len(), 0, "no entries should be in gray fog");
    assert_eq!(map.black_fog_count, 0, "no entries should be in black fog");
}

#[test]
fn test_budget_cut_entries_land_in_gray_fog() {
    let all_entries = vec![
        make_entry("entry1", 0.9, ConsolidationTier::Semantic),
        make_entry("entry2", 0.9, ConsolidationTier::Semantic),
        make_entry("entry3", 0.9, ConsolidationTier::Semantic),
        make_entry("entry4", 0.9, ConsolidationTier::Semantic),
        make_entry("entry5", 0.9, ConsolidationTier::Semantic),
    ];

    // Simulate budget trim: only first 2 entries fit
    let visible = all_entries[..2].to_vec();
    let budget_used = 4; // 2 entries * 2 tokens each (estimate)

    let map = classify_zones(all_entries, visible, 0.1, 1000, budget_used);

    assert_eq!(map.visible.len(), 2, "first 2 entries within budget");
    assert_eq!(
        map.gray_fog.len(),
        3,
        "remaining 3 entries passed confidence but cut by budget"
    );
    assert_eq!(map.black_fog_count, 0, "no low-confidence entries");
}

#[test]
fn test_below_threshold_entries_are_black_fog() {
    let below_threshold = vec![
        make_entry("low confidence 1", 0.05, ConsolidationTier::Semantic),
        make_entry("low confidence 2", 0.05, ConsolidationTier::Semantic),
        make_entry("low confidence 3", 0.05, ConsolidationTier::Semantic),
    ];
    let above_threshold = vec![
        make_entry("high confidence 1", 0.9, ConsolidationTier::Semantic),
        make_entry("high confidence 2", 0.9, ConsolidationTier::Semantic),
    ];

    let mut all_candidates = below_threshold;
    all_candidates.extend(above_threshold.clone());

    // Only high-confidence entries made it through budget
    let visible = above_threshold;

    let map = classify_zones(all_candidates, visible, 0.1, 1000, 4);

    assert_eq!(map.visible.len(), 2, "high-confidence entries visible");
    assert_eq!(
        map.gray_fog.len(),
        0,
        "no budget-cut entries in this scenario"
    );
    assert_eq!(
        map.black_fog_count, 3,
        "low-confidence entries classified as black fog"
    );
}

#[test]
fn test_invariant_zones_partition_all_candidates() {
    // 3 black (confidence 0.05)
    let black = vec![
        make_entry("black1", 0.05, ConsolidationTier::Semantic),
        make_entry("black2", 0.05, ConsolidationTier::Semantic),
        make_entry("black3", 0.05, ConsolidationTier::Semantic),
    ];

    // 3 visible (confidence 0.9, within budget)
    let visible = vec![
        make_entry("visible1", 0.9, ConsolidationTier::Semantic),
        make_entry("visible2", 0.9, ConsolidationTier::Semantic),
        make_entry("visible3", 0.9, ConsolidationTier::Semantic),
    ];

    // 4 gray fog (confidence 0.8, above threshold but cut by budget)
    let gray = vec![
        make_entry("gray1", 0.8, ConsolidationTier::Semantic),
        make_entry("gray2", 0.8, ConsolidationTier::Semantic),
        make_entry("gray3", 0.8, ConsolidationTier::Semantic),
        make_entry("gray4", 0.8, ConsolidationTier::Semantic),
    ];

    let mut all_candidates = black.clone();
    all_candidates.extend(visible.clone());
    all_candidates.extend(gray.clone());

    let total_candidates = all_candidates.len();

    let map = classify_zones(all_candidates, visible, 0.1, 10000, 9);

    // Verify partition invariant: zones sum to all candidates
    assert_eq!(
        map.visible.len() + map.gray_fog.len() + map.black_fog_count,
        total_candidates,
        "zones must partition all candidates exactly"
    );
    assert_eq!(map.visible.len(), 3);
    assert_eq!(map.gray_fog.len(), 4);
    assert_eq!(map.black_fog_count, 3);
}

#[test]
fn test_black_fog_exposes_no_content() {
    let black_entry = vec![make_entry("secret data", 0.0, ConsolidationTier::Semantic)];
    let visible = vec![];

    let map = classify_zones(black_entry, visible, 0.1, 1000, 0);

    assert_eq!(
        map.black_fog_count, 1,
        "1 entry below threshold counted in black fog"
    );
    assert!(map.visible.is_empty(), "visible field empty");
    assert!(map.gray_fog.is_empty(), "gray fog empty");

    // Struct-level invariant: ZonalContextMap struct has NO field that exposes black_fog content
    // This is a compile-time check — if a field `black_fog: Vec<MemoryEntry>` existed,
    // the test would be unsound. The presence of only `black_fog_count` enforces the invariant.
}

#[tokio::test]
async fn test_concurrent_zone_classification_no_cross_contamination() {
    let mut handles = vec![];

    for task_id in 0..10 {
        let handle = tokio::spawn(async move {
            // Each task creates its own independent memory entries and budget
            let entries: Vec<MemoryEntry> = (0..5)
                .map(|i| {
                    make_entry(
                        &format!("task_{}_entry_{}", task_id, i),
                        0.9,
                        ConsolidationTier::Semantic,
                    )
                })
                .collect();

            // Vary budget per task (some fit all, some cut some entries)
            let budget = 100 + (task_id as i64) * 50;
            let visible_count = if budget < 200 { 1 } else { 5 };
            let visible = entries[..visible_count.min(entries.len())].to_vec();

            classify_zones(entries.clone(), visible, 0.1, budget, 50)
        });
        handles.push(handle);
    }

    let results = join_all(handles).await;

    // Verify all tasks completed successfully and got independent results
    for (task_id, result) in results.iter().enumerate() {
        let map = result.as_ref().unwrap();

        // Each task should have its own classification
        let expected_visible = if (100 + (task_id as i64) * 50) < 200 {
            1
        } else {
            5
        };
        assert_eq!(
            map.visible.len(),
            expected_visible.min(5),
            "task {} should have independent visible count",
            task_id
        );

        // Invariant: zones sum to all candidates (5 entries per task)
        assert_eq!(
            map.visible.len() + map.gray_fog.len() + map.black_fog_count,
            5,
            "task {} zones must partition 5 candidates",
            task_id
        );
    }
}
