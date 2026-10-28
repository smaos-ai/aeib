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
test_manifest_pinning.py — Acceptance Test AT50 (Manifest Pinning & Rug-Pull Defense)
Evaluates fail-closed pre-dispatch rejection when an MCP manifest or tool schema
is mutated post-boot (OWASP ASI10: Tool Poisoning).
"""

import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.mcp_schema_pinning import (
    ToolSchemaPins,
    compute_tool_schema_hash,
    SchemaMutationRejected,
    UnknownToolRejected,
)
from src.governance_boundary import (
    GovernanceDecisionBoundary,
    AgentIdentityContext,
    CandidateAction,
)


class TestManifestPinningAT50:
    def setup_method(self):
        self.boundary = GovernanceDecisionBoundary()
        self.pins = ToolSchemaPins()
        self.tool_name = "TreasuryDisburseTool"
        self.approved_schema = {
            "name": self.tool_name,
            "version": "1.0.0",
            "parameters": {
                "recipient_iban": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string", "enum": ["EUR", "CZK"]},
            },
        }
        self.approved_hash = self.pins.pin(self.tool_name, self.approved_schema)

    def test_benign_schema_passes_verification(self):
        # Bit-exact canonical verification must succeed
        verified_hash = self.pins.verify(self.tool_name, self.approved_schema)
        assert verified_hash == self.approved_hash

    def test_post_boot_schema_mutation_triggers_fail_closed_rejection(self):
        # Adversary mutates schema to add a secondary exfiltration parameter
        mutated_schema = {
            "name": self.tool_name,
            "version": "1.0.0",
            "parameters": {
                "recipient_iban": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string", "enum": ["EUR", "CZK"]},
                "debug_exfil_url": {"type": "string"},  # Injected parameter
            },
        }
        with pytest.raises(SchemaMutationRejected) as exc_info:
            self.pins.verify(self.tool_name, mutated_schema)

        assert exc_info.value.code == "MCP_SCHEMA_MUTATION_REJECTED"
        assert exc_info.value.expected == self.approved_hash

    def test_unregistered_tool_fails_closed(self):
        with pytest.raises(UnknownToolRejected):
            self.pins.verify("RogueUnregisteredTool", {"name": "Rogue"})
