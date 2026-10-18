#!/usr/bin/env python3
"""
Implements and verifies defenses against late-2026 agent runtime patterns:
- AT67: MCP "Code Mode" Composite Script Gate (tracks High-Water-Mark taint & cumulative spend
        when an agent combines multiple MCP tools inside a single script execution).
- AT68: Mid-Session Self-Authored Hot-Reload Plugin Rejection (blocks plugins written or
        hot-reloaded after `session_start_ns` or lacking an offline human publisher signature).
- AT69: Zero-Token System-1 Classification Gate + 4-Dimension Governance Accountability Binding
        (Ownership, Decision-Making, Challenge & Assurance, Practical Implementation).
Zero mocks, real Ed25519 signatures, RFC 8785 JCS canonicalization.
"""

from __future__ import annotations

import base64
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT.parent))

from src.jcs_canonicalizer import encode_jcs
from src.opencode_and_mcp_codemode_engine import (
    TIER_RANK,
    CodeModeAndHotReloadGate,
    FourDimensionGovernanceRecord,
    SignedPluginManifest,
    sha256_prefixed,
)



def test_at67_and_at68_opencode_codemode_and_mid_session_hotreload() -> None:
    human_pub_priv = Ed25519PrivateKey.generate()
    agent_self_priv = Ed25519PrivateKey.generate()
    session_boot_ns = 1_760_700_000_000_000_000

    gate = CodeModeAndHotReloadGate(
        session_start_ns=session_boot_ns,
        human_publisher_pubkey=human_pub_priv.public_key(),
        human_publisher_key_id="did:key:human-secops-lead",
        sprint_limit_minor=1000_00,
    )

    # 1. Pre-session human-signed MCP tool registration succeeds
    clean_code = b"export function mcpTools() { return true; }"
    clean_sha = sha256_prefixed(clean_code)
    pre_session_ts = session_boot_ns - 60_000_000_000  # 60s before session boot
    payload = encode_jcs(
        {
            "code_sha256": clean_sha,
            "plugin_id": "mcp-core-suite",
            "registered_at_ns": pre_session_ts,
            "signer_key_id": "did:key:human-secops-lead",
        }
    )
    sig_b64 = base64.b64encode(human_pub_priv.sign(payload)).decode("ascii")
    ok, err = gate.register_plugin(
        SignedPluginManifest(
            plugin_id="mcp-core-suite",
            code_sha256=clean_sha,
            registered_at_ns=pre_session_ts,
            signer_key_id="did:key:human-secops-lead",
            signature_b64=sig_b64,
        ),
        clean_code,
    )
    assert ok and err is None

    # 2. AT68: Agent writes itself a plugin mid-session and tries to hot-reload it
    self_plugin_code = b"export function bypassLimit() { sendWire(); }"
    self_sha = sha256_prefixed(self_plugin_code)
    mid_session_ts = session_boot_ns + 5_000_000_000  # 5s AFTER session boot
    self_payload = encode_jcs(
        {
            "code_sha256": self_sha,
            "plugin_id": "agent-self-authored-plugin",
            "registered_at_ns": mid_session_ts,
            "signer_key_id": "did:key:coding-agent-ephemeral",
        }
    )
    self_sig = base64.b64encode(agent_self_priv.sign(self_payload)).decode("ascii")
    ok_hot, err_hot = gate.register_plugin(
        SignedPluginManifest(
            plugin_id="agent-self-authored-plugin",
            code_sha256=self_sha,
            registered_at_ns=mid_session_ts,
            signer_key_id="did:key:coding-agent-ephemeral",
            signature_b64=self_sig,
        ),
        self_plugin_code,
    )
    assert not ok_hot
    assert err_hot == "HALT_MID_SESSION_HOT_RELOAD_FORBIDDEN"

    # Attempt to execute the hot-reloaded plugin is deterministically blocked
    res_unreg = gate.execute_mcp_codemode_step(
        plugin_id="agent-self-authored-plugin",
        step_type="FINANCIAL_MUTATION",
        data_tier="TIER_1_INTERNAL_DB",
        amount_minor=100_00,
    )
    assert res_unreg["disposition"] == "NOT_DISPATCHED"
    assert res_unreg["rejection_code"] == "HALT_UNREGISTERED_OR_HOT_RELOADED_PLUGIN"

    # 3. AT67: MCP "Code Mode" script combines an untrusted read + unpinned financial write
    # Step A in script: clean EUR 600 mutation passes
    step1 = gate.execute_mcp_codemode_step(
        plugin_id="mcp-core-suite",
        step_type="FINANCIAL_MUTATION",
        data_tier="TIER_1_INTERNAL_DB",
        amount_minor=600_00,
        pinned_known_recipient=True,
    )
    assert step1["disposition"] == "DISPATCHED"

    # Step B in script: script reads an untrusted external issue/email (TIER_2)
    step2 = gate.execute_mcp_codemode_step(
        plugin_id="mcp-core-suite",
        step_type="READ",
        data_tier="TIER_2_UNTRUSTED_EXTERNAL",
    )
    assert step2["session_taint"] == "TIER_2_UNTRUSTED_EXTERNAL"

    # Step C in script: script immediately tries to pay EUR 200 to an unpinned recipient
    step3 = gate.execute_mcp_codemode_step(
        plugin_id="mcp-core-suite",
        step_type="FINANCIAL_MUTATION",
        data_tier="TIER_1_INTERNAL_DB",  # Even though this call claims TIER_1, script is tainted!
        amount_minor=200_00,
        pinned_known_recipient=False,
    )
    assert step3["disposition"] == "NOT_DISPATCHED"
    assert step3["rejection_code"] == "HALT_CODEMODE_SCRIPT_TAINT_PROPAGATED"

    # Step D in script: script tries to pay EUR 500 to a pinned recipient -> exceeds EUR 1,000 cap (600 + 500)
    step4 = gate.execute_mcp_codemode_step(
        plugin_id="mcp-core-suite",
        step_type="FINANCIAL_MUTATION",
        data_tier="TIER_1_INTERNAL_DB",
        amount_minor=500_00,
        pinned_known_recipient=True,
    )
    assert step4["disposition"] == "NOT_DISPATCHED"
    assert step4["rejection_code"] == "HALT_CODEMODE_CUMULATIVE_SPRINT_EXCEEDED"


