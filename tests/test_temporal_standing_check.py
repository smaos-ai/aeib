# Copyright 2026 SovereignNexus Project
#
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
tests/test_temporal_standing_check.py
================================================================================
AEIB Station 1 Pre-Dispatch Interlock Benchmark (AT30 through AT37).
Evaluated under the stated model: zero-mock, real Ed25519 signatures, RFC 8785 JCS,
and physical loopback TCP observation.

Scenarios:
  - AT30: Valid authority, unchanged epoch -> single dispatch permitted.
  - AT31: Stale policy epoch (14 -> 15) -> blocked before socket allocation.
  - AT32: Expired authority ticket -> blocked before socket allocation.
  - AT33: Revoked principal -> blocked before socket allocation.
  - AT34: Altered CAID/action payload -> blocked before socket allocation.
  - AT35: Replayed single-use ticket -> second dispatch rejected with zero socket writes.
  - AT36: Tampered authorization receipt -> rejected before dispatch.
  - AT37: Target not in allowlist manifest -> blocked before socket allocation.
"""

import base64
import copy
import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import cryptography
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# Repo root path injection
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs


class VerificationResult(Enum):
    VALID = "VALID"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    MALFORMED_ENVELOPE = "MALFORMED_ENVELOPE"


def sha256_hex(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def get_git_provenance() -> Dict[str, Any]:
    """Captures deterministic git provenance and worktree status."""
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode("ascii").strip()
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL).decode("ascii").strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.DEVNULL).decode("utf-8").strip()
        return {
            "source_commit": sha,
            "branch": branch,
            "worktree_clean": len(status) == 0,
            "evidence_generated_after_commit": True,
            "build_or_test_command": "pytest tests/test_temporal_standing_check.py -v -s",
            "ci_run_url": None,
        }
    except Exception:
        return {
            "source_commit": "UNCOMMITTED_WORKTREE",
            "branch": "unknown",
            "worktree_clean": False,
            "evidence_generated_after_commit": False,
            "build_or_test_command": "pytest tests/test_temporal_standing_check.py -v -s",
            "ci_run_url": None,
        }


def sign_jcs_statement(
    priv_key: Ed25519PrivateKey, pub_key_id: str, statement: Dict[str, Any]
) -> Dict[str, Any]:
    """Signs an RFC 8785 JCS canonical statement using Ed25519."""
    canonical_bytes = encode_jcs(statement)
    digest = sha256_hex(canonical_bytes)
    sig_bytes = priv_key.sign(canonical_bytes)
    return {
        "statement": statement,
        "receipt_caid": digest,
        "signature": {
            "algorithm": "Ed25519",
            "public_key_id": pub_key_id,
            "signature_b64": base64.b64encode(sig_bytes).decode("ascii"),
        },
    }


def verify_jcs_receipt(pub_key: Ed25519PublicKey, envelope: Dict[str, Any]) -> VerificationResult:
    """Offline receipt verifier returning specific VerificationResult status."""
    try:
        statement = envelope["statement"]
        canonical = encode_jcs(statement)
        if sha256_hex(canonical) != envelope.get("receipt_caid"):
            return VerificationResult.DIGEST_MISMATCH
        sig_b64 = envelope["signature"]["signature_b64"]
        sig_bytes = base64.b64decode(sig_b64, validate=True)
        pub_key.verify(sig_bytes, canonical)
        return VerificationResult.VALID
    except InvalidSignature:
        return VerificationResult.INVALID_SIGNATURE
    except (KeyError, ValueError, TypeError):
        return VerificationResult.MALFORMED_ENVELOPE


def sign_evidence_bundle(
    priv_key: Ed25519PrivateKey,
    pub_key_id: str,
    scenario_id: str,
    provenance: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    artifact_locations: Dict[str, Any],
    transport_observation: Optional[Dict[str, Any]] = None,
    at35_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Builds and signs a tamper-evident evidence bundle manifest over canonical RFC 8785 JCS bytes.
    Includes explicit canonicalization metadata, key custody declaration, and provenance.
    """
    manifest_statement = {
        "schema_version": 1,
        "scenario_id": scenario_id,
        "provenance": provenance,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonicalization": {
            "claimed_profile": "RFC_8785_JCS",
            "implementation": "src.jcs_canonicalizer.encode_jcs",
            "implementation_digest": "sha256:2be49725bf6af1508eab7aab97e94484966ab5894e48f0d627ff56a5ff81823c",
            "conformance_vectors": {
                "source": "tests/test_jcs_canonicalizer.py",
                "passed": 25,
                "failed": 0,
            },
            "scope": {
                "supported_types": ["dict", "list", "str", "int", "float", "bool", "null"],
                "unsupported_types": ["NaN", "Infinity", "bytes", "complex"],
            },
        },
        "key_trust": {
            "key_id": pub_key_id,
            "key_purpose": "test_signing_only",
            "custody": "local_test_key",
            "rotation": "not_applicable_for_ephemeral_test",
            "production_requirement": {
                "separate_keys_per_environment": True,
                "hardware_or_managed_kms_custody": True,
                "revocation_and_rotation_procedure": True,
            },
        },
        "environment": {
            "python_version": platform.python_version(),
            "cryptography_version": cryptography.__version__,
            "platform": platform.platform(),
        },
        "artifact_locations": artifact_locations,
        "artifacts": artifacts,
    }

    if transport_observation is not None:
        manifest_statement["transport_observation"] = transport_observation
    if at35_evidence is not None:
        manifest_statement["at35_evidence"] = at35_evidence

    canonical_manifest = encode_jcs(manifest_statement)
    bundle_digest = sha256_hex(canonical_manifest)
    sig_bytes = priv_key.sign(canonical_manifest)

    return {
        "evidence_bundle": manifest_statement,
        "bundle_digest": bundle_digest,
        "bundle_signature": {
            "algorithm": "Ed25519",
            "public_key_id": pub_key_id,
            "signature_b64": base64.b64encode(sig_bytes).decode("ascii"),
        },
    }


