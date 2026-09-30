#!/usr/bin/env python3
r"""
transport_observer.py — MCP Sidecar Transport Observer & Execution Boundary Guard
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB v0.2.1)

Intercepts incoming MCP JSON-RPC requests, computes RFC 8785 JCS canonical digests,
injects deterministic UUIDv5 idempotency keys, catches transport-level failures (504, EOF),
evaluates mapping contracts, probes downstream state, and emits signed AEIB receipts.
"""

import json
import uuid
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
from src.sqlite_probe_adapter import SQLiteOutcomeProbeAdapter

# Standard AEIB UUIDv5 Namespace URL
AEIB_NAMESPACE_URL = uuid.NAMESPACE_URL

# Fallback default mapping rules if external YAML mapping file is not present
DEFAULT_MAPPING_RULES = [
    {
        "id": "RULE-05-CONFLICT",
        "priority": 10,
        "match": {"transport_code": 409, "probe_status": "STATE_CONFLICT"},
        "target_disposition": "RECONCILIATION_CONFLICT",
        "retry_policy": "PROHIBITED_LOCK_RECORD",
        "retry_permitted": False,
    },
    {
        "id": "RULE-06-CONTEXT-REFUSED",
        "priority": 15,
        "match": {"transport_code": 403, "probe_status": "NOT_DISPATCHED"},
        "target_disposition": "CONTEXT_POLICY_VIOLATION",
        "retry_policy": "PROHIBITED_POLICY_BLOCK",
        "retry_permitted": False,
    },
    {
        "id": "RULE-07-AUTHORITY-EXPIRED",
        "priority": 15,
        "match": {"transport_code": 401, "probe_status": "NOT_DISPATCHED"},
        "target_disposition": "AUTHORITY_NOT_BOUND",
        "retry_policy": "PROHIBITED_REAUTH_REQUIRED",
        "retry_permitted": False,
    },
    {
        "id": "RULE-04-PAYLOAD-MISMATCH",
        "priority": 20,
        "match": {"transport_code": 504, "probe_status": "PAYLOAD_MISMATCH"},
        "target_disposition": "RECONCILIATION_FAILED",
        "retry_policy": "PROHIBITED_ESCALATE_AUDIT",
        "retry_permitted": False,
    },
    {
        "id": "RULE-02B-504-RECONCILED",
        "priority": 25,
        "match": {"transport_code": 504, "probe_status": "FOUND_COMMITTED"},
        "target_disposition": "OUTCOME_VERIFIED",
        "retry_policy": "PROHIBITED_ALREADY_COMMITTED",
        "retry_permitted": False,
    },
    {
        "id": "RULE-03-RESET-NOT-FOUND",
        "priority": 25,
        "match": {"transport_code": 504, "probe_status": "RECORD_NOT_FOUND"},
        "target_disposition": "RECONCILIATION_NOT_FOUND",
        "retry_policy": "PERMITTED_UNDER_HUMAN_APPROVAL",
        "retry_permitted": True,
    },
    {
        "id": "RULE-02A-504-AMBIGUOUS",
        "priority": 30,
        "match": {"transport_code": 504, "probe_status": "AWAITING_OPERATOR_PROBE"},
        "target_disposition": "DISPATCHED_UNCONFIRMED",
        "retry_policy": "PROHIBITED_AWAITING_PROBE",
        "retry_permitted": False,
    },
    {
        "id": "RULE-01-CONFIRMED",
        "priority": 50,
        "match": {"transport_code": 200, "probe_status": "NOT_REQUIRED"},
        "target_disposition": "OUTCOME_VERIFIED",
        "retry_policy": "NOT_APPLICABLE_COMPLETED",
        "retry_permitted": False,
    },
]


def derive_uuidv5_idempotency_key(payload_hash: str) -> str:
    """Derives deterministic UUIDv5 idempotency key bound to the payload hash."""
    return str(uuid.uuid5(AEIB_NAMESPACE_URL, f"urn:aeib:payload:{payload_hash}"))


