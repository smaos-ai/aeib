use l10_did_registry::{PolicyRegistry, Policy};
use serde_json::json;
use uuid::Uuid;

#[test]
fn test_create_policy() {
    let mut registry = PolicyRegistry::new();
    let tenant_id = Uuid::new_v4();
    let rules = json!({"max_requests": 100, "timeout_ms": 5000});

    let policy = registry.create_policy(
        tenant_id,
        "egress".to_string(),
        rules.clone(),
    );

    assert_eq!(policy.tenant_id, tenant_id);
    assert_eq!(policy.category, "egress");
    assert_eq!(policy.rules, rules);
    assert_eq!(policy.version, 1);
    assert_eq!(policy.published_at, None);
}

#[test]
fn test_publish_policy() {
    let mut registry = PolicyRegistry::new();
    let tenant_id = Uuid::new_v4();
    let rules = json!({"action": "allow"});

    let policy = registry.create_policy(
        tenant_id,
        "consent".to_string(),
        rules,
    );

    let published = registry.publish_policy(policy.id).unwrap();
    assert!(published.published_at.is_some());
}

#[test]
fn test_get_policy() {
    let mut registry = PolicyRegistry::new();
    let tenant_id = Uuid::new_v4();
    let rules = json!({"level": "high"});

    let policy = registry.create_policy(
        tenant_id,
        "audit".to_string(),
        rules.clone(),
    );

    let retrieved = registry.get_policy(policy.id).unwrap();
    assert_eq!(retrieved.id, policy.id);
    assert_eq!(retrieved.rules, rules);
}

#[test]
fn test_get_policy_nonexistent() {
    let registry = PolicyRegistry::new();
    let fake_id = Uuid::new_v4();

    let result = registry.get_policy(fake_id);
    assert!(result.is_none());
}

#[test]
fn test_policy_versioning() {
    let mut registry = PolicyRegistry::new();
    let tenant_id = Uuid::new_v4();
    let rules_v1 = json!({"version": 1});

    let policy = registry.create_policy(
        tenant_id,
        "egress".to_string(),
        rules_v1,
    );

    let rules_v2 = json!({"version": 2, "enhanced": true});
    let updated = registry.update_policy_rules(policy.id, rules_v2.clone()).unwrap();

    assert_eq!(updated.version, 2);
    assert_eq!(updated.rules, rules_v2);

    let versions = registry.list_policy_versions(policy.id);
    assert_eq!(versions.len(), 2);
    assert_eq!(versions[0].version_number, 1);
    assert_eq!(versions[1].version_number, 2);
}

#[test]
fn test_get_specific_policy_version() {
    let mut registry = PolicyRegistry::new();
    let tenant_id = Uuid::new_v4();
    let rules_v1 = json!({"count": 1});

    let policy = registry.create_policy(
        tenant_id,
        "egress".to_string(),
        rules_v1,
    );

    registry.update_policy_rules(policy.id, json!({"count": 2})).unwrap();

    let v1 = registry.get_policy_version(policy.id, 1).unwrap();
    assert_eq!(v1.version_number, 1);
    assert_eq!(v1.rules, json!({"count": 1}));

    let v2 = registry.get_policy_version(policy.id, 2).unwrap();
    assert_eq!(v2.version_number, 2);
    assert_eq!(v2.rules, json!({"count": 2}));
}

#[test]
fn test_policy_inheritance_override() {
    let mut registry = PolicyRegistry::new();
    let tenant_a = Uuid::new_v4();
    let tenant_b = Uuid::new_v4();

    // Tenant A creates base policy (catalog)
    let base_policy = registry.create_policy(
        tenant_a,
        "consent".to_string(),
        json!({"default_timeout": 30, "max_retries": 3}),
    );
    registry.publish_policy(base_policy.id);

    // Tenant B creates override for tenant A's policy
    let override_policy = registry
        .create_override(
            tenant_b,
            base_policy.id,
            json!({"default_timeout": 60}),  // Override timeout only
        )
        .unwrap();

    assert_eq!(override_policy.inheritance_parent_id, Some(base_policy.id));
    assert_eq!(override_policy.tenant_id, tenant_b);
}

