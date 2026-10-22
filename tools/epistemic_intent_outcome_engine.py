#!/usr/bin/env python3
# File: tools/epistemic_intent_outcome_engine.py
"""
AEIB Epistemic Intent-Outcome Two-Phase Execution Engine (Vercel durable-harness alignment).

Implements:
1. `record_intent(action_payload, target_endpoint, escrow_minor)`:
   Computes deterministic `intent_hash`, persists durable WAL checkpoint before external
   call, and reserves minor budget in escrow.
2. `record_outcome(intent_token, response_data)`:
   Transitions status to `SETTLED` and converts escrow to confirmed expenditure.
3. `handle_timeout_or_fault(intent_token)`:
   Latches status to `EFFECT_INDETERMINATE` and freezes escrowed budget until out-of-band
   reconciliation completes.
4. `resolve_replay(intent_hash)`:
   Returns cached outcome upon worker crash/restart or retry, preventing duplicate side-effects.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def canonical_jcs_bytes(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) encoding."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    """Compute sha256:<hex> digest."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _safe_fsync(fd: int) -> None:
    """Execute Darwin F_FULLFSYNC or fallback to standard os.fsync."""
    if sys.platform == "darwin":
        try:
            fcntl.fcntl(fd, 51)  # F_FULLFSYNC
            return
        except OSError:
            pass
    os.fsync(fd)


@dataclass(frozen=True)
class IntentToken:
    token_id: str
    intent_hash: str
    target_endpoint: str
    escrow_minor: int
    timestamp_ns: int
    status: str = "INTENT_RECORDED"


@dataclass(frozen=True)
class OutcomeToken:
    intent_hash: str
    response_digest: str
    response_payload: Dict[str, Any]
    status: str = "SETTLED"
    timestamp_ns: int = 0


@dataclass(frozen=True)
class IndeterminateRecord:
    intent_hash: str
    error_reason: str
    status: str = "EFFECT_INDETERMINATE"
    retry_safe: bool = False
    timestamp_ns: int = 0