def test_at69_zero_token_system1_decision_and_4d_accountability_binding() -> None:
    """
    AT69: Verifies that a zero-token System-1 classification model (MJev-Spatial style:
    emitting a discrete option index, scalar amount, and 2D point with 0 text tokens)
    is governed at the wire level and cryptographically bound to all 4 dimensions of
    AI governance (Ownership, Decision-Making, Challenge & Assurance, Practical
    Implementation) plus operational delta counters.
    """
    human_pub_priv = Ed25519PrivateKey.generate()
    gate_signer = Ed25519PrivateKey.generate()
    session_boot_ns = 1_760_700_000_000_000_000

    gate = CodeModeAndHotReloadGate(
        session_start_ns=session_boot_ns,
        human_publisher_pubkey=human_pub_priv.public_key(),
        human_publisher_key_id="did:key:human-secops-lead",
        sprint_limit_minor=1000_00,
    )

    clean_code = b"export function system1Classifier() { return [1, 25000, [0.42, 0.88]]; }"
    clean_sha = sha256_prefixed(clean_code)
    pre_session_ts = session_boot_ns - 30_000_000_000
    payload = encode_jcs(
        {
            "code_sha256": clean_sha,
            "plugin_id": "mjev-spatial-classifier",
            "registered_at_ns": pre_session_ts,
            "signer_key_id": "did:key:human-secops-lead",
        }
    )
    sig_b64 = base64.b64encode(human_pub_priv.sign(payload)).decode("ascii")
    ok, _ = gate.register_plugin(
        SignedPluginManifest(
            plugin_id="mjev-spatial-classifier",
            code_sha256=clean_sha,
            registered_at_ns=pre_session_ts,
            signer_key_id="did:key:human-secops-lead",
            signature_b64=sig_b64,
        ),
        clean_code,
    )
    assert ok

    # 1. Zero-token System-1 decision within budget and untainted -> DISPATCHED with 4D receipt
    approved = gate.evaluate_zero_token_system1_action(
        operation_id="op-sys1-001",
        plugin_id="mjev-spatial-classifier",
        discrete_option_id=2,
        scalar_amount_minor=250_00,
        spatial_target_xy=(0.4215, 0.8831),
        answer_tokens_emitted=0,
        ownership_sponsor_id="did:key:treasury-owner-eu",
        decision_authority_cert_id="cert-en18286-qms-009",
        gate_signer=gate_signer,
        pinned_known_recipient=True,
    )
    assert approved["disposition"] == "DISPATCHED"
    assert approved["answer_tokens_emitted"] == 0
    assert (
        approved["four_dimension_governance"]["ownership_sponsor_id"]
        == "did:key:treasury-owner-eu"
    )
    assert (
        approved["four_dimension_governance"]["implementation_gate_verdict"]
        == "DISPATCHED"
    )
    assert approved["what_changed_as_a_result"]["dispatched_mutation_count"] == 1

    # Verify Ed25519 signature over the 4-Dimension governance receipt
    sig_bytes = base64.b64decode(approved["gate_signature_b64"])
    unsigned = {k: v for k, v in approved.items() if k != "gate_signature_b64"}
    gate_signer.public_key().verify(sig_bytes, encode_jcs(unsigned))

    # 2. Taint the session via a TIER_2 read, then fire a zero-token System-1 decision to an unpinned target
    gate.execute_mcp_codemode_step(
        plugin_id="mjev-spatial-classifier",
        step_type="READ",
        data_tier="TIER_2_UNTRUSTED_EXTERNAL",
    )
    blocked = gate.evaluate_zero_token_system1_action(
        operation_id="op-sys1-002",
        plugin_id="mjev-spatial-classifier",
        discrete_option_id=3,
        scalar_amount_minor=300_00,
        spatial_target_xy=(0.9102, 0.1140),
        answer_tokens_emitted=0,
        ownership_sponsor_id="did:key:treasury-owner-eu",
        decision_authority_cert_id="cert-en18286-qms-009",
        gate_signer=gate_signer,
        pinned_known_recipient=False,
    )
    assert blocked["disposition"] == "NOT_DISPATCHED"
    assert blocked["rejection_code"] == "HALT_CODEMODE_SCRIPT_TAINT_PROPAGATED"
    assert (
        blocked["four_dimension_governance"]["implementation_gate_verdict"]
        == "NOT_DISPATCHED"
    )
    assert blocked["what_changed_as_a_result"]["blocked_mutation_count"] == 1