#[test]
fn test_resolve_effective_policy_with_inheritance() {
    let mut registry = PolicyRegistry::new();
    let tenant_a = Uuid::new_v4();
    let tenant_b = Uuid::new_v4();

    let base = registry.create_policy(
        tenant_a,
        "egress".to_string(),
        json!({"level": "basic", "timeout": 30}),
    );

    let override_policy = registry
        .create_override(
            tenant_b,
            base.id,
            json!({"timeout": 60}),
        )
        .unwrap();

    let effective = registry.resolve_effective_policy(override_policy.id).unwrap();
    assert_eq!(effective["level"], "basic");
    assert_eq!(effective["timeout"], 60);
}

#[test]
fn test_list_tenant_policies() {
    let mut registry = PolicyRegistry::new();
    let tenant_id = Uuid::new_v4();

    let p1 = registry.create_policy(
        tenant_id,
        "egress".to_string(),
        json!({"rule": 1}),
    );
    let p2 = registry.create_policy(
        tenant_id,
        "audit".to_string(),
        json!({"rule": 2}),
    );
    let p3 = registry.create_policy(
        tenant_id,
        "consent".to_string(),
        json!({"rule": 3}),
    );

    let policies = registry.list_tenant_policies(tenant_id);
    assert_eq!(policies.len(), 3);

    let ids: Vec<_> = policies.iter().map(|p| p.id).collect();
    assert!(ids.contains(&p1.id));
    assert!(ids.contains(&p2.id));
    assert!(ids.contains(&p3.id));
}

#[test]
fn test_count_tenant_policies() {
    let mut registry = PolicyRegistry::new();
    let tenant_id = Uuid::new_v4();

    for i in 0..5 {
        registry.create_policy(
            tenant_id,
            format!("category_{}", i),
            json!({"index": i}),
        );
    }

    assert_eq!(registry.count_tenant_policies(tenant_id), 5);
}

#[test]
fn test_count_policy_versions() {
    let mut registry = PolicyRegistry::new();
    let tenant_id = Uuid::new_v4();

    let policy = registry.create_policy(
        tenant_id,
        "egress".to_string(),
        json!({"v": 1}),
    );

    registry.update_policy_rules(policy.id, json!({"v": 2})).unwrap();
    registry.update_policy_rules(policy.id, json!({"v": 3})).unwrap();

    assert_eq!(registry.count_policy_versions(policy.id), 3);
}

#[test]
fn test_update_unpublishes_policy() {
    let mut registry = PolicyRegistry::new();
    let tenant_id = Uuid::new_v4();

    let policy = registry.create_policy(
        tenant_id,
        "egress".to_string(),
        json!({"version": 1}),
    );

    registry.publish_policy(policy.id);
    let published = registry.get_policy(policy.id).unwrap();
    assert!(published.published_at.is_some());

    registry.update_policy_rules(policy.id, json!({"version": 2})).unwrap();
    let unpublished = registry.get_policy(policy.id).unwrap();
    assert!(unpublished.published_at.is_none());
}

#[test]
fn test_multi_tenant_isolation() {
    let mut registry = PolicyRegistry::new();
    let tenant_a = Uuid::new_v4();
    let tenant_b = Uuid::new_v4();

    let policy_a = registry.create_policy(
        tenant_a,
        "egress".to_string(),
        json!({"tenant": "a"}),
    );

    let policy_b = registry.create_policy(
        tenant_b,
        "egress".to_string(),
        json!({"tenant": "b"}),
    );

    let a_policies = registry.list_tenant_policies(tenant_a);
    assert_eq!(a_policies.len(), 1);
    assert_eq!(a_policies[0].id, policy_a.id);

    let b_policies = registry.list_tenant_policies(tenant_b);
    assert_eq!(b_policies.len(), 1);
    assert_eq!(b_policies[0].id, policy_b.id);
}
