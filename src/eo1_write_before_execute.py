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
src/eo1_write_before_execute.py
================================================================================
AEIB EO-1 Evidence-Before-Effect Pre-Dispatch Intent Interlock.
Evaluated under the stated model. Preserves strict epistemic lock.

Core Invariants:
  1. Wire access is conditioned on an immutable pre-dispatch ledger record.
     Zero network connections or bytes are transmitted if the intent write fails.
  2. If an outbound call is interrupted mid-syscall (e.g. SIGKILL, crash, or wire fault),
     the unfulfilled intent is latched into EFFECT_INDETERMINATE with retry_safe: False.
  3. Subsequent mutations on a latched CAID are halted fail-closed until out-of-band
     reconciliation resolves target-side state.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs


class IntentLifecycleState(str, Enum):
    INTENT_COMMITTED = "INTENT_COMMITTED"
    DISPATCH_IN_FLIGHT = "DISPATCH_IN_FLIGHT"
    RECONCILED = "RECONCILED"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"


class PreDispatchLedgerWriteError(RuntimeError):
    """Raised when writing the pre-dispatch intent record to disk fails."""
    pass


class LatchedCaidExecutionHaltedError(RuntimeError):
    """Raised when dispatch on a latched CAID is blocked fail-closed."""
    pass


class IntentVerificationError(ValueError):
    """Raised when cryptographic verification of an intent or receipt fails."""
    pass


def compute_caid(payload: Any) -> str:
    """Computes the SHA-256 digest over the RFC 8785 JCS canonical bytes of payload."""
    return hashlib.sha256(encode_jcs(payload)).hexdigest()


@dataclass(frozen=True)
class DispatchIntentRecord:
    record_type: str
    schema_version: str
    intent_id: str
    caid: str
    target_uri: str
    tool_name: str
    policy_epoch: int
    authority_id: str
    timestamp_utc: str
    payload_digest: str
    boundary_signature_b64: str
    boundary_public_key_pem: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authority_id": self.authority_id,
            "boundary_public_key_pem": self.boundary_public_key_pem,
            "boundary_signature_b64": self.boundary_signature_b64,
            "caid": self.caid,
            "intent_id": self.intent_id,
            "payload_digest": self.payload_digest,
            "policy_epoch": self.policy_epoch,
            "record_type": self.record_type,
            "schema_version": self.schema_version,
            "target_uri": self.target_uri,
            "timestamp_utc": self.timestamp_utc,
            "tool_name": self.tool_name,
        }

    def statement_for_signature(self) -> Dict[str, Any]:
        return {
            "authority_id": self.authority_id,
            "caid": self.caid,
            "intent_id": self.intent_id,
            "payload_digest": self.payload_digest,
            "policy_epoch": self.policy_epoch,
            "record_type": self.record_type,
            "schema_version": self.schema_version,
            "target_uri": self.target_uri,
            "timestamp_utc": self.timestamp_utc,
            "tool_name": self.tool_name,
        }


@dataclass(frozen=True)
class ContinuityReceipt:
    record_type: str
    schema_version: str
    intent_id: str
    caid: str
    status: str
    lifecycle_state: str
    retry_safe: bool
    policy_epoch: int
    reconciled_at: str
    chain_tip: str
    boundary_signature_b64: str
    boundary_public_key_pem: str
    reconciliation_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_public_key_pem": self.boundary_public_key_pem,
            "boundary_signature_b64": self.boundary_signature_b64,
            "caid": self.caid,
            "chain_tip": self.chain_tip,
            "intent_id": self.intent_id,
            "lifecycle_state": self.lifecycle_state,
            "policy_epoch": self.policy_epoch,
            "reconciled_at": self.reconciled_at,
            "reconciliation_details": self.reconciliation_details,
            "record_type": self.record_type,
            "retry_safe": self.retry_safe,
            "schema_version": self.schema_version,
            "status": self.status,
        }

    def statement_for_signature(self) -> Dict[str, Any]:
        return {
            "caid": self.caid,
            "chain_tip": self.chain_tip,
            "intent_id": self.intent_id,
            "lifecycle_state": self.lifecycle_state,
            "policy_epoch": self.policy_epoch,
            "reconciled_at": self.reconciled_at,
            "reconciliation_details": self.reconciliation_details,
            "record_type": self.record_type,
            "retry_safe": self.retry_safe,
            "schema_version": self.schema_version,
            "status": self.status,
        }


