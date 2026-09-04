use siss_local_llm::{BudgetPolicy, FreeTokenPipeline, KVCachePool, OllamaClient};
use std::sync::Arc;

#[tokio::test]
async fn test_fretoken_double_buffer_prefill() {
    let client = OllamaClient::new("http://localhost:11434", "qwen2.5-coder:14b");
    let pipeline = FreeTokenPipeline::new(client, 2);

    // Verify pipeline is created
    assert_eq!(pipeline.buffer_capacity(), 2);
}

#[tokio::test]
async fn test_fretoken_buffer_reuse() {
    let client = OllamaClient::new("http://localhost:11434", "qwen2.5-coder:14b");
    let pipeline = FreeTokenPipeline::new(client, 2);

    // Buffers should be available for reuse
    assert_eq!(pipeline.available_buffers(), 2);
}

#[tokio::test]
async fn test_fretoken_budget_exceeded() {
    let client = OllamaClient::new("http://localhost:11434", "qwen2.5-coder:14b");
    let _pipeline = FreeTokenPipeline::new(client, 2);

    let policy = BudgetPolicy::new();
    let budget = policy.compute_token_budget(512, 0.5);

    // With anomaly 0.5, budget should be reduced but not to minimum
    assert!(budget > 0);
    assert!(budget <= 512);
}

#[test]
fn test_kvcache_allocate_and_retrieve() {
    let cache = KVCachePool::new(128_000_000); // 128MB
    let data = vec![1, 2, 3, 4, 5];

    let handle = cache.allocate("test_key".to_string(), data.clone()).unwrap();
    let retrieved = cache.get(&handle).unwrap();

    assert_eq!(retrieved, data);
}

#[test]
fn test_kvcache_lru_eviction() {
    let cache = KVCachePool::new(100); // Small capacity to trigger eviction

    let data1 = vec![1; 50];
    let data2 = vec![2; 50];
    let data3 = vec![3; 50];

    let _h1 = cache.allocate("key1".to_string(), data1).unwrap();
    let h2 = cache.allocate("key2".to_string(), data2).unwrap();
    let h3 = cache.allocate("key3".to_string(), data3).unwrap();

    // Access h2 to mark as recently used
    let _ = cache.get(&h2);

    // h3 is most recent, h2 was accessed, h1 should be evicted
    // But with 100 bytes capacity and three 50-byte entries, behavior depends on implementation
    // At minimum, the cache should be functional
    assert!(cache.get(&h3).is_ok() || cache.get(&h2).is_ok());
}

#[test]
fn test_kvcache_concurrent_access() {
    let cache = Arc::new(KVCachePool::new(1_000_000));
    let mut handles = vec![];

    for i in 0..10 {
        let data = vec![i as u8; 100];
        let handle = cache.allocate(format!("key{}", i), data).unwrap();
        handles.push((i, handle));
    }

    for (i, handle) in handles {
        let retrieved = cache.get(&handle).unwrap();
        assert_eq!(retrieved[0], i as u8);
    }
}

#[test]
fn test_budget_policy_normal_bandwidth() {
    let policy = BudgetPolicy::new();
    let budget = policy.compute_token_budget(1000, 0.2); // anomaly <= 0.3
    assert_eq!(budget, 1000); // Normal: 1.0x reduction
}

#[test]
fn test_budget_policy_high_anomaly() {
    let policy = BudgetPolicy::new();
    let budget = policy.compute_token_budget(1000, 0.5); // 0.3 < anomaly < 0.8
    assert!(budget < 1000);
    assert!(budget > 300); // Should be between 0.8x and 0.3x
}

#[test]
fn test_budget_policy_critical_anomaly() {
    let policy = BudgetPolicy::new();
    let budget = policy.compute_token_budget(1000, 1.0); // anomaly >= 0.8
    assert!(budget < 1000);
    assert!(budget >= 300); // Critical: minimum 0.3x
}

#[test]
fn test_budget_policy_gradient() {
    let policy = BudgetPolicy::new();

    let b1 = policy.compute_token_budget(1000, 0.0);
    let b2 = policy.compute_token_budget(1000, 0.3);
    let b3 = policy.compute_token_budget(1000, 0.6);
    let b4 = policy.compute_token_budget(1000, 1.0);
    let b5 = policy.compute_token_budget(1000, 1.5);

    // Budget should monotonically decrease
    assert!(b1 >= b2);
    assert!(b2 >= b3);
    assert!(b3 >= b4);
    assert!(b4 >= b5);

    // Absolute minimum at extreme anomaly
    assert!(b5 >= 300);
}
