use l10_did_registry::{DID, DidRegistry, DidVerifier};
use l10_did_registry::did::PublicKey;

#[test]
fn test_did_creation() {
    let did = DID::sov("abc123".to_string());
    assert_eq!(did.method, "did:sov");
    assert_eq!(did.identifier, "abc123");
}

#[test]
fn test_did_to_string() {
    let did = DID::sov("xyz789".to_string());
    assert_eq!(did.to_string(), "did:sov:xyz789");
}

#[test]
fn test_did_parsing() {
    let did_str = "did:sov:test123";
    let did = DID::from_string(did_str).unwrap();
    assert_eq!(did.method, "did:sov");
    assert_eq!(did.identifier, "test123");
}

#[test]
fn test_did_hash_computation() {
    let did = DID::sov("test".to_string());
    let hash = DidVerifier::compute_did_hash(&did);
    assert!(!hash.is_empty());
    assert_eq!(hash.len(), 64); // SHA256 hex = 64 chars
}

#[test]
fn test_registry_register_did() {
    let mut registry = DidRegistry::new();
    let did = DID::sov("org_001".to_string());

    let result = registry.register_did(did.clone(), None, "tenant_1".to_string());
    assert!(result.is_ok());

    let doc = result.unwrap();
    assert_eq!(doc.id, did);
    assert_eq!(registry.count_dids(), 1);
}

#[test]
fn test_registry_duplicate_did_rejected() {
    let mut registry = DidRegistry::new();
    let did = DID::sov("org_001".to_string());

    registry
        .register_did(did.clone(), None, "tenant_1".to_string())
        .unwrap();

    let result = registry.register_did(did, None, "tenant_1".to_string());
    assert!(result.is_err());
}

#[test]
fn test_registry_resolve_did() {
    let mut registry = DidRegistry::new();
    let did = DID::key("pubkey123".to_string());

    registry
        .register_did(did.clone(), None, "tenant_1".to_string())
        .unwrap();

    let resolved = registry.resolve_did(&did).unwrap();
    assert_eq!(resolved.id, did);
    assert!(resolved.proof.is_some());
}

#[test]
fn test_registry_resolve_nonexistent() {
    let registry = DidRegistry::new();
    let did = DID::web("nonexistent".to_string());

    let result = registry.resolve_did(&did);
    assert!(result.is_err());
}

#[test]
fn test_add_public_key() {
    let mut registry = DidRegistry::new();
    let did = DID::sov("org_002".to_string());

    registry
        .register_did(did.clone(), None, "tenant_1".to_string())
        .unwrap();

    let pub_key = PublicKey::new(
        "key_001".to_string(),
        "Ed25519VerificationKey2020".to_string(),
        "abcd1234".to_string(),
    );

    let result = registry.add_public_key(&did, pub_key.clone());
    assert!(result.is_ok());

    let doc = result.unwrap();
    assert_eq!(doc.public_keys.len(), 1);
    assert_eq!(doc.public_keys[0].id, "key_001");
}

#[test]
fn test_list_tenant_dids() {
    let mut registry = DidRegistry::new();

    let did1 = DID::sov("org_001".to_string());
    let did2 = DID::key("key_001".to_string());
    let did3 = DID::sov("org_003".to_string());

    registry
        .register_did(did1, None, "tenant_1".to_string())
        .unwrap();
    registry
        .register_did(did2, None, "tenant_1".to_string())
        .unwrap();
    registry
        .register_did(did3, None, "tenant_2".to_string())
        .unwrap();

    let tenant1_dids = registry.list_tenant_dids("tenant_1");
    assert_eq!(tenant1_dids.len(), 2);

    let tenant2_dids = registry.list_tenant_dids("tenant_2");
    assert_eq!(tenant2_dids.len(), 1);
}

#[test]
fn test_verify_did_ownership() {
    let mut registry = DidRegistry::new();
    let did = DID::sov("org_001".to_string());

    registry
        .register_did(did.clone(), None, "tenant_1".to_string())
        .unwrap();

    let is_owner = registry.verify_did_ownership(&did, "tenant_1").unwrap();
    assert!(is_owner);

    let is_not_owner = registry.verify_did_ownership(&did, "tenant_2").unwrap();
    assert!(!is_not_owner);
}

#[test]
fn test_count_dids() {
    let mut registry = DidRegistry::new();

    for i in 0..5 {
        let did = DID::sov(format!("org_{}", i));
        registry
            .register_did(did, None, "tenant_1".to_string())
            .unwrap();
    }

    assert_eq!(registry.count_dids(), 5);
}

#[test]
fn test_count_tenant_dids() {
    let mut registry = DidRegistry::new();

    for i in 0..3 {
        let did = DID::sov(format!("org_{}", i));
        registry
            .register_did(did, None, "tenant_1".to_string())
            .unwrap();
    }

    for i in 3..5 {
        let did = DID::sov(format!("org_{}", i));
        registry
            .register_did(did, None, "tenant_2".to_string())
            .unwrap();
    }

    assert_eq!(registry.count_tenant_dids("tenant_1"), 3);
    assert_eq!(registry.count_tenant_dids("tenant_2"), 2);
}
