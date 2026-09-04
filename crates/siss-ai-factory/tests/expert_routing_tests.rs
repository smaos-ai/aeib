//! Integration tests for expert router and LRU cache.

use siss_ai_factory::{ExpertRouter, ExpertDomain, ExpertCache};
use std::collections::HashMap;

#[test]
fn test_expert_router_route_hotel() {
    let router = ExpertRouter::new_default();
    let model = router.route(ExpertDomain::Hotel);
    assert_eq!(model, "qwen2.5-coder:14b");
}

#[test]
fn test_expert_router_route_glass() {
    let router = ExpertRouter::new_default();
    let model = router.route(ExpertDomain::Glass);
    assert_eq!(model, "qwen2.5-coder:14b");
}

#[test]
fn test_expert_router_route_auto() {
    let router = ExpertRouter::new_default();
    let model = router.route(ExpertDomain::Auto);
    assert_eq!(model, "qwen2.5-coder:14b");
}

#[test]
fn test_expert_router_different_domains_different_models() {
    let mut experts = HashMap::new();
    experts.insert("hotel".to_string(), "claude-3-opus:200k".to_string());
    experts.insert("glass".to_string(), "gpt-4-turbo".to_string());
    experts.insert("auto".to_string(), "llama-2-70b".to_string());

    let router = ExpertRouter::with_expert_map(experts);
    assert_eq!(router.route(ExpertDomain::Hotel), "claude-3-opus:200k");
    assert_eq!(router.route(ExpertDomain::Glass), "gpt-4-turbo");
    assert_eq!(router.route(ExpertDomain::Auto), "llama-2-70b");
}

#[test]
fn test_expert_router_custom_models() {
    let mut experts = HashMap::new();
    experts.insert("hotel".to_string(), "model-hotel-v1".to_string());
    experts.insert("glass".to_string(), "model-glass-v1".to_string());
    experts.insert("auto".to_string(), "model-auto-v1".to_string());

    let router = ExpertRouter::with_expert_map(experts);
    assert_eq!(router.route(ExpertDomain::Hotel), "model-hotel-v1");
    assert_eq!(router.route(ExpertDomain::Glass), "model-glass-v1");
    assert_eq!(router.route(ExpertDomain::Auto), "model-auto-v1");
}

#[test]
fn test_expert_router_deterministic() {
    let router = ExpertRouter::new_default();
    let route1 = router.route(ExpertDomain::Hotel);
    let route2 = router.route(ExpertDomain::Hotel);
    let route3 = router.route(ExpertDomain::Hotel);

    assert_eq!(route1, route2);
    assert_eq!(route2, route3);
}

#[test]
fn test_expert_cache_load_once() {
    let cache = ExpertCache::new(3);
    let router = ExpertRouter::new_default();

    let model = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
    assert_eq!(model.id(), "qwen2.5-coder:14b");
    assert_eq!(cache.cached_count(), 1);
}

#[test]
fn test_expert_cache_lru_eviction() {
    let cache = ExpertCache::new(2);
    let router = ExpertRouter::new_default();

    // Load hotel
    cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
    assert_eq!(cache.cached_count(), 1);

    // Load glass
    cache.get_or_load(ExpertDomain::Glass, &router).unwrap();
    assert_eq!(cache.cached_count(), 2);

    // Load auto (evicts hotel)
    cache.get_or_load(ExpertDomain::Auto, &router).unwrap();
    assert_eq!(cache.cached_count(), 2);

    // Verify hotel was evicted
    assert!(!cache.is_cached(ExpertDomain::Hotel));
    assert!(cache.is_cached(ExpertDomain::Glass));
    assert!(cache.is_cached(ExpertDomain::Auto));
}

#[test]
fn test_expert_cache_size_tracking() {
    let cache = ExpertCache::new(3);
    let router = ExpertRouter::new_default();

    assert_eq!(cache.cached_count(), 0);

    cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
    assert_eq!(cache.cached_count(), 1);

    cache.get_or_load(ExpertDomain::Glass, &router).unwrap();
    assert_eq!(cache.cached_count(), 2);

    cache.get_or_load(ExpertDomain::Auto, &router).unwrap();
    assert_eq!(cache.cached_count(), 3);
}

#[test]
fn test_expert_cache_clear() {
    let cache = ExpertCache::new(3);
    let router = ExpertRouter::new_default();

    cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
    cache.get_or_load(ExpertDomain::Glass, &router).unwrap();
    assert_eq!(cache.cached_count(), 2);

    cache.clear();
    assert_eq!(cache.cached_count(), 0);
}

#[test]
fn test_expert_cache_lru_refresh_on_access() {
    let cache = ExpertCache::new(2);
    let router = ExpertRouter::new_default();

    // Load hotel and glass
    cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
    cache.get_or_load(ExpertDomain::Glass, &router).unwrap();

    // Access hotel to mark it recently used
    let _ = cache.get_cached(ExpertDomain::Hotel).unwrap();

    // Load auto (should evict glass, not hotel)
    cache.get_or_load(ExpertDomain::Auto, &router).unwrap();

    assert!(cache.is_cached(ExpertDomain::Hotel));
    assert!(!cache.is_cached(ExpertDomain::Glass));
    assert!(cache.is_cached(ExpertDomain::Auto));
}

#[test]
fn test_expert_router_register_expert() {
    let mut router = ExpertRouter::new_default();
    let original = router.route(ExpertDomain::Hotel);
    assert_eq!(original, "qwen2.5-coder:14b");

    router.register_expert(ExpertDomain::Hotel, "new-model:v2".to_string());
    let updated = router.route(ExpertDomain::Hotel);
    assert_eq!(updated, "new-model:v2");
}

#[test]
fn test_expert_router_list_experts() {
    let router = ExpertRouter::new_default();
    let experts = router.list_experts();

    assert_eq!(experts.len(), 3);
    assert!(experts.iter().any(|(d, _)| d == "hotel"));
    assert!(experts.iter().any(|(d, _)| d == "glass"));
    assert!(experts.iter().any(|(d, _)| d == "auto"));
}

#[test]
fn test_expert_cache_get_or_load_reuses_cached() {
    let cache = ExpertCache::new(3);
    let router = ExpertRouter::new_default();

    let model1 = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();
    let model2 = cache.get_or_load(ExpertDomain::Hotel, &router).unwrap();

    assert_eq!(model1.id(), model2.id());
    assert_eq!(cache.cached_count(), 1);
}

#[test]
fn test_expert_domain_case_insensitive() {
    assert_eq!(ExpertDomain::from_str("hotel"), Some(ExpertDomain::Hotel));
    assert_eq!(ExpertDomain::from_str("HOTEL"), Some(ExpertDomain::Hotel));
    assert_eq!(ExpertDomain::from_str("Hotel"), Some(ExpertDomain::Hotel));
    assert_eq!(ExpertDomain::from_str("glass"), Some(ExpertDomain::Glass));
    assert_eq!(ExpertDomain::from_str("GLASS"), Some(ExpertDomain::Glass));
    assert_eq!(ExpertDomain::from_str("auto"), Some(ExpertDomain::Auto));
    assert_eq!(ExpertDomain::from_str("AUTO"), Some(ExpertDomain::Auto));
}

#[test]
fn test_expert_router_route_by_string() {
    let router = ExpertRouter::new_default();

    assert_eq!(
        router.route_by_string("hotel"),
        Some("qwen2.5-coder:14b".to_string())
    );
    assert_eq!(
        router.route_by_string("HOTEL"),
        Some("qwen2.5-coder:14b".to_string())
    );
    assert_eq!(router.route_by_string("unknown"), None);
}
