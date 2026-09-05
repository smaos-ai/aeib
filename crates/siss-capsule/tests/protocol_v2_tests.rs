// Phase 26 Task 2: CAPSULE v2.2 Protocol v2 Bridge (Tier 3)
// TDD: All 23 tests written failing first, then implemented

use siss_capsule::protocol_bridge::ProtocolV2Bridge;

// ============================================================================
// TIER A: @file Scoping (4 tests)
// ============================================================================

#[test]
fn test_protocol_v2_bridge_new() {
    let _bridge = ProtocolV2Bridge::new();
    // Bridge starts with no scope rules
}

#[test]
fn test_protocol_v2_bridge_add_scope_rule() {
    let bridge = ProtocolV2Bridge::new();

    let rule_pattern = "@crates/siss-capsule".to_string();
    let allowed_mutations = vec!["src/**".to_string(), "tests/**".to_string()];
    let forbidden_paths = vec!["Cargo.toml".to_string()];

    bridge.add_scope_rule(rule_pattern.clone(), allowed_mutations, forbidden_paths);

    // Verify rule was added
}

#[test]
fn test_protocol_v2_bridge_scoping_match() {
    let bridge = ProtocolV2Bridge::new();

    let rule_pattern = "@crates/siss-".to_string();
    let allowed_mutations = vec!["src/**".to_string()];
    let forbidden_paths = vec![];

    bridge.add_scope_rule(rule_pattern, allowed_mutations, forbidden_paths);

    // Test that pattern matches crates/siss-capsule/src/lib.rs (file starts with "crates/siss-")
    let result = bridge.validate_mutation("crates/siss-capsule/src/lib.rs", "");
    assert!(result.is_ok());
}

#[test]
fn test_protocol_v2_bridge_scoping_forbidden() {
    let bridge = ProtocolV2Bridge::new();

    let rule_pattern = "@crates/siss-capsule".to_string();
    let allowed_mutations = vec!["src/**".to_string()];
    let forbidden_paths = vec!["Cargo.toml".to_string()];

    bridge.add_scope_rule(rule_pattern, allowed_mutations, forbidden_paths);

    let result = bridge.validate_mutation("Cargo.toml", "");
    assert!(result.is_err());
}

// ============================================================================
// TIER B: Diff-Only Validation (15 tests)
// ============================================================================

#[test]
fn test_protocol_v2_bridge_text_diff_valid() {
    let bridge = ProtocolV2Bridge::new();
    let old = "pub fn foo() { }";
    let new = "pub fn foo() { println!(\"hello\"); }";
    assert!(bridge.is_valid_diff(old, new));
}

#[test]
fn test_protocol_v2_bridge_empty_old_valid() {
    let bridge = ProtocolV2Bridge::new();
    let old = "";
    let new = "fn new_function() { }";
    assert!(bridge.is_valid_diff(old, new));
}

#[test]
fn test_protocol_v2_bridge_empty_new_valid() {
    let bridge = ProtocolV2Bridge::new();
    let old = "fn removed_function() { }";
    let new = "";
    assert!(bridge.is_valid_diff(old, new));
}

#[test]
fn test_protocol_v2_bridge_binary_null_byte_invalid() {
    let bridge = ProtocolV2Bridge::new();
    let old = "\x00\x01\x02";
    let new = "\x00\x01\x03";
    assert!(!bridge.is_valid_diff(old, new));
}

#[test]
fn test_protocol_v2_bridge_unicode_text_valid() {
    let bridge = ProtocolV2Bridge::new();
    let old = "let x = \"hello\";";
    let new = "let x = \"こんにちは\";";
    assert!(bridge.is_valid_diff(old, new));
}

#[test]
fn test_protocol_v2_bridge_large_diff_valid() {
    let bridge = ProtocolV2Bridge::new();
    let old = "fn main() { }";
    let new_str = "fn main() { \n  ".to_string() + &"x".repeat(1000) + "\n}";
    assert!(bridge.is_valid_diff(old, &new_str));
}

