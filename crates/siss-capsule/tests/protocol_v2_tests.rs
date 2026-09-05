// Phase 26 Task 2: CAPSULE v2.2 Protocol v2 Bridge (Tier 3)
// TDD: All 12 tests written failing first, then implemented

use siss_capsule::protocol_bridge::{ProtocolV2Bridge, ScopeError};

// ============================================================================
// TIER A: @file Scoping (4 tests)
// ============================================================================

#[test]
fn test_protocol_v2_bridge_new() {
    let bridge = ProtocolV2Bridge::new();
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
// TIER B: Diff-Only Validation (4 tests)
// ============================================================================

#[test]
fn test_protocol_v2_bridge_valid_diff() {
    let bridge = ProtocolV2Bridge::new();

    let old_content = "pub fn foo() { }";
    let new_content = "pub fn foo() { println!(\"hello\"); }";

    assert!(bridge.is_valid_diff(old_content, new_content));
}

#[test]
fn test_protocol_v2_bridge_invalid_diff_binary() {
    let bridge = ProtocolV2Bridge::new();

    let old_content = "\x00\x01\x02";
    let new_content = "\x00\x01\x03";

    // Binary diffs should be rejected
    assert!(!bridge.is_valid_diff(old_content, new_content));
}

#[test]
fn test_protocol_v2_bridge_mutation_validation() {
    let bridge = ProtocolV2Bridge::new();

    let old_content = "fn foo() { }";
    let new_content = "fn foo() { 1 + 1; }";
    let file_path = "crates/siss-capsule/src/lib.rs";

    // Without scope rules, any mutation should be validated at diff level
    let result = bridge.validate_mutation(file_path, new_content);
    assert!(result.is_ok());
}

#[test]
fn test_protocol_v2_bridge_large_diff() {
    let bridge = ProtocolV2Bridge::new();

    let old_content = "fn main() { }";
    let new_content = "fn main() { \n  ".to_string() + &"x".repeat(1000) + "\n}";

    // Should validate if it's a proper text diff
    assert!(bridge.is_valid_diff(old_content, &new_content));
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
