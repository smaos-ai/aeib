# Copyright 2026 SovereignNexus Project
# tests/test_adversarial_fuzz_and_negative_invariants.py
#
# Adversarial Property-Based, Fuzzing & Negative Path Test Battery.
# Evaluates JCS canonicalization, Merkle proof integrity, Ed25519 signature corruption,
# UnitBoost conflict isolation, and negative-path latency/overhead metrics.
#
# Epistemic Notice: Evaluated and tested under the stated local verification model.

import copy
import hashlib
import json
import random
import time
from typing import Any, Dict, List

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.unitboost_merge_operator import (
    UnitBoostProposal,
    UnitBoostMergeOperator,
    SlotResolutionStatus,
)
from src.ebpf_agent_guard_controller import (
    EbpfAgentGuardController,
    PROT_READ,
    PROT_WRITE,
    PROT_EXEC,
)


def _compute_sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


# ── 1. ADVERSARIAL JCS FUZZING & PROPERTY-BASED INVARIANTS ──────────────────

def test_adversarial_jcs_canonicalization_idempotency_and_fuzz():
    """Evaluates JCS canonicalization idempotency across 100 randomized nested dictionaries."""
    prng = random.Random(20261020)

    for i in range(100):
        # Generate arbitrary randomized nested dictionary with mixed types
        sample: Dict[str, Any] = {
            f"key_{prng.randint(0, 1000)}": prng.choice([
                prng.randint(-1000000, 1000000),
                f"string_val_{prng.randint(0, 500)}_€_ü_中",
                prng.choice([True, False, None]),
                [prng.randint(0, 100) for _ in range(prng.randint(0, 5))],
                {"nested_b": prng.randint(1, 10), "nested_a": "alpha"}
            ])
            for _ in range(prng.randint(1, 10))
        }

        # Invariant 1: Idempotency (JCS(JCS(x)) == JCS(x))
        canonical_1 = encode_jcs(sample)
        reparsed = json.loads(canonical_1.decode("utf-8"))
        canonical_2 = encode_jcs(reparsed)
        assert canonical_1 == canonical_2, f"JCS non-idempotent on iteration {i}"

        # Invariant 2: Key ordering must be strictly sorted by UTF-16 code units
        keys = list(reparsed.keys())
        sorted_keys = sorted(keys)
        # Note: In standard ASCII/BMP, UTF-16 code unit order matches Python unicode sort
        assert keys == sorted_keys, f"Keys not sorted on iteration {i}"


def test_adversarial_jcs_malformed_float_rejection():
    """Asserts that non-finite floating point numbers (NaN, Infinity) are rejected fail-closed."""
    with pytest.raises(Exception):
        encode_jcs({"invalid_val": float("nan")})

    with pytest.raises(Exception):
        encode_jcs({"invalid_val": float("inf")})


# ── 2. ADVERSARIAL MERKLE INCLUSION PROOF TAMPERING ──────────────────────────

def test_adversarial_merkle_tree_proof_fuzzing():
    """Asserts that any bit-flip or path tampering in Merkle proofs fails closed."""
    prng = random.Random(42)

    # Simple 4-leaf RFC 9162 Merkle tree construction
    leaves = [f"leaf_{i}".encode("utf-8") for i in range(4)]
    leaf_hashes = [_compute_sha256(b"\x00" + l) for l in leaves]

    n01 = _compute_sha256(b"\x01" + leaf_hashes[0] + leaf_hashes[1])
    n23 = _compute_sha256(b"\x01" + leaf_hashes[2] + leaf_hashes[3])
    root = _compute_sha256(b"\x01" + n01 + n23)

    # Valid proof for leaf 0: audit path is [leaf_hashes[1], n23]
    audit_path = [leaf_hashes[1], n23]

    def verify_inclusion(target_leaf: bytes, path: List[bytes], expected_root: bytes) -> bool:
        cur = _compute_sha256(b"\x00" + target_leaf)
        cur = _compute_sha256(b"\x01" + cur + path[0])
        cur = _compute_sha256(b"\x01" + cur + path[1])
        return cur == expected_root

    assert verify_inclusion(leaves[0], audit_path, root) is True

    # Fuzz 50 random mutations: every tampered proof must fail closed
    for _ in range(50):
        tampered_path = copy.deepcopy(audit_path)
        mutation_idx = prng.choice([0, 1])
        bad_bytes = bytearray(tampered_path[mutation_idx])
        bad_byte_idx = prng.randint(0, len(bad_bytes) - 1)
        bad_bytes[bad_byte_idx] ^= prng.randint(1, 255)
        tampered_path[mutation_idx] = bytes(bad_bytes)

        assert verify_inclusion(leaves[0], tampered_path, root) is False


# ── 3. ADVERSARIAL ED25519 SIGNATURE CORRUPTION ──────────────────────────────

def test_adversarial_ed25519_signature_corruption():
    """Asserts that bit-level tampering with Ed25519 signatures is rejected with InvalidSignature."""
    prng = random.Random(999)
    privkey = ed25519.Ed25519PrivateKey.generate()
    pubkey = privkey.public_key()

    message = b"action_caid_20261020_consequential_mutation"
    valid_sig = privkey.sign(message)

    # Verify positive path
    pubkey.verify(valid_sig, message)

    # Fuzz 50 mutated signatures
    for _ in range(50):
        sig_bytes = bytearray(valid_sig)
        idx = prng.randint(0, len(sig_bytes) - 1)
        sig_bytes[idx] ^= prng.randint(1, 255)

        with pytest.raises(InvalidSignature):
            pubkey.verify(bytes(sig_bytes), message)