#[test]
fn test_protocol_v2_bridge_whitespace_only_diff_valid() {
    let bridge = ProtocolV2Bridge::new();
    let old = "fn foo() { }";
    let new = "fn foo() {   }"; // Extra spaces
    assert!(bridge.is_valid_diff(old, new));
}

#[test]
fn test_protocol_v2_bridge_multiline_diff_valid() {
    let bridge = ProtocolV2Bridge::new();
    let old = "fn foo() {\n    let x = 1;\n}";
    let new = "fn foo() {\n    let x = 1;\n    let y = 2;\n}";
    assert!(bridge.is_valid_diff(old, new));
}

#[test]
fn test_protocol_v2_bridge_compute_diff_hash() {
    let bridge = ProtocolV2Bridge::new();
    let old = "fn foo() { }";
    let new = "fn foo() { println!(\"hi\"); }";
    let hash = bridge.compute_diff_hash(old, new);

    // Hash should be a valid hex string
    assert!(!hash.is_empty());
    // SHA256 produces 64 hex characters (32 bytes)
    assert_eq!(hash.len(), 64);
}

#[test]
fn test_protocol_v2_bridge_different_diffs_different_hashes() {
    let bridge = ProtocolV2Bridge::new();
    let old = "fn foo() { }";
    let new1 = "fn foo() { println!(\"hi\"); }";
    let new2 = "fn foo() { println!(\"bye\"); }";

    let hash1 = bridge.compute_diff_hash(old, new1);
    let hash2 = bridge.compute_diff_hash(old, new2);

    // Different diffs should produce different hashes
    assert_ne!(hash1, hash2);
}

#[test]
fn test_protocol_v2_bridge_diff_size_calculation() {
    let bridge = ProtocolV2Bridge::new();
    let old = "hello";
    let new = "hello world";
    let size = bridge.diff_size_bytes(old, new);

    // Size should be sum of old + new lengths (in bytes)
    let expected = old.len() + new.len();
    assert_eq!(size, expected);
}

#[test]
fn test_protocol_v2_bridge_semantic_validation_matching_braces() {
    let bridge = ProtocolV2Bridge::new();
    let old = "fn foo() {}";
    let new = "fn foo() { let x = 1; }";

    let result = bridge.validate_diff_semantics(old, new);
    assert!(result.is_ok());
}

#[test]
fn test_protocol_v2_bridge_semantic_validation_unmatched_braces() {
    let bridge = ProtocolV2Bridge::new();
    let old = "fn foo() {}";
    let new = "fn foo() { let x = 1;";  // Missing closing brace

    let result = bridge.validate_diff_semantics(old, new);
    assert!(result.is_err());
}

#[test]
fn test_protocol_v2_bridge_semantics_quotes_balanced() {
    let bridge = ProtocolV2Bridge::new();
    let old = "let s = \"hello\";";
    let new = "let s = \"hello world\";";

    let result = bridge.validate_diff_semantics(old, new);
    assert!(result.is_ok());
}

#[test]
fn test_protocol_v2_bridge_semantics_quotes_unbalanced() {
    let bridge = ProtocolV2Bridge::new();
    let old = "let s = \"hello\";";
    let new = "let s = \"hello world;";  // Missing closing quote

    let result = bridge.validate_diff_semantics(old, new);
    assert!(result.is_err());
}

// ============================================================================
// TIER C: Test-Gating (4 tests)
// ============================================================================

#[test]
fn test_protocol_v2_bridge_scope_wildcard() {
    let bridge = ProtocolV2Bridge::new();

    let rule_pattern = "@crates/siss-*".to_string();
    let allowed_mutations = vec!["**".to_string()];
    let forbidden_paths = vec![];

    bridge.add_scope_rule(rule_pattern, allowed_mutations, forbidden_paths);

    let result = bridge.validate_mutation("crates/siss-behavioral-firewall/src/lib.rs", "");
    assert!(result.is_ok());
}