@dataclass(frozen=True)
class RecoveredIntentState:
    intent_id: str
    caid: str
    target_uri: str
    tool_name: str
    lifecycle_state: IntentLifecycleState
    retry_safe: bool
    reconciliation_required: bool
    latched_at: str
    reproducibility_evidence_sha256: str


@dataclass(frozen=True)
class DispatchResult:
    lifecycle_state: IntentLifecycleState
    caid: str
    receipt: ContinuityReceipt
    response: Dict[str, Any]


def verify_dispatch_intent(
    record_dict: Dict[str, Any],
    public_key: Union[Ed25519PublicKey, str],
    expected_payload: Optional[Any] = None,
) -> bool:
    """Verifies an Ed25519-signed DISPATCH_INTENT record."""
    if isinstance(public_key, str):
        pub = serialization.load_pem_public_key(public_key.encode("utf-8"))
        if not isinstance(pub, Ed25519PublicKey):
            raise IntentVerificationError("Loaded key is not an Ed25519PublicKey")
        public_key = pub

    # Expected payload verification
    if expected_payload is not None:
        computed_caid = compute_caid(expected_payload)
        if computed_caid != record_dict.get("caid"):
            raise IntentVerificationError(
                f"CAID mismatch: record caid '{record_dict.get('caid')}' != computed caid '{computed_caid}'"
            )

    # Reconstruct canonical statement
    statement = {
        "authority_id": record_dict["authority_id"],
        "caid": record_dict["caid"],
        "intent_id": record_dict["intent_id"],
        "payload_digest": record_dict["payload_digest"],
        "policy_epoch": record_dict["policy_epoch"],
        "record_type": record_dict["record_type"],
        "schema_version": record_dict["schema_version"],
        "target_uri": record_dict["target_uri"],
        "timestamp_utc": record_dict["timestamp_utc"],
        "tool_name": record_dict["tool_name"],
    }
    jcs_bytes = encode_jcs(statement)

    sig_b64 = record_dict.get("boundary_signature_b64")
    if not sig_b64:
        raise IntentVerificationError("Missing boundary_signature_b64 in DISPATCH_INTENT")
    try:
        sig_bytes = base64.b64decode(sig_b64)
        public_key.verify(sig_bytes, jcs_bytes)
        return True
    except (InvalidSignature, ValueError) as err:
        raise IntentVerificationError(f"Ed25519 intent signature verification failed: {err}") from err


def verify_continuity_receipt(
    receipt_dict: Dict[str, Any],
    public_key: Union[Ed25519PublicKey, str],
) -> bool:
    """Verifies an Ed25519-signed CONTINUITY_RECEIPT record."""
    if isinstance(public_key, str):
        pub = serialization.load_pem_public_key(public_key.encode("utf-8"))
        if not isinstance(pub, Ed25519PublicKey):
            raise IntentVerificationError("Loaded key is not an Ed25519PublicKey")
        public_key = pub

    statement = {
        "caid": receipt_dict["caid"],
        "chain_tip": receipt_dict["chain_tip"],
        "intent_id": receipt_dict["intent_id"],
        "lifecycle_state": receipt_dict["lifecycle_state"],
        "policy_epoch": receipt_dict["policy_epoch"],
        "reconciled_at": receipt_dict["reconciled_at"],
        "reconciliation_details": receipt_dict.get("reconciliation_details", {}),
        "record_type": receipt_dict["record_type"],
        "retry_safe": receipt_dict["retry_safe"],
        "schema_version": receipt_dict["schema_version"],
        "status": receipt_dict["status"],
    }
    jcs_bytes = encode_jcs(statement)

    sig_b64 = receipt_dict.get("boundary_signature_b64")
    if not sig_b64:
        raise IntentVerificationError("Missing boundary_signature_b64 in CONTINUITY_RECEIPT")
    try:
        sig_bytes = base64.b64decode(sig_b64)
        public_key.verify(sig_bytes, jcs_bytes)
        return True
    except (InvalidSignature, ValueError) as err:
        raise IntentVerificationError(f"Ed25519 continuity receipt signature verification failed: {err}") from err


