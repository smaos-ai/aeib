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
src/harness_router.py
================================================================================
KV Cache Transfer & Multi-Model Cascade Router (NVIDIA Model Transfer Pattern).

Implements KV cache handoff across multi-model cascades:
1. Multi-Tier Model Cascade:
   Routes fast perception/draft queries to cheap models (e.g. Qwen / Haiku) and
   escalates complex reasoning / mutation tasks to frontier models (e.g. Claude / DeepSeek).
2. KV Cache Handoff & Prefill Skip:
   Enables transferring cached context representations between models to avoid
   redundant prefill token burn.
3. Cache Fidelity Threshold Latch:
   Evaluates alignment fidelity in integer basis points (0..10000 bps). If fidelity
   drops below the 9500 bps (95.0%) threshold, fails closed with HALT_KV_CACHE_DIVERGENCE
   and forces deterministic clean-slate re-prefill.
4. Anti-Replay & Stale Cache Defense:
   Prevents replay of consumed cache handoff nonces and halts on expired cache TTLs.
5. Ed25519-Signed SCITT Handoff Receipts:
   Emits an RFC 8785 canonical JSON transfer receipt for every model switch.

Evaluated under the stated model:
- Zero fake crypto: Real Ed25519 asymmetric cryptography.
- RFC 8785 canonical JSON sorting and SHA-256 digests.
- Fail-closed halts on cache divergence, nonce replay, or stale TTLs.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:
    from jcs_canonicalizer import encode_jcs as _reference_encode_jcs

MIN_CACHE_FIDELITY_BPS: int = 9500  # claim: config (95.0% minimum cache fidelity)
DEFAULT_CACHE_TTL_SEC: int = 300  # claim: config (5 minutes TTL)


def canonical_json_v1(obj: Any) -> bytes:
    """
    Deterministic RFC 8785 JSON canonical serializer.
    Rejects non-finite floats, non-string dictionary keys, and extraneous whitespace.
    """
    def _check(v: Any) -> None:
        if isinstance(v, float):
            if v != v or v == float("inf") or v == float("-inf"):
                raise ValueError("ERR_NON_FINITE_FLOAT")
        elif isinstance(v, dict):
            for k, val in v.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check(val)
        elif isinstance(v, (list, tuple)):
            for item in v:
                _check(item)

    _check(obj)
    return _reference_encode_jcs(obj)


