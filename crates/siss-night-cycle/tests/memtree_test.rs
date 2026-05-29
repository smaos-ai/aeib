use siss_night_cycle::memtree::{Capsule, MemTree, ScopeType};
use std::time::SystemTime;

fn create_test_capsule(id: &str) -> Capsule {
    Capsule {
        id: id.to_string(),
        content: serde_json::json!({"test": true}),
        created_at: SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap()
            .as_secs(),
    }
}

#[test]
fn test_memtree_insert_capsule_session_scope() {
    // Arrange
    let mut tree = MemTree::new();
    let capsule = create_test_capsule("session-1");

    // Act
    tree.insert_capsule(ScopeType::Session, capsule.clone());

    // Assert
    let inserted = tree.fetch_by_scope(ScopeType::Session, &capsule.id);
    assert!(!inserted.is_empty());
    assert_eq!(inserted[0].id, capsule.id);
}

#[test]
fn test_memtree_fetch_by_scope_returns_capsules() {
    let mut tree = MemTree::new();
    let cap1 = create_test_capsule("scope-1");
    let cap2 = create_test_capsule("scope-2");

    tree.insert_capsule(ScopeType::Session, cap1.clone());
    tree.insert_capsule(ScopeType::Entity, cap2.clone());

    let session_caps = tree.fetch_by_scope(ScopeType::Session, &"*".to_string());
    assert_eq!(session_caps.len(), 1);
    assert_eq!(session_caps[0].id, cap1.id);
}

#[test]
fn test_memtree_parallel_compression_updates_summaries() {
    let mut tree = MemTree::new();
    for i in 0..100 {
        tree.insert_capsule(ScopeType::Session, create_test_capsule(&format!("cap-{}", i)));
    }

    let before_count = tree.node_count();
    tree.parallel_compress_all();
    let after_count = tree.node_count();

    // After compression, interval summaries should reduce node count or keep it same
    assert!(after_count <= before_count);
    assert_eq!(before_count, 100); // Initial count should be 100
}

#[test]
fn test_memtree_multiple_scopes_isolated() {
    let mut tree = MemTree::new();
    let session_cap = create_test_capsule("session");
    let entity_cap = create_test_capsule("entity");

    tree.insert_capsule(ScopeType::Session, session_cap);
    tree.insert_capsule(ScopeType::Entity, entity_cap);

    let session_only = tree.fetch_by_scope(ScopeType::Session, &"*".to_string());
    assert_eq!(session_only.len(), 1);
    assert_eq!(session_only[0].id, "session");

    let entity_only = tree.fetch_by_scope(ScopeType::Entity, &"*".to_string());
    assert_eq!(entity_only.len(), 1);
    assert_eq!(entity_only[0].id, "entity");
}