def verify_ledger_file(
    ledger_path: Path,
    public_key: Union[Ed25519PublicKey, str],
) -> List[Dict[str, Any]]:
    """Verifies every line in the append-only ledger against the trusted public key."""
    ledger_path = Path(ledger_path)
    if not ledger_path.exists():
        return []

    verified_records: List[Dict[str, Any]] = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            rec_type = record.get("record_type")
            if rec_type == "DISPATCH_INTENT":
                verify_dispatch_intent(record, public_key)
            elif rec_type == "CONTINUITY_RECEIPT":
                verify_continuity_receipt(record, public_key)
            else:
                raise IntentVerificationError(f"Line {idx}: Unrecognized record_type '{rec_type}'")
            verified_records.append(record)
    return verified_records


def recover_unresolved_intents(
    ledger_path: Path,
    output_state_dir: Path,
    public_key: Optional[Union[Ed25519PublicKey, str]] = None,
    verify_signatures: bool = False,
) -> List[RecoveredIntentState]:
    """
    Scans the ledger for DISPATCH_INTENT records lacking a matching CONTINUITY_RECEIPT.
    Latches them into EFFECT_INDETERMINATE and writes latch markers into output_state_dir.
    """
    ledger_path = Path(ledger_path)
    output_state_dir = Path(output_state_dir)
    output_state_dir.mkdir(parents=True, exist_ok=True)

    if not ledger_path.exists():
        return []

    intents: Dict[str, Dict[str, Any]] = {}
    receipts: set[str] = set()

    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rtype = rec.get("record_type")
            if rtype == "DISPATCH_INTENT":
                if verify_signatures and public_key is not None:
                    verify_dispatch_intent(rec, public_key)
                intents[rec["intent_id"]] = rec
            elif rtype == "CONTINUITY_RECEIPT":
                if verify_signatures and public_key is not None:
                    verify_continuity_receipt(rec, public_key)
                receipts.add(rec["intent_id"])

    recovered: List[RecoveredIntentState] = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for intent_id, intent_dict in intents.items():
        if intent_id not in receipts:
            caid = intent_dict["caid"]
            evidence_sha256 = hashlib.sha256(encode_jcs(intent_dict)).hexdigest()

            state = RecoveredIntentState(
                intent_id=intent_id,
                caid=caid,
                target_uri=intent_dict["target_uri"],
                tool_name=intent_dict["tool_name"],
                lifecycle_state=IntentLifecycleState.EFFECT_INDETERMINATE,
                retry_safe=False,
                reconciliation_required=True,
                latched_at=now_iso,
                reproducibility_evidence_sha256=evidence_sha256,
            )
            recovered.append(state)

            # Persist latch marker to output_state_dir
            latch_file = output_state_dir / f"latched_{caid}.json"
            latch_payload = {
                "caid": caid,
                "intent_id": intent_id,
                "latched_at": now_iso,
                "lifecycle_state": "EFFECT_INDETERMINATE",
                "reconciliation_required": True,
                "retry_safe": False,
                "target_uri": intent_dict["target_uri"],
                "tool_name": intent_dict["tool_name"],
            }
            latch_file.write_text(json.dumps(latch_payload, indent=2), encoding="utf-8")

    return recovered


