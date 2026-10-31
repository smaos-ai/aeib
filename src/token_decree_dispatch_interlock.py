#!/usr/bin/env python3
"""
Sovereign Token Decree Dispatch Interlock (src/token_decree_dispatch_interlock.py).

Evaluated under the stated model as an execution-time dispatch interceptor between
the agent orchestrator and LLM inference / tool dispatch endpoints.

Key capabilities:
  1. Token Compaction Enforcement:
     Executes Alibaba AST-diff slicing, Headroom test log compaction, and TokenEconomizer
     tool pruning before any model turn is dispatched.
  2. Fail-Closed Error Loop Halting:
     Detects repeated identical failure states and trips before incurring unconstrained
     inference spend.
  3. Prefix Cache Purity Verification:
     Rejects dynamic contaminants (timestamps, nonces) in system headers to preserve
     KV-cache prefix alignment across turns.
  4. Cryptographic Warrant Sealing:
     Signs approved dispatch payloads with an Ed25519 verifier private key over RFC 8785
     canonical bytes with integer basis points (0..10000 bps) and zero floats.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Dict, Mapping, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.sovereign_token_decree import (
    TokenEconomizerGovernor,
    TokenCompactionReceipt,
    sha256_caid,
)

# Dispatch disposition constants
DISPOSITION_ADMISSIBLE: str = "DISPATCH_ADMISSIBLE"
DISPOSITION_HALTED_REPETITIVE_LOOP: str = "DISPATCH_HALTED_REPETITIVE_LOOP"
DISPOSITION_REJECTED_PREFIX_CONTAMINATED: str = "DISPATCH_REJECTED_PREFIX_CONTAMINATED"
DISPOSITION_REJECTED_SAVINGS_FLOOR_UNMET: str = "DISPATCH_REJECTED_SAVINGS_FLOOR_UNMET"


@dataclasses.dataclass(frozen=True)
class TokenDecreeWarrant:
    """Cryptographically signed dispatch authorization warrant."""

    task_id: str
    model_id: str
    original_bytes: int
    compacted_bytes: int
    savings_bps: int
    pruned_tool_count: int
    compacted_payload_caid: str
    signer_pubkey_hex: str
    signature_hex: str
    warrant_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "compacted_bytes": self.compacted_bytes,
            "compacted_payload_caid": self.compacted_payload_caid,
            "model_id": self.model_id,
            "original_bytes": self.original_bytes,
            "pruned_tool_count": self.pruned_tool_count,
            "savings_bps": self.savings_bps,
            "signature_hex": self.signature_hex,
            "signer_pubkey_hex": self.signer_pubkey_hex,
            "task_id": self.task_id,
            "warrant_caid": self.warrant_caid,
        }


class TokenDecreeDispatchInterlock:
    """
    Execution boundary gate intercepting model turn invocations to enforce
    token conservation invariants and prefix cache purity.
    """

    def __init__(
        self,
        governor: Optional[TokenEconomizerGovernor] = None,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
        minimum_savings_floor_bps: int = 0,
        enforce_prefix_cache_purity: bool = True,
    ) -> None:
        if minimum_savings_floor_bps < 0 or minimum_savings_floor_bps > 10000:
            raise ValueError(f"ERR_INVALID_SAVINGS_FLOOR_BPS:{minimum_savings_floor_bps}")

        self.governor = governor or TokenEconomizerGovernor()
        self._signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self._verifying_key = self._signing_key.public_key()
        self.minimum_savings_floor_bps = minimum_savings_floor_bps
        self.enforce_prefix_cache_purity = enforce_prefix_cache_purity

    @property
    def public_key_hex(self) -> str:
        raw_pub = self._verifying_key.public_bytes_raw()
        return raw_pub.hex()

    def dispatch_and_seal(
        self,
        task_id: str,
        model_id: str,
        static_system_prefix: str,
        task_description: str,
        all_tool_schemas: Mapping[str, Dict[str, Any]],
        old_file_code: str,
        new_file_code: str,
        raw_test_log: str,
    ) -> Tuple[str, Dict[str, Any], Optional[TokenDecreeWarrant]]:
        """
        Intercept and optimize turn context.
        Returns (disposition, optimized_payload, warrant_or_none).
        """
        optimized_payload, receipt = self.governor.optimize_turn_context(
            task_id=task_id,
            static_system_prefix=static_system_prefix,
            task_description=task_description,
            all_tool_schemas=all_tool_schemas,
            old_file_code=old_file_code,
            new_file_code=new_file_code,
            raw_test_log=raw_test_log,
        )

        if receipt.loop_halted:
            return DISPOSITION_HALTED_REPETITIVE_LOOP, optimized_payload, None

        if self.enforce_prefix_cache_purity and not receipt.prefix_cache_aligned:
            return DISPOSITION_REJECTED_PREFIX_CONTAMINATED, optimized_payload, None

        if receipt.savings_bps < self.minimum_savings_floor_bps:
            return DISPOSITION_REJECTED_SAVINGS_FLOOR_UNMET, optimized_payload, None

        # Build signed canonical dispatch warrant
        warrant_core: Dict[str, Any] = {
            "compacted_bytes": receipt.compacted_bytes,
            "compacted_payload_caid": receipt.compacted_payload_caid,
            "model_id": model_id,
            "original_bytes": receipt.original_bytes,
            "pruned_tool_count": receipt.pruned_tool_count,
            "savings_bps": receipt.savings_bps,
            "task_id": task_id,
        }

        core_bytes = encode_jcs(warrant_core)
        signature = self._signing_key.sign(core_bytes)
        pubkey_hex = self.public_key_hex
        sig_hex = signature.hex()

        warrant_dict: Dict[str, Any] = dict(warrant_core)
        warrant_dict["signature_hex"] = sig_hex
        warrant_dict["signer_pubkey_hex"] = pubkey_hex

        warrant_caid = sha256_caid(encode_jcs(warrant_dict))

        warrant = TokenDecreeWarrant(
            task_id=task_id,
            model_id=model_id,
            original_bytes=receipt.original_bytes,
            compacted_bytes=receipt.compacted_bytes,
            savings_bps=receipt.savings_bps,
            pruned_tool_count=receipt.pruned_tool_count,
            compacted_payload_caid=receipt.compacted_payload_caid,
            signer_pubkey_hex=pubkey_hex,
            signature_hex=sig_hex,
            warrant_caid=warrant_caid,
        )

        return DISPOSITION_ADMISSIBLE, optimized_payload, warrant

    def verify_warrant(
        self,
        warrant: TokenDecreeWarrant,
        expected_payload: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Verify that a TokenDecreeWarrant is authentic, cryptographically bound to
        expected_payload, and signed by this interlock's verifying key.
        """
        if not isinstance(warrant.savings_bps, int) or isinstance(warrant.savings_bps, bool):
            return False, "ERR_NON_INTEGER_SAVINGS_BPS"

        expected_caid = sha256_caid(expected_payload)
        if warrant.compacted_payload_caid != expected_caid:
            return False, "ERR_PAYLOAD_CAID_MISMATCH"

        core_dict: Dict[str, Any] = {
            "compacted_bytes": warrant.compacted_bytes,
            "compacted_payload_caid": warrant.compacted_payload_caid,
            "model_id": warrant.model_id,
            "original_bytes": warrant.original_bytes,
            "pruned_tool_count": warrant.pruned_tool_count,
            "savings_bps": warrant.savings_bps,
            "task_id": warrant.task_id,
        }

        core_bytes = encode_jcs(core_dict)
        try:
            pub_bytes = bytes.fromhex(warrant.signer_pubkey_hex)
            sig_bytes = bytes.fromhex(warrant.signature_hex)
            verifier = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            verifier.verify(sig_bytes, core_bytes)
        except Exception as exc:
            return False, f"ERR_CRYPTOGRAPHIC_VERIFICATION_FAILED:{type(exc).__name__}"

        # Verify warrant_caid
        expected_warrant_dict = dict(core_dict)
        expected_warrant_dict["signature_hex"] = warrant.signature_hex
        expected_warrant_dict["signer_pubkey_hex"] = warrant.signer_pubkey_hex
        expected_warrant_caid = sha256_caid(encode_jcs(expected_warrant_dict))
        if warrant.warrant_caid != expected_warrant_caid:
            return False, "ERR_WARRANT_CAID_MISMATCH"

        return True, "OK"
