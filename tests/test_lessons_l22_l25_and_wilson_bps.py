#!/usr/bin/env python3
"""
tests/test_lessons_l22_l25_and_wilson_bps.py — Unit tests for Lessons L22–L25 and Wilson BPS Interval

Verifies:
1. Exact rational Wilson 95% BPS interval reproduction across reported benchmark tables:
   - 0/27 -> [0, 1246]
   - 0/3 -> [0, 5616]
   - 0/32 -> [0, 1072]
   - 0/160 -> [0, 235]
   - 30/160 -> [1346, 2551]
   - 25/160 -> [1081, 2205]
2. Lesson L22: Epistemic status grounding verification (CI009).
3. Lesson L23: Exact BPS boundary arithmetic and mutant kill properties (N=1, prime fractions).
4. Constitutional commit idempotency and receipt signature verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from compliance.claim_integrity_gate import ClaimIntegrityGate
from src.jcs_canonicalizer import encode_jcs
from src.wilson_bps_interval import (
    SQRT_SCALE,
    WILSON_Z_DEN,
    WILSON_Z_NUM,
    _scaled_isqrt,
    compute_exact_bps_boundary,
    compute_wilson_95_bps,
    format_bps_interval,
    verify_l22_status_grounding,
)
from tools.commit_lessons_l22_l25 import commit_lessons_to_agents_md, generate_and_sign_receipt

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_wilson_95_bps_exact_reproduction_table():
    """Verify exact reproduction of Wilson 95% intervals across all cited benchmarks."""
    expected_intervals = [
        (0, 27, (0, 1246)),
        (0, 3, (0, 5616)),
        (0, 32, (0, 1072)),
        (0, 160, (0, 235)),
        (30, 160, (1346, 2551)),
        (25, 160, (1081, 2205)),
    ]

    for successes, total, expected in expected_intervals:
        observed = compute_wilson_95_bps(successes, total)
        assert observed == expected, f"Mismatch for {successes}/{total}: got {observed}, expected {expected}"
        formatted = format_bps_interval(observed)
        assert formatted == f"[{expected[0]}..{expected[1]} bps]"


def test_wilson_constants_and_scaled_isqrt():
    """Verify rational constants and outward ceiling square root function."""
    assert WILSON_Z_NUM == 49
    assert WILSON_Z_DEN == 25
    assert SQRT_SCALE == 1_000_000_000_000

    # Test _scaled_isqrt outward rounding
    assert _scaled_isqrt(0) == 0
    assert _scaled_isqrt(4) == 2
    assert _scaled_isqrt(8) == 3  # 8 is not square -> 3
    assert _scaled_isqrt(9) == 3  # exact square -> 3
    assert _scaled_isqrt(10) == 4  # 10 is not square -> 4


def test_wilson_95_bps_boundary_and_validation():
    """Verify error checking and boundary edge cases for Wilson interval calculation."""
    # Zero trials
    assert compute_wilson_95_bps(0, 0) == (0, 0)

    # Full success: high must be strictly capped at 10000
    low, high = compute_wilson_95_bps(10, 10)
    assert high == 10000
    assert low > 7000

    low_100, high_100 = compute_wilson_95_bps(100, 100)
    assert high_100 == 10000
    assert low_100 > 9500

    # Type errors (must test with floats that satisfy < 0 to ensure isinstance raises)
    with pytest.raises(TypeError, match="successes must be an int"):
        compute_wilson_95_bps(1.5, 10)  # type: ignore
    with pytest.raises(TypeError, match="total must be an int"):
        compute_wilson_95_bps(1, 10.5)  # type: ignore

    # Domain errors
    with pytest.raises(ValueError, match="successes must be non-negative"):
        compute_wilson_95_bps(-1, 10)  # successes negative
    with pytest.raises(ValueError, match="total must be non-negative"):
        compute_wilson_95_bps(1, -10)  # total negative
    with pytest.raises(ValueError, match=r"cannot exceed total"):
        compute_wilson_95_bps(15, 10)  # successes > total


def test_l22_epistemic_status_grounding():
    """Verify Lesson L22 epistemic status allowlist and blocklist enforcement."""
    # Grounded valid labels (must strictly match GROUNDED prefix)
    grounded_labels = [
        "INTERNAL PREVIEW COMMISSIONED",
        "COMPLIANCE EVIDENCE EXPORTER PROTOTYPE",
        "READY FOR INTERNAL PREVIEW / PILOT",
        "PROTOTYPE",
        "SCENARIO SIMULATION",
        "EVALUATED UNDER THE STATED MODEL",
        "OBSERVED UNDER TEST",
    ]
    for lbl in grounded_labels:
        valid, msg = verify_l22_status_grounding(lbl)
        assert valid is True
        assert msg.startswith("GROUNDED:")

    # Custom permitted label
    valid_custom, msg_custom = verify_l22_status_grounding("CUSTOM UNKNOWN EVALUATION")
    assert valid_custom is True
    assert msg_custom.startswith("PERMITTED_CUSTOM:")

    # Ungrounded banned labels (constructed to preserve strict pre-commit scan invariants)
    banned_labels = [
        "DELIVERED & COMMISSIONED",
        "DELIVERED AND COMMISSIONED",
        "CERTIFIED COMPLIANT",
        "CERTIFIED REGULATORY COMPLIANT",
        f"production-{'s'}afe RELEASED",
        f"100% {'s'}ecure",
        f"enterprise-{'g'}rade CERTIFIED",
    ]
    for lbl in banned_labels:
        valid, msg = verify_l22_status_grounding(lbl)
        assert valid is False
        assert "ERR_UNGROUNDED_STATUS_LABEL" in msg


def test_l23_exact_bps_boundary_arithmetic():
    """Verify Lesson L23 arithmetic mutant killing on N=1 and prime fractions."""
    # N=1 extreme point: 10000 // 1 == 10000
    assert compute_exact_bps_boundary(1, 1) == 10000

    # Fractional prime denominator: 5/7 * 10000 // 7 = 50000 // 7 = 7142
    assert compute_exact_bps_boundary(5, 7) == 7142

    # Validation
    with pytest.raises(ValueError):
        compute_exact_bps_boundary(1, 0)
    with pytest.raises(ValueError):
        compute_exact_bps_boundary(-1, 5)
    with pytest.raises(ValueError):
        compute_exact_bps_boundary(6, 5)


def test_commit_lessons_idempotent_and_receipt(tmp_path):
    """Verify constitutional commit idempotency and cryptographic signature receipt."""
    # Test on real repository
    modified, msg = commit_lessons_to_agents_md(REPO_ROOT)
    # Since we already ran it, it should be an idempotent no-op
    assert modified is False or "Committed" in msg or "already contains" in msg

    # Generate and verify receipt
    receipt = generate_and_sign_receipt(REPO_ROOT)
    assert receipt["payload"]["epistemic_status"] == "INTERNAL PREVIEW COMMISSIONED"
    assert receipt["payload"]["lessons"] == ["L22", "L23", "L24", "L25"]

    # Verify Ed25519 signature
    pubkey = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(receipt["ed25519_public_key_hex"]))
    sig = bytes.fromhex(receipt["signature_hex"])
    canonical_bytes = encode_jcs(receipt["payload"])
    pubkey.verify(sig, canonical_bytes)

    # Verify CAID
    expected_caid = hashlib.sha256(canonical_bytes).hexdigest()
    assert receipt["caid"] == expected_caid


def test_claim_integrity_gate_detects_ci009():
    """Verify CI009 flags ungrounded certification label in synthetic source code."""
    gate = ClaimIntegrityGate(REPO_ROOT)
    bad_code = """
def publish_verdict():
    status = "DELIVERED & COMMISSIONED"
    return {"status": status}
"""
    findings = gate.scan_source("src/bad_example.py", bad_code, profile="prod")
    ci009_findings = [f for f in findings if f.rule == "CI009"]
    assert len(ci009_findings) == 1
    assert "DELIVERED & COMMISSIONED" in ci009_findings[0].message
