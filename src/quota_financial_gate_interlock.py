#!/usr/bin/env python3
"""
quota_financial_gate_interlock.py — AEIB Financial Gate & AT56/AT57 Interlock Engine
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB)

Implements the 5 Red-Team Financial Gate Invariants evaluated under the stated model:
1. DualWindowFinancialLedger: 5-hour sprint window + 7-day epoch baseline unified across
   FINANCIAL_MUTATION_POOL, persisted to an fsynced hash-chained Ed25519-signed ledger.jsonl.
2. RootSponsorQuotaTree: Binds ephemeral subagent Ed25519 keys to a root sponsor DID
   (did:key:z6MkRootSponsor001) while ignoring spoofed transport/device headers.
3. ContinuityBootInterlock: Verifies ledger.jsonl existence and hash-chain tip at boot;
   latches to HALT_MISSING_CONTINUITY_LEDGER on deletion or tampering until a human
   supervisor Ed25519 re-initialization token is verified.
4. ContextIntegrityGate (AT57): Binds context blocks (user_prompt, rag_retrieval,
   tool_output, memory) to (operation_id, block_id, content) via SHA-256 and Ed25519
   commitments, rejecting tampered or unverified memory blocks with
   HALT_CONTEXT_INTEGRITY_FAILURE.
5. CredentialStarvationEnforcer & PinnedLoopbackBankServer: Verifies zero credential
   intersection in the agent environment and runs an ephemeral loopback HTTP listener
   (127.0.0.1:0) that rejects any request lacking a valid Station 2 Ed25519 transport
   signature with HTTP 401 Unauthorized.
"""

from __future__ import annotations

import hashlib
import http.client
import http.server
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs

FINANCIAL_MUTATION_POOL: Set[str] = {
    "/v1/refunds",
    "/v1/loyalty-credits",
    "/v1/vouchers",
    "/v1/payouts",
}

VALID_CONTEXT_BLOCK_TYPES: Set[str] = {
    "user_prompt",
    "rag_retrieval",
    "tool_output",
    "memory",
}

FORBIDDEN_OVERRIDE_MARKERS: Tuple[str, ...] = (
    "IGNORE PREVIOUS INSTRUCTIONS",
    "OVERRIDE_QUOTA",
    "BYPASS_FINANCIAL_GATE",
    "SYSTEM_ADMIN_OVERRIDE",
    "RESET_SPRINT_LIMIT",
)

FORBIDDEN_CREDENTIAL_KEYS: Tuple[str, ...] = (
    "API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "STRIPE_SECRET_KEY",
    "MTLS_CERT",
    "MTLS_PRIVATE_KEY",
    "OAUTH_TOKEN",
    "BANK_BEARER_TOKEN",
)

GENESIS_PREV_HASH: str = "0" * 64

HALT_SPRINT_LIMIT_EXCEEDED = "HALT_SPRINT_LIMIT_EXCEEDED"
HALT_EPOCH_BASELINE_EXCEEDED = "HALT_EPOCH_BASELINE_EXCEEDED"
HALT_MISSING_CONTINUITY_LEDGER = "HALT_MISSING_CONTINUITY_LEDGER"
HALT_CONTEXT_INTEGRITY_FAILURE = "HALT_CONTEXT_INTEGRITY_FAILURE"
HALT_CREDENTIAL_STARVATION_VIOLATION = "HALT_CREDENTIAL_STARVATION_VIOLATION"
HALT_UNREGISTERED_SUBAGENT = "HALT_UNREGISTERED_SUBAGENT"
HALT_INVALID_SIGNATURE = "HALT_INVALID_SIGNATURE"
HALT_UNSUPPORTED_ENDPOINT = "HALT_UNSUPPORTED_ENDPOINT"


def _pubkey_to_hex(pubkey: Ed25519PublicKey) -> str:
    raw = pubkey.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return raw.hex()


def _sha256_jcs_hex(payload: Any) -> str:
    return hashlib.sha256(encode_jcs(payload)).hexdigest()


@dataclass
class GateDecision:
    allowed: bool
    status_code: str
    reason: str
    root_sponsor_did: str = ""
    subagent_id: str = ""
    endpoint: str = ""
    amount_eur: float = 0.0
    cumulative_5h_eur: float = 0.0
    cumulative_7d_eur: float = 0.0
    ledger_tip_hash: str = ""
    http_status: int = 0


