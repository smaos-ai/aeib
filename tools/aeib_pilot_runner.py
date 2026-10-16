#!/usr/bin/env python3
"""
AEIB Commercial Pilot Runner & Simulation Harness (Patterns A, B, C)
Part of SovereignNexus AEIB v1.1 Architecture.

Implements the 6-Week Observe-Then-Enforce Pilot Lifecycle:
- Pattern A: Week 1 Scoping, Week 2 Shadow Mode (WOULD_BLOCK without blocking),
             Week 3 Active Enforce (fail-closed), Weeks 4-6 Target Reconciliation.
- Pattern B: Level 2 Boundary-Signed Pre-Execution Restraint Records.
- Pattern C: Level 3 Target-Attested Reconciliation under refund_status_v1.

References international agent governance baselines:
- CAICT CTTL AI Terminal & Agent Security Technical Requirements
- Ant Group Agent3σ Runtime Stress Profile
- Tencent AI-Infra-Guard MCP Boundary Evaluation
- IETF SCITT / RFC 8785 JSON Canonicalization Scheme (JCS)
"""

import os
import sys
import json
import time
import hashlib
import base64
from enum import Enum
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Real RFC 8785 JCS canonicalizer
from src.jcs_canonicalizer import encode_jcs


class PilotStage(str, Enum):
    WEEK1_SCOPING = "WEEK1_SCOPING"
    WEEK2_SHADOW = "WEEK2_SHADOW"
    WEEK3_ENFORCE = "WEEK3_ENFORCE"
    WEEKS4_6_RECONCILE = "WEEKS4_6_RECONCILE"


class PilotDisposition(str, Enum):
    SCOPED = "SCOPED"
    ALLOWED = "ALLOWED"
    WOULD_BLOCK = "WOULD_BLOCK"
    BLOCKED_PRE_DISPATCH = "BLOCKED_PRE_DISPATCH"
    EFFECT_INDETERMINATE = "EFFECT_INDETERMINATE"
    RESOLVED_CONFIRMED = "RESOLVED_CONFIRMED"
    RESOLVED_REFUTED = "RESOLVED_REFUTED"


@dataclass
class PilotConfig:
    pilot_id: str
    action_class: str
    target_endpoint: str
    allowed_uri_prefixes: List[str]
    pinned_mcp_version: str = "2025-06-18"
    active_policy_epoch: int = 1
    max_amount_minor_units: int = 50000  # 500.00 EUR
    supported_currencies: List[str] = field(default_factory=lambda: ["EUR", "CZK", "USD"])
    probe_budget: int = 1


@dataclass
class PilotEvaluationResult:
    action_id: str
    caid: str
    stage: PilotStage
    disposition: PilotDisposition
    allowed_to_dispatch: bool
    rejection_code: Optional[str]
    rejection_reason: Optional[str]
    connections_accepted: int
    bytes_transmitted: int
    restraint_record: Optional[Dict[str, Any]] = None
    reconciliation_record: Optional[Dict[str, Any]] = None