class EpistemicIntentOutcomeEngine:
    """
    Two-Phase Durable Intent-Outcome State Machine with crash-safe replay cache.
    """

    def __init__(
        self,
        wal_path: Path,
        total_budget_minor: int = 10000_00,
        signing_key: Optional[Ed25519PrivateKey] = None,
    ) -> None:
        self.wal_path = Path(wal_path)
        self.wal_path.parent.mkdir(parents=True, exist_ok=True)
        self.total_budget_minor = total_budget_minor
        self.signing_key = signing_key or Ed25519PrivateKey.generate()

        self._intents: Dict[str, IntentToken] = {}
        self._outcomes: Dict[str, OutcomeToken] = {}
        self._indeterminate: Dict[str, IndeterminateRecord] = {}
        self._escrow_locked_minor = 0
        self._settled_expenditure_minor = 0

        self._replay_wal_on_startup()

    def _replay_wal_on_startup(self) -> None:
        """Recovers in-memory state monotonically from WAL file on disk."""
        if not self.wal_path.exists():
            return
        with open(self.wal_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                etype = entry.get("entry_type")
                ihash = entry.get("intent_hash")
                if etype == "INTENT_RECORDED":
                    tok = IntentToken(
                        token_id=entry["token_id"],
                        intent_hash=ihash,
                        target_endpoint=entry["target_endpoint"],
                        escrow_minor=entry["escrow_minor"],
                        timestamp_ns=entry["timestamp_ns"],
                        status="INTENT_RECORDED",
                    )
                    self._intents[ihash] = tok
                    self._escrow_locked_minor += tok.escrow_minor
                elif etype == "SETTLED":
                    out = OutcomeToken(
                        intent_hash=ihash,
                        response_digest=entry["response_digest"],
                        response_payload=entry.get("response_payload", {}),
                        status="SETTLED",
                        timestamp_ns=entry["timestamp_ns"],
                    )
                    self._outcomes[ihash] = out
                    if ihash in self._intents:
                        esc = self._intents[ihash].escrow_minor
                        self._escrow_locked_minor -= esc
                        self._settled_expenditure_minor += esc
                elif etype == "EFFECT_INDETERMINATE":
                    ind = IndeterminateRecord(
                        intent_hash=ihash,
                        error_reason=entry["error_reason"],
                        status="EFFECT_INDETERMINATE",
                        retry_safe=False,
                        timestamp_ns=entry["timestamp_ns"],
                    )
                    self._indeterminate[ihash] = ind

    def _append_wal_entry(self, entry: Dict[str, Any]) -> None:
        entry_bytes = json.dumps(entry, sort_keys=True).encode("utf-8") + b"\n"
        with open(self.wal_path, "ab") as f:
            f.write(entry_bytes)
            f.flush()
            _safe_fsync(f.fileno())

    def record_intent(
        self,
        action_payload: Dict[str, Any],
        target_endpoint: str,
        escrow_minor: int,
    ) -> Tuple[bool, Optional[IntentToken], str]:
        """
        Phase 1: Validates budget solvency, records durable intent, locks escrow.
        """
        available_budget = (
            self.total_budget_minor
            - self._settled_expenditure_minor
            - self._escrow_locked_minor
        )
        if escrow_minor > available_budget:
            return (
                False,
                None,
                f"HALT_INSUFFICIENT_ESCROW_BUDGET: Requested {escrow_minor} minor units, available {available_budget}",
            )

        payload_bytes = canonical_jcs_bytes(action_payload)
        ihash = sha256_prefixed(payload_bytes)

        # Check if already latched as INDETERMINATE
        if ihash in self._indeterminate:
            return (
                False,
                None,
                f"HALT_INTENT_ALREADY_LATCHED_INDETERMINATE: State locked pending out-of-band resolution for {ihash}",
            )

        token_id = f"intent:{ihash[7:23]}"
        now_ns = time.time_ns()
        tok = IntentToken(
            token_id=token_id,
            intent_hash=ihash,
            target_endpoint=target_endpoint,
            escrow_minor=escrow_minor,
            timestamp_ns=now_ns,
            status="INTENT_RECORDED",
        )

        entry = {
            "entry_type": "INTENT_RECORDED",
            "token_id": token_id,
            "intent_hash": ihash,
            "target_endpoint": target_endpoint,
            "escrow_minor": escrow_minor,
            "timestamp_ns": now_ns,
        }
        self._append_wal_entry(entry)
        self._intents[ihash] = tok
        self._escrow_locked_minor += escrow_minor

        return True, tok, "INTENT_DURABLY_RECORDED"

    def record_outcome(
        self,
        intent_token: IntentToken,
        response_data: Dict[str, Any],
    ) -> OutcomeToken:
        """
        Phase 2: Transitions intent to SETTLED and releases escrow to settled expenditure.
        """
        ihash = intent_token.intent_hash
        resp_bytes = canonical_jcs_bytes(response_data)
        rdigest = sha256_prefixed(resp_bytes)
        now_ns = time.time_ns()

        out = OutcomeToken(
            intent_hash=ihash,
            response_digest=rdigest,
            response_payload=response_data,
            status="SETTLED",
            timestamp_ns=now_ns,
        )

        entry = {
            "entry_type": "SETTLED",
            "intent_hash": ihash,
            "response_digest": rdigest,
            "response_payload": response_data,
            "timestamp_ns": now_ns,
        }
        self._append_wal_entry(entry)

        self._outcomes[ihash] = out
        if ihash in self._intents:
            self._escrow_locked_minor -= intent_token.escrow_minor
            self._settled_expenditure_minor += intent_token.escrow_minor

        return out

    def handle_timeout_or_fault(
        self,
        intent_token: IntentToken,
        error_reason: str = "HTTP_504_GATEWAY_TIMEOUT",
    ) -> IndeterminateRecord:
        """
        Latches intent into EFFECT_INDETERMINATE on transport failure.
        """
        ihash = intent_token.intent_hash
        now_ns = time.time_ns()
        ind = IndeterminateRecord(
            intent_hash=ihash,
            error_reason=error_reason,
            status="EFFECT_INDETERMINATE",
            retry_safe=False,
            timestamp_ns=now_ns,
        )
        entry = {
            "entry_type": "EFFECT_INDETERMINATE",
            "intent_hash": ihash,
            "error_reason": error_reason,
            "timestamp_ns": now_ns,
        }
        self._append_wal_entry(entry)
        self._indeterminate[ihash] = ind
        return ind

    def resolve_replay(self, intent_hash: str) -> Optional[OutcomeToken]:
        """
        Vercel durable-harness replay resolver: returns cached outcome if already settled.
        """
        return self._outcomes.get(intent_hash)

    @property
    def escrow_locked_minor(self) -> int:
        return self._escrow_locked_minor

    @property
    def settled_expenditure_minor(self) -> int:
        return self._settled_expenditure_minor
