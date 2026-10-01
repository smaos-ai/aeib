#!/usr/bin/env python3
"""
src/transport_interceptor.py — Fail-Closed Transport Interceptor & Outcome Reconciler
Unified implementation of Moat 3 for the AEIB wire fault & PostgreSQL/SQLite probe harness.

Bridges:
1. Wire interposition (catches HTTP 504 / TCP RST / Network Timeout)
2. Fail-closed disposition mapping (DISPATCHED_UNCONFIRMED / PROBE_REQUIRED_NO_ORIGINAL_RETRY)
3. Out-of-band state probe delegation (PostgresProbeAdapter / SQLiteProbe)
4. Cryptographic sealing via SCITT COSE_Sign1 (RFC 8785 JCS + Ed25519) and BBS+ Selective Redaction
"""

import os
import sys
import json
import time
import uuid
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, Union

# Relative/project imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cose_signer import jcs_canonicalize, generate_keypair, sign_trust_passport
from src.bbs_signer import BBSPlusEngine, SovereignAuditLogEntry

try:
    from aeib_postgresql_probe.adapter import PostgresProbeAdapter, ProbeResult, ProbeOutcome
except ImportError:
    PostgresProbeAdapter = None
    ProbeResult = None
    ProbeOutcome = None


@dataclass
class InterceptorAction:
    action_id: str
    idempotency_key: str
    operation: str
    payload: Dict[str, Any]
    destination: str
    timestamp_iso: str = ""

    def __post_init__(self):
        if not self.timestamp_iso:
            self.timestamp_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


@dataclass
class InterceptorResult:
    disposition: str
    retry_policy: str
    wire_status: Union[int, str]
    action: InterceptorAction
    probe_outcome: Optional[Dict[str, Any]] = None
    signed_envelope: Optional[Dict[str, Any]] = None
    redacted_proof: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "disposition": self.disposition,
            "retry_policy": self.retry_policy,
            "wire_status": self.wire_status,
            "action_id": self.action.action_id,
            "idempotency_key": self.action.idempotency_key,
            "operation": self.action.operation,
            "probe_outcome": self.probe_outcome,
            "signed_envelope": self.signed_envelope,
            "redacted_proof": self.redacted_proof
        }