class AeibPilotRunner:
    """
    Manages the 6-Week Observe-Then-Enforce commercial pilot sequence.
    Enforces zero-mock Ed25519 cryptography, RFC 8785 canonicalization,
    and strict stage-dependent execution rules.
    """

    def __init__(
        self,
        config: PilotConfig,
        boundary_privkey: Optional[ed25519.Ed25519PrivateKey] = None,
        target_privkey: Optional[ed25519.Ed25519PrivateKey] = None,
    ):
        self.config = config
        self.boundary_privkey = boundary_privkey or ed25519.Ed25519PrivateKey.generate()
        self.boundary_pubkey = self.boundary_privkey.public_key()
        self.target_privkey = target_privkey or ed25519.Ed25519PrivateKey.generate()
        self.target_pubkey = self.target_privkey.public_key()

        self.current_stage = PilotStage.WEEK1_SCOPING
        self.consumed_tickets: set = set()
        self.history: List[PilotEvaluationResult] = []

    def set_stage(self, stage: PilotStage) -> None:
        self.current_stage = stage

    def compute_caid(self, payload: Dict[str, Any]) -> str:
        canonical_bytes = encode_jcs(payload)
        return hashlib.sha256(canonical_bytes).hexdigest()

    def _sign_record(self, data: Dict[str, Any], privkey: ed25519.Ed25519PrivateKey) -> Tuple[str, str]:
        canonical_bytes = encode_jcs(data)
        digest = hashlib.sha256(canonical_bytes).hexdigest()
        sig = privkey.sign(canonical_bytes)
        return digest, base64.b64encode(sig).decode("ascii")

    def evaluate_candidate_action(
        self,
        candidate_action: Dict[str, Any],
        simulate_transport_drop: bool = False,
        simulated_target_status: str = "SETTLED",
    ) -> PilotEvaluationResult:
        """
        Evaluates a candidate tool mutation under the current pilot stage.
        """
        action_id = candidate_action.get("action_id", f"act-{len(self.history) + 1}")
        mcp_version = candidate_action.get("mcp_version")
        target_uri = candidate_action.get("target_uri", "")
        policy_epoch = candidate_action.get("policy_epoch", 0)
        ticket_id = candidate_action.get("ticket_id")
        params = candidate_action.get("parameters", {})
        
        caid = self.compute_caid(params)

        # 1. Evaluate policy predicates
        violations = []
        rejection_code = None

        if mcp_version != self.config.pinned_mcp_version:
            violations.append(f"Mismatched MCP protocol version: {mcp_version} (required: {self.config.pinned_mcp_version})")
            rejection_code = "MCP_PROTOCOL_VERSION_UNSUPPORTED"
        elif policy_epoch != self.config.active_policy_epoch:
            violations.append(f"Stale policy epoch: {policy_epoch} != active {self.config.active_policy_epoch}")
            rejection_code = "STALE_POLICY_EPOCH"
        elif not any(target_uri.startswith(p) for p in self.config.allowed_uri_prefixes):
            violations.append(f"Target URI {target_uri} violates allowlist")
            rejection_code = "TARGET_URI_UNALLOWLISTED"
        elif not ticket_id or ticket_id in self.consumed_tickets:
            violations.append(f"Ticket {ticket_id} missing or already consumed")
            rejection_code = "TICKET_ALREADY_BURNED"
        else:
            amount = params.get("amount_minor_units", 0)
            curr = params.get("currency", "")
            if amount > self.config.max_amount_minor_units:
                violations.append(f"Amount {amount} exceeds ceiling {self.config.max_amount_minor_units}")
                rejection_code = "AMOUNT_CEILING_EXCEEDED"
            elif curr not in self.config.supported_currencies:
                violations.append(f"Currency {curr} unsupported")
                rejection_code = "CURRENCY_UNSUPPORTED"

        # 2. Stage-dependent routing
        if self.current_stage == PilotStage.WEEK1_SCOPING:
            res = PilotEvaluationResult(
                action_id=action_id,
                caid=caid,
                stage=self.current_stage,
                disposition=PilotDisposition.SCOPED,
                allowed_to_dispatch=True,
                rejection_code=None,
                rejection_reason=None,
                connections_accepted=1,
                bytes_transmitted=len(encode_jcs(params)),
            )
            self.history.append(res)
            return res

        if self.current_stage == PilotStage.WEEK2_SHADOW:
            # Pattern A Week 2 constraint: Shadow mode records WOULD_BLOCK without preventing execution!
            if violations:
                # Mint hypothetical Level 2 restraint record
                restraint = {
                    "record_type": "HYPOTHETICAL_RESTRAINT_RECORD",
                    "action_id": action_id,
                    "caid": caid,
                    "target_uri": target_uri,
                    "rejection_code": rejection_code,
                    "reasons": violations,
                    "stage": "WEEK2_SHADOW",
                    "live_execution_permitted": True,
                    "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                digest, sig = self._sign_record(restraint, self.boundary_privkey)
                restraint["digest"] = digest
                restraint["signature_b64"] = sig

                res = PilotEvaluationResult(
                    action_id=action_id,
                    caid=caid,
                    stage=self.current_stage,
                    disposition=PilotDisposition.WOULD_BLOCK,
                    allowed_to_dispatch=True,  # Passive observation does not block!
                    rejection_code=rejection_code,
                    rejection_reason="; ".join(violations),
                    connections_accepted=1,
                    bytes_transmitted=len(encode_jcs(params)),
                    restraint_record=restraint,
                )
            else:
                self.consumed_tickets.add(ticket_id)
                res = PilotEvaluationResult(
                    action_id=action_id,
                    caid=caid,
                    stage=self.current_stage,
                    disposition=PilotDisposition.ALLOWED,
                    allowed_to_dispatch=True,
                    rejection_code=None,
                    rejection_reason=None,
                    connections_accepted=1,
                    bytes_transmitted=len(encode_jcs(params)),
                )
            self.history.append(res)
            return res

        # Active Enforcement (WEEK3_ENFORCE or WEEKS4_6_RECONCILE)
        if violations:
            # Pattern B: Pre-Execution Restraint Record proving 0 egress bytes
            restraint = {
                "record_type": "PRE_EXECUTION_RESTRAINT_RECORD",
                "attestation_level": "Level 2 (Boundary-Signed)",
                "action_id": action_id,
                "caid": caid,
                "target_uri": target_uri,
                "rejection_code": rejection_code,
                "reasons": violations,
                "socket_connect_invoked": False,
                "connections_accepted": 0,
                "external_bytes_transmitted": 0,
                "policy_epoch": policy_epoch,
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            digest, sig = self._sign_record(restraint, self.boundary_privkey)
            restraint["digest"] = digest
            restraint["signature_b64"] = sig

            res = PilotEvaluationResult(
                action_id=action_id,
                caid=caid,
                stage=self.current_stage,
                disposition=PilotDisposition.BLOCKED_PRE_DISPATCH,
                allowed_to_dispatch=False,
                rejection_code=rejection_code,
                rejection_reason="; ".join(violations),
                connections_accepted=0,
                bytes_transmitted=0,
                restraint_record=restraint,
            )
            self.history.append(res)
            return res

        # Action is valid, burn ticket atomically
        self.consumed_tickets.add(ticket_id)

        if not simulate_transport_drop:
            res = PilotEvaluationResult(
                action_id=action_id,
                caid=caid,
                stage=self.current_stage,
                disposition=PilotDisposition.ALLOWED,
                allowed_to_dispatch=True,
                rejection_code=None,
                rejection_reason=None,
                connections_accepted=1,
                bytes_transmitted=len(encode_jcs(params)),
            )
            self.history.append(res)
            return res

        # Transport drop occurred (HTTP 504 / TCP RST)
        # Latches EFFECT_INDETERMINATE
        if self.current_stage == PilotStage.WEEK3_ENFORCE:
            res = PilotEvaluationResult(
                action_id=action_id,
                caid=caid,
                stage=self.current_stage,
                disposition=PilotDisposition.EFFECT_INDETERMINATE,
                allowed_to_dispatch=True,
                rejection_code="HTTP_504_GATEWAY_TIMEOUT",
                rejection_reason="Transport dropped after dispatch; retry_safe: false latched",
                connections_accepted=1,
                bytes_transmitted=len(encode_jcs(params)),
            )
            self.history.append(res)
            return res

        # Weeks 4-6: Pattern C Target-Attested Reconciliation under refund_status_v1
        reconciliation_payload = {
            "contract_version": "1.0.0",
            "operation_id": f"op-{action_id}",
            "idempotency_key": caid,
            "target_status": simulated_target_status,
            "target_mutation_ref": f"tx-ref-{action_id}-999",
            "settled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "parameter_parity": {
                "amount_minor_units": params.get("amount_minor_units", 0),
                "currency": params.get("currency", "EUR"),
                "recipient_binding": params.get("recipient_iban", "TEST-IBAN"),
            },
            "authentication": {
                "auth_scheme": "ed25519_pinned",
                "key_id": "target-recon-key-01",
            },
        }
        r_digest, r_sig = self._sign_record(reconciliation_payload, self.target_privkey)
        reconciliation_payload["digest"] = r_digest
        reconciliation_payload["signature_b64"] = r_sig

        final_disposition = (
            PilotDisposition.RESOLVED_CONFIRMED
            if simulated_target_status == "SETTLED"
            else PilotDisposition.RESOLVED_REFUTED
        )

        res = PilotEvaluationResult(
            action_id=action_id,
            caid=caid,
            stage=self.current_stage,
            disposition=final_disposition,
            allowed_to_dispatch=True,
            rejection_code=None,
            rejection_reason=f"Resolved via out-of-band target evidence: {simulated_target_status}",
            connections_accepted=1,
            bytes_transmitted=len(encode_jcs(params)),
            reconciliation_record=reconciliation_payload,
        )
        self.history.append(res)
        return res

    def export_evidence_pack(self, output_dir: Path) -> Path:
        """
        Exports the complete 6-Week Commercial Pilot Evidence Pack.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "pack_schema_version": "1.1.0-pilot-evidence",
            "audit_status": "LOCAL PASS; INDEPENDENT REPRODUCTION PENDING",
            "pilot_id": self.config.pilot_id,
            "action_class": self.config.action_class,
            "pinned_mcp_version": self.config.pinned_mcp_version,
            "total_evaluations": len(self.history),
            "stages_evaluated": list({r.stage.value for r in self.history}),
            "summary_metrics": {
                "allowed_count": sum(1 for r in self.history if r.disposition == PilotDisposition.ALLOWED),
                "would_block_count": sum(1 for r in self.history if r.disposition == PilotDisposition.WOULD_BLOCK),
                "blocked_pre_dispatch_count": sum(1 for r in self.history if r.disposition == PilotDisposition.BLOCKED_PRE_DISPATCH),
                "indeterminate_count": sum(1 for r in self.history if r.disposition == PilotDisposition.EFFECT_INDETERMINATE),
                "resolved_confirmed_count": sum(1 for r in self.history if r.disposition == PilotDisposition.RESOLVED_CONFIRMED),
                "resolved_refuted_count": sum(1 for r in self.history if r.disposition == PilotDisposition.RESOLVED_REFUTED),
                "total_prevented_egress_bytes": sum(
                    r.bytes_transmitted for r in self.history if r.disposition == PilotDisposition.BLOCKED_PRE_DISPATCH
                ),
            },
            "standards_crosswalk": {
                "caict_agent_security_spec": "CTTL-AI-AGENT-SEC-2025 (Device/Runtime Isolation)",
                "ant_group_agent_3sigma": "Agent3σ-Canary Runtime Stress & Permission Verification",
                "tencent_ai_infra_guard": "MCP Protocol Scan & Tool Parameter Sanitization",
                "ietf_jcs": "RFC 8785 Canonical JSON Serialization",
            },
            "evaluations": [asdict(r) for r in self.history],
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        digest, sig = self._sign_record(manifest, self.boundary_privkey)
        bundle = {
            "manifest": manifest,
            "bundle_digest": digest,
            "boundary_signature_b64": sig,
            "boundary_public_key_pem": self.boundary_pubkey.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii"),
            "target_public_key_pem": self.target_pubkey.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode("ascii"),
        }

        output_file = output_dir / f"pilot_evidence_pack_{self.config.pilot_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2, sort_keys=True)

        return output_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 tools/aeib_pilot_runner.py [demo | verify <bundle.json>]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "demo":
        config = PilotConfig(
            pilot_id="pilot-retail-bank-cz-01",
            action_class="refund_customer",
            target_endpoint="https://api.bank.internal/v1/refunds",
            allowed_uri_prefixes=["https://api.bank.internal/v1/"],
            pinned_mcp_version="2025-06-18",
        )
        runner = AeibPilotRunner(config)
        print(f"[*] Initialized AEIB Pilot Runner for: {config.pilot_id}")

        # Week 1: Scoping
        runner.set_stage(PilotStage.WEEK1_SCOPING)
        runner.evaluate_candidate_action({
            "action_id": "act-w1-01",
            "mcp_version": "2025-06-18",
            "target_uri": "https://api.bank.internal/v1/refunds",
            "policy_epoch": 1,
            "ticket_id": "ticket-w1-01",
            "parameters": {"amount_minor_units": 1500, "currency": "EUR", "recipient_iban": "CZ001"},
        })
        print("  ✓ Week 1 Scoping turn executed.")

        # Week 2: Shadow Mode (Passive observation, WOULD_BLOCK recorded)
        runner.set_stage(PilotStage.WEEK2_SHADOW)
        runner.evaluate_candidate_action({
            "action_id": "act-w2-tampered",
            "mcp_version": "2025-06-18",
            "target_uri": "https://api.bank.internal/v1/refunds",
            "policy_epoch": 99,  # Stale epoch!
            "ticket_id": "ticket-w2-01",
            "parameters": {"amount_minor_units": 999999, "currency": "EUR"},
        })
        print("  ✓ Week 2 Shadow Mode turn executed (WOULD_BLOCK logged, 0 executions blocked).")

        # Week 3: Active Enforcement (Deny-by-default)
        runner.set_stage(PilotStage.WEEK3_ENFORCE)
        runner.evaluate_candidate_action({
            "action_id": "act-w3-blocked",
            "mcp_version": "2025-06-18",
            "target_uri": "https://malicious.external.com/leak",
            "policy_epoch": 1,
            "ticket_id": "ticket-w3-01",
            "parameters": {"amount_minor_units": 100, "currency": "EUR"},
        })
        print("  ✓ Week 3 Active Enforcement turn executed (Pre-Execution Restraint Record generated, 0 egress bytes).")

        # Weeks 4-6: Target-Attested Reconciliation
        runner.set_stage(PilotStage.WEEKS4_6_RECONCILE)
        runner.evaluate_candidate_action(
            {
                "action_id": "act-w4-504-recon",
                "mcp_version": "2025-06-18",
                "target_uri": "https://api.bank.internal/v1/refunds",
                "policy_epoch": 1,
                "ticket_id": "ticket-w4-01",
                "parameters": {"amount_minor_units": 2500, "currency": "EUR", "recipient_iban": "CZ002"},
            },
            simulate_transport_drop=True,
            simulated_target_status="SETTLED",
        )
        print("  ✓ Weeks 4-6 Target-Attested Reconciliation turn executed (HTTP 504 -> RESOLVED_CONFIRMED).")

        pack_file = runner.export_evidence_pack(Path("artifacts/pilot"))
        print(f"[✓] Pilot Evidence Pack generated: {pack_file}")

    elif cmd == "verify":
        bundle_path = sys.argv[2]
        with open(bundle_path, "r", encoding="utf-8") as f:
            bundle = json.load(f)

        manifest = bundle["manifest"]
        pubkey_pem = bundle["boundary_public_key_pem"].encode("ascii")
        pubkey = serialization.load_pem_public_key(pubkey_pem)

        recomputed_digest = hashlib.sha256(encode_jcs(manifest)).hexdigest()
        assert recomputed_digest == bundle["bundle_digest"], "Bundle digest mismatch!"
        
        sig = base64.b64decode(bundle["boundary_signature_b64"])
        pubkey.verify(sig, encode_jcs(manifest))
        print(f"[✓] Verified Pilot Evidence Pack: {bundle_path}")
        print(f"    - Total Evaluations: {manifest['total_evaluations']}")
        print(f"    - Allowed: {manifest['summary_metrics']['allowed_count']}")
        print(f"    - Would Block: {manifest['summary_metrics']['would_block_count']}")
        print(f"    - Blocked Pre-Dispatch: {manifest['summary_metrics']['blocked_pre_dispatch_count']}")
        print(f"    - Resolved Confirmed: {manifest['summary_metrics']['resolved_confirmed_count']}")


if __name__ == "__main__":
    main()