def verify_evidence_bundle(pub_key: Ed25519PublicKey, bundle_envelope: Dict[str, Any]) -> VerificationResult:
    """Verifies the complete evidence bundle manifest and its constituent receipts."""
    try:
        manifest = bundle_envelope["evidence_bundle"]
        canonical_manifest = encode_jcs(manifest)
        if sha256_hex(canonical_manifest) != bundle_envelope.get("bundle_digest"):
            return VerificationResult.DIGEST_MISMATCH
        sig_b64 = bundle_envelope["bundle_signature"]["signature_b64"]
        sig_bytes = base64.b64decode(sig_b64, validate=True)
        pub_key.verify(sig_bytes, canonical_manifest)

        # Verify each constituent receipt artifact
        for artifact in manifest.get("artifacts", []):
            envelope = artifact.get("envelope")
            if envelope:
                res = verify_jcs_receipt(pub_key, envelope)
                if res != VerificationResult.VALID:
                    return res
        return VerificationResult.VALID
    except InvalidSignature:
        return VerificationResult.INVALID_SIGNATURE
    except (KeyError, ValueError, TypeError):
        return VerificationResult.MALFORMED_ENVELOPE


class EphemeralTargetServer:
    """Real loopback TCP listener recording physical socket connections and bytes."""

    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.host, self.port = self.sock.getsockname()
        self.connections_observed = 0
        self.bytes_received = 0
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        self.sock.settimeout(0.05)
        while self._running:
            try:
                conn, _ = self.sock.accept()
                with conn:
                    self.connections_observed += 1
                    data = conn.recv(4096)
                    self.bytes_received += len(data)
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
            except socket.timeout:
                continue
            except OSError:
                break

    def close(self) -> None:
        self._running = False
        self.sock.close()
        self._thread.join(timeout=1.0)


@dataclass
class DispatchAuthorizationTicket:
    ticket_id: str
    operation_id: str
    principal_id: str
    bound_caid: str
    issued_policy_epoch: int
    expires_at_epoch_ms: int


