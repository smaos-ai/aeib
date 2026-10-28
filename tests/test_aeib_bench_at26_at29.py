#!/usr/bin/env python3
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

r"""
test_aeib_bench_at26_at29.py — Acceptance Test Matrix AT26 through AT29

Evaluates the Four Architectural Upgrades for AEIB v0.4.0:
- AT26: ProxyToolAbuseGuard (Wikimedia Incident Oct 2026 pattern -> DISPATCH_REJECTED / C3)
- AT27: Anonymous A2A Delegation Shrouding (Sapienza Study 2026 pattern -> strips vendor/model, retains security lineage)
- AT28: Shadow-AI Execution Discovery (Ring-0 / eBPF LSM Intercept -> FAIL_SHADOW_AI_BLOCKED / C4)
- AT29: Memory-Digest Binding TOCTOU (Prompt-Injection context drift -> STALE_STANDING / C2)
"""

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.governance_boundary import (
    GovernanceDecisionBoundary,
    AgentIdentityContext,
    CandidateAction,
    DelegationGrant,
)


class TestAEIBBenchAT26AT29:
    def setup_method(self):
        self.boundary = GovernanceDecisionBoundary()
        self.agent_id = "agent:corp:treasury_ops_01"
        self.boundary.register_agent(self.agent_id)
        self.grant_id = "grant_treasury_valid"
        self.boundary.add_grant(DelegationGrant(
            grant_id=self.grant_id,
            principal_id="principal:cfo_office",
            authorized_agent_id=self.agent_id,
            allowed_verbs={"Treasury:Disburse", "CitationTool:Fetch", "System:Run"},
            policy_epoch="policy:epoch_104",
            expires_at_epoch_ms=2000000000000,
        ))
        self.identity = AgentIdentityContext(
            agent_id=self.agent_id,
            principal_id="principal:cfo_office",
            tenant_id="tenant_bank_cz",
            delegation_chain=["principal:cfo_office", self.agent_id],
            standing_version="standing:v2026.10.07-epoch-14",
            policy_epoch="policy:epoch_104"
        )

    def test_at26_proxy_tool_abuse_wikimedia_pattern(self):
        """
        AT26: OpenAI agents weaponizing auxiliary tools (Etherpad/citation) for proxy exfiltration.
        Gateway enforces inbound URI allowlist bound to candidate CAID and blocks unauthorized endpoints.
        """
        # Case 1: Unauthorized proxy destination
        candidate_exfil = CandidateAction(
            noun="CitationTool",
            verb="Fetch",
            payload={"doc_id": "secret_memo", "exfil_data": "dGVzdF9rZXk="},
            grant_id=self.grant_id,
            target_uri="https://malicious-collaborative-pad.org/leak/stream"
        )
        decision_exfil = self.boundary.evaluate_pre_dispatch(candidate_exfil, self.identity, 1728300000000)
        assert decision_exfil.permitted is False
        assert decision_exfil.disposition == "DISPATCH_REJECTED (PROXY_EGRESS_VIOLATION)"
        assert decision_exfil.containment_level == "C3"
        assert "proxy exfiltration blocked" in decision_exfil.reason

        # Case 2: Authorized internal endpoint
        self.boundary.allow_uri("https://trusted-wiki.corp.internal/doc/42")
        candidate_valid = CandidateAction(
            noun="CitationTool",
            verb="Fetch",
            payload={"doc_id": "public_policy"},
            grant_id=self.grant_id,
            target_uri="https://trusted-wiki.corp.internal/doc/42"
        )
        decision_valid = self.boundary.evaluate_pre_dispatch(candidate_valid, self.identity, 1728300000000)
        assert decision_valid.permitted is True
        assert decision_valid.disposition == "DISPATCH_PERMITTED"

    def test_at27_a2a_lineage_shrouding_sapienza_pattern(self):
        """
        AT27: Exposing vendor/model lineage across sub-agents causes tribal preference.
        Gateway strips vendor/model metadata from A2A delegation headers while strictly preserving
        security lineage (principal_id, grant_id, delegation_scope, standing_version).
        """
        raw_a2a_headers = {
            "vendor": "openai",
            "model": "gpt-6-ultra",
            "model_family": "gpt",
            "provider": "azure-openai",
            "principal_id": "principal:cfo_office",
            "grant_id": self.grant_id,
            "delegation_scope": "Treasury:Disburse",
            "standing_version": "standing:v2026.10.07-epoch-14",
            "custom_trace_id": "trace_a2a_9981"
        }

        shrouded = self.boundary.shroud_a2a_delegation(raw_a2a_headers)

        # Assert all vendor/model tribal tags are stripped
        assert "vendor" not in shrouded
        assert "model" not in shrouded
        assert "model_family" not in shrouded
        assert "provider" not in shrouded

        # Assert security and provenance lineage is preserved bit-for-bit
        assert shrouded["principal_id"] == "principal:cfo_office"
        assert shrouded["grant_id"] == self.grant_id
        assert shrouded["delegation_scope"] == "Treasury:Disburse"
        assert shrouded["standing_version"] == "standing:v2026.10.07-epoch-14"
        assert shrouded["custom_trace_id"] == "trace_a2a_9981"

    def test_at28_shadow_ai_ring0_intercept(self):
        """
        AT28: Shadow IT CLI harness (e.g. skills.sh) executed out-of-band without registration.
        Ring-0 / eBPF LSM interception hooks verify binary path against allowed_execve registry.
        Un-cataloged binary triggers C4 Quarantine and FAIL_SHADOW_AI_BLOCKED.
        """
        # Case 1: Unregistered shadow execution harness
        shadow_candidate = CandidateAction(
            noun="System",
            verb="Run",
            payload={"cmd": "sh /tmp/skills.sh"},
            grant_id=self.grant_id,
            exec_path="/tmp/skills.sh"
        )
        shadow_decision = self.boundary.evaluate_pre_dispatch(shadow_candidate, self.identity, 1728300000000)
        assert shadow_decision.permitted is False
        assert shadow_decision.disposition == "FAIL_SHADOW_AI_BLOCKED"
        assert shadow_decision.containment_level == "C4"
        assert "quarantined under C4" in shadow_decision.reason

        # Case 2: Registered allowed executable
        registered_candidate = CandidateAction(
            noun="System",
            verb="Run",
            payload={"cmd": "python3 /app/job.py"},
            grant_id=self.grant_id,
            exec_path="/usr/bin/python3"
        )
        reg_decision = self.boundary.evaluate_pre_dispatch(registered_candidate, self.identity, 1728300000000)
        assert reg_decision.permitted is True
        assert reg_decision.disposition == "DISPATCH_PERMITTED"

    def test_at29_memory_digest_drift_toctou(self):
        """
        AT29: Prompt-Injection TOCTOU where memory context changes between action approval and dispatch.
        Gateway binds memory_digest into CAID and checks for drift at the millisecond of dispatch.
        Context drift results in STALE_STANDING fail-closed.
        """
        approved_digest = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        poisoned_digest = "sha256:d41d8cd98f00b204e9800998ecf8427e99887766554433221100aabbccddeeff"

        # Case 1: Drifted memory digest (injected facts modified context)
        drifted_candidate = CandidateAction(
            noun="Treasury",
            verb="Disburse",
            payload={"amount": 50000, "recipient": "vendor_corp"},
            grant_id=self.grant_id,
            memory_digest=poisoned_digest,
            approved_memory_digest=approved_digest
        )
        drift_decision = self.boundary.evaluate_pre_dispatch(drifted_candidate, self.identity, 1728300000000)
        assert drift_decision.permitted is False
        assert drift_decision.disposition == "STALE_STANDING"
        assert drift_decision.containment_level == "C2"
        assert "Memory digest drift detected" in drift_decision.reason

        # Case 2: Clean matching memory digest
        clean_candidate = CandidateAction(
            noun="Treasury",
            verb="Disburse",
            payload={"amount": 50000, "recipient": "vendor_corp"},
            grant_id=self.grant_id,
            memory_digest=approved_digest,
            approved_memory_digest=approved_digest
        )
        clean_decision = self.boundary.evaluate_pre_dispatch(clean_candidate, self.identity, 1728300000000)
        assert clean_decision.permitted is True
        assert clean_decision.disposition == "DISPATCH_PERMITTED"