#[test]
fn test_protocol_v2_bridge_test_gating_path() {
    let bridge = ProtocolV2Bridge::new();

    let rule_pattern = "@crates/siss-".to_string();
    let allowed_mutations = vec!["src/**".to_string(), "tests/**".to_string()];
    let forbidden_paths = vec![];

    bridge.add_scope_rule(rule_pattern, allowed_mutations, forbidden_paths);

    // Test path should be allowed (matches pattern and allowed_mutations)
    let result = bridge.validate_mutation("crates/siss-capsule/tests/lib.rs", "");
    assert!(result.is_ok());
}

#[test]
fn test_protocol_v2_bridge_mutation_rejects_outside_scope() {
    let bridge = ProtocolV2Bridge::new();

    let rule_pattern = "@crates/siss-capsule".to_string();
    let allowed_mutations = vec!["src/**".to_string()];
    let forbidden_paths = vec![];

    bridge.add_scope_rule(rule_pattern, allowed_mutations, forbidden_paths);

    let result = bridge.validate_mutation("crates/siss-gatekeeper/src/lib.rs", "");
    assert!(result.is_err());
}

#[test]
fn test_protocol_v2_bridge_diff_validation_integration() {
    let bridge = ProtocolV2Bridge::new();

    let old_code = "fn test() { }";
    let new_code = "fn test() { assert_eq!(1, 1); }";

    assert!(bridge.is_valid_diff(old_code, new_code));

    let file_path = "crates/siss-capsule/src/lib.rs";
    let result = bridge.validate_mutation(file_path, new_code);
    assert!(result.is_ok());
}

// ============================================================================
// TIER D: Proof Integration Module (18 tests, TDD Phase 1)
// ============================================================================

use siss_capsule::proof_integration::{CryptoMutation, MutationLedger, TestGate};

// ---- CryptoMutation Tests (6) ----

#[test]
fn test_crypto_mutation_new_creates_valid_id() {
    let mutation = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old code".to_string(),
        "new code".to_string(),
    );
    assert!(!mutation.id.is_empty());
}

#[test]
fn test_crypto_mutation_new_computes_sha256_hash() {
    let mutation = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old code".to_string(),
        "new code".to_string(),
    );
    // SHA256 hash should be 64 hex characters
    assert_eq!(mutation.content_hash.len(), 64);
}

#[test]
fn test_crypto_mutation_new_has_no_signature() {
    let mutation = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old code".to_string(),
        "new code".to_string(),
    );
    assert!(mutation.signature.is_none());
    assert!(mutation.signed_by.is_none());
}

#[test]
fn test_crypto_mutation_sign_adds_signature() {
    let mut mutation = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old code".to_string(),
        "new code".to_string(),
    );
    let result = mutation.sign("test_signature".to_string(), "alice@example.com".to_string());
    assert!(result.is_ok());
    assert!(mutation.signature.is_some());
    assert!(mutation.signed_by.is_some());
}

#[test]
fn test_crypto_mutation_sign_double_sign_rejected() {
    let mut mutation = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old code".to_string(),
        "new code".to_string(),
    );
    let result1 = mutation.sign("sig1".to_string(), "alice@example.com".to_string());
    assert!(result1.is_ok());

    let result2 = mutation.sign("sig2".to_string(), "bob@example.com".to_string());
    assert!(result2.is_err());
}

#[test]
fn test_crypto_mutation_different_content_different_hash() {
    let mutation1 = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old code".to_string(),
        "new code A".to_string(),
    );
    let mutation2 = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old code".to_string(),
        "new code B".to_string(),
    );
    assert_ne!(mutation1.content_hash, mutation2.content_hash);
}

// ---- TestGate Tests (6) ----

#[test]
fn test_test_gate_new_creates_empty() {
    let gate = TestGate::new();
    assert_eq!(gate.required_tests.len(), 0);
}

#[test]
fn test_test_gate_add_requirement() {
    let mut gate = TestGate::new();
    gate.add_test_requirement("test_foo".to_string(), true);
    assert_eq!(gate.required_tests.len(), 1);
}

