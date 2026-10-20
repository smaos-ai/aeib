// Copyright 2026 SovereignNexus Project
// crates/aeib-ebpf-lsm/tests/test_ebpf_controller.rs
//
// Verification suite for AEIB eBPF LSM controller and security invariants.

use aeib_ebpf_lsm::*;

#[test]
fn test_bprm_security_allowlist_and_digest_pinning() {
    let controller = EbpfAgentGuardController::new();

    let inode_node = 1001u64;
    let expected_hash = [0xabu8; 32];
    controller.allow_executable(inode_node, expected_hash, 0x5);

    // 1. Nominal allowed binary passes
    let res = controller.check_bprm_security(501, inode_node, &expected_hash);
    assert!(res.is_ok());

    // 2. Unregistered binary fails closed
    let inode_unregistered = 9999u64;
    let err = controller.check_bprm_security(501, inode_unregistered, &expected_hash);
    assert_eq!(
        err,
        Err(EbpfGuardError::ExecutableNotPermitted(inode_unregistered))
    );

    // 3. Digest mismatch (tampered binary) fails closed
    let tampered_hash = [0xfeu8; 32];
    let err_mismatch = controller.check_bprm_security(501, inode_node, &tampered_hash);
    assert_eq!(
        err_mismatch,
        Err(EbpfGuardError::BinaryDigestMismatch(inode_node))
    );
}

#[test]
fn test_memory_w_xor_x_isolation() {
    let controller = EbpfAgentGuardController::new();
    let pid = 777;

    // Read only (0x1) -> Allow
    assert!(controller.check_mprotect(pid, 0x1).is_ok());

    // Read + Write (0x3) -> Allow
    assert!(controller.check_mprotect(pid, 0x3).is_ok());

    // Read + Execute (0x5) -> Allow
    assert!(controller.check_mprotect(pid, 0x5).is_ok());

    // Write + Execute (0x6) -> Deny (W^X violation)
    let err_wx = controller.check_mprotect(pid, 0x6);
    assert_eq!(err_wx, Err(EbpfGuardError::MemoryWxViolation(0x6)));

    // Read + Write + Execute (0x7) -> Deny (W^X violation)
    let err_rwx = controller.check_mprotect(pid, 0x7);
    assert_eq!(err_rwx, Err(EbpfGuardError::MemoryWxViolation(0x7)));
}

#[test]
fn test_model_weight_tensor_verification() {
    let controller = EbpfAgentGuardController::new();
    let pid = 888;
    let inode_weights = 4001u64;
    let valid_tensor_hash = [0x55u8; 32];

    controller.register_tensor_weights(inode_weights, 0, 1024 * 1024, valid_tensor_hash);

    // Nominal matching weights pass
    assert!(controller
        .check_mmap_weights(pid, inode_weights, 0, 1024 * 1024, &valid_tensor_hash)
        .is_ok());

    // Poisoned/corrupted weights fail closed
    let corrupted_hash = [0x66u8; 32];
    let err = controller.check_mmap_weights(
        pid,
        inode_weights,
        0,
        1024 * 1024,
        &corrupted_hash,
    );
    assert_eq!(
        err,
        Err(EbpfGuardError::ModelWeightDigestMismatch(inode_weights))
    );
}

#[test]
fn test_socket_egress_taint_isolation() {
    let controller = EbpfAgentGuardController::new();

    let pid_system = 100;
    let pid_tainted = 200;

    controller.set_process_taint(pid_system, TAINT_TIER_0_SYSTEM, 1000_00);
    controller.set_process_taint(pid_tainted, TAINT_TIER_2_UNTRUSTED, 0);

    // System process allowed to initiate connection
    assert!(controller.check_socket_connect(pid_system, 0x7f000001, 8080).is_ok());

    // Tainted guest agent process denied direct socket egress fail-closed
    let err = controller.check_socket_connect(pid_tainted, 0x7f000001, 8080);
    assert_eq!(err, Err(EbpfGuardError::SocketEgressDenied(pid_tainted)));
}

#[test]
fn test_scitt_ringbuf_audit_drain() {
    let controller = EbpfAgentGuardController::new();

    assert_eq!(controller.event_count(), 0);

    // Trigger several events
    let _ = controller.check_mprotect(10, 0x1);
    let _ = controller.check_mprotect(10, 0x6); // Rejected
    let _ = controller.check_socket_connect(10, 0x7f000001, 80);

    assert_eq!(controller.event_count(), 3);

    let events = controller.drain_audit_events();
    assert_eq!(events.len(), 3);
    assert_eq!(controller.event_count(), 0);

    // Event 0: allow
    assert_eq!(events[0].hook_id, HOOK_FILE_MPROTECT);
    assert_eq!(events[0].status_code, VERDICT_ALLOW);

    // Event 1: deny
    assert_eq!(events[1].hook_id, HOOK_FILE_MPROTECT);
    assert_eq!(events[1].status_code, VERDICT_EACCES);

    // Event 2: allow
    assert_eq!(events[2].hook_id, HOOK_SOCKET_CONNECT);
    assert_eq!(events[2].status_code, VERDICT_ALLOW);
}