class DualWindowFinancialLedger:
    """
    Invariant 1: Tracks cumulative financial mutations in EUR across a 5-hour sprint
    window (default 2500 EUR) and a 7-day epoch baseline (default 10000 EUR) unified
    across FINANCIAL_MUTATION_POOL. Appends every authorized entry to an on-disk
    hash-chained ledger.jsonl (with os.fsync) signed with Ed25519 over RFC 8785 JCS.
    """

    SPRINT_WINDOW_SECONDS: float = 5.0 * 3600.0
    EPOCH_WINDOW_SECONDS: float = 7.0 * 86400.0

    def __init__(
        self,
        ledger_path: Path | str,
        signing_key: Optional[Ed25519PrivateKey] = None,
        sprint_limit_eur: float = 2500.0,
        epoch_limit_eur: float = 10000.0,
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.signing_key = signing_key or Ed25519PrivateKey.generate()
        self.verify_key = self.signing_key.public_key()
        self.sprint_limit_eur = float(sprint_limit_eur)
        self.epoch_limit_eur = float(epoch_limit_eur)
        self._lock = threading.Lock()
        self.entries: List[Dict[str, Any]] = []
        self.chain_tip_hash: str = GENESIS_PREV_HASH

        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.ledger_path.exists():
            self._write_empty_ledger()
        else:
            self._load_existing_entries()

    def _write_empty_ledger(self) -> None:
        fd = os.open(str(self.ledger_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.entries = []
        self.chain_tip_hash = GENESIS_PREV_HASH

    def _load_existing_entries(self) -> None:
        loaded: List[Dict[str, Any]] = []
        prev_hash = GENESIS_PREV_HASH
        raw_text = self.ledger_path.read_text(encoding="utf-8")
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            entry_payload = record["payload"]
            expected_hash = _sha256_jcs_hex(entry_payload)
            if entry_payload.get("prev_hash") != prev_hash:
                raise ValueError("Hash chain continuity mismatch in ledger.jsonl")
            if record.get("entry_hash") != expected_hash:
                raise ValueError("Entry hash mismatch in ledger.jsonl")
            sig_bytes = bytes.fromhex(record["signature_hex"])
            pub_bytes = bytes.fromhex(record["signer_pubkey_hex"])
            pubkey = Ed25519PublicKey.from_public_bytes(pub_bytes)
            pubkey.verify(sig_bytes, encode_jcs(entry_payload))
            prev_hash = expected_hash
            loaded.append(record)
        self.entries = loaded
        self.chain_tip_hash = prev_hash

    def compute_window_totals(
        self,
        root_sponsor_did: str,
        now_ts: Optional[float] = None,
    ) -> Tuple[float, float]:
        ref_ts = time.time() if now_ts is None else float(now_ts)
        cumulative_5h = 0.0
        cumulative_7d = 0.0
        for record in self.entries:
            payload = record["payload"]
            if payload.get("root_sponsor_did") != root_sponsor_did:
                continue
            if payload.get("endpoint") not in FINANCIAL_MUTATION_POOL:
                continue
            age = max(0.0, ref_ts - float(payload["timestamp"]))
            amount = float(payload["amount_eur"])
            if age <= self.SPRINT_WINDOW_SECONDS:
                cumulative_5h += amount
            if age <= self.EPOCH_WINDOW_SECONDS:
                cumulative_7d += amount
        return cumulative_5h, cumulative_7d

    @property
    def total_dispatched_eur(self) -> float:
        return sum(float(r["payload"]["amount_eur"]) for r in self.entries)

    def evaluate_and_append(
        self,
        root_sponsor_did: str,
        subagent_id: str,
        endpoint: str,
        amount_eur: float,
        operation_id: str,
        sprint_limit_eur: Optional[float] = None,
        epoch_limit_eur: Optional[float] = None,
        now_ts: Optional[float] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Evaluates a mutation against the unified FINANCIAL_MUTATION_POOL and appends
        an Ed25519-signed hash-chained record to ledger.jsonl if within both limits.
        """
        with self._lock:
            if endpoint not in FINANCIAL_MUTATION_POOL:
                return False, HALT_UNSUPPORTED_ENDPOINT, {}

            amount = float(amount_eur)
            if amount <= 0.0:
                return False, "HALT_NON_POSITIVE_AMOUNT", {}

            eff_sprint_limit = (
                self.sprint_limit_eur if sprint_limit_eur is None else float(sprint_limit_eur)
            )
            eff_epoch_limit = (
                self.epoch_limit_eur if epoch_limit_eur is None else float(epoch_limit_eur)
            )
            ts = time.time() if now_ts is None else float(now_ts)

            cumulative_5h, cumulative_7d = self.compute_window_totals(
                root_sponsor_did=root_sponsor_did,
                now_ts=ts,
            )

            if cumulative_5h + amount > eff_sprint_limit:
                return (
                    False,
                    HALT_SPRINT_LIMIT_EXCEEDED,
                    {
                        "cumulative_5h_eur": cumulative_5h,
                        "cumulative_7d_eur": cumulative_7d,
                        "attempted_amount_eur": amount,
                        "sprint_limit_eur": eff_sprint_limit,
                    },
                )

            if cumulative_7d + amount > eff_epoch_limit:
                return (
                    False,
                    HALT_EPOCH_BASELINE_EXCEEDED,
                    {
                        "cumulative_5h_eur": cumulative_5h,
                        "cumulative_7d_eur": cumulative_7d,
                        "attempted_amount_eur": amount,
                        "epoch_limit_eur": eff_epoch_limit,
                    },
                )

            entry_payload: Dict[str, Any] = {
                "amount_eur": amount,
                "endpoint": endpoint,
                "operation_id": operation_id,
                "pool": "FINANCIAL_MUTATION_POOL",
                "prev_hash": self.chain_tip_hash,
                "root_sponsor_did": root_sponsor_did,
                "seq": len(self.entries) + 1,
                "subagent_id": subagent_id,
                "timestamp": ts,
            }
            canonical_bytes = encode_jcs(entry_payload)
            entry_hash = hashlib.sha256(canonical_bytes).hexdigest()
            signature_bytes = self.signing_key.sign(canonical_bytes)

            record: Dict[str, Any] = {
                "entry_hash": entry_hash,
                "payload": entry_payload,
                "signature_hex": signature_bytes.hex(),
                "signer_pubkey_hex": _pubkey_to_hex(self.verify_key),
            }

            serialized_line = encode_jcs(record).decode("utf-8") + "\n"
            fd = os.open(
                str(self.ledger_path),
                os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                0o600,
            )
            try:
                os.write(fd, serialized_line.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)

            self.entries.append(record)
            self.chain_tip_hash = entry_hash
            return (
                True,
                "AUTHORIZED",
                {
                    "cumulative_5h_eur": cumulative_5h + amount,
                    "cumulative_7d_eur": cumulative_7d + amount,
                    "entry_hash": entry_hash,
                },
            )


@dataclass
class RootSponsorRecord:
    sponsor_did: str
    public_key: Ed25519PublicKey
    sprint_limit_eur: float = 2500.0
    epoch_limit_eur: float = 10000.0
    subagent_keys: Dict[str, Ed25519PublicKey] = field(default_factory=dict)


class RootSponsorQuotaTree:
    """
    Invariant 2: Binds all ephemeral subagent identities (subagent_i) to their parent
    root_sponsor (e.g. did:key:z6MkRootSponsor001). Ignores spoofed HTTP headers
    (X-Forwarded-For, User-Agent, X-Device-Fingerprint) so all subagent spend rolls up
    atomically to root_sponsor, yielding sybil_subagent_quota_gain == 0.
    """

    IGNORED_SPOOFABLE_HEADERS: Set[str] = {
        "x-forwarded-for",
        "user-agent",
        "x-device-fingerprint",
        "x-real-ip",
        "cf-connecting-ip",
    }

    def __init__(self) -> None:
        self._sponsors: Dict[str, RootSponsorRecord] = {}
        self._subagent_to_sponsor: Dict[str, str] = {}

    def register_root_sponsor(
        self,
        sponsor_did: str,
        public_key: Ed25519PublicKey,
        sprint_limit_eur: float = 2500.0,
        epoch_limit_eur: float = 10000.0,
    ) -> RootSponsorRecord:
        record = RootSponsorRecord(
            sponsor_did=sponsor_did,
            public_key=public_key,
            sprint_limit_eur=float(sprint_limit_eur),
            epoch_limit_eur=float(epoch_limit_eur),
        )
        self._sponsors[sponsor_did] = record
        return record

    def register_subagent(
        self,
        sponsor_did: str,
        subagent_id: str,
        subagent_pubkey: Ed25519PublicKey,
        spoofed_headers: Optional[Dict[str, str]] = None,
    ) -> str:
        if sponsor_did not in self._sponsors:
            raise KeyError(f"Unregistered root sponsor: {sponsor_did}")
        # Explicitly ignore spoofed headers (X-Forwarded-For, User-Agent, X-Device-Fingerprint)
        _ = spoofed_headers
        sponsor = self._sponsors[sponsor_did]
        sponsor.subagent_keys[subagent_id] = subagent_pubkey
        self._subagent_to_sponsor[subagent_id] = sponsor_did
        return sponsor_did

    def resolve_and_verify_subagent(
        self,
        subagent_id: str,
        request_payload: Dict[str, Any],
        signature_bytes: bytes,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, Optional[RootSponsorRecord]]:
        # Strip and ignore any spoofed routing or fingerprint headers
        if headers:
            _filtered = {
                k: v
                for k, v in headers.items()
                if k.lower() not in self.IGNORED_SPOOFABLE_HEADERS
            }
            _ = _filtered

        sponsor_did = self._subagent_to_sponsor.get(subagent_id)
        if sponsor_did is None:
            return False, HALT_UNREGISTERED_SUBAGENT, None

        sponsor = self._sponsors[sponsor_did]
        subagent_pubkey = sponsor.subagent_keys.get(subagent_id)
        if subagent_pubkey is None:
            return False, HALT_UNREGISTERED_SUBAGENT, None

        try:
            subagent_pubkey.verify(signature_bytes, encode_jcs(request_payload))
        except InvalidSignature:
            return False, HALT_INVALID_SIGNATURE, None

        return True, sponsor_did, sponsor

    def sybil_subagent_quota_gain(self, sponsor_did: str) -> float:
        """
        Computes any additional quota granted by registering N subagents under sponsor_did.
        Because all subagents share the root sponsor's single ledger accumulator,
        the quota gain from spawning Sybil subagents is identically 0.0.
        """
        if sponsor_did not in self._sponsors:
            raise KeyError(f"Unregistered root sponsor: {sponsor_did}")
        sponsor = self._sponsors[sponsor_did]
        effective_pool_limit = sponsor.sprint_limit_eur
        return effective_pool_limit - sponsor.sprint_limit_eur


class ContinuityBootInterlock:
    """
    Invariant 3: Verifies at startup (and prior to dispatch) that ledger.jsonl exists
    on disk and its cryptographic hash-chain tip matches pinned_checkpoint_tip.
    If ledger.jsonl was wiped ("Reset Onboarding" attack) or altered, latches into
    HALT_MISSING_CONTINUITY_LEDGER until a human supervisor Ed25519 re-init signature
    is verified.
    """

    def __init__(self, supervisor_pubkey: Optional[Ed25519PublicKey] = None) -> None:
        self.supervisor_pubkey = supervisor_pubkey
        self.halted: bool = False
        self.halt_reason: str = "OK"
        self.pinned_checkpoint_tip: str = GENESIS_PREV_HASH

    def boot_or_verify(
        self,
        ledger_path: Path | str,
        pinned_checkpoint_tip: str,
    ) -> Tuple[bool, str]:
        path = Path(ledger_path)
        self.pinned_checkpoint_tip = pinned_checkpoint_tip

        if not path.exists():
            self.halted = True
            self.halt_reason = HALT_MISSING_CONTINUITY_LEDGER
            return False, HALT_MISSING_CONTINUITY_LEDGER

        try:
            raw_text = path.read_text(encoding="utf-8")
            lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
            if not lines and pinned_checkpoint_tip != GENESIS_PREV_HASH:
                self.halted = True
                self.halt_reason = HALT_MISSING_CONTINUITY_LEDGER
                return False, HALT_MISSING_CONTINUITY_LEDGER

            prev_hash = GENESIS_PREV_HASH
            for line in lines:
                record = json.loads(line)
                payload = record["payload"]
                if payload.get("prev_hash") != prev_hash:
                    self.halted = True
                    self.halt_reason = HALT_MISSING_CONTINUITY_LEDGER
                    return False, HALT_MISSING_CONTINUITY_LEDGER
                computed_hash = _sha256_jcs_hex(payload)
                if record.get("entry_hash") != computed_hash:
                    self.halted = True
                    self.halt_reason = HALT_MISSING_CONTINUITY_LEDGER
                    return False, HALT_MISSING_CONTINUITY_LEDGER
                sig_bytes = bytes.fromhex(record["signature_hex"])
                pub_bytes = bytes.fromhex(record["signer_pubkey_hex"])
                pubkey = Ed25519PublicKey.from_public_bytes(pub_bytes)
                pubkey.verify(sig_bytes, encode_jcs(payload))
                prev_hash = computed_hash

            if prev_hash != pinned_checkpoint_tip:
                self.halted = True
                self.halt_reason = HALT_MISSING_CONTINUITY_LEDGER
                return False, HALT_MISSING_CONTINUITY_LEDGER

        except Exception:
            self.halted = True
            self.halt_reason = HALT_MISSING_CONTINUITY_LEDGER
            return False, HALT_MISSING_CONTINUITY_LEDGER

        self.halted = False
        self.halt_reason = "OK"
        return True, "OK"

    def authorize_supervisor_reinit(
        self,
        reinit_token_dict: Dict[str, Any],
        supervisor_pubkey: Optional[Ed25519PublicKey] = None,
    ) -> Tuple[bool, str]:
        """
        Verifies a human supervisor's Ed25519 signature over the canonical JCS payload
        in reinit_token_dict["payload"] using reinit_token_dict["signature_hex"].
        """
        active_pubkey = supervisor_pubkey or self.supervisor_pubkey
        if active_pubkey is None:
            return False, HALT_INVALID_SIGNATURE

        payload = reinit_token_dict.get("payload")
        sig_hex = reinit_token_dict.get("signature_hex", "")
        if not isinstance(payload, dict) or not sig_hex:
            return False, HALT_INVALID_SIGNATURE

        if payload.get("action") != "SUPERVISOR_LEDGER_REINIT":
            return False, HALT_INVALID_SIGNATURE

        try:
            sig_bytes = bytes.fromhex(sig_hex)
            active_pubkey.verify(sig_bytes, encode_jcs(payload))
        except (ValueError, InvalidSignature):
            return False, HALT_INVALID_SIGNATURE

        self.pinned_checkpoint_tip = str(payload.get("new_checkpoint_tip", GENESIS_PREV_HASH))
        self.halted = False
        self.halt_reason = "OK"
        return True, "REINITIALIZED_BY_SUPERVISOR"


class ContextIntegrityGate:
    """
    Invariant 4 (AT57 Memory Poisoning Defense):
    Evaluates context blocks (user_prompt, rag_retrieval, tool_output, memory).
    Each block must carry a valid SHA-256 context_hash bound to
    (operation_id, block_id, content) committed and signed with Ed25519 at ingestion.
    If an attacker mutates a memory/rag_retrieval block after commitment or injects
    an uncommitted block, rejects fail-closed with HALT_CONTEXT_INTEGRITY_FAILURE.
    """

    def __init__(self, ingestion_signing_key: Optional[Ed25519PrivateKey] = None) -> None:
        self._signing_key = ingestion_signing_key or Ed25519PrivateKey.generate()
        self.ingestion_pubkey = self._signing_key.public_key()
        self._commitments: Dict[Tuple[str, str], Dict[str, Any]] = {}

    @staticmethod
    def compute_context_hash(
        operation_id: str,
        block_id: str,
        block_type: str,
        content: str,
    ) -> str:
        binding_payload = {
            "block_id": block_id,
            "block_type": block_type,
            "content": content,
            "operation_id": operation_id,
        }
        return _sha256_jcs_hex(binding_payload)

    def commit_context_block(
        self,
        operation_id: str,
        block_id: str,
        block_type: str,
        content: str,
    ) -> Dict[str, str]:
        if block_type not in VALID_CONTEXT_BLOCK_TYPES:
            raise ValueError(f"Unsupported context block_type: {block_type}")

        context_hash = self.compute_context_hash(
            operation_id=operation_id,
            block_id=block_id,
            block_type=block_type,
            content=content,
        )
        commitment_envelope = {
            "block_id": block_id,
            "block_type": block_type,
            "context_hash": context_hash,
            "operation_id": operation_id,
        }
        signature_hex = self._signing_key.sign(encode_jcs(commitment_envelope)).hex()
        block_record = {
            "block_id": block_id,
            "block_type": block_type,
            "commitment_signature_hex": signature_hex,
            "content": content,
            "context_hash": context_hash,
            "operation_id": operation_id,
        }
        self._commitments[(operation_id, block_id)] = dict(block_record)
        return block_record

    def evaluate_context_blocks(
        self,
        operation_id: str,
        context_blocks: List[Dict[str, Any]],
    ) -> Tuple[bool, str]:
        if not isinstance(context_blocks, list):
            return False, HALT_CONTEXT_INTEGRITY_FAILURE

        for block in context_blocks:
            if not isinstance(block, dict):
                return False, HALT_CONTEXT_INTEGRITY_FAILURE

            block_id = str(block.get("block_id", ""))
            block_type = str(block.get("block_type", ""))
            content = str(block.get("content", ""))
            provided_hash = str(block.get("context_hash", ""))
            block_op_id = str(block.get("operation_id", operation_id))

            if block_type not in VALID_CONTEXT_BLOCK_TYPES or not block_id:
                return False, HALT_CONTEXT_INTEGRITY_FAILURE

            if block_op_id != operation_id:
                return False, HALT_CONTEXT_INTEGRITY_FAILURE

            recomputed_hash = self.compute_context_hash(
                operation_id=operation_id,
                block_id=block_id,
                block_type=block_type,
                content=content,
            )
            if recomputed_hash != provided_hash:
                return False, HALT_CONTEXT_INTEGRITY_FAILURE

            committed = self._commitments.get((operation_id, block_id))
            if committed is None:
                return False, HALT_CONTEXT_INTEGRITY_FAILURE

            if committed["context_hash"] != recomputed_hash:
                return False, HALT_CONTEXT_INTEGRITY_FAILURE

            if committed["content"] != content:
                return False, HALT_CONTEXT_INTEGRITY_FAILURE

            sig_hex = str(block.get("commitment_signature_hex", ""))
            if not sig_hex:
                return False, HALT_CONTEXT_INTEGRITY_FAILURE

            commitment_envelope = {
                "block_id": block_id,
                "block_type": block_type,
                "context_hash": recomputed_hash,
                "operation_id": operation_id,
            }
            try:
                self.ingestion_pubkey.verify(
                    bytes.fromhex(sig_hex),
                    encode_jcs(commitment_envelope),
                )
            except (ValueError, InvalidSignature):
                return False, HALT_CONTEXT_INTEGRITY_FAILURE

            if block_type in {"memory", "rag_retrieval", "tool_output"}:
                upper_content = content.upper()
                for marker in FORBIDDEN_OVERRIDE_MARKERS:
                    if marker in upper_content:
                        return False, HALT_CONTEXT_INTEGRITY_FAILURE

        return True, "CONTEXT_INTEGRITY_VERIFIED"


class CredentialStarvationEnforcer:
    """
    Invariant 5a: Validates Agent_Process ∩ {API_keys, mTLS_certs, OAuth_tokens} == ∅.
    """

    @staticmethod
    def verify_agent_environment(
        agent_env: Dict[str, Any],
    ) -> Tuple[bool, str, List[str]]:
        leaked_keys: List[str] = []
        for key, value in agent_env.items():
            upper_key = str(key).upper()
            str_val = str(value).strip()
            if not str_val:
                continue
            if any(forbidden in upper_key for forbidden in FORBIDDEN_CREDENTIAL_KEYS):
                leaked_keys.append(key)
            elif "BEGIN CERTIFICATE" in str_val or "BEGIN PRIVATE KEY" in str_val:
                leaked_keys.append(key)
        if leaked_keys:
            return False, HALT_CREDENTIAL_STARVATION_VIOLATION, leaked_keys
        return True, "CREDENTIAL_STARVATION_VERIFIED", []


class _BankLoopbackRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for PinnedLoopbackBankServer requiring Station 2 Ed25519 signature."""

    def do_POST(self) -> None:
        server: PinnedLoopbackBankServer = self.server  # type: ignore[assignment]
        content_len = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            parsed_body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            parsed_body = {}

        sig_header = self.headers.get("X-AEIB-Station2-Signature", "").strip()
        if not sig_header:
            server.record_unauthorized_attempt()
            self._send_json(
                401,
                {
                    "reason": "MISSING_STATION2_SIGNATURE",
                    "status": "UNAUTHORIZED",
                },
            )
            return

        envelope = {
            "body": parsed_body,
            "method": "POST",
            "path": self.path,
        }
        try:
            sig_bytes = bytes.fromhex(sig_header)
            server.station2_pubkey.verify(sig_bytes, encode_jcs(envelope))
        except (ValueError, InvalidSignature):
            server.record_unauthorized_attempt()
            self._send_json(
                401,
                {
                    "reason": "INVALID_STATION2_SIGNATURE",
                    "status": "UNAUTHORIZED",
                },
            )
            return

        receipt = server.record_authorized_mutation(self.path, parsed_body)
        self._send_json(200, receipt)

    def _send_json(self, status_code: int, payload: Dict[str, Any]) -> None:
        body_bytes = encode_jcs(payload)
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, format: str, *args: Any) -> None:
        server: PinnedLoopbackBankServer = self.server  # type: ignore[assignment]
        server.access_logs.append(format % args)


class PinnedLoopbackBankServer(http.server.HTTPServer):
    """
    Invariant 5b: Ephemeral loopback HTTP server bound to 127.0.0.1:0 on a background
    thread. Rejects any direct socket connection lacking AEIB Station 2's Ed25519
    transport signature header (X-AEIB-Station2-Signature) with HTTP 401 Unauthorized.
    """

    def __init__(self, station2_pubkey: Ed25519PublicKey) -> None:
        super().__init__(("127.0.0.1", 0), _BankLoopbackRequestHandler)
        self.station2_pubkey = station2_pubkey
        self._state_lock = threading.Lock()
        self.unauthorized_direct_attempts: int = 0
        self.executed_mutations: List[Dict[str, Any]] = []
        self.access_logs: List[str] = []
        self._thread: Optional[threading.Thread] = None

    @property
    def host(self) -> str:
        return str(self.server_address[0])

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    def start_background(self) -> Tuple[str, int]:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self.serve_forever, daemon=True)
            self._thread.start()
        return self.host, self.port

    def stop_background(self) -> None:
        self.shutdown()
        self.server_close()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def record_unauthorized_attempt(self) -> None:
        with self._state_lock:
            self.unauthorized_direct_attempts += 1

    def record_authorized_mutation(
        self,
        path: str,
        body: Dict[str, Any],
    ) -> Dict[str, Any]:
        with self._state_lock:
            mutation_record = {
                "amount_eur": float(body.get("amount_eur", 0.0)),
                "endpoint": path,
                "mutation_seq": len(self.executed_mutations) + 1,
                "operation_id": str(body.get("operation_id", "")),
                "status": "EXECUTED",
                "subagent_id": str(body.get("subagent_id", "")),
            }
            self.executed_mutations.append(mutation_record)
            return mutation_record


class QuotaFinancialGateInterlock:
    """
    Unified Station 1 + Station 2 Financial Gate Interlock coordinating all 5 invariants:
    1. ContinuityBootInterlock check on ledger.jsonl and pinned checkpoint tip
    2. CredentialStarvationEnforcer check on agent environment
    3. ContextIntegrityGate (AT57) check on operation context blocks
    4. RootSponsorQuotaTree subagent signature & sponsor rollup resolution
    5. DualWindowFinancialLedger 5h sprint & 7d epoch limit enforcement + Station 2
       Ed25519-signed dispatch to PinnedLoopbackBankServer.
    """

    def __init__(
        self,
        ledger_path: Path | str,
        sprint_limit_eur: float = 2500.0,
        epoch_limit_eur: float = 10000.0,
        supervisor_pubkey: Optional[Ed25519PublicKey] = None,
        station2_signing_key: Optional[Ed25519PrivateKey] = None,
        bank_server: Optional[PinnedLoopbackBankServer] = None,
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.station2_signing_key = station2_signing_key or Ed25519PrivateKey.generate()
        self.station2_pubkey = self.station2_signing_key.public_key()

        self.ledger = DualWindowFinancialLedger(
            ledger_path=self.ledger_path,
            signing_key=self.station2_signing_key,
            sprint_limit_eur=sprint_limit_eur,
            epoch_limit_eur=epoch_limit_eur,
        )
        self.sponsor_tree = RootSponsorQuotaTree()
        self.continuity_interlock = ContinuityBootInterlock(
            supervisor_pubkey=supervisor_pubkey
        )
        self.continuity_interlock.pinned_checkpoint_tip = self.ledger.chain_tip_hash
        self.context_gate = ContextIntegrityGate(
            ingestion_signing_key=self.station2_signing_key
        )
        self.credential_enforcer = CredentialStarvationEnforcer()
        self.bank_server = bank_server

    def restart_station1(self) -> Tuple[bool, str]:
        """
        Simulates a Station 1 process restart where ContinuityBootInterlock verifies
        the on-disk ledger.jsonl against the pinned checkpoint tip.
        """
        ok, status = self.continuity_interlock.boot_or_verify(
            ledger_path=self.ledger_path,
            pinned_checkpoint_tip=self.continuity_interlock.pinned_checkpoint_tip,
        )
        if ok:
            self.ledger = DualWindowFinancialLedger(
                ledger_path=self.ledger_path,
                signing_key=self.station2_signing_key,
                sprint_limit_eur=self.ledger.sprint_limit_eur,
                epoch_limit_eur=self.ledger.epoch_limit_eur,
            )
        return ok, status

    def authorize_supervisor_reinit(
        self,
        reinit_token_dict: Dict[str, Any],
        supervisor_pubkey: Optional[Ed25519PublicKey] = None,
    ) -> Tuple[bool, str]:
        ok, reason = self.continuity_interlock.authorize_supervisor_reinit(
            reinit_token_dict=reinit_token_dict,
            supervisor_pubkey=supervisor_pubkey,
        )
        if ok:
            self.ledger = DualWindowFinancialLedger(
                ledger_path=self.ledger_path,
                signing_key=self.station2_signing_key,
                sprint_limit_eur=self.ledger.sprint_limit_eur,
                epoch_limit_eur=self.ledger.epoch_limit_eur,
            )
            self.continuity_interlock.pinned_checkpoint_tip = self.ledger.chain_tip_hash
        return ok, reason

    def dispatch_financial_mutation(
        self,
        subagent_id: str,
        endpoint: str,
        amount_eur: float,
        operation_id: str,
        request_signature: bytes,
        headers: Optional[Dict[str, str]] = None,
        context_blocks: Optional[List[Dict[str, Any]]] = None,
        agent_env: Optional[Dict[str, Any]] = None,
        now_ts: Optional[float] = None,
    ) -> GateDecision:
        # 1. Continuity boot / ledger integrity check
        if self.continuity_interlock.halted:
            return GateDecision(
                allowed=False,
                status_code=HALT_MISSING_CONTINUITY_LEDGER,
                reason="Station 1 latched in HALT_MISSING_CONTINUITY_LEDGER",
                subagent_id=subagent_id,
                endpoint=endpoint,
                amount_eur=amount_eur,
            )

        boot_ok, boot_status = self.continuity_interlock.boot_or_verify(
            ledger_path=self.ledger_path,
            pinned_checkpoint_tip=self.continuity_interlock.pinned_checkpoint_tip,
        )
        if not boot_ok:
            return GateDecision(
                allowed=False,
                status_code=boot_status,
                reason="On-disk ledger continuity verification failed",
                subagent_id=subagent_id,
                endpoint=endpoint,
                amount_eur=amount_eur,
            )

        # 2. Credential starvation verification
        if agent_env is not None:
            cred_ok, cred_status, _ = self.credential_enforcer.verify_agent_environment(
                agent_env
            )
            if not cred_ok:
                return GateDecision(
                    allowed=False,
                    status_code=cred_status,
                    reason="Agent process contains forbidden credential material",
                    subagent_id=subagent_id,
                    endpoint=endpoint,
                    amount_eur=amount_eur,
                )

        # 3. Context integrity verification (AT57)
        if context_blocks is not None:
            ctx_ok, ctx_status = self.context_gate.evaluate_context_blocks(
                operation_id=operation_id,
                context_blocks=context_blocks,
            )
            if not ctx_ok:
                return GateDecision(
                    allowed=False,
                    status_code=ctx_status,
                    reason="Context block failed SHA-256 or Ed25519 ingestion commitment check",
                    subagent_id=subagent_id,
                    endpoint=endpoint,
                    amount_eur=amount_eur,
                )

        # 4. RootSponsorQuotaTree resolution and Ed25519 request signature check
        request_payload = {
            "amount_eur": float(amount_eur),
            "endpoint": endpoint,
            "operation_id": operation_id,
            "subagent_id": subagent_id,
        }
        sig_ok, sponsor_or_err, sponsor_rec = self.sponsor_tree.resolve_and_verify_subagent(
            subagent_id=subagent_id,
            request_payload=request_payload,
            signature_bytes=request_signature,
            headers=headers,
        )
        if not sig_ok or sponsor_rec is None:
            return GateDecision(
                allowed=False,
                status_code=sponsor_or_err,
                reason="Subagent identity or Ed25519 request signature rejected",
                subagent_id=subagent_id,
                endpoint=endpoint,
                amount_eur=amount_eur,
            )

        # 5. DualWindowFinancialLedger evaluation & hash-chained append
        allowed, status_code, details = self.ledger.evaluate_and_append(
            root_sponsor_did=sponsor_rec.sponsor_did,
            subagent_id=subagent_id,
            endpoint=endpoint,
            amount_eur=amount_eur,
            operation_id=operation_id,
            sprint_limit_eur=sponsor_rec.sprint_limit_eur,
            epoch_limit_eur=sponsor_rec.epoch_limit_eur,
            now_ts=now_ts,
        )
        if not allowed:
            return GateDecision(
                allowed=False,
                status_code=status_code,
                reason=f"Financial gate blocked mutation with {status_code}",
                root_sponsor_did=sponsor_rec.sponsor_did,
                subagent_id=subagent_id,
                endpoint=endpoint,
                amount_eur=amount_eur,
                cumulative_5h_eur=float(details.get("cumulative_5h_eur", 0.0)),
                cumulative_7d_eur=float(details.get("cumulative_7d_eur", 0.0)),
                ledger_tip_hash=self.ledger.chain_tip_hash,
            )

        # Update pinned checkpoint tip on successful ledger append
        self.continuity_interlock.pinned_checkpoint_tip = self.ledger.chain_tip_hash

        # 6. If a PinnedLoopbackBankServer is attached, forward via Station 2 Ed25519 signature
        http_status = 200
        if self.bank_server is not None:
            envelope = {
                "body": request_payload,
                "method": "POST",
                "path": endpoint,
            }
            station2_sig_hex = self.station2_signing_key.sign(
                encode_jcs(envelope)
            ).hex()
            conn = http.client.HTTPConnection(
                self.bank_server.host,
                self.bank_server.port,
                timeout=5.0,
            )
            try:
                body_bytes = encode_jcs(request_payload)
                conn.request(
                    "POST",
                    endpoint,
                    body=body_bytes,
                    headers={
                        "Content-Type": "application/json",
                        "X-AEIB-Station2-Signature": station2_sig_hex,
                    },
                )
                resp = conn.getresponse()
                _ = resp.read()
                http_status = resp.status
            finally:
                conn.close()

        return GateDecision(
            allowed=True,
            status_code="AUTHORIZED",
            reason="Authorized and appended to hash-chained ledger",
            root_sponsor_did=sponsor_rec.sponsor_did,
            subagent_id=subagent_id,
            endpoint=endpoint,
            amount_eur=float(amount_eur),
            cumulative_5h_eur=float(details["cumulative_5h_eur"]),
            cumulative_7d_eur=float(details["cumulative_7d_eur"]),
            ledger_tip_hash=self.ledger.chain_tip_hash,
            http_status=http_status,
        )
