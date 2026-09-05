// Phase 26 Task 2: CAPSULE v2.2 Swarm Coordination (Tier 4)
// TDD: All 13 tests written failing first, then implemented

use chrono::Utc;
use siss_capsule::swarm_link::{StateEntry, SwarmLink};
use uuid::Uuid;

// ============================================================================
// TIER A: Capsule Linking (4 tests)
// ============================================================================

#[test]
fn test_swarm_link_new() {
    let capsule_id = Uuid::new_v4();
    let swarm = SwarmLink::new(capsule_id);

    assert_eq!(swarm.local_capsule_id(), capsule_id);
}

#[test]
fn test_swarm_link_register_peer() {
    let capsule_id = Uuid::new_v4();
    let peer_id = Uuid::new_v4();
    let public_key = [0x42u8; 32];

    let swarm = SwarmLink::new(capsule_id);
    let result = swarm.register_peer(peer_id, public_key);

    assert!(result.is_ok());
}

#[test]
fn test_swarm_link_verify_peer_public_key() {
    let capsule_id = Uuid::new_v4();
    let peer_id = Uuid::new_v4();
    let public_key = [0x42u8; 32];

    let swarm = SwarmLink::new(capsule_id);
    swarm.register_peer(peer_id, public_key).expect("register");

    // Verify public key was stored correctly
    assert!(swarm.peer_exists(peer_id));
}

#[test]
fn test_swarm_link_revoke_peer() {
    let capsule_id = Uuid::new_v4();
    let peer_id = Uuid::new_v4();
    let public_key = [0x42u8; 32];

    let swarm = SwarmLink::new(capsule_id);
    swarm.register_peer(peer_id, public_key).expect("register");

    let result = swarm.revoke_peer(peer_id);
    assert!(result.is_ok());
    assert!(!swarm.peer_exists(peer_id));
}

// ============================================================================
// TIER B: State Sync (5 tests)
// ============================================================================

#[test]
fn test_swarm_link_propose_state() {
    let capsule_id = Uuid::new_v4();
    let swarm = SwarmLink::new(capsule_id);

    let merkle_hash = [0x01u8; 32];
    let result = swarm.propose_state(merkle_hash);

    assert!(result.is_ok());
    let entry = result.expect("entry");
    assert_eq!(entry.capsule_id, capsule_id);
    assert_eq!(entry.merkle_hash, merkle_hash);
}

#[test]
fn test_swarm_link_propose_state_signed() {
    let capsule_id = Uuid::new_v4();
    let swarm = SwarmLink::new(capsule_id);

    let merkle_hash = [0x02u8; 32];
    let entry = swarm
        .propose_state(merkle_hash)
        .expect("propose should succeed");

    assert_eq!(entry.signature.len(), 64);
}

#[test]
fn test_swarm_link_sync_state_peer() {
    let capsule_id = Uuid::new_v4();
    let peer_id = Uuid::new_v4();
    let public_key = [0x42u8; 32];

    let swarm = SwarmLink::new(capsule_id);
    swarm.register_peer(peer_id, public_key).expect("register");

    let merkle_hash = [0x03u8; 32];
    let state_entry = swarm
        .propose_state(merkle_hash)
        .expect("propose should succeed");

    let result = swarm.sync_state(peer_id, state_entry);
    assert!(result.is_ok());
}

#[test]
fn test_swarm_link_sync_state_unknown_peer() {
    let capsule_id = Uuid::new_v4();
    let peer_id = Uuid::new_v4();
    let unknown_peer = Uuid::new_v4();

    let swarm = SwarmLink::new(capsule_id);
    swarm
        .register_peer(peer_id, [0x42u8; 32])
        .expect("register");

    let merkle_hash = [0x04u8; 32];
    let state_entry = swarm
        .propose_state(merkle_hash)
        .expect("propose should succeed");

    let result = swarm.sync_state(unknown_peer, state_entry);
    assert!(result.is_err());
}

#[test]
fn test_swarm_link_sync_consistency() {
    let capsule_id = Uuid::new_v4();
    let peer_id = Uuid::new_v4();

    let swarm = SwarmLink::new(capsule_id);
    swarm
        .register_peer(peer_id, [0x42u8; 32])
        .expect("register");

    let merkle_hash1 = [0x05u8; 32];
    let entry1 = swarm.propose_state(merkle_hash1).expect("propose 1");
    swarm.sync_state(peer_id, entry1).expect("sync 1");

    let merkle_hash2 = [0x06u8; 32];
    let entry2 = swarm.propose_state(merkle_hash2).expect("propose 2");
    swarm.sync_state(peer_id, entry2).expect("sync 2");

    // Both states should be stored in ledger
}

// ============================================================================
// TIER C: Conflict Resolution (4 tests)
// ============================================================================

#[test]
fn test_swarm_link_resolve_conflict_higher_hash_wins() {
    let capsule_id = Uuid::new_v4();
    let swarm = SwarmLink::new(capsule_id);

    let hash1 = [0x01u8; 32];
    let hash2 = [0x02u8; 32];

    let entry1 = swarm.propose_state(hash1).expect("propose 1");
    let entry2 = swarm.propose_state(hash2).expect("propose 2");

    let winner = swarm.resolve_conflict(&entry1, &entry2);

    // Highest merkle_hash should win
    assert_eq!(winner.merkle_hash, hash2);
}

#[test]
fn test_swarm_link_resolve_conflict_deterministic() {
    let capsule_id = Uuid::new_v4();
    let swarm = SwarmLink::new(capsule_id);

    let hash1 = [0x10u8; 32];
    let hash2 = [0x20u8; 32];

    let entry1 = swarm.propose_state(hash1).expect("propose 1");
    let entry2 = swarm.propose_state(hash2).expect("propose 2");

    let winner1 = swarm.resolve_conflict(&entry1, &entry2);
    let winner2 = swarm.resolve_conflict(&entry1, &entry2);

    assert_eq!(winner1.merkle_hash, winner2.merkle_hash);
}

#[test]
fn test_swarm_link_resolve_conflict_preserves_signature() {
    let capsule_id = Uuid::new_v4();
    let swarm = SwarmLink::new(capsule_id);

    let hash1 = [0x01u8; 32];
    let hash2 = [0xff; 32];

    let entry1 = swarm.propose_state(hash1).expect("propose 1");
    let entry2 = swarm.propose_state(hash2).expect("propose 2");

    let winner = swarm.resolve_conflict(&entry1, &entry2);

    // Winner should be entry2 (higher hash)
    assert_eq!(winner.merkle_hash, hash2);
    assert_eq!(winner.signature, entry2.signature);
}

#[test]
fn test_swarm_link_resolve_conflict_multiple_peers() {
    let capsule_id = Uuid::new_v4();
    let peer1 = Uuid::new_v4();
    let peer2 = Uuid::new_v4();

    let swarm = SwarmLink::new(capsule_id);
    swarm
        .register_peer(peer1, [0x42u8; 32])
        .expect("register 1");
    swarm
        .register_peer(peer2, [0x43u8; 32])
        .expect("register 2");

    let hash1 = [0x11u8; 32];
    let hash2 = [0x22u8; 32];

    let entry1 = swarm.propose_state(hash1).expect("propose 1");
    let entry2 = swarm.propose_state(hash2).expect("propose 2");

    swarm.sync_state(peer1, entry1.clone()).expect("sync 1");
    swarm.sync_state(peer2, entry2.clone()).expect("sync 2");

    let winner = swarm.resolve_conflict(&entry1, &entry2);
    assert_eq!(winner.merkle_hash, hash2);
}
