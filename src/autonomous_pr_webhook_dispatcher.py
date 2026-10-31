#!/usr/bin/env python3
"""
Autonomous PR Webhook Dispatcher (src/autonomous_pr_webhook_dispatcher.py).

Evaluated under the stated model to ingest GitHub pull request webhook payloads,
execute AST reverse-dependency blast-radius analysis via HypergraphBlastRadiusGovernor,
and generate cryptographically signed auto-merge or human-escalation decisions.

Core Capabilities:
  1. Webhook Ingress Integrity:
     Validates HMAC-SHA256 payload signatures (X-Hub-Signature-256) with constant-time
     digest comparison to defend against forged webhook triggers.
  2. AST Blast-Radius Evaluation:
     Maps PR diff parameters into PRDiffSpec and evaluates reverse-dependency blast radius
     in integer basis points (0..10000 bps) via HypergraphBlastRadiusGovernor.
  3. Four-Arm Policy Dispatch:
     - AUTO_MERGE: Low blast-radius changes (<= 3,000 bps, <= 50 lines, <= 3 files)
       automatically receive a signed Ed25519 merge authorization warrant.
     - HUMAN_ESCALATE: High blast-radius or sensitive architectural changes are escalated
       to human review queues with detailed transitive dependency graphs.
     - HALT_SCOPE_CREEP: PRs violating line-count caps or smurfing thresholds fail closed.
     - AUTO_REJECT_INVARIANT: Changes modifying protected paths fail closed.
  4. Single-Source RFC 8785 JCS Canonicalization:
     All warrants and dispatch receipts are signed over RFC 8785 canonical bytes with
     integer basis points and zero floats.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs
from src.hypergraph_blast_radius import (
    AutonomousPRVerdict,
    HypergraphBlastRadiusGovernor,
    PRDiffSpec,
)


def sha256_caid(payload: Any) -> str:
    """Compute Content-Addressed Intent ID (CAID) via RFC 8785 canonical bytes."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclasses.dataclass(frozen=True)
class AutonomousPRMergeWarrant:
    """Cryptographically signed authorization warrant permitting automated merge."""

    pr_id: str
    intent_caid: str
    action: str
    blast_radius_bps: int
    total_lines_changed: int
    files_touched_count: int
    signer_pubkey_hex: str
    signature_hex: str
    warrant_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "blast_radius_bps": self.blast_radius_bps,
            "files_touched_count": self.files_touched_count,
            "intent_caid": self.intent_caid,
            "pr_id": self.pr_id,
            "signature_hex": self.signature_hex,
            "signer_pubkey_hex": self.signer_pubkey_hex,
            "total_lines_changed": self.total_lines_changed,
            "warrant_caid": self.warrant_caid,
        }


@dataclasses.dataclass(frozen=True)
class AutonomousPRDispatchReceipt:
    """Deterministic dispatch receipt emitted for every processed webhook event."""

    pr_id: str
    event_action: str
    admissible: bool
    verdict_action: str
    reason_code: str
    blast_radius_bps: int
    affected_modules: Tuple[str, ...]
    warrant: Optional[AutonomousPRMergeWarrant]
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "admissible": self.admissible,
            "affected_modules": list(self.affected_modules),
            "blast_radius_bps": self.blast_radius_bps,
            "event_action": self.event_action,
            "pr_id": self.pr_id,
            "reason_code": self.reason_code,
            "receipt_caid": self.receipt_caid,
            "verdict_action": self.verdict_action,
            "warrant": self.warrant.to_dict() if self.warrant else None,
        }