# ── 4. ADVERSARIAL UNITBOOST CONFLICT & TIE-BREAKING RESOLUTION ──────────────

def test_adversarial_unitboost_tie_and_conflict_isolation():
    """Asserts that conflicting agent proposals with ties or low confidence trigger UNCERTAINTY_HALT."""
    operator = UnitBoostMergeOperator(
        margin_threshold=0.20,
        critical_slots={"action_class", "recipient_iban", "amount_minor"}
    )

    # Case 1: Exact 50/50 conflict between two models on recipient_iban
    prop1 = UnitBoostProposal(
        model_id="model_claude",
        harness_id="claude_code",
        slot_values={
            "action_class": "disburse_refund",
            "recipient_iban": "DE89370400440532013000",
            "amount_minor": 1500_00
        },
        model_weight=1.0
    )

    prop2 = UnitBoostProposal(
        model_id="model_deepseek",
        harness_id="deepseek_r1",
        slot_values={
            "action_class": "disburse_refund",
            "recipient_iban": "GB29NWBK60161331926819",  # Contradicting payee!
            "amount_minor": 1500_00
        },
        model_weight=1.0
    )

    # Must fail closed with UNCERTAINTY_HALT because recipient_iban is in conflict
    result = operator.merge_proposals([prop1, prop2])

    assert result.verdict == "UNCERTAINTY_HALT"
    assert result.requires_step_up is True
    assert "recipient_iban" in result.residual_uncertainty_slots


def test_adversarial_unitboost_order_invariance_fuzz():
    """Asserts commutativity: order of proposals does not alter merged state."""
    operator = UnitBoostMergeOperator(margin_threshold=0.15)

    p_a = UnitBoostProposal(
        model_id="model_a",
        harness_id="harness_1",
        slot_values={"target": "api_v1", "param": "value_a"},
        model_weight=1.0
    )
    p_b = UnitBoostProposal(
        model_id="model_b",
        harness_id="harness_2",
        slot_values={"target": "api_v1", "param": "value_b"},
        model_weight=0.5
    )

    res1 = operator.merge_proposals([p_a, p_b])
    res2 = operator.merge_proposals([p_b, p_a])

    assert res1.resolved_slots == res2.resolved_slots
    assert res1.consensus_caid == res2.consensus_caid
    assert res1.verdict == res2.verdict


# ── 5. NEGATIVE PATH BENCHMARK & LATENCY OVERHEAD QUANTIFICATION ─────────────

def test_negative_path_benchmark_and_latency_quantification(tmp_path):
    """Executes a 100-episode negative adversarial schedule and quantifies p50/p95/p99 latency."""
    prng = random.Random(1337)
    controller = EbpfAgentGuardController()

    # Pre-register allowed binary
    bin_file = tmp_path / "valid_agent_runner"
    bin_file.write_bytes(b"VALID_BINARY_PAYLOAD_BYTES")
    bin_hash = hashlib.sha256(bin_file.read_bytes()).hexdigest()
    controller.register_allowed_binary("valid_agent_runner", str(bin_file), bin_hash)

    unregistered_bin = tmp_path / "unregistered_binary"
    unregistered_bin.write_bytes(b"MALICIOUS_UNREGISTERED")

    latencies_ms: List[float] = []
    verdicts = {"ALLOWED": 0, "BLOCKED": 0}

    # 100 episodes: 50 nominal allowed, 50 adversarial blocked
    for ep in range(100):
        t0 = time.perf_counter()

        is_adversarial = (ep % 2 == 1)
        if is_adversarial:
            mode = prng.choice(["unregistered", "wx_violation", "socket_taint"])
            if mode == "unregistered":
                allowed, reason, event = controller.attest_binary_execution(str(unregistered_bin), pid=ep)
            elif mode == "wx_violation":
                allowed, reason, event = controller.attest_memory_protection_escalation("heap_buffer", PROT_EXEC, pid=ep)
            else:
                allowed, reason, event = controller.attest_socket_connect("93.184.216.34", 443, 2, pid=ep)

            assert not allowed
            verdicts["BLOCKED"] += 1
        else:
            allowed, reason, event = controller.attest_binary_execution(str(bin_file), pid=ep)
            assert allowed
            verdicts["ALLOWED"] += 1

        duration_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(duration_ms)

    # Compute empirical latency distribution
    latencies_ms.sort()
    p50 = latencies_ms[int(len(latencies_ms) * 0.50)]
    p95 = latencies_ms[int(len(latencies_ms) * 0.95)]
    p99 = latencies_ms[int(len(latencies_ms) * 0.99)]

    print(f"\n[Negative Benchmark] Evaluated 100 episodes: {verdicts}")
    print(f"[Negative Benchmark] Latency: p50={p50:.4f}ms, p95={p95:.4f}ms, p99={p99:.4f}ms")

    assert verdicts["ALLOWED"] == 50
    assert verdicts["BLOCKED"] == 50
    # Boundary gate latency overhead must remain under 1.0 ms for in-memory checks
    assert p99 < 1.0, f"p99 latency overhead exceeded: {p99}ms"