def _json_safe(val: Any) -> Any:
    from decimal import Decimal
    from datetime import datetime, date
    if isinstance(val, Decimal):
        return float(val)
    elif isinstance(val, (datetime, date)):
        return val.isoformat()
    elif isinstance(val, dict):
        return {k: _json_safe(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_json_safe(v) for v in val]
    return val

class TransportInterceptor:
    """
    Fail-Closed Transport Interceptor and Out-of-Band Reconciler.
    """

    AMBIGUOUS_WIRE_STATUSES = {504, 502, 503, "504", "TCP_RST", "TIMEOUT", "DROP"}

    def __init__(
        self,
        probe_adapter: Optional[Any] = None,
        signing_key_path: Optional[Path] = None,
        export_dir: Path = Path("./audit_out")
    ):
        self.probe_adapter = probe_adapter
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        key_path = signing_key_path or (self.export_dir / "smaos_signing_key.pem")
        self.signing_key = generate_keypair(key_path)

    def intercept_and_reconcile(
        self,
        action: InterceptorAction,
        wire_status: Union[int, str],
        redact_pii: bool = False,
        statement_timeout_ms: int = 5000
    ) -> InterceptorResult:
        """
        Intercepts an action response, detects ambiguous wire failure, executes OOB probe,
        and cryptographically seals the resulting disposition.
        """
        is_ambiguous = wire_status in self.AMBIGUOUS_WIRE_STATUSES or (
            isinstance(wire_status, int) and wire_status in (502, 503, 504)
        )

        probe_dict: Optional[Dict[str, Any]] = None

        if not is_ambiguous:
            # Nominal or clear definitive wire outcome
            if wire_status in (200, 201, 204):
                disposition = "CONFIRMED"
                retry_policy = "MUTATION_COMMITTED_NO_RETRY"
            else:
                disposition = "REJECTED_DEFINITIVE"
                retry_policy = "RETRY_PERMITTED_NEW_KEY"
        else:
            # Ambiguous transport severance (HTTP 504, TCP_RST, etc.)
            disposition = "DISPATCHED_UNCONFIRMED"
            retry_policy = "PROBE_REQUIRED_NO_ORIGINAL_RETRY"

            # Execute out-of-band probe if adapter available
            if self.probe_adapter:
                if hasattr(self.probe_adapter, "execute_probe"):
                    outcome = self.probe_adapter.execute_probe(
                        idempotency_key=action.idempotency_key,
                        statement_timeout_ms=statement_timeout_ms
                    )
                    probe_dict = {
                        "result": outcome.result.value if hasattr(outcome.result, "value") else str(outcome.result),
                        "evidence": _json_safe(outcome.evidence),
                        "error_message": outcome.error_message
                    }

                    # Reconcile disposition based on out-of-band ground truth
                    res_val = outcome.result.value if hasattr(outcome.result, "value") else str(outcome.result)
                    if res_val == "OUTCOME_VERIFIED":
                        disposition = "OUTCOME_VERIFIED"
                        retry_policy = "PROBE_CONFIRMED_COMMITTED_NO_RETRY"
                    elif res_val == "RECONCILIATION_NOT_FOUND":
                        disposition = "RECONCILIATION_NOT_FOUND"
                        retry_policy = "PROBE_CONFIRMED_UNCOMMITTED_RETRY_PERMITTED"
                    elif res_val == "RECONCILIATION_CONFLICT":
                        disposition = "RECONCILIATION_CONFLICT"
                        retry_policy = "PROBE_CONFLICT_FAIL_CLOSED_NO_RETRY"
                    elif res_val == "PROBE_TIMEOUT":
                        disposition = "DISPATCHED_UNCONFIRMED"
                        retry_policy = "PROBE_TIMEOUT_FAIL_CLOSED_HOLD"

        # Build Trust Passport Payload
        passport_payload = {
            "version": "0.3.0",
            "issuer": "urn:smaos:gateway:prague_01",
            "action_id": action.action_id,
            "idempotency_key": action.idempotency_key,
            "operation": action.operation,
            "wire_status": str(wire_status),
            "disposition": disposition,
            "retry_policy": retry_policy,
            "timestamp": action.timestamp_iso,
            "probe_outcome": probe_dict
        }

        # Step 4: Cryptographic Sealing (SCITT COSE_Sign1)
        signed_envelope = sign_trust_passport(passport_payload, self.signing_key)
        cose_path = self.export_dir / "trust_passport.cose.json"
        with open(cose_path, "w", encoding="utf-8") as f:
            json.dump(signed_envelope, f, indent=2)

        # Optional BBS+ Selective Redaction
        redacted_proof_dict = None
        if redact_pii:
            redacted_proof_dict = self._apply_bbs_redaction(action, disposition, passport_payload)

        return InterceptorResult(
            disposition=disposition,
            retry_policy=retry_policy,
            wire_status=wire_status,
            action=action,
            probe_outcome=probe_dict,
            signed_envelope=signed_envelope,
            redacted_proof=redacted_proof_dict
        )

    def _apply_bbs_redaction(
        self,
        action: InterceptorAction,
        disposition: str,
        passport_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Blinds customer PII while generating a zero-knowledge selective proof."""
        payload_data = action.payload or {}
        log_data = {
            "event_id": f"EVT-{action.action_id[:8]}",
            "timestamp_iso": action.timestamp_iso,
            "agent_id": "SMAOS-TREASURY-01",
            "tool_name": action.operation,
            "user_full_name": payload_data.get("full_name", "REDACTED_USER"),
            "user_iban": payload_data.get("iban", "CZ6508000000001234567890"),
            "user_tax_id": payload_data.get("tax_id", "TAX-EXAMPLE-001"),
            "credit_limit_eur": str(payload_data.get("amount", 50000)),
            "policy_verdict": disposition,
            "boundary_hash": signed_hash if (signed_hash := passport_payload.get("payload_hash")) else hashlib.sha256(b"dummy").hexdigest()
        }

        field_names = SovereignAuditLogEntry.get_field_names()
        priv_key, pub_key = BBSPlusEngine.generate_keypair(
            message_count=len(field_names),
            key_id="smaos-bbs-audit-01"
        )
        entry = SovereignAuditLogEntry(log_data)
        messages = entry.to_message_vector()
        sig = BBSPlusEngine.sign_messages(priv_key, messages)

        disclosed_indices = SovereignAuditLogEntry.get_non_pii_indices()
        proof = BBSPlusEngine.create_selective_proof(
            pub_key=pub_key,
            signature=sig,
            messages=messages,
            field_names=field_names,
            disclosed_indices=disclosed_indices
        )

        is_valid, msg, _ = BBSPlusEngine.verify_selective_proof(
            pub_key=pub_key,
            proof=proof,
            field_names=field_names
        )

        if not is_valid:
            raise RuntimeError(f"BBS+ selective proof verification failed: {msg}")

        redacted_doc = {
            "type": "BBSPlusSelectiveDisclosureProof",
            "status": "VERIFIED_REDACTED",
            "proof": proof.to_dict(),
            "public_key": pub_key.to_dict(),
            "disclosed_fields": [field_names[i] for i in sorted(disclosed_indices)]
        }

        redacted_path = self.export_dir / "trust_passport.redacted.json"
        with open(redacted_path, "w", encoding="utf-8") as f:
            json.dump(redacted_doc, f, indent=2)

        return redacted_doc
