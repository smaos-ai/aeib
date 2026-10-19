#!/usr/bin/env python3
"""
tests/test_space_egress_and_harness2_lock.py
================================================================================
Verifies Next-Gen AEIB Backlog Invariants (AT70, AT71, AT72, Move 1 Scion-Lite, Actuarial Ledger):
- AT70 (Perplexity SPACE-style Egress + Secret Injection Interlock):
  Blocks DNS-spoofing / shared-CDN IP laundering where TLS SNI != HTTP Host or IP is unpinned,
  and injects downstream API secrets ONLY after Station 1 cryptographic authorization.
- AT71 (Google Harness² / Terminal-RSI Ring-0 Guardrail Lock):
  Allows self-evolving harnesses to rewrite Ring-3 files (prompts, EXPERIENCE.md, skills)
  while deterministically halting any candidate harness that modifies Ring-0 guardrails/middleware.
- AT72 (Caveman-style Input Compression Proxy with Dual-Digest Taint Preservation):
  Compresses large tool outputs for token efficiency while preserving raw SHA-256 auditability
  and strict TIER_2 taint propagation.
- Move 1 Virtual Changeset Coordinator: Enforces disjoint path leases (A_i ∩ A_j = ∅).
- Actuarial Underwriting Ledger: Aggregates warrants and near-misses for cyber-insurance.

Zero mocks, real Ed25519 cryptography, RFC 8785 JCS canonicalization.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.adapters.harness2_ring0_lock import Harness2Ring0Enforcer
from src.adapters.space_egress_interceptor import (
    HostEgressSecretInjector,
    OutboundMicroVmRequest,
)
from src.caveman_compression_proxy import (
    DualDigestCompressedContext,
    compress_and_seal_tool_output,
)
from src.jcs_canonicalizer import encode_jcs
from tools.export_actuarial_ledger import (
    ActuarialUnderwritingLedgerExporter,
    verify_actuarial_report,
)
from tools.virtual_changeset_coordinator import VirtualChangesetCoordinator


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def test_at70_at71_at72_space_egress_harness2_and_compression(tmp_path: Path) -> None:
    # 1. Verify AT70: Host-Side Egress & Secret Injection
    station1_priv = Ed25519PrivateKey.generate()
    injector = HostEgressSecretInjector(
        station1_pubkey=station1_priv.public_key(),
        allowed_domains_to_ips={"api.stripe.com": {"192.0.2.10", "192.0.2.11"}},
        host_secret_vault={"api.stripe.com": "sk_live_REAL_VAULT_SECRET_991"},
    )
    body_caid = sha256_prefixed(b'{"amount":2500,"currency":"eur"}')
    warrant_payload = encode_jcs(
        {
            "canonical_body_caid": body_caid,
            "domain": "api.stripe.com",
            "http_method": "POST",
            "operation_id": "op-space-01",
            "path": "/v1/refunds",
        }
    )
    valid_sig = base64.b64encode(station1_priv.sign(warrant_payload)).decode("ascii")

    # Attack A: Agent attempts DNS spoofing / shared-CDN IP bypass to an unpinned IP
    status_ip, code_ip, hdrs_ip = injector.inspect_and_inject_secret(
        OutboundMicroVmRequest(
            operation_id="op-space-01",
            tls_sni="api.stripe.com",
            http_host_header="api.stripe.com",
            resolved_dest_ip="203.0.113.99",  # Rogue IP behind shared CDN
            http_method="POST",
            path="/v1/refunds",
            canonical_body_caid=body_caid,
            station1_approval_sig_b64=valid_sig,
        )
    )
    assert status_ip == "BLOCKED"
    assert code_ip == "HALT_EGRESS_DNS_OR_SHARED_CDN_IP_SPOOF"
    assert hdrs_ip is None

    # Attack B: Agent attempts SNI vs. HTTP Host mismatch (domain fronting)
    status_sni, code_sni, _ = injector.inspect_and_inject_secret(
        OutboundMicroVmRequest(
            operation_id="op-space-01",
            tls_sni="api.stripe.com",
            http_host_header="attacker-controlled.example.com",
            resolved_dest_ip="192.0.2.10",
            http_method="POST",
            path="/v1/refunds",
            canonical_body_caid=body_caid,
            station1_approval_sig_b64=valid_sig,
        )
    )
    assert status_sni == "BLOCKED"
    assert code_sni == "HALT_EGRESS_SNI_HOST_MISMATCH"

    # Valid Authorized Call: Passes SNI, IP, and Station 1 Warrant -> Host injects secret
    status_ok, code_ok, hdrs_ok = injector.inspect_and_inject_secret(
        OutboundMicroVmRequest(
            operation_id="op-space-01",
            tls_sni="api.stripe.com",
            http_host_header="api.stripe.com",
            resolved_dest_ip="192.0.2.10",
            http_method="POST",
            path="/v1/refunds",
            canonical_body_caid=body_caid,
            station1_approval_sig_b64=valid_sig,
        )
    )
    assert status_ok == "DISPATCHED_WITH_HOST_SECRET" and code_ok is None
    assert hdrs_ok is not None
    assert hdrs_ok["Authorization"] == "Bearer sk_live_REAL_VAULT_SECRET_991"

    # 2. Verify AT71: Google Harness² Ring-0 Guardrail Lock
    ring0_guardrail_bytes = b"MAX_SPRINT_EUR_MINOR = 250000\nREQUIRE_STEP_UP_ON_TIER2 = True\n"
    enforcer = Harness2Ring0Enforcer(
        ring0_baseline_hashes={"guardrails": sha256_prefixed(ring0_guardrail_bytes)}
    )

    # Candidate 1: Harness² edits `memory_experience_md` and `system_prompt` (Ring-3) -> ALLOWED
    ok_c1, err_c1 = enforcer.validate_proposed_harness_candidate(
        {
            "guardrails": ring0_guardrail_bytes,
            "system_prompt": b"Improved domain prompt from Propose-Probe-Compose",
            "memory_experience_md": b"Lesson 1: Always validate schema before tool call.",
        }
    )
    assert ok_c1 and err_c1 is None

    # Candidate 2: Harness² attempts to edit `guardrails` (Ring-0) to raise cap -> HALTED
    ok_c2, err_c2 = enforcer.validate_proposed_harness_candidate(
        {
            "guardrails": b"MAX_SPRINT_EUR_MINOR = 99999900\nREQUIRE_STEP_UP_ON_TIER2 = False\n",
            "system_prompt": b"Improved domain prompt",
        }
    )
    assert not ok_c2
    assert err_c2 == "HALT_HARNESS2_RING0_RELAXATION_ATTEMPT:guardrails"

    # 3. Verify AT72: Caveman-style Dual-Digest Input Compression
    verbose_log = {
        "status": "WARN",
        "error_code": "NONE",
        "summary": "Customer requested refund to new IBAN",
        "verbose_stack_trace": "frame_01 " * 400,
    }
    sealed = compress_and_seal_tool_output(
        "ctx-log-1", "TIER_2_UNTRUSTED_EXTERNAL", verbose_log, vault_dir=tmp_path / "vault"
    )
    assert sealed.token_reduction_pct > 80.0
    assert sealed.source_tier == "TIER_2_UNTRUSTED_EXTERNAL"
    assert sealed.raw_bytes_sha256 != sealed.compressed_view_sha256
    assert sealed.vault_blob_path is not None
    assert Path(sealed.vault_blob_path).exists()


def test_virtual_changeset_coordinator_disjoint_leases(tmp_path: Path) -> None:
    db_file = tmp_path / "test_changeset_wal.sqlite"
    privkey = Ed25519PrivateKey.generate()
    coordinator = VirtualChangesetCoordinator(coordinator_privkey=privkey, db_path=db_file)

    # Subagent Alpha requests lease for payments module
    res_a = coordinator.acquire_path_lease(
        subagent_id="subagent_alpha",
        paths=["src/payments/refund.py", "src/payments/models.py"],
    )
    assert res_a["granted"] is True
    assert res_a["status"] == "LEASE_GRANTED"

    # Subagent Beta requests overlapping lease -> HALT_OVERLAPPING_WRITE_SET_COLLISION
    res_b = coordinator.acquire_path_lease(
        subagent_id="subagent_beta",
        paths=["src/payments/refund.py", "src/auth/login.py"],
    )
    assert res_b["granted"] is False
    assert res_b["status"] == "HALT_OVERLAPPING_WRITE_SET_COLLISION"
    assert len(res_b["conflicting_paths"]) == 1
    assert res_b["conflicting_paths"][0]["path"] == "src/payments/refund.py"

    # Subagent Gamma requests disjoint lease -> GRANTED
    res_g = coordinator.acquire_path_lease(
        subagent_id="subagent_gamma",
        paths=["src/reports/audit.py"],
    )
    assert res_g["granted"] is True

    # Commit virtual changeset by Alpha
    patch = {
        "target_paths": ["src/payments/refund.py"],
        "diff": "+ # Applied refund fix",
    }
    commit_res = coordinator.commit_virtual_changeset(
        subagent_id="subagent_alpha",
        changeset_id="cs-001",
        patch_payload=patch,
    )
    assert commit_res["committed"] is True
    assert commit_res["status"] == "CHANGESET_COMMITTED"


def test_actuarial_underwriting_ledger_exporter() -> None:
    privkey = Ed25519PrivateKey.generate()
    exporter = ActuarialUnderwritingLedgerExporter(signing_key=privkey)

    intercepted = [
        {"reason": "HALT_SPRINT_LIMIT_EXCEEDED", "prevented_amount_minor": 150000},
        {"reason": "HTTP_504_GATEWAY_TIMEOUT_RETRY_BLOCKED", "prevented_amount_minor": 85000},
        {"reason": "UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP", "prevented_amount_minor": 50000},
        {"reason": "HALT_HONEYPOT_TRIPWIRE_TRIGGERED", "prevented_amount_minor": 0},
    ]

    report = exporter.generate_actuarial_report(
        executed_warrants_count=120,
        executed_volume_eur_minor=4500000,
        intercepted_events=intercepted,
        assessment_window_days=30,
    )

    metrics = report["payload"]["metrics"]
    assert metrics["executed_warrants_count"] == 120
    assert metrics["total_near_miss_interventions"] == 4
    assert metrics["prevented_loss_exposure_minor"] == 285000
    assert metrics["breakdown_by_category"]["sybil_quota_bursts_blocked"] == 1
    assert metrics["breakdown_by_category"]["duplicate_retry_storms_blocked"] == 1
    assert metrics["breakdown_by_category"]["taint_escalation_blocked"] == 1
    assert metrics["breakdown_by_category"]["honeypot_canary_tripwires_triggered"] == 1

    assert verify_actuarial_report(exporter.public_key, report) is True