class PreDispatchIntentInterlock:
    """
    Enforces EO-1 (Evidence-Before-Effect) at the socket boundary.
    """

    def __init__(
        self,
        ledger_path: Path,
        boundary_private_key: Optional[Ed25519PrivateKey] = None,
        output_state_dir: Optional[Path] = None,
        authority_id: str = "default-authority",
        policy_epoch: int = 1,
        simulate_write_error: bool = False,
        auto_recover: bool = True,
    ):
        self.ledger_path = Path(ledger_path)
        self.output_state_dir = Path(output_state_dir) if output_state_dir else self.ledger_path.parent / "state"
        self.boundary_private_key = boundary_private_key or Ed25519PrivateKey.generate()
        self.authority_id = authority_id
        self.policy_epoch = policy_epoch
        self.simulate_write_error = simulate_write_error
        self._lock = threading.Lock()
        self._chain_tip: str = hashlib.sha256(b"aeib-eo1-chain-genesis").hexdigest()

        pub_bytes = self.boundary_private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.boundary_public_key_pem = pub_bytes.decode("utf-8")
        self.output_state_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        self._latched_intents: Dict[str, RecoveredIntentState] = {}
        if auto_recover:
            self._run_startup_recovery()

    def _run_startup_recovery(self) -> None:
        # Load any existing disk latch files
        for latch_file in self.output_state_dir.glob("latched_*.json"):
            try:
                data = json.loads(latch_file.read_text(encoding="utf-8"))
                caid = data["caid"]
                self._latched_intents[caid] = RecoveredIntentState(
                    intent_id=data["intent_id"],
                    caid=caid,
                    target_uri=data["target_uri"],
                    tool_name=data["tool_name"],
                    lifecycle_state=IntentLifecycleState.EFFECT_INDETERMINATE,
                    retry_safe=False,
                    reconciliation_required=True,
                    latched_at=data["latched_at"],
                    reproducibility_evidence_sha256="",
                )
            except Exception:
                pass

        # Scan ledger for unfulfilled intents
        recovered = recover_unresolved_intents(self.ledger_path, self.output_state_dir)
        for r in recovered:
            self._latched_intents[r.caid] = r

    def is_caid_latched(self, caid: str) -> bool:
        with self._lock:
            return caid in self._latched_intents

    def get_latched_caids(self) -> Dict[str, RecoveredIntentState]:
        with self._lock:
            return dict(self._latched_intents)

    def record_intent(
        self,
        target_uri: str,
        tool_name: str,
        payload: Any,
        intent_id: Optional[str] = None,
    ) -> DispatchIntentRecord:
        """
        Appends and signs an immutable DISPATCH_INTENT record to the ledger.
        Fails closed before any wire access if write fails.
        """
        with self._lock:
            if self.simulate_write_error:
                raise PreDispatchLedgerWriteError(
                    "Pre-dispatch ledger write failed: simulated write fault; halted fail-closed before wire access"
                )

            caid = compute_caid(payload)
            if caid in self._latched_intents:
                raise LatchedCaidExecutionHaltedError(
                    f"Action CAID {caid} is latched in EFFECT_INDETERMINATE with retry_safe=False. Dispatch refused."
                )

            intent_id = intent_id or f"intent-{hashlib.sha256(str(datetime.now(timezone.utc)).encode()).hexdigest()[:16]}"
            payload_digest = hashlib.sha256(encode_jcs(payload)).hexdigest()
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            statement = {
                "authority_id": self.authority_id,
                "caid": caid,
                "intent_id": intent_id,
                "payload_digest": payload_digest,
                "policy_epoch": self.policy_epoch,
                "record_type": "DISPATCH_INTENT",
                "schema_version": "1.1.0-eo1-intent",
                "target_uri": target_uri,
                "timestamp_utc": now_iso,
                "tool_name": tool_name,
            }

            jcs_bytes = encode_jcs(statement)
            sig_bytes = self.boundary_private_key.sign(jcs_bytes)
            sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

            record = DispatchIntentRecord(
                record_type="DISPATCH_INTENT",
                schema_version="1.1.0-eo1-intent",
                intent_id=intent_id,
                caid=caid,
                target_uri=target_uri,
                tool_name=tool_name,
                policy_epoch=self.policy_epoch,
                authority_id=self.authority_id,
                timestamp_utc=now_iso,
                payload_digest=payload_digest,
                boundary_signature_b64=sig_b64,
                boundary_public_key_pem=self.boundary_public_key_pem,
            )

            # Atomic append to ledger
            try:
                line = json.dumps(record.to_dict()) + "\n"
                with open(self.ledger_path, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
            except Exception as exc:
                raise PreDispatchLedgerWriteError(
                    f"Pre-dispatch ledger write failed: {exc}; halted fail-closed before wire access"
                ) from exc

            return record

    def dispatch(
        self,
        target_uri: str,
        tool_name: str,
        payload: Any,
        dispatch_fn: Optional[Callable[[], Any]] = None,
        intent_id: Optional[str] = None,
    ) -> DispatchResult:
        """
        Executes an outbound action strictly after committing pre-dispatch intent to disk.
        """
        caid = compute_caid(payload)
        intent = self.record_intent(target_uri, tool_name, payload, intent_id=intent_id)

        # Wire execution
        try:
            if dispatch_fn is not None:
                resp_data = dispatch_fn()
            else:
                req_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    target_uri,
                    data=req_bytes,
                    headers={"Content-Type": "application/json", "X-AEIB-CAID": caid},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    resp_body = resp.read()
                    resp_data = {
                        "status_code": resp.status,
                        "body": resp_body.decode("utf-8", errors="replace"),
                    }

            # On wire success -> emit RECONCILED receipt
            receipt = self._emit_receipt(
                intent_id=intent.intent_id,
                caid=caid,
                status="RECONCILED",
                lifecycle_state="RECONCILED",
                retry_safe=False,
                details=resp_data if isinstance(resp_data, dict) else {"result": str(resp_data)},
            )
            return DispatchResult(
                lifecycle_state=IntentLifecycleState.RECONCILED,
                caid=caid,
                receipt=receipt,
                response=resp_data if isinstance(resp_data, dict) else {"result": resp_data},
            )
        except Exception as wire_fault:
            # Wire failure mid-syscall -> latch into EFFECT_INDETERMINATE
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            latch_state = RecoveredIntentState(
                intent_id=intent.intent_id,
                caid=caid,
                target_uri=target_uri,
                tool_name=tool_name,
                lifecycle_state=IntentLifecycleState.EFFECT_INDETERMINATE,
                retry_safe=False,
                reconciliation_required=True,
                latched_at=now_iso,
                reproducibility_evidence_sha256="",
            )
            with self._lock:
                self._latched_intents[caid] = latch_state
                latch_file = self.output_state_dir / f"latched_{caid}.json"
                latch_file.write_text(
                    json.dumps({
                        "caid": caid,
                        "intent_id": intent.intent_id,
                        "latched_at": now_iso,
                        "lifecycle_state": "EFFECT_INDETERMINATE",
                        "retry_safe": False,
                        "wire_fault": str(wire_fault),
                    }),
                    encoding="utf-8",
                )
            raise RuntimeError(f"Wire dispatch error; action latched in EFFECT_INDETERMINATE: {wire_fault}") from wire_fault

    def reconcile_out_of_band(
        self,
        caid: str,
        reconciliation_evidence: Dict[str, Any],
        intent_id: Optional[str] = None,
    ) -> ContinuityReceipt:
        """
        Clears the indeterminate latch following out-of-band reconciliation and writes receipt.
        """
        with self._lock:
            receipt = self._emit_receipt(
                intent_id=intent_id or f"reconciled-{caid[:16]}",
                caid=caid,
                status="RECONCILED",
                lifecycle_state="RECONCILED",
                retry_safe=False,
                details=reconciliation_evidence,
            )
            # Remove in-memory and disk latches
            self._latched_intents.pop(caid, None)
            latch_file = self.output_state_dir / f"latched_{caid}.json"
            if latch_file.exists():
                latch_file.unlink()
            return receipt

    def _emit_receipt(
        self,
        intent_id: str,
        caid: str,
        status: str,
        lifecycle_state: str,
        retry_safe: bool,
        details: Dict[str, Any],
    ) -> ContinuityReceipt:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        statement = {
            "caid": caid,
            "chain_tip": self._chain_tip,
            "intent_id": intent_id,
            "lifecycle_state": lifecycle_state,
            "policy_epoch": self.policy_epoch,
            "reconciled_at": now_iso,
            "reconciliation_details": details,
            "record_type": "CONTINUITY_RECEIPT",
            "retry_safe": retry_safe,
            "schema_version": "1.1.0-eo1-receipt",
            "status": status,
        }
        jcs_bytes = encode_jcs(statement)
        sig_bytes = self.boundary_private_key.sign(jcs_bytes)
        sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

        receipt = ContinuityReceipt(
            record_type="CONTINUITY_RECEIPT",
            schema_version="1.1.0-eo1-receipt",
            intent_id=intent_id,
            caid=caid,
            status=status,
            lifecycle_state=lifecycle_state,
            retry_safe=retry_safe,
            policy_epoch=self.policy_epoch,
            reconciled_at=now_iso,
            chain_tip=self._chain_tip,
            boundary_signature_b64=sig_b64,
            boundary_public_key_pem=self.boundary_public_key_pem,
            reconciliation_details=details,
        )

        # Update chain tip
        self._chain_tip = hashlib.sha256(jcs_bytes).hexdigest()

        # Append to ledger
        line = json.dumps(receipt.to_dict()) + "\n"
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

        return receipt
