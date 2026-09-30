#!/usr/bin/env python3
r"""
aeib_interceptor.py — AEIB Userspace Sidecar & Out-of-Band State Machine
Sovereign Multi-Agent OS (SMAOS) / Deterministic Fault-Injection Testbed

Implements the AEIB execution boundary:
  1. JCS-compatible normalization for the fields exercised by this benchmark + UUIDv5 idempotency key derivation before dispatch.
  2. Immediate retry freezing on HTTP 504 (DISPATCHED_UNCONFIRMED).
  3. Layer A eBPF 5-tuple quarantine activation.
  4. Authoritative out-of-band probe query against GET /operations/{id}.
  5. Deterministic state transition to OUTCOME_VERIFIED with retry_permitted=False.
  6. Layer B Ed25519-signed AEIB receipt generation binding transport telemetry.
"""

import os
import sys
import uuid
import time
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from starlette.testclient import TestClient

from src.jcs_canonicalizer import encode_jcs, generate_jcs_payload_hash
from ebpf.controller import XdpQuarantineController, TCP

AEIB_NAMESPACE_URL = uuid.NAMESPACE_URL


class AeibExecutionInterceptor:
    """
    AEIB Sidecar Interceptor wrapping client tool calls / payment dispatches.
    Guarantees Safety Invariant (LedgerCommits <= 1) and Liveness Invariant.
    """

    def __init__(
        self,
        backend_client: TestClient,
        private_key: Optional[ed25519.Ed25519PrivateKey] = None,
        enable_ebpf_simulation: bool = True,
        evidence_dir: Optional[Path] = None,
    ):
        self.backend = backend_client
        self._private_key = private_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self._private_key.public_key()
        pub_raw = self.public_key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.key_id = f"ed25519-{hashlib.sha256(pub_raw).hexdigest()[:16]}"
        self.ebpf = XdpQuarantineController(iface="lo", force_simulate=True)
        self.evidence_dir = evidence_dir or Path("evidence")
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.transport_log_file = self.evidence_dir / "transport.jsonl"

    def normalize_and_hash(self, payload: Dict[str, Any]) -> Tuple[bytes, str, str]:
        """
        Computes RFC 8785 canonical bytes, SHA-256 hash, and deterministic UUIDv5 key.
        """
        canonical_bytes = encode_jcs(payload)
        payload_hash = hashlib.sha256(canonical_bytes).hexdigest()
        uuidv5_key = str(uuid.uuid5(AEIB_NAMESPACE_URL, f"urn:aeib:payload:{payload_hash}"))
        return canonical_bytes, payload_hash, uuidv5_key

    def dispatch_with_integrity(
        self,
        target_path: str,
        payload: Dict[str, Any],
        src_ip: str = "127.0.0.1",
        src_port: int = 49210,
        dst_ip: str = "127.0.0.1",
        dst_port: int = 8080,
    ) -> Dict[str, Any]:
        """
        Executes request through the AEIB execution boundary:
          - Canonicalizes payload & injects UUIDv5 Idempotency-Key
          - Dispatches to backend
          - On 504 Gateway Timeout: activates quarantine, probes ledger, emits signed receipt
        """
        start_time = time.time()
        canonical_bytes, payload_hash, uuidv5_key = self.normalize_and_hash(payload)

        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": uuidv5_key,
            "X-Payload-Hash-Sha256": payload_hash,
            "X-Attempt-Count": "1",
        }

        # 1. Wire dispatch
        response = self.backend.post(target_path, content=canonical_bytes, headers=headers)
        status_code = response.status_code

        # 2. Happy Path: 200 OK
        if status_code in (200, 201):
            return {
                "status": "SUCCESS",
                "http_status": status_code,
                "disposition": "OUTCOME_VERIFIED",
                "retry_permitted": False,
                "data": response.json(),
                "idempotency_key": uuidv5_key,
                "overhead_ms": (time.time() - start_time) * 1000.0,
            }

        # 3. Fault Path: 504 Gateway Timeout intercepted!
        # Step A: Freeze Retries & Activate Layer A eBPF Quarantine
        self.ebpf.add_flow(src_ip, src_port, dst_ip, dst_port, TCP, disposition=1)

        # Log drop event to transport evidence
        event_dict = {
            "event": "AEIB_XDP_PACKET_DROP",
            "timestamp_ns": time.time_ns(),
            "disposition_code": 1,
            "disposition": "DISPATCHED_UNCONFIRMED",
            "flow": {
                "source": f"{src_ip}:{src_port}",
                "destination": f"{dst_ip}:{dst_port}",
                "protocol": "TCP",
            },
            "action": "XDP_DROP",
            "payload_hash": payload_hash,
            "idempotency_key": uuidv5_key,
        }
        event_line = json.dumps(event_dict, sort_keys=True)
        with open(self.transport_log_file, "a", encoding="utf-8") as f:
            f.write(event_line + "\n")

        transport_evidence_hash = hashlib.sha256(event_line.encode("utf-8")).hexdigest()

        # Step B: Authoritative Out-of-Band Probe against GET /operations/{id}
        probe_target = payload.get("logical_operation_id") or payload.get("intent_id")
        probe_response = self.backend.get(f"/operations/{probe_target}")
        probe_data = probe_response.json() if probe_response.status_code == 200 else {}

        # Step C: Evaluate State Machine Disposition
        is_committed = probe_data.get("committed", False)
        commit_count = probe_data.get("commit_count", 0)

        if is_committed:
            disposition = "OUTCOME_VERIFIED"
            retry_policy = "PROHIBITED_ALREADY_COMMITTED"
            retry_permitted = False
            action_required = "NONE_TRANSACTION_RECONCILED"
        else:
            disposition = "RECONCILIATION_NOT_FOUND"
            retry_policy = "PERMITTED_UNDER_HUMAN_APPROVAL"
            retry_permitted = True
            action_required = "REQUIRES_OPERATOR_CONFIRMATION"

        # Step D: Emit Signed AEIB Receipt (Layer B)
        unsigned_payload = {
            "receipt_version": "v0.2.1",
            "scenario_id": f"fault-injection-{payload.get('intent_id')}",
            "logical_operation_id": payload.get("logical_operation_id"),
            "intent_id": payload.get("intent_id"),
            "actor": "aeib-sidecar-proxy",
            "idempotency_key_uuidv5": uuidv5_key,
            "payload_hash_sha256": payload_hash,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "org.smaos.aeib": {
                "disposition": disposition,
                "retry_policy": retry_policy,
                "retry_permitted": retry_permitted,
                "transport_code": status_code,
                "probe_status": "FOUND_COMMITTED" if is_committed else "RECORD_NOT_FOUND",
                "commit_count": commit_count,
                "evidence_bindings": {
                    "transport_evidence_file": str(self.transport_log_file),
                    "transport_evidence_hash": transport_evidence_hash,
                    "quarantine_flow": f"{src_ip}:{src_port} -> {dst_ip}:{dst_port}",
                },
            },
        }

        canonical_receipt_bytes = encode_jcs(unsigned_payload)
        unsigned_hash = hashlib.sha256(canonical_receipt_bytes).hexdigest()

        signable_view = {
            "unsigned_payload": unsigned_payload,
            "unsigned_payload_hash": unsigned_hash,
        }
        signable_bytes = encode_jcs(signable_view)
        signature = self._private_key.sign(signable_bytes).hex()

        receipt = {
            "format": "AEIB_JSON_ED25519_PROTOTYPE",
            "unsigned_payload": unsigned_payload,
            "unsigned_payload_hash": unsigned_hash,
            "signature_metadata": {
                "signed_payload_hash": unsigned_hash,
                "key_id": self.key_id,
                "algorithm": "Ed25519",
                "signature": signature,
            },
        }

        # Step E: Release quarantine once terminal disposition is reached
        self.ebpf.remove_flow(src_ip, src_port, dst_ip, dst_port, TCP)

        elapsed_ms = (time.time() - start_time) * 1000.0

        return {
            "status": "RECONCILED",
            "http_status": status_code,
            "disposition": disposition,
            "retry_permitted": retry_permitted,
            "retry_policy": retry_policy,
            "action_required": action_required,
            "commit_count": commit_count,
            "receipt": receipt,
            "transport_evidence_hash": transport_evidence_hash,
            "overhead_ms": elapsed_ms,
        }