#[test]
fn test_test_gate_validate_pass_all_requirements() {
    let mut gate = TestGate::new();
    gate.add_test_requirement("test_foo".to_string(), true);
    gate.add_test_requirement("test_bar".to_string(), true);

    let mut results = std::collections::HashMap::new();
    results.insert("test_foo".to_string(), true);
    results.insert("test_bar".to_string(), true);

    let result = gate.validate(&results);
    assert!(result.is_ok());
}

#[test]
fn test_test_gate_validate_fail_missing_test() {
    let mut gate = TestGate::new();
    gate.add_test_requirement("test_foo".to_string(), true);
    gate.add_test_requirement("test_bar".to_string(), true);

    let mut results = std::collections::HashMap::new();
    results.insert("test_foo".to_string(), true);
    // test_bar is missing

    let result = gate.validate(&results);
    assert!(result.is_err());
}

#[test]
fn test_test_gate_validate_fail_test_failed() {
    let mut gate = TestGate::new();
    gate.add_test_requirement("test_foo".to_string(), true);

    let mut results = std::collections::HashMap::new();
    results.insert("test_foo".to_string(), false);

    let result = gate.validate(&results);
    assert!(result.is_err());
}

#[test]
fn test_test_gate_validate_partial_optional_tests() {
    let mut gate = TestGate::new();
    gate.add_test_requirement("test_critical".to_string(), true);
    gate.add_test_requirement("test_optional".to_string(), false);

    let mut results = std::collections::HashMap::new();
    results.insert("test_critical".to_string(), true);
    // test_optional not required, but provided
    results.insert("test_optional".to_string(), true);

    let result = gate.validate(&results);
    assert!(result.is_ok());
}

// ---- MutationLedger Tests (6) ----

#[test]
fn test_mutation_ledger_new_creates_empty() {
    let ledger = MutationLedger::new();
    assert_eq!(ledger.len(), 0);
}

#[test]
fn test_mutation_ledger_log_mutation_adds_entry() {
    let mut ledger = MutationLedger::new();
    let mutation = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old".to_string(),
        "new".to_string(),
    );
    let gate = TestGate::new();

    let result = ledger.log_mutation(mutation, &gate);
    assert!(result.is_ok());
    assert_eq!(ledger.len(), 1);
}

#[test]
fn test_mutation_ledger_log_mutation_fails_with_unsatisfied_gate() {
    let mut ledger = MutationLedger::new();
    let mutation = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old".to_string(),
        "new".to_string(),
    );
    let mut gate = TestGate::new();
    gate.add_test_requirement("critical_test".to_string(), true);

    let result = ledger.log_mutation(mutation, &gate);
    assert!(result.is_err());
    assert_eq!(ledger.len(), 0);
}

#[test]
fn test_mutation_ledger_get_mutations_returns_logged() {
    let mut ledger = MutationLedger::new();
    let mutation = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old".to_string(),
        "new".to_string(),
    );
    let gate = TestGate::new();

    ledger.log_mutation(mutation, &gate).ok();
    let mutations = ledger.get_mutations();
    assert_eq!(mutations.len(), 1);
}

#[test]
fn test_mutation_ledger_multiple_mutations() {
    let mut ledger = MutationLedger::new();
    let gate = TestGate::new();

    for i in 0..5 {
        let mutation = CryptoMutation::new(
            format!("src/file{}.rs", i),
            "old".to_string(),
            format!("new {}", i),
        );
        ledger.log_mutation(mutation, &gate).ok();
    }

    assert_eq!(ledger.len(), 5);
}

#[test]
fn test_mutation_ledger_serializable() {
    let mut ledger = MutationLedger::new();
    let mutation = CryptoMutation::new(
        "src/lib.rs".to_string(),
        "old".to_string(),
        "new".to_string(),
    );
    let gate = TestGate::new();

    ledger.log_mutation(mutation, &gate).ok();
    // Verify ledger can be serialized (no panics)
    let json = serde_json::to_string(&ledger);
    assert!(json.is_ok());
}
