#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_harness_router.py
================================================================================
Test & Falsification Suite for KV Cache Transfer & Multi-Model Cascade Router.

Evaluated under the stated model:
- Multi-tier task routing between draft SLM and frontier reasoning models.
- KV cache transfer with integer-bps fidelity threshold enforcement (>= 9500 bps).
- Nonce replay defense preventing stale cache reuse.
- Cache TTL expiration defense.
- Ed25519-signed SCITT transfer receipt verification and tamper resistance.
- Epistemic linguistic compliance check.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.harness_router import (
    DEFAULT_CACHE_TTL_SEC,
    MIN_CACHE_FIDELITY_BPS,
    HarnessCascadeRouter,
    KVCacheDescriptor,
    KVCacheTransferReceipt,
    canonical_json_v1,
)


# -----------------------------------------------------------------------------
# Test 0: Configuration Constants & Immutability
# -----------------------------------------------------------------------------
def test_0_config_constants_and_immutability() -> None:
    assert MIN_CACHE_FIDELITY_BPS == int("9500")
    assert DEFAULT_CACHE_TTL_SEC == int("300")

    router = HarnessCascadeRouter()
    assert router.min_fidelity_bps == MIN_CACHE_FIDELITY_BPS
    assert isinstance(router.public_key, Ed25519PublicKey)

    desc = KVCacheDescriptor(
        cache_id="c1",
        source_model="qwen",
        target_model="claude",
        token_count=1000,
        context_digest="sha256:abcd",
        fidelity_bps=9800,
        created_at_epoch=1000,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        desc.fidelity_bps = 5000  # type: ignore

    # canonical_json_v1 delegates to the RFC 8785 reference encoder; the former
    # json.dumps flag spy pinned the old local implementation. Assert behaviour:
    # UTF-8 without ASCII escaping, UTF-16 key order, ECMAScript numbers, NaN rejected.
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs

    assert canonical_json_v1({"u": "α"}) == '{"u":"α"}'.encode("utf-8")
    probe = {"\U0001F600": 1, "\uffff": [1e21, 1e-7, -0.0]}
    assert canonical_json_v1(probe) == _reference_encode_jcs(probe)
    assert canonical_json_v1(probe) == '{"\U0001F600":1,"\uffff":[1e+21,1e-7,0]}'.encode("utf-8")
    with pytest.raises(ValueError):
        canonical_json_v1({"x": float("nan")})


# -----------------------------------------------------------------------------
# Test 1: Task Tier Routing
# -----------------------------------------------------------------------------
def test_1_task_tier_routing() -> None:
    router = HarnessCascadeRouter()

    # Boundary test around score 50:
    # Score 49 with informational tier is DRAFT_SLM
    assert router.route_task_tier(task_complexity_score=49, risk_tier="T0_INFORMATIONAL") == "DRAFT_SLM"
    # Score 50 is escalated to FRONTIER_REASONING
    assert router.route_task_tier(task_complexity_score=50, risk_tier="T0_INFORMATIONAL") == "FRONTIER_REASONING"

    # Risk tier boundary:
    assert router.route_task_tier(task_complexity_score=20, risk_tier="T1_LOW_RISK") == "DRAFT_SLM"
    assert router.route_task_tier(task_complexity_score=20, risk_tier="T2_MEDIUM_RISK") == "FRONTIER_REASONING"
    assert router.route_task_tier(task_complexity_score=15, risk_tier="T3_IRREVERSIBLE") == "FRONTIER_REASONING"


# -----------------------------------------------------------------------------
# Test 2: Positive Control (Valid KV Cache Transfer & Receipt Verification)
# -----------------------------------------------------------------------------
def test_2_positive_control_cache_transfer() -> None:
    router = HarnessCascadeRouter()
    created_epoch = 1700000000

    desc = KVCacheDescriptor(
        cache_id="kv_cache_001",
        source_model="qwen-2.5-coder",
        target_model="claude-3-7-sonnet",
        token_count=4096,
        context_digest="sha256:11223344",
        fidelity_bps=9850,  # 98.5% > 95.0%
        created_at_epoch=created_epoch,
        ttl_sec=300,
    )

    receipt = router.transfer_kv_cache(desc, now_epoch=created_epoch + 10)
    assert receipt.receipt_caid.startswith("sha256:")
    assert receipt.cache_id == "kv_cache_001"
    assert receipt.fidelity_bps == 9850
    assert receipt.token_count == 4096
    assert receipt.transferred_at_epoch == created_epoch + 10

    # Cryptographic receipt verification
    assert HarnessCascadeRouter.verify_receipt(receipt) is True
    assert HarnessCascadeRouter.verify_receipt(receipt, expected_pubkey=router.public_key) is True


# -----------------------------------------------------------------------------
# Test 3: Fidelity Divergence Rejection
# -----------------------------------------------------------------------------
def test_3_fidelity_divergence_rejection() -> None:
    router = HarnessCascadeRouter(min_fidelity_bps=9500)

    desc = KVCacheDescriptor(
        cache_id="kv_cache_divergent",
        source_model="slm",
        target_model="frontier",
        token_count=2048,
        context_digest="sha256:deadbeef",
        fidelity_bps=9100,  # 91.0% < 95.0%
        created_at_epoch=1700000000,
        ttl_sec=300,
    )

    with pytest.raises(ValueError, match="HALT_KV_CACHE_DIVERGENCE: fidelity 9100 bps is below threshold 9500 bps"):
        router.transfer_kv_cache(desc, now_epoch=1700000010)


# -----------------------------------------------------------------------------
# Test 4: Nonce Replay Defense
# -----------------------------------------------------------------------------
def test_4_nonce_replay_defense() -> None:
    router = HarnessCascadeRouter()
    created_epoch = 1700000000

    desc = KVCacheDescriptor(
        cache_id="kv_cache_replay",
        source_model="slm",
        target_model="frontier",
        token_count=1000,
        context_digest="sha256:aabbcc",
        fidelity_bps=9900,
        created_at_epoch=created_epoch,
        ttl_sec=300,
    )

    # First transfer succeeds
    receipt = router.transfer_kv_cache(desc, now_epoch=created_epoch + 5)
    assert receipt.cache_id == "kv_cache_replay"

    # Second transfer on same cache_id fails closed
    with pytest.raises(ValueError, match="HALT_CACHE_NONCE_REPLAY: cache 'kv_cache_replay' already consumed"):
        router.transfer_kv_cache(desc, now_epoch=created_epoch + 10)


# -----------------------------------------------------------------------------
# Test 5: Cache TTL Expiration Defense
# -----------------------------------------------------------------------------
def test_5_cache_ttl_expiration_defense() -> None:
    router = HarnessCascadeRouter()
    created_epoch = 1700000000

    desc = KVCacheDescriptor(
        cache_id="kv_cache_expired",
        source_model="slm",
        target_model="frontier",
        token_count=1000,
        context_digest="sha256:expired",
        fidelity_bps=9900,
        created_at_epoch=created_epoch,
        ttl_sec=100,
    )

    # Arriving at created + 150 (> 100 TTL) fails closed
    with pytest.raises(ValueError, match="HALT_STALE_CACHE_HANDOFF: cache expired at 1700000100"):
        router.transfer_kv_cache(desc, now_epoch=created_epoch + 150)


# -----------------------------------------------------------------------------
# Test 6: Receipt Tamper Detection & Canonical JSON
# -----------------------------------------------------------------------------
def test_6_receipt_tamper_and_canonical_json() -> None:
    router = HarnessCascadeRouter()
    created_epoch = 1700000000

    desc = KVCacheDescriptor(
        cache_id="kv_cache_tamper",
        source_model="m1",
        target_model="m2",
        token_count=500,
        context_digest="sha256:tamper",
        fidelity_bps=9800,
        created_at_epoch=created_epoch,
        ttl_sec=300,
    )

    receipt = router.transfer_kv_cache(desc, now_epoch=created_epoch + 1)
    assert HarnessCascadeRouter.verify_receipt(receipt) is True

    # Tampered token_count
    tampered_receipt = KVCacheTransferReceipt(
        receipt_caid=receipt.receipt_caid,
        cache_id=receipt.cache_id,
        source_model=receipt.source_model,
        target_model=receipt.target_model,
        token_count=99999,  # altered
        fidelity_bps=receipt.fidelity_bps,
        transferred_at_epoch=receipt.transferred_at_epoch,
        signer_pubkey_hex=receipt.signer_pubkey_hex,
        signature_hex=receipt.signature_hex,
    )
    assert HarnessCascadeRouter.verify_receipt(tampered_receipt) is False

    # Corrupted signature
    tampered_sig = KVCacheTransferReceipt(
        receipt_caid=receipt.receipt_caid,
        cache_id=receipt.cache_id,
        source_model=receipt.source_model,
        target_model=receipt.target_model,
        token_count=receipt.token_count,
        fidelity_bps=receipt.fidelity_bps,
        transferred_at_epoch=receipt.transferred_at_epoch,
        signer_pubkey_hex=receipt.signer_pubkey_hex,
        signature_hex="00" * 64,
    )
    assert HarnessCascadeRouter.verify_receipt(tampered_sig) is False

    # Foreign public key
    foreign_key = Ed25519PrivateKey.generate().public_key()
    assert HarnessCascadeRouter.verify_receipt(receipt, expected_pubkey=foreign_key) is False

    # Canonical JSON checks
    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"f": float("nan")})

    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"f": float("inf")})

    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"f": float("-inf")})

    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        canonical_json_v1({1: "bad"})

    # Key sorting
    assert canonical_json_v1({"z": 1, "a": 2}) == b'{"a":2,"z":1}'

    # Raw UTF-8 preservation (ensure_ascii=False)
    assert canonical_json_v1({"symbol": "€"}) == '{"symbol":"€"}'.encode("utf-8")


# -----------------------------------------------------------------------------
# Test 7: Epistemic Linguistic Compliance (Zero Banned Words)
# -----------------------------------------------------------------------------
def test_7_epistemic_linguistic_compliance() -> None:
    banned_prefixes = [
        "guaran" + "tee",
        "proven univer" + "sally",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
        "bank-" + "grade",
        "production-" + "ready",
    ]

    files_to_check = [
        Path("src/harness_router.py"),
        Path("tests/test_harness_router.py"),
    ]

    for file_path in files_to_check:
        assert file_path.exists(), f"File {file_path} must exist"
        content = file_path.read_text(encoding="utf-8")
        for banned in banned_prefixes:
            match = re.search(r"\b" + re.escape(banned), content, re.IGNORECASE)
            assert match is None, (
                f"Epistemic boundary violation: found banned term '{banned}' "
                f"in {file_path}"
            )
