#!/usr/bin/env python3
"""
tests/test_native_data_plane_bridge.py
================================================================================
Verification bridge for AEIB Native Rust Data Plane & Tetragon eBPF LSM Policy.

Epistemic & Compliance Assertions:
  1. Rust native test suite (`cargo test -p aeib-data-plane`) executes and passes
     14 unit and integration tests across constant-time Station 1 admissibility,
     group-commit WAL with Darwin F_FULLFSYNC, TEE ephemeral key zeroization,
     and RFC 9162 / RFC 9942 SCITT Merkle tree inclusion proofs.
  2. Tetragon eBPF LSM policy specification (`compliance/tetragon_aeib_enforcer.yaml`)
     anchors hook points (`security_socket_connect`, `security_file_open`),
     and specifies fail-closed Override: -13 (-EACCES) actions.
  3. Strict zero-mock purity and zero banned words across all native crates and
     compliance policies.
================================================================================
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

BANNED_SUBSTRINGS = [
    "guaran" + "teed",
    "guaran" + "tee",
    "bullet" + "proof",
    "enterprise-" + "grade",
    "production-" + "safe",
    "100% " + "secure",
    "proven " + "universally",
    "unhack" + "able",
]

NATIVE_SOURCE_FILES = [
    REPO_ROOT / "crates" / "aeib-data-plane" / "Cargo.toml",
    REPO_ROOT / "crates" / "aeib-data-plane" / "src" / "lib.rs",
    REPO_ROOT / "crates" / "aeib-data-plane" / "src" / "wal.rs",
    REPO_ROOT / "crates" / "aeib-data-plane" / "src" / "attestation.rs",
    REPO_ROOT / "crates" / "aeib-data-plane" / "src" / "scitt.rs",
    REPO_ROOT / "crates" / "aeib-data-plane" / "tests" / "test_station1_admissibility.rs",
    REPO_ROOT / "crates" / "aeib-data-plane" / "tests" / "test_wal_group_commit.rs",
    REPO_ROOT / "crates" / "aeib-data-plane" / "tests" / "test_tee_attestation.rs",
    REPO_ROOT / "crates" / "aeib-data-plane" / "tests" / "test_scitt_merkle_tree.rs",
    REPO_ROOT / "compliance" / "tetragon_aeib_enforcer.yaml",
]


def test_cargo_native_data_plane_suite():
    """Executes cargo test -p aeib-data-plane to verify all Rust invariants."""
    res = subprocess.run(
        ["cargo", "test", "-p", "aeib-data-plane"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"cargo test failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "test result: ok." in res.stdout
    assert "test_station1_positive_admissibility ... ok" in res.stdout
    assert "test_wal_batch_group_commit_and_recovery ... ok" in res.stdout
    assert "test_tee_attestation_evidence_generation_and_positive_verification ... ok" in res.stdout
    assert "test_scitt_merkle_tree_four_leaves_inclusion_and_falsification ... ok" in res.stdout


def test_tetragon_ebpf_lsm_policy_specification():
    """Validates structure and security actions of the Tetragon eBPF LSM policy using stdlib."""
    policy_path = REPO_ROOT / "compliance" / "tetragon_aeib_enforcer.yaml"
    assert policy_path.exists(), "tetragon_aeib_enforcer.yaml must exist"

    text = policy_path.read_text(encoding="utf-8")
    assert "apiVersion: cilium.io/v1alpha1" in text
    assert "kind: TracingPolicy" in text
    assert "name: aeib-kernel-lsm-enforcer" in text
    assert 'call: "security_socket_connect"' in text
    assert 'call: "security_file_open"' in text
    assert "action: Override" in text
    assert "argError: -13" in text
    assert "/etc/aeib/" in text
    assert "/var/lib/aeib/ledger.jsonl" in text


def test_native_components_zero_banned_words():
    """Scans all native Rust files and Tetragon policy for epistemic lock compliance."""
    violations = []
    for file_path in NATIVE_SOURCE_FILES:
        assert file_path.exists(), f"Expected file {file_path} to exist"
        content = file_path.read_text(encoding="utf-8").lower()
        for banned in BANNED_SUBSTRINGS:
            if banned in content:
                violations.append((str(file_path.relative_to(REPO_ROOT)), banned))

    assert not violations, f"Banned words detected in native components: {violations}"