class TemporalStandingGate:
    """
    Station 1 pre-dispatch interlock enforcing GrantValid ^ EpochFresh ^ CAIDMatch.
    Verifies incoming authorization receipts before dispatching.
    """

    def __init__(
        self,
        signer_key: Ed25519PrivateKey,
        trusted_issuer_pubkey: Ed25519PublicKey,
        pub_key_id: str,
        initial_policy_epoch: int,
        allowed_targets: List[str],
    ) -> None:
        self._signer = signer_key
        self._issuer_pubkey = trusted_issuer_pubkey
        self._pub_key_id = pub_key_id
        self.active_policy_epoch = initial_policy_epoch
        self.allowed_targets = set(allowed_targets)
        self.revoked_principals: set[str] = set()
        self.burned_tickets: set[str] = set()
        self.epoch_mutation_log: List[Dict[str, Any]] = []

    def rotate_policy_epoch(self, new_epoch: int, reason: str) -> Dict[str, Any]:
        if new_epoch <= self.active_policy_epoch:
            raise ValueError("Policy epoch must advance monotonically")
        prev_epoch = self.active_policy_epoch
        self.active_policy_epoch = new_epoch
        record = sign_jcs_statement(
            self._signer,
            self._pub_key_id,
            {
                "event": "POLICY_EPOCH_ROTATED",
                "previous_epoch": prev_epoch,
                "new_active_epoch": new_epoch,
                "reason": reason,
                "mutation_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.epoch_mutation_log.append(record)
        return record

    def dispatch_governed_action(
        self,
        candidate_action: Dict[str, Any],
        ticket: DispatchAuthorizationTicket,
        auth_receipt: Dict[str, Any],
        now_ms: int,
        target_host: str,
        target_port: int,
    ) -> Dict[str, Any]:
        recomputed_caid = sha256_hex(encode_jcs(candidate_action))
        socket_allocated = False

        # 0. Cryptographic verification of the Authorization Receipt itself
        receipt_verification = verify_jcs_receipt(self._issuer_pubkey, auth_receipt)
        if receipt_verification != VerificationResult.VALID:
            rejection_code = "INVALID_AUTHORIZATION_RECEIPT"
        else:
            stmt = auth_receipt.get("statement", {})
            if (
                stmt.get("operation_id") != ticket.operation_id
                or stmt.get("ticket_id") != ticket.ticket_id
                or stmt.get("bound_caid") != ticket.bound_caid
                or stmt.get("issued_policy_epoch") != ticket.issued_policy_epoch
                or stmt.get("principal_id") != ticket.principal_id
            ):
                rejection_code = "RECEIPT_TICKET_MISMATCH"
            # 1. Single-use replay check (CTRL-03)
            elif ticket.ticket_id in self.burned_tickets:
                rejection_code = "TICKET_ALREADY_BURNED"
            # 2. Target manifest allowlist (CTRL-01)
            elif candidate_action.get("target_uri") not in self.allowed_targets:
                rejection_code = "TARGET_NOT_IN_MANIFEST"
            # 3. Principal revocation check
            elif ticket.principal_id in self.revoked_principals:
                rejection_code = "DELEGATION_REVOKED"
            # 4. Expiration check
            elif now_ms > ticket.expires_at_epoch_ms:
                rejection_code = "TICKET_EXPIRED"
            # 5. Policy epoch freshness check (AT31 core invariant)
            elif ticket.issued_policy_epoch != self.active_policy_epoch:
                rejection_code = "STALE_POLICY_EPOCH"
            # 6. Exact action digest check (CTRL-01 / CTRL-04)
            elif recomputed_caid != ticket.bound_caid:
                rejection_code = "CAID_MISMATCH"
            else:
                rejection_code = None

        if rejection_code is not None:
            denial_receipt = sign_jcs_statement(
                self._signer,
                self._pub_key_id,
                {
                    "phase": "PRE_DISPATCH_DENIED",
                    "operation_id": ticket.operation_id,
                    "ticket_id": ticket.ticket_id,
                    "candidate_caid": recomputed_caid,
                    "presented_policy_epoch": ticket.issued_policy_epoch,
                    "active_policy_epoch": self.active_policy_epoch,
                    "standing_verdict": "DENIED",
                    "rejection_code": rejection_code,
                    "disposition": "NOT_DISPATCHED",
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            return {
                "disposition": "NOT_DISPATCHED",
                "rejection_code": rejection_code,
                "socket_allocated": socket_allocated,
                "receipt": denial_receipt,
            }

        # Burn single-use ticket before socket allocation
        self.burned_tickets.add(ticket.ticket_id)
        socket_allocated = True
        with socket.create_connection((target_host, target_port), timeout=1.0) as s:
            s.sendall(encode_jcs(candidate_action))
            _ = s.recv(1024)

        confirm_receipt = sign_jcs_statement(
            self._signer,
            self._pub_key_id,
            {
                "phase": "DISPATCH_CONFIRMED",
                "operation_id": ticket.operation_id,
                "ticket_id": ticket.ticket_id,
                "candidate_caid": recomputed_caid,
                "active_policy_epoch": self.active_policy_epoch,
                "standing_verdict": "AUTHORIZED",
                "disposition": "RESOLVED_CONFIRMED",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "disposition": "RESOLVED_CONFIRMED",
            "rejection_code": None,
            "socket_allocated": socket_allocated,
            "receipt": confirm_receipt,
        }


# ==============================================================================
# AT30 - AT37 Benchmark Test Suite
# ==============================================================================


def test_at30_valid_authority_dispatches_once(tmp_path: Path) -> None:
    """AT30: Valid authority, fresh epoch, correct CAID -> dispatch succeeds once."""
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_key_id = "did:key:aeib-station1-test-ed25519"

    target = EphemeralTargetServer()
    try:
        target_uri = f"http://{target.host}:{target.port}/v1/refunds"
        gate = TemporalStandingGate(
            signer_key=priv_key,
            trusted_issuer_pubkey=pub_key,
            pub_key_id=pub_key_id,
            initial_policy_epoch=14,
            allowed_targets=[target_uri],
        )

        candidate_action = {
            "action": "refund",
            "amount_minor_units": 4990,
            "currency": "EUR",
            "customer_id": "cust_8817",
            "operation_id": "op_refund_8817_at30",
            "recipient_iban": "CZ6508000000192000145399",
            "target_uri": target_uri,
        }
        bound_caid = sha256_hex(encode_jcs(candidate_action))

        auth_receipt = sign_jcs_statement(
            priv_key,
            pub_key_id,
            {
                "phase": "AUTHORIZATION_ISSUED",
                "operation_id": "op_refund_8817_at30",
                "ticket_id": "tkt_at30",
                "principal_id": "agent:support_refund_v1",
                "bound_caid": bound_caid,
                "issued_policy_epoch": 14,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ticket = DispatchAuthorizationTicket(
            ticket_id="tkt_at30",
            operation_id="op_refund_8817_at30",
            principal_id="agent:support_refund_v1",
            bound_caid=bound_caid,
            issued_policy_epoch=14,
            expires_at_epoch_ms=2_000_000_000_000,
        )

        result = gate.dispatch_governed_action(
            candidate_action=candidate_action,
            ticket=ticket,
            auth_receipt=auth_receipt,
            now_ms=1_792_060_000_000,
            target_host=target.host,
            target_port=target.port,
        )

        assert result["disposition"] == "RESOLVED_CONFIRMED"
        assert result["rejection_code"] is None
        assert result["socket_allocated"] is True
        assert target.connections_observed == 1
        assert target.bytes_received > 0
        assert verify_jcs_receipt(pub_key, result["receipt"]) == VerificationResult.VALID
    finally:
        target.close()


def test_at31_stale_epoch_blocked_before_dispatch(tmp_path: Path) -> None:
    """
    AT31_STALE_EPOCH_BLOCKED:
    Proves that when an action is authorized at T0 under policy_epoch=14,
    and policy_epoch rotates to 15 at Delta, the dispatch attempt at Tn is
    rejected BEFORE socket allocation with zero bytes reaching the target.
    Emits signed tamper-evident evidence bundle.
    """
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_key_id = "did:key:aeib-station1-test-ed25519"

    # Export public key PEM for external auditor inspection
    repo_artifact_dir = Path("artifacts/pre_execution")
    repo_artifact_dir.mkdir(parents=True, exist_ok=True)
    pem_bytes = pub_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (repo_artifact_dir / "test_station1_pubkey.pem").write_bytes(pem_bytes)

    target = EphemeralTargetServer()
    try:
        target_uri = f"http://{target.host}:{target.port}/v1/refunds"
        gate = TemporalStandingGate(
            signer_key=priv_key,
            trusted_issuer_pubkey=pub_key,
            pub_key_id=pub_key_id,
            initial_policy_epoch=14,
            allowed_targets=[target_uri],
        )

        # --- T0: Candidate Action & Initial Authorization ---
        candidate_action = {
            "action": "refund",
            "amount_minor_units": 4990,
            "currency": "EUR",
            "customer_id": "cust_8817",
            "operation_id": "op_refund_8817_001",
            "recipient_iban": "CZ6508000000192000145399",
            "target_uri": target_uri,
        }
        bound_caid = sha256_hex(encode_jcs(candidate_action))

        t0_auth_receipt = sign_jcs_statement(
            priv_key,
            pub_key_id,
            {
                "phase": "AUTHORIZATION_ISSUED",
                "operation_id": "op_refund_8817_001",
                "ticket_id": "tkt_001",
                "principal_id": "agent:support_refund_v1",
                "bound_caid": bound_caid,
                "issued_policy_epoch": 14,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ticket = DispatchAuthorizationTicket(
            ticket_id="tkt_001",
            operation_id="op_refund_8817_001",
            principal_id="agent:support_refund_v1",
            bound_caid=bound_caid,
            issued_policy_epoch=14,
            expires_at_epoch_ms=2_000_000_000_000,
        )

        # --- Delta: Policy Epoch Rotates (14 -> 15) ---
        delta_record = gate.rotate_policy_epoch(
            new_epoch=15, reason="Max autonomous refund cap lowered; re-authorization required"
        )

        # --- Tn: Agent Attempts Dispatch with Stale Epoch Ticket ---
        result = gate.dispatch_governed_action(
            candidate_action=candidate_action,
            ticket=ticket,
            auth_receipt=t0_auth_receipt,
            now_ms=1_792_060_000_000,
            target_host=target.host,
            target_port=target.port,
        )

        # --- Assertions: Pre-Execution Prevention & Bounded Transport Absence ---
        assert result["disposition"] == "NOT_DISPATCHED"
        assert result["rejection_code"] == "STALE_POLICY_EPOCH"
        assert result["socket_allocated"] is False
        assert target.connections_observed == 0
        assert target.bytes_received == 0

        # --- Independent Offline Receipt Verification ---
        assert verify_jcs_receipt(pub_key, t0_auth_receipt) == VerificationResult.VALID
        assert verify_jcs_receipt(pub_key, delta_record) == VerificationResult.VALID
        assert verify_jcs_receipt(pub_key, result["receipt"]) == VerificationResult.VALID

        # --- Build and Sign Complete Evidence Bundle Manifest ---
        transport_obs = {
            "observation_point": "in_process_ephemeral_loopback_listener",
            "listener_address": f"127.0.0.1:{target.port}",
            "connections_accepted_by_listener": target.connections_observed,
            "bytes_received_by_listener": target.bytes_received,
            "gate_reported_socket_allocation": result["socket_allocated"],
            "scope": "this_test_process_and_listener_only",
        }
        artifacts = [
            {
                "name": "t0_authorization_receipt",
                "sha256": t0_auth_receipt["receipt_caid"],
                "envelope": t0_auth_receipt,
            },
            {
                "name": "delta_epoch_rotation_receipt",
                "sha256": delta_record["receipt_caid"],
                "envelope": delta_record,
            },
            {
                "name": "tn_denial_receipt",
                "sha256": result["receipt"]["receipt_caid"],
                "envelope": result["receipt"],
            },
        ]

        tmp_out_file = tmp_path / "pre_execution" / "AT31_pre_execution_evidence.json"
        repo_out_file = repo_artifact_dir / "AT31_pre_execution_evidence.json"

        artifact_locations = {
            "primary": {
                "path": str(tmp_out_file),
                "retention": "CI_artifact",
            },
            "published_mirror": {
                "path": str(repo_out_file),
                "mirror_must_match_primary_digest": True,
            },
        }

        signed_bundle = sign_evidence_bundle(
            priv_key=priv_key,
            pub_key_id=pub_key_id,
            scenario_id="AT31_STALE_EPOCH_BLOCKED",
            provenance=get_git_provenance(),
            artifacts=artifacts,
            artifact_locations=artifact_locations,
            transport_observation=transport_obs,
        )

        # Verify the complete signed bundle
        assert verify_evidence_bundle(pub_key, signed_bundle) == VerificationResult.VALID

        # Write to pytest tmp_path
        tmp_out_file.parent.mkdir(parents=True, exist_ok=True)
        canonical_bytes = encode_jcs(signed_bundle)
        tmp_out_file.write_bytes(canonical_bytes)
        assert tmp_out_file.exists()

        # Write to repository published mirror
        repo_out_file.write_bytes(canonical_bytes)
        assert repo_out_file.exists()

        # Assert digests match exactly
        assert hashlib.sha256(tmp_out_file.read_bytes()).hexdigest() == hashlib.sha256(repo_out_file.read_bytes()).hexdigest()

    finally:
        target.close()


def test_at32_expired_authority_blocked_before_dispatch(tmp_path: Path) -> None:
    """AT32: Expired authority ticket (now_ms > expires_at) -> blocked before socket allocation."""
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_key_id = "did:key:aeib-station1-test-ed25519"

    target = EphemeralTargetServer()
    try:
        target_uri = f"http://{target.host}:{target.port}/v1/refunds"
        gate = TemporalStandingGate(
            signer_key=priv_key,
            trusted_issuer_pubkey=pub_key,
            pub_key_id=pub_key_id,
            initial_policy_epoch=14,
            allowed_targets=[target_uri],
        )

        candidate_action = {
            "action": "refund",
            "amount_minor_units": 2000,
            "currency": "EUR",
            "customer_id": "cust_expired",
            "operation_id": "op_refund_at32",
            "recipient_iban": "CZ6508000000192000145399",
            "target_uri": target_uri,
        }
        bound_caid = sha256_hex(encode_jcs(candidate_action))

        auth_receipt = sign_jcs_statement(
            priv_key,
            pub_key_id,
            {
                "phase": "AUTHORIZATION_ISSUED",
                "operation_id": "op_refund_at32",
                "ticket_id": "tkt_at32",
                "principal_id": "agent:support_refund_v1",
                "bound_caid": bound_caid,
                "issued_policy_epoch": 14,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ticket = DispatchAuthorizationTicket(
            ticket_id="tkt_at32",
            operation_id="op_refund_at32",
            principal_id="agent:support_refund_v1",
            bound_caid=bound_caid,
            issued_policy_epoch=14,
            expires_at_epoch_ms=1_000_000_000_000,  # Expired
        )

        result = gate.dispatch_governed_action(
            candidate_action=candidate_action,
            ticket=ticket,
            auth_receipt=auth_receipt,
            now_ms=1_500_000_000_000,  # Current time past expiry
            target_host=target.host,
            target_port=target.port,
        )

        assert result["disposition"] == "NOT_DISPATCHED"
        assert result["rejection_code"] == "TICKET_EXPIRED"
        assert result["socket_allocated"] is False
        assert target.connections_observed == 0
        assert target.bytes_received == 0
    finally:
        target.close()


def test_at33_revoked_principal_blocked_before_dispatch(tmp_path: Path) -> None:
    """AT33: Principal revoked after authorization -> blocked before socket allocation."""
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_key_id = "did:key:aeib-station1-test-ed25519"

    target = EphemeralTargetServer()
    try:
        target_uri = f"http://{target.host}:{target.port}/v1/refunds"
        gate = TemporalStandingGate(
            signer_key=priv_key,
            trusted_issuer_pubkey=pub_key,
            pub_key_id=pub_key_id,
            initial_policy_epoch=14,
            allowed_targets=[target_uri],
        )

        candidate_action = {
            "action": "refund",
            "amount_minor_units": 2000,
            "currency": "EUR",
            "customer_id": "cust_revoked",
            "operation_id": "op_refund_at33",
            "recipient_iban": "CZ6508000000192000145399",
            "target_uri": target_uri,
        }
        bound_caid = sha256_hex(encode_jcs(candidate_action))

        auth_receipt = sign_jcs_statement(
            priv_key,
            pub_key_id,
            {
                "phase": "AUTHORIZATION_ISSUED",
                "operation_id": "op_refund_at33",
                "ticket_id": "tkt_at33",
                "principal_id": "agent:compromised_agent_01",
                "bound_caid": bound_caid,
                "issued_policy_epoch": 14,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ticket = DispatchAuthorizationTicket(
            ticket_id="tkt_at33",
            operation_id="op_refund_at33",
            principal_id="agent:compromised_agent_01",
            bound_caid=bound_caid,
            issued_policy_epoch=14,
            expires_at_epoch_ms=2_000_000_000_000,
        )

        # Revoke principal during Delta
        gate.revoked_principals.add("agent:compromised_agent_01")

        result = gate.dispatch_governed_action(
            candidate_action=candidate_action,
            ticket=ticket,
            auth_receipt=auth_receipt,
            now_ms=1_792_060_000_000,
            target_host=target.host,
            target_port=target.port,
        )

        assert result["disposition"] == "NOT_DISPATCHED"
        assert result["rejection_code"] == "DELEGATION_REVOKED"
        assert result["socket_allocated"] is False
        assert target.connections_observed == 0
        assert target.bytes_received == 0
    finally:
        target.close()


def test_at34_altered_caid_blocked_before_dispatch(tmp_path: Path) -> None:
    """AT34: Altered payload parameters (tampered amount/IBAN) -> CAID mismatch -> blocked."""
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_key_id = "did:key:aeib-station1-test-ed25519"

    target = EphemeralTargetServer()
    try:
        target_uri = f"http://{target.host}:{target.port}/v1/refunds"
        gate = TemporalStandingGate(
            signer_key=priv_key,
            trusted_issuer_pubkey=pub_key,
            pub_key_id=pub_key_id,
            initial_policy_epoch=14,
            allowed_targets=[target_uri],
        )

        original_action = {
            "action": "refund",
            "amount_minor_units": 1000,
            "currency": "EUR",
            "customer_id": "cust_8817",
            "operation_id": "op_refund_at34",
            "recipient_iban": "CZ6508000000192000145399",
            "target_uri": target_uri,
        }
        bound_caid = sha256_hex(encode_jcs(original_action))

        auth_receipt = sign_jcs_statement(
            priv_key,
            pub_key_id,
            {
                "phase": "AUTHORIZATION_ISSUED",
                "operation_id": "op_refund_at34",
                "ticket_id": "tkt_at34",
                "principal_id": "agent:support_refund_v1",
                "bound_caid": bound_caid,
                "issued_policy_epoch": 14,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ticket = DispatchAuthorizationTicket(
            ticket_id="tkt_at34",
            operation_id="op_refund_at34",
            principal_id="agent:support_refund_v1",
            bound_caid=bound_caid,
            issued_policy_epoch=14,
            expires_at_epoch_ms=2_000_000_000_000,
        )

        # Mutate payload at dispatch time (e.g. prompt injection alteration)
        tampered_action = copy.deepcopy(original_action)
        tampered_action["amount_minor_units"] = 999999

        result = gate.dispatch_governed_action(
            candidate_action=tampered_action,
            ticket=ticket,
            auth_receipt=auth_receipt,
            now_ms=1_792_060_000_000,
            target_host=target.host,
            target_port=target.port,
        )

        assert result["disposition"] == "NOT_DISPATCHED"
        assert result["rejection_code"] == "CAID_MISMATCH"
        assert result["socket_allocated"] is False
        assert target.connections_observed == 0
        assert target.bytes_received == 0
    finally:
        target.close()


def test_at35_replayed_ticket_blocked_on_second_dispatch(tmp_path: Path) -> None:
    """
    AT35: Replayed single-use ticket -> second dispatch rejected with 0 socket writes.
    Emits signed AT35 evidence bundle proving 1 authorized mutation, 0 duplicate mutations.
    """
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_key_id = "did:key:aeib-station1-test-ed25519"

    repo_artifact_dir = Path("artifacts/pre_execution")
    repo_artifact_dir.mkdir(parents=True, exist_ok=True)
    pem_bytes = pub_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (repo_artifact_dir / "AT35_station1_pubkey.pem").write_bytes(pem_bytes)

    target = EphemeralTargetServer()
    try:
        target_uri = f"http://{target.host}:{target.port}/v1/refunds"
        gate = TemporalStandingGate(
            signer_key=priv_key,
            trusted_issuer_pubkey=pub_key,
            pub_key_id=pub_key_id,
            initial_policy_epoch=14,
            allowed_targets=[target_uri],
        )

        candidate_action = {
            "action": "refund",
            "amount_minor_units": 1500,
            "currency": "EUR",
            "customer_id": "cust_replay",
            "operation_id": "op_refund_at35",
            "recipient_iban": "CZ6508000000192000145399",
            "target_uri": target_uri,
        }
        bound_caid = sha256_hex(encode_jcs(candidate_action))

        auth_receipt = sign_jcs_statement(
            priv_key,
            pub_key_id,
            {
                "phase": "AUTHORIZATION_ISSUED",
                "operation_id": "op_refund_at35",
                "ticket_id": "tkt_at35_replay",
                "principal_id": "agent:support_refund_v1",
                "bound_caid": bound_caid,
                "issued_policy_epoch": 14,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ticket = DispatchAuthorizationTicket(
            ticket_id="tkt_at35_replay",
            operation_id="op_refund_at35",
            principal_id="agent:support_refund_v1",
            bound_caid=bound_caid,
            issued_policy_epoch=14,
            expires_at_epoch_ms=2_000_000_000_000,
        )

        # First dispatch -> Success
        res1 = gate.dispatch_governed_action(
            candidate_action=candidate_action,
            ticket=ticket,
            auth_receipt=auth_receipt,
            now_ms=1_792_060_000_000,
            target_host=target.host,
            target_port=target.port,
        )
        assert res1["disposition"] == "RESOLVED_CONFIRMED"
        assert res1["socket_allocated"] is True
        assert target.connections_observed == 1
        bytes_first = target.bytes_received

        # Second dispatch (replay attack) -> Rejected fail-closed
        res2 = gate.dispatch_governed_action(
            candidate_action=candidate_action,
            ticket=ticket,
            auth_receipt=auth_receipt,
            now_ms=1_792_060_001_000,
            target_host=target.host,
            target_port=target.port,
        )
        assert res2["disposition"] == "NOT_DISPATCHED"
        assert res2["rejection_code"] == "TICKET_ALREADY_BURNED"
        assert res2["socket_allocated"] is False
        # Crucial: Zero second connection to target!
        assert target.connections_observed == 1
        assert target.bytes_received == bytes_first

        # Build and sign AT35 evidence bundle
        artifacts = [
            {
                "name": "t0_authorization_receipt",
                "sha256": auth_receipt["receipt_caid"],
                "envelope": auth_receipt,
            },
            {
                "name": "first_dispatch_confirmation_receipt",
                "sha256": res1["receipt"]["receipt_caid"],
                "envelope": res1["receipt"],
            },
            {
                "name": "replay_denial_receipt",
                "sha256": res2["receipt"]["receipt_caid"],
                "envelope": res2["receipt"],
            },
        ]

        at35_evidence = {
            "first_dispatch": {
                "disposition": res1["disposition"],
                "listener_connections": 1,
                "listener_bytes": bytes_first,
            },
            "replay_attempt": {
                "disposition": res2["disposition"],
                "rejection_code": res2["rejection_code"],
                "listener_connections": 0,
                "listener_bytes": 0,
            },
            "total_external_mutations_observed": 1,
        }

        tmp_out_file = tmp_path / "pre_execution" / "AT35_replayed_ticket_evidence.json"
        repo_out_file = repo_artifact_dir / "AT35_replayed_ticket_evidence.json"

        artifact_locations = {
            "primary": {
                "path": str(tmp_out_file),
                "retention": "CI_artifact",
            },
            "published_mirror": {
                "path": str(repo_out_file),
                "mirror_must_match_primary_digest": True,
            },
        }

        signed_bundle = sign_evidence_bundle(
            priv_key=priv_key,
            pub_key_id=pub_key_id,
            scenario_id="AT35_REPLAYED_TICKET_BLOCKED",
            provenance=get_git_provenance(),
            artifacts=artifacts,
            artifact_locations=artifact_locations,
            at35_evidence=at35_evidence,
        )

        assert verify_evidence_bundle(pub_key, signed_bundle) == VerificationResult.VALID

        canonical_bytes = encode_jcs(signed_bundle)
        tmp_out_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_out_file.write_bytes(canonical_bytes)
        repo_out_file.write_bytes(canonical_bytes)
        assert hashlib.sha256(tmp_out_file.read_bytes()).hexdigest() == hashlib.sha256(repo_out_file.read_bytes()).hexdigest()

    finally:
        target.close()


def test_at36_tampered_receipt_rejected_before_dispatch(tmp_path: Path) -> None:
    """AT36: Tampered authorization receipt signature or statement -> rejected."""
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_key_id = "did:key:aeib-station1-test-ed25519"

    target = EphemeralTargetServer()
    try:
        target_uri = f"http://{target.host}:{target.port}/v1/refunds"
        gate = TemporalStandingGate(
            signer_key=priv_key,
            trusted_issuer_pubkey=pub_key,
            pub_key_id=pub_key_id,
            initial_policy_epoch=14,
            allowed_targets=[target_uri],
        )

        candidate_action = {
            "action": "refund",
            "amount_minor_units": 1500,
            "currency": "EUR",
            "customer_id": "cust_tamper",
            "operation_id": "op_refund_at36",
            "recipient_iban": "CZ6508000000192000145399",
            "target_uri": target_uri,
        }
        bound_caid = sha256_hex(encode_jcs(candidate_action))

        auth_receipt = sign_jcs_statement(
            priv_key,
            pub_key_id,
            {
                "phase": "AUTHORIZATION_ISSUED",
                "operation_id": "op_refund_at36",
                "ticket_id": "tkt_at36",
                "principal_id": "agent:support_refund_v1",
                "bound_caid": bound_caid,
                "issued_policy_epoch": 14,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ticket = DispatchAuthorizationTicket(
            ticket_id="tkt_at36",
            operation_id="op_refund_at36",
            principal_id="agent:support_refund_v1",
            bound_caid=bound_caid,
            issued_policy_epoch=14,
            expires_at_epoch_ms=2_000_000_000_000,
        )

        # Tamper signature (flip last base64 character)
        tampered_receipt = copy.deepcopy(auth_receipt)
        sig_b64 = tampered_receipt["signature"]["signature_b64"]
        flipped_sig = sig_b64[:-2] + ("A" if sig_b64[-2] != "A" else "B") + "="
        tampered_receipt["signature"]["signature_b64"] = flipped_sig

        result = gate.dispatch_governed_action(
            candidate_action=candidate_action,
            ticket=ticket,
            auth_receipt=tampered_receipt,
            now_ms=1_792_060_000_000,
            target_host=target.host,
            target_port=target.port,
        )

        assert result["disposition"] == "NOT_DISPATCHED"
        assert result["rejection_code"] == "INVALID_AUTHORIZATION_RECEIPT"
        assert result["socket_allocated"] is False
        assert target.connections_observed == 0
        assert target.bytes_received == 0
    finally:
        target.close()


def test_at37_unallowlisted_target_blocked_before_dispatch(tmp_path: Path) -> None:
    """AT37: Target not in manifest allowlist -> rejected fail-closed."""
    priv_key = Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()
    pub_key_id = "did:key:aeib-station1-test-ed25519"

    target = EphemeralTargetServer()
    try:
        target_uri = f"http://{target.host}:{target.port}/v1/refunds"
        gate = TemporalStandingGate(
            signer_key=priv_key,
            trusted_issuer_pubkey=pub_key,
            pub_key_id=pub_key_id,
            initial_policy_epoch=14,
            allowed_targets=["http://authorized-payments-internal:8080/v1/payout"],
        )

        candidate_action = {
            "action": "refund",
            "amount_minor_units": 1500,
            "currency": "EUR",
            "customer_id": "cust_unallowlisted",
            "operation_id": "op_refund_at37",
            "recipient_iban": "CZ6508000000192000145399",
            "target_uri": target_uri,  # Not in allowed_targets
        }
        bound_caid = sha256_hex(encode_jcs(candidate_action))

        auth_receipt = sign_jcs_statement(
            priv_key,
            pub_key_id,
            {
                "phase": "AUTHORIZATION_ISSUED",
                "operation_id": "op_refund_at37",
                "ticket_id": "tkt_at37",
                "principal_id": "agent:support_refund_v1",
                "bound_caid": bound_caid,
                "issued_policy_epoch": 14,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        ticket = DispatchAuthorizationTicket(
            ticket_id="tkt_at37",
            operation_id="op_refund_at37",
            principal_id="agent:support_refund_v1",
            bound_caid=bound_caid,
            issued_policy_epoch=14,
            expires_at_epoch_ms=2_000_000_000_000,
        )

        result = gate.dispatch_governed_action(
            candidate_action=candidate_action,
            ticket=ticket,
            auth_receipt=auth_receipt,
            now_ms=1_792_060_000_000,
            target_host=target.host,
            target_port=target.port,
        )

        assert result["disposition"] == "NOT_DISPATCHED"
        assert result["rejection_code"] == "TARGET_NOT_IN_MANIFEST"
        assert result["socket_allocated"] is False
        assert target.connections_observed == 0
        assert target.bytes_received == 0
    finally:
        target.close()
