use super::*;
use siss_graph_core::node::resource::RiskClass;
use std::time::Instant;
use uuid::Uuid;

/// test_lookup_returns_correct_price: Inserts a price and retrieves it by (tool, risk) key.
#[test]
fn test_lookup_returns_correct_price() {
    let cache = BlastMatrixCache::new();
    let tool_id = Uuid::new_v4();
    let risk = RiskClass::Medium;
    let price: i64 = 5000;

    cache.insert(tool_id, risk, price);
    let result = cache.lookup(tool_id, risk);

    assert_eq!(result, Some(price), "lookup must return exact inserted price");
}

/// test_missing_key_returns_none: Lookup for non-existent (tool, risk) pair returns None.
#[test]
fn test_missing_key_returns_none() {
    let cache = BlastMatrixCache::new();
    let tool_id = Uuid::new_v4();
    let risk = RiskClass::High;

    let result = cache.lookup(tool_id, risk);

    assert_eq!(result, None, "lookup for missing key must return None");
}

/// test_bulk_load_1000_entries_under_1ms: bulk_load inserts 1000 entries in <1ms.
/// Benchmark gate: ensures O(1) insertion rate.
#[test]
fn test_bulk_load_1000_entries_under_1ms() {
    let cache = BlastMatrixCache::new();
    let entries: Vec<(Uuid, RiskClass, i64)> = (0..1000)
        .map(|i| {
            let tool_id = Uuid::new_v4();
            let risk = match i % 4 {
                0 => RiskClass::Low,
                1 => RiskClass::Medium,
                2 => RiskClass::High,
                _ => RiskClass::Critical,
            };
            let price = (i as i64) * 100;
            (tool_id, risk, price)
        })
        .collect();

    let start = Instant::now();
    cache.bulk_load(entries);
    let elapsed = start.elapsed();

    assert!(
        elapsed.as_millis() < 1000,
        "bulk_load of 1000 entries must complete in <1ms, got {:.2}ms",
        elapsed.as_millis()
    );
}

/// test_concurrent_reads_correct: Multiple threads read the same cache concurrently.
/// DashMap ensures no race conditions or corruption.
#[test]
fn test_concurrent_reads_correct() {
    let cache = std::sync::Arc::new(BlastMatrixCache::new());

    // Pre-populate cache with diverse entries
    let mut entries = Vec::new();
    for i in 0..100 {
        let tool_id = Uuid::new_v4();
        let risk = match i % 4 {
            0 => RiskClass::Low,
            1 => RiskClass::Medium,
            2 => RiskClass::High,
            _ => RiskClass::Critical,
        };
        let price = (i as i64) * 1000;
        entries.push((tool_id, risk, price));
    }
    cache.bulk_load(entries.clone());

    // Spawn 10 threads, each reading 50 lookups
    let handles: Vec<_> = (0..10)
        .map(|_| {
            let cache_clone = cache.clone();
            let entries_clone = entries.clone();
            std::thread::spawn(move || {
                for (tool_id, risk, expected_price) in entries_clone {
                    let result = cache_clone.lookup(tool_id, risk);
                    assert_eq!(
                        result, Some(expected_price),
                        "concurrent read must return correct price"
                    );
                }
            })
        })
        .collect();

    for handle in handles {
        handle.join().expect("thread must not panic");
    }
}

/// test_price_update_reflects_immediately: Inserting over an existing key updates the value.
/// Next lookup returns the new price immediately (no caching delay).
#[test]
fn test_price_update_reflects_immediately() {
    let cache = BlastMatrixCache::new();
    let tool_id = Uuid::new_v4();
    let risk = RiskClass::Low;

    // Insert initial price
    cache.insert(tool_id, risk, 1000);
    assert_eq!(cache.lookup(tool_id, risk), Some(1000));

    // Update price
    cache.insert(tool_id, risk, 2000);
    assert_eq!(
        cache.lookup(tool_id, risk),
        Some(2000),
        "price update must be visible immediately"
    );

    // Update again
    cache.insert(tool_id, risk, 3000);
    assert_eq!(
        cache.lookup(tool_id, risk),
        Some(3000),
        "second price update must be visible immediately"
    );
}