def sha256_hex_prefixed(data: bytes) -> str:
    """Computes a lowercase hex SHA-256 digest with sha256: prefix."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class KVCacheDescriptor:
    """Immutable descriptor of intermediate KV cache context ready for handoff."""
    cache_id: str
    source_model: str
    target_model: str
    token_count: int
    context_digest: str
    fidelity_bps: int
    created_at_epoch: int
    ttl_sec: int = DEFAULT_CACHE_TTL_SEC


@dataclass(frozen=True)
class KVCacheTransferReceipt:
    """Signed execution receipt for an authorized KV cache handoff."""
    receipt_caid: str
    cache_id: str
    source_model: str
    target_model: str
    token_count: int
    fidelity_bps: int
    transferred_at_epoch: int
    signer_pubkey_hex: str
    signature_hex: str


class HarnessCascadeRouter:
    """
    Routes tasks across models and manages KV cache handoffs with fidelity bounds.
    """

    def __init__(
        self,
        min_fidelity_bps: int = MIN_CACHE_FIDELITY_BPS,
        signing_key: Optional[Ed25519PrivateKey] = None,
    ) -> None:
        self.min_fidelity_bps = min_fidelity_bps
        self._consumed_cache_ids: Set[str] = set()
        if signing_key is None:
            self._signing_key = Ed25519PrivateKey.generate()
        else:
            self._signing_key = signing_key
        self._public_key = self._signing_key.public_key()

    @property
    def public_key(self) -> Ed25519PublicKey:
        return self._public_key

    def public_key_hex(self) -> str:
        return self._public_key.public_bytes_raw().hex()

    def route_task_tier(self, task_complexity_score: int, risk_tier: str) -> str:
        """
        Determines the appropriate model tier based on task complexity and risk.
        Score < 50 and informational -> 'DRAFT_SLM'; else 'FRONTIER_REASONING'.
        """
        if task_complexity_score < 50 and risk_tier in ("T0_INFORMATIONAL", "T1_LOW_RISK"):
            return "DRAFT_SLM"
        return "FRONTIER_REASONING"

    def transfer_kv_cache(
        self,
        descriptor: KVCacheDescriptor,
        now_epoch: Optional[int] = None,
    ) -> KVCacheTransferReceipt:
        """
        Evaluates and authorizes KV cache handoff from source model to target model.
        Fails closed on replay, expiry, or fidelity divergence.
        """
        # 1. Nonce replay defense
        if descriptor.cache_id in self._consumed_cache_ids:
            raise ValueError(f"HALT_CACHE_NONCE_REPLAY: cache '{descriptor.cache_id}' already consumed")

        # 2. Stale TTL check
        current_time = int(time.time()) if now_epoch is None else now_epoch
        if current_time > descriptor.created_at_epoch + descriptor.ttl_sec:
            raise ValueError(
                f"HALT_STALE_CACHE_HANDOFF: cache expired at "
                f"{descriptor.created_at_epoch + descriptor.ttl_sec}, current is {current_time}"
            )

        # 3. Minimum fidelity check
        if descriptor.fidelity_bps < self.min_fidelity_bps:
            raise ValueError(
                f"HALT_KV_CACHE_DIVERGENCE: fidelity {descriptor.fidelity_bps} bps "
                f"is below threshold {self.min_fidelity_bps} bps"
            )

        # Mark cache ID as consumed
        self._consumed_cache_ids.add(descriptor.cache_id)

        # Emit signed receipt
        receipt_body = {
            "cache_id": descriptor.cache_id,
            "fidelity_bps": descriptor.fidelity_bps,
            "source_model": descriptor.source_model,
            "target_model": descriptor.target_model,
            "token_count": descriptor.token_count,
            "transferred_at_epoch": current_time,
        }
        canonical_bytes = canonical_json_v1(receipt_body)
        receipt_caid = sha256_hex_prefixed(canonical_bytes)
        signature = self._signing_key.sign(canonical_bytes)

        return KVCacheTransferReceipt(
            receipt_caid=receipt_caid,
            cache_id=descriptor.cache_id,
            source_model=descriptor.source_model,
            target_model=descriptor.target_model,
            token_count=descriptor.token_count,
            fidelity_bps=descriptor.fidelity_bps,
            transferred_at_epoch=current_time,
            signer_pubkey_hex=self.public_key_hex(),
            signature_hex=signature.hex(),
        )

    @staticmethod
    def verify_receipt(
        receipt: KVCacheTransferReceipt,
        expected_pubkey: Optional[Ed25519PublicKey] = None,
    ) -> bool:
        """Cryptographically verifies a KV cache transfer receipt."""
        try:
            pub_key = expected_pubkey
            if pub_key is None:
                pub_key = Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(receipt.signer_pubkey_hex)
                )

            receipt_body = {
                "cache_id": receipt.cache_id,
                "fidelity_bps": receipt.fidelity_bps,
                "source_model": receipt.source_model,
                "target_model": receipt.target_model,
                "token_count": receipt.token_count,
                "transferred_at_epoch": receipt.transferred_at_epoch,
            }
            canonical_bytes = canonical_json_v1(receipt_body)
            computed_caid = sha256_hex_prefixed(canonical_bytes)
            if computed_caid != receipt.receipt_caid:
                return False

            pub_key.verify(bytes.fromhex(receipt.signature_hex), canonical_bytes)
            return True
        except (InvalidSignature, ValueError, Exception):
            return False