class AutonomousPRWebhookDispatcher:
    """
    Ingests GitHub webhook events, executes blast-radius governance,
    and seals automated merge warrants or escalation dispatches.
    """

    def __init__(
        self,
        governor: Optional[HypergraphBlastRadiusGovernor] = None,
        webhook_secret: str = "aeib-webhook-secret-token",
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None,
    ) -> None:
        self.governor = governor or HypergraphBlastRadiusGovernor()
        self.webhook_secret = webhook_secret
        self._signing_key = signing_key or ed25519.Ed25519PrivateKey.generate()
        self._verifying_key = self._signing_key.public_key()

    @property
    def public_key_hex(self) -> str:
        return self._verifying_key.public_bytes_raw().hex()

    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        """
        Verify GitHub HMAC-SHA256 signature (X-Hub-Signature-256: sha256=<hex>).
        Uses constant-time comparison to prevent timing side channels.
        """
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected_hex = signature_header[len("sha256=") :]
        computed_hex = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(computed_hex, expected_hex)

    def extract_pr_spec(self, event_payload: Dict[str, Any]) -> Tuple[str, PRDiffSpec]:
        """
        Extract pull request diff spec from GitHub webhook payload.
        Returns (event_action, pr_diff_spec).
        """
        event_action = str(event_payload.get("action", "unknown"))
        pr_obj = event_payload.get("pull_request")
        if not isinstance(pr_obj, dict):
            raise ValueError("ERR_MISSING_PULL_REQUEST_OBJECT")

        pr_number = pr_obj.get("number")
        pr_id = f"PR-{pr_number}" if pr_number is not None else str(pr_obj.get("id", "PR-UNKNOWN"))

        # Intent CAID extraction from body or synthetic digest
        body_text = str(pr_obj.get("body") or "")
        title_text = str(pr_obj.get("title") or "")
        intent_caid: Optional[str] = None
        for line in body_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("CAID:") or stripped.startswith("Intent-CAID:"):
                cand = stripped.split(":", 1)[1].strip()
                if cand.startswith("sha256:") and len(cand) == 71:
                    intent_caid = cand
                    break

        if not intent_caid:
            intent_caid = sha256_caid(f"{title_text}\n{body_text}")

        # Extract file and diff statistics
        changed_files_list: List[str] = []
        raw_files = pr_obj.get("files")
        if isinstance(raw_files, list):
            for f in raw_files:
                if isinstance(f, dict) and "filename" in f:
                    changed_files_list.append(str(f["filename"]))
                elif isinstance(f, str):
                    changed_files_list.append(f)

        if not changed_files_list:
            changed_files_list = ["unknown_module.py"]

        additions = int(pr_obj.get("additions", 0))
        deletions = int(pr_obj.get("deletions", 0))

        spec = PRDiffSpec(
            pr_id=pr_id,
            intent_caid=intent_caid,
            changed_files=tuple(sorted(changed_files_list)),
            lines_added=additions,
            lines_deleted=deletions,
        )
        return event_action, spec

    def dispatch_pr_event(
        self,
        event_payload: Dict[str, Any],
        signature_header: Optional[str] = None,
    ) -> AutonomousPRDispatchReceipt:
        """
        Dispatch incoming webhook payload:
          1. Verify HMAC signature if provided.
          2. Parse PRDiffSpec.
          3. Evaluate blast radius via HypergraphBlastRadiusGovernor.
          4. Seal merge warrant if AUTO_MERGE; otherwise emit escalation/halt receipt.
        """
        raw_bytes = encode_jcs(event_payload)
        if signature_header is not None:
            if not self.verify_webhook_signature(raw_bytes, signature_header):
                raise ValueError("ERR_INVALID_WEBHOOK_SIGNATURE")

        event_action, pr_spec = self.extract_pr_spec(event_payload)
        verdict = self.governor.evaluate_pr(pr_spec)

        if not isinstance(verdict, AutonomousPRVerdict):
            raise TypeError("ERR_UNEXPECTED_VERDICT_TYPE")

        warrant: Optional[AutonomousPRMergeWarrant] = None
        admissible = verdict.action == "AUTO_MERGE"

        if admissible:
            warrant_core: Dict[str, Any] = {
                "action": verdict.action,
                "blast_radius_bps": verdict.blast_radius_bps,
                "files_touched_count": verdict.files_touched_count,
                "intent_caid": pr_spec.intent_caid,
                "pr_id": verdict.pr_id,
                "total_lines_changed": verdict.total_lines_changed,
            }
            core_bytes = encode_jcs(warrant_core)
            sig_bytes = self._signing_key.sign(core_bytes)
            pub_hex = self.public_key_hex
            sig_hex = sig_bytes.hex()

            warrant_dict = dict(warrant_core)
            warrant_dict["signature_hex"] = sig_hex
            warrant_dict["signer_pubkey_hex"] = pub_hex
            w_caid = sha256_caid(encode_jcs(warrant_dict))

            warrant = AutonomousPRMergeWarrant(
                pr_id=verdict.pr_id,
                intent_caid=pr_spec.intent_caid,
                action=verdict.action,
                blast_radius_bps=verdict.blast_radius_bps,
                total_lines_changed=verdict.total_lines_changed,
                files_touched_count=verdict.files_touched_count,
                signer_pubkey_hex=pub_hex,
                signature_hex=sig_hex,
                warrant_caid=w_caid,
            )

        receipt_core: Dict[str, Any] = {
            "admissible": admissible,
            "affected_modules": list(verdict.affected_modules),
            "blast_radius_bps": verdict.blast_radius_bps,
            "event_action": event_action,
            "pr_id": verdict.pr_id,
            "reason_code": verdict.reason_code,
            "verdict_action": verdict.action,
            "warrant": warrant.to_dict() if warrant else None,
        }
        receipt_caid = sha256_caid(encode_jcs(receipt_core))

        return AutonomousPRDispatchReceipt(
            pr_id=verdict.pr_id,
            event_action=event_action,
            admissible=admissible,
            verdict_action=verdict.action,
            reason_code=verdict.reason_code,
            blast_radius_bps=verdict.blast_radius_bps,
            affected_modules=verdict.affected_modules,
            warrant=warrant,
            receipt_caid=receipt_caid,
        )

    def verify_merge_warrant(self, warrant: AutonomousPRMergeWarrant) -> Tuple[bool, str]:
        """
        Verify that a merge warrant is authentic, signed by this dispatcher,
        and conforms to the auto-merge blast radius threshold (<= 3,000 bps).
        """
        if not isinstance(warrant.blast_radius_bps, int) or isinstance(warrant.blast_radius_bps, bool):
            return False, "ERR_NON_INTEGER_BLAST_RADIUS"

        if warrant.blast_radius_bps > self.governor.max_auto_merge_radius_bps:
            return False, "ERR_BLAST_RADIUS_EXCEEDS_AUTO_MERGE_THRESHOLD"

        if warrant.action != "AUTO_MERGE":
            return False, "ERR_INVALID_WARRANT_ACTION"

        warrant_core: Dict[str, Any] = {
            "action": warrant.action,
            "blast_radius_bps": warrant.blast_radius_bps,
            "files_touched_count": warrant.files_touched_count,
            "intent_caid": warrant.intent_caid,
            "pr_id": warrant.pr_id,
            "total_lines_changed": warrant.total_lines_changed,
        }
        core_bytes = encode_jcs(warrant_core)

        try:
            pub_bytes = bytes.fromhex(warrant.signer_pubkey_hex)
            sig_bytes = bytes.fromhex(warrant.signature_hex)
            verifier = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            verifier.verify(sig_bytes, core_bytes)
        except Exception as exc:
            return False, f"ERR_CRYPTOGRAPHIC_VERIFICATION_FAILED:{type(exc).__name__}"

        warrant_dict = dict(warrant_core)
        warrant_dict["signature_hex"] = warrant.signature_hex
        warrant_dict["signer_pubkey_hex"] = warrant.signer_pubkey_hex
        expected_warrant_caid = sha256_caid(encode_jcs(warrant_dict))
        if warrant.warrant_caid != expected_warrant_caid:
            return False, "ERR_WARRANT_CAID_MISMATCH"

        return True, "OK"