class TransportObserver:
    """
    AEIB Sidecar Interceptor and traffic observer.
    Guards tool execution integrity across stdio and HTTP JSON-RPC boundaries.
    """

    def __init__(
        self,
        private_key: Optional[ed25519.Ed25519PrivateKey] = None,
        probe_adapter: Optional[SQLiteOutcomeProbeAdapter] = None,
        key_id: str = "ed25519-local-sidecar-01",
        mapping_path: Optional[str] = None,
    ):
        self.key_id = key_id
        if private_key is None:
            self._private_key = ed25519.Ed25519PrivateKey.generate()
        else:
            self._private_key = private_key

        self.public_key = self._private_key.public_key()
        self.public_key_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        self.probe_adapter = probe_adapter
        self.rules = self._load_rules(mapping_path)

    def _load_rules(self, mapping_path: Optional[str]) -> list:
        if mapping_path and Path(mapping_path).exists():
            try:
                import yaml
                data = yaml.safe_load(Path(mapping_path).read_text(encoding="utf-8"))
                rules = data.get("rules", [])
                if rules:
                    for r in rules:
                        if "retry_permitted" not in r:
                            r["retry_permitted"] = (r.get("target_disposition") == "RECONCILIATION_NOT_FOUND")
                    return sorted(rules, key=lambda x: x.get("priority", 999))
            except Exception:
                pass
        return DEFAULT_MAPPING_RULES

    def intercept_request(self, json_rpc_request: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Intercepts an incoming JSON-RPC request before dispatch.
        Computes JCS canonical payload hash and injects UUIDv5 idempotency key.
        """
        req = json.loads(json.dumps(json_rpc_request))  # Deep copy
        method = req.get("method", "")
        params = req.get("params", {})
        req_id = req.get("id")

        if method == "tools/call":
            tool_name = params.get("name", "unknown_tool")
            args = params.get("arguments", {})
            action_id = f"mcp://sidecar/{tool_name}"
        else:
            tool_name = method
            args = params
            action_id = f"mcp://sidecar/{method}"

        # 1. Canonicalize payload arguments and compute deterministic hash
        payload_hash = f"sha256:{generate_jcs_payload_hash(args)}"

        # 2. Derive deterministic UUIDv5 idempotency key
        idempotency_key = derive_uuidv5_idempotency_key(payload_hash)

        # 3. Inject metadata into request parameters
        if "_meta" not in params:
            params["_meta"] = {}
        params["_meta"]["idempotency_key"] = idempotency_key
        params["_meta"]["unsigned_payload_hash"] = payload_hash
        req["params"] = params

        # Context record for dispatch tracking
        dispatch_ctx = {
            "request_id": req_id,
            "action_id": action_id,
            "tool_name": tool_name,
            "arguments": args,
            "payload_hash": payload_hash,
            "idempotency_key": idempotency_key,
            "dispatched_at_utc": datetime.now(timezone.utc).isoformat(),
            "timestamp": int(time.time()),
        }
        return req, dispatch_ctx

    def evaluate_rule(self, transport_code: int, probe_status: str) -> Dict[str, Any]:
        """Evaluates mapping rules strictly in priority order."""
        for rule in self.rules:
            m = rule.get("match", {})
            if m.get("transport_code") == transport_code and m.get("probe_status") == probe_status:
                return rule
        return {
            "id": "RULE-UNKNOWN",
            "priority": 999,
            "target_disposition": "DISPATCHED_UNCONFIRMED",
            "retry_policy": "PROHIBITED_UNKNOWN_FAULT",
            "retry_permitted": False,
        }

    def emit_receipt(
        self,
        dispatch_ctx: Dict[str, Any],
        transport_code: int,
        probe_status: Optional[str] = None,
        transport_fault: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Emits and cryptographically signs an AEIB_JSON_ED25519_PROTOTYPE receipt.
        """
        # 1. Resolve probe status via probe adapter if not explicitly supplied
        idempotency_key = dispatch_ctx["idempotency_key"]
        payload_hash = dispatch_ctx["payload_hash"]

        if probe_status is None:
            if self.probe_adapter is not None:
                probe_res = self.probe_adapter.probe(idempotency_key, expected_payload_hash=payload_hash)
                if probe_res == "OUTCOME_VERIFIED":
                    probe_status = "FOUND_COMMITTED"
                elif probe_res == "RECONCILIATION_NOT_FOUND":
                    probe_status = "RECORD_NOT_FOUND"
                elif probe_res == "RECONCILIATION_FAILED":
                    probe_status = "PAYLOAD_MISMATCH"
                else:
                    probe_status = "AWAITING_OPERATOR_PROBE"
            else:
                if transport_code == 504:
                    probe_status = "AWAITING_OPERATOR_PROBE"
                elif transport_code in (401, 403):
                    probe_status = "NOT_DISPATCHED"
                elif transport_code == 200:
                    probe_status = "NOT_REQUIRED"
                else:
                    probe_status = "AWAITING_OPERATOR_PROBE"

        if transport_fault is None:
            transport_fault = f"TRANSPORT_HTTP_{transport_code}" if transport_code != 200 else "NONE"

        # 2. Evaluate rule from mapping
        rule = self.evaluate_rule(transport_code, probe_status)
        disposition = rule.get("target_disposition", "DISPATCHED_UNCONFIRMED")
        retry_policy_id = rule.get("retry_policy", "PROHIBITED_UNKNOWN")

        # 3. Assemble evidence identifiers
        t_event_id = f"tr_{dispatch_ctx['request_id']}"
        p_event_id = f"probe_{dispatch_ctx['request_id']}"
        t_event_hash = hashlib.sha256(f"{t_event_id}:{transport_code}:{transport_fault}".encode()).hexdigest()
        p_event_hash = hashlib.sha256(f"{p_event_id}:{probe_status}".encode()).hexdigest()

        # 4. Construct unsigned_payload
        unsigned_payload = {
            "receipt_version": "v0.2.0",
            "scenario_id": f"sidecar-{dispatch_ctx['request_id']}",
            "action_id": dispatch_ctx["action_id"],
            "actor": "aeib-mcp-sidecar-proxy",
            "idempotency_key_uuidv5": idempotency_key,
            "timestamp": dispatch_ctx["timestamp"],
            "timestamp_utc": dispatch_ctx["dispatched_at_utc"],
            "org.smaos.aeib": {
                "disposition": disposition,
                "retry_policy": retry_policy_id,
                "matched_rule_id": rule.get("id"),
                "transport_code": transport_code,
                "transport_fault": transport_fault,
                "probe_status": probe_status,
                "evidence_bindings": {
                    "transport_event_id": t_event_id,
                    "transport_event_hash": t_event_hash,
                    "probe_event_id": p_event_id,
                    "probe_event_hash": p_event_hash,
                },
            },
        }

        # 5. Compute canonical hash of unsigned payload
        payload_bytes = encode_jcs(unsigned_payload)
        unsigned_hash = hashlib.sha256(payload_bytes).hexdigest()

        # 6. Form signable view and sign with Ed25519
        signable_view = {
            "unsigned_payload": unsigned_payload,
            "unsigned_payload_hash": unsigned_hash,
        }
        signable_bytes = encode_jcs(signable_view)
        signature_bytes = self._private_key.sign(signable_bytes)

        receipt = {
            "format": "AEIB_JSON_ED25519_PROTOTYPE",
            "scenario_id": f"sidecar-{dispatch_ctx['request_id']}",
            "unsigned_payload": unsigned_payload,
            "unsigned_payload_hash": unsigned_hash,
            "signature_metadata": {
                "signed_payload_hash": unsigned_hash,
                "key_id": self.key_id,
                "algorithm": "Ed25519",
                "signature": signature_bytes.hex(),
            },
        }
        return receipt

    def intercept_transport_fault(
        self,
        dispatch_ctx: Dict[str, Any],
        transport_code: int = 504,
        error_message: str = "Gateway Timeout",
        probe_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Intercepts transport failure, generates signed AEIB receipt,
        and returns standard JSON-RPC error suppressing unhedged agent retries.
        """
        receipt = self.emit_receipt(
            dispatch_ctx=dispatch_ctx,
            transport_code=transport_code,
            probe_status=probe_status,
            transport_fault=f"TRANSPORT_FAULT_{transport_code}_{error_message.replace(' ', '_').upper()}",
        )

        rule = self.evaluate_rule(transport_code, receipt["unsigned_payload"]["org.smaos.aeib"]["probe_status"])
        retry_permitted = rule.get("retry_permitted", False)
        disposition = receipt["unsigned_payload"]["org.smaos.aeib"]["disposition"]

        return {
            "jsonrpc": "2.0",
            "id": dispatch_ctx["request_id"],
            "error": {
                "code": -32000,
                "message": f"AEIB Execution Boundary Intercepted Fault: {rule.get('id')} ({disposition})",
                "data": {
                    "disposition": disposition,
                    "retry_permitted": retry_permitted,
                    "retry_policy": rule.get("retry_policy"),
                    "action_required": "OUT_OF_BAND_RECONCILIATION_REQUIRED" if not retry_permitted else "SAFE_TO_RESEND",
                    "receipt": receipt,
                },
            },
        }

    def emit_ebpf_xdp_receipt(
        self,
        dispatch_ctx: Dict[str, Any],
        kernel_telemetry: Dict[str, Any],
        decision: str = "permit",
        execution_observation: str = "tcp_retry_dropped_by_xdp",
        outcome_verification: str = "not_confirmed",
    ) -> Dict[str, Any]:
        """
        Binds eBPF Ringbuf telemetry into the transport_evidence block of an AEIB receipt.
        Enforces RFC 8785 JCS canonicalization and Ed25519 signature attestation.
        """
        idempotency_key = dispatch_ctx["idempotency_key"]
        payload_hash = dispatch_ctx["payload_hash"]

        unsigned_payload = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "receipt_version": "aeib-0.2",
            "receipt_id": f"urn:uuid:{uuid.uuid4()}",
            "action_id": dispatch_ctx["action_id"],
            "decision": decision,
            "execution_observation": execution_observation,
            "outcome_verification": outcome_verification,
            "aeib_extension": {
                "version": "0.1",
                "disposition": "DISPATCHED_UNCONFIRMED",
                "retry_policy": "PROBE_REQUIRED_NO_ORIGINAL_RETRY",
                "dora_binding": {
                    "incident_class": None,
                    "classification_timestamp_utc": None,
                    "classification_status": "PENDING_HUMAN_REVIEW",
                },
            },
            "transport_evidence": {
                "adapter_type": "ebpf_xdp_driver",
                "adapter_version": "0.1",
                "observation": "quarantine_flow_dropped",
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "kernel_telemetry": kernel_telemetry,
            },
            "outcome_probe": {
                "adapter_type": "database_ledger",
                "probe_status": "not_yet_attempted",
                "authoritative_source_id": "ledger:sqlite-downstream",
                "expected_payload_hash": payload_hash,
                "idempotency_key": idempotency_key,
            },
        }

        # Canonicalize and hash with RFC 8785 JCS
        payload_bytes = encode_jcs(unsigned_payload)
        unsigned_hash = hashlib.sha256(payload_bytes).hexdigest()

        signable_view = {
            "unsigned_payload": unsigned_payload,
            "unsigned_payload_hash": unsigned_hash,
        }
        signable_bytes = encode_jcs(signable_view)
        signature_bytes = self._private_key.sign(signable_bytes)

        receipt = {
            "format": "AEIB_JSON_ED25519_PROTOTYPE",
            "receipt_id": unsigned_payload["receipt_id"],
            "unsigned_payload": unsigned_payload,
            "unsigned_payload_hash": unsigned_hash,
            "signature_metadata": {
                "signed_payload_hash": unsigned_hash,
                "key_id": self.key_id,
                "algorithm": "Ed25519",
                "signature": signature_bytes.hex(),
            },
        }
        return receipt

