#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
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
tests/test_dynamic_tool_registry.py
================================================================================
Test suite for Dynamic Capability Classification & Context-Optimized Tool Registry.
Evaluated under the stated model (scaffold verifier).
Zero-mock, deterministic test assertions and mutation adequacy verification.
"""

from __future__ import annotations

import dataclasses
import pytest

from src.dynamic_tool_registry import (
    DynamicToolRegistry,
    ToolDefinition,
    ToolSelectionResult,
)


def test_dynamic_tool_registry_dataclass_frozenness() -> None:
    tool = ToolDefinition(
        name="test_tool",
        category="ci_cd",
        description="A testing tool",
        schema_json='{"type": "object"}',
        risk_tier="T1",
        is_write=False,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        tool.name = "tampered"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        tool.category = "finance"  # type: ignore[misc]

    res = ToolSelectionResult(
        selected_tools=(tool,),
        active_category="ci_cd",
        total_registered=1,
        selected_count=1,
        tokens_saved_estimate=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.active_category = "finance"  # type: ignore[misc]

    with pytest.raises(dataclasses.FrozenInstanceError):
        res.total_registered = 99  # type: ignore[misc]


def test_intent_category_classification() -> None:
    registry = DynamicToolRegistry()

    assert registry.classify_intent_category("") == "general"
    assert registry.classify_intent_category("   \n\t  ") == "general"
    assert registry.classify_intent_category("tell me a random story about clouds") == "general"

    # Single keyword match verification
    assert registry.classify_intent_category("wire") == "finance"
    assert registry.classify_intent_category("lint") == "ci_cd"

    assert registry.classify_intent_category("please run lint and test before PR commit") == "ci_cd"
    assert registry.classify_intent_category("execute wire transfer and payment escrow via x402") == "finance"
    assert registry.classify_intent_category("query dbsnp for gene variant and protein sequence") == "bio_genomics"
    assert registry.classify_intent_category("check ebpf lsm network socket and kill process") == "system"


def test_tool_registration_and_replacement() -> None:
    registry = DynamicToolRegistry(max_injected_tools=3)

    t1 = ToolDefinition("tool_a", "ci_cd", "v1", "{}", "T1", False)
    t1_updated = ToolDefinition("tool_a", "ci_cd", "v2", "{}", "T1", False)
    t2 = ToolDefinition("tool_b", "custom_cat", "custom tool", "{}", "T2", True)

    registry.register_tool(t1)
    assert len(registry._tools_by_name) == 1
    assert registry._tools_by_name["tool_a"].description == "v1"

    # Replacement by name updates tool in category list without duplication
    registry.register_tool(t1_updated)
    assert len(registry._tools_by_name) == 1
    assert registry._tools_by_name["tool_a"].description == "v2"
    assert len(registry._tools_by_category["ci_cd"]) == 1

    registry.register_tool(t2)
    assert len(registry._tools_by_name) == 2
    assert "custom_cat" in registry._tools_by_category


def test_context_slicing_and_token_saving() -> None:
    # Register 8 finance tools and 2 general tools
    finance_tools = [
        ToolDefinition(f"fin_tool_{i}", "finance", f"desc_{i}", "{}", "T2", True)
        for i in range(8)
    ]
    gen_tools = [
        ToolDefinition(f"gen_tool_{i}", "general", f"desc_{i}", "{}", "T1", False)
        for i in range(2)
    ]

    registry = DynamicToolRegistry(
        max_injected_tools=3,
        initial_tools=finance_tools + gen_tools,
    )

    # Classification picks finance and caps to 3
    res_fin = registry.select_tools_for_request("execute wire transfer to wallet")
    assert res_fin.active_category == "finance"
    assert res_fin.selected_count == 3
    assert len(res_fin.selected_tools) == 3
    assert res_fin.total_registered == 10
    # Tokens saved: (10 - 3) * 400 = 2800
    assert res_fin.tokens_saved_estimate == 2800

    # Force category
    res_forced = registry.select_tools_for_request("any prompt", force_category="general")
    assert res_forced.active_category == "general"
    assert res_forced.selected_count == 2
    assert res_forced.tokens_saved_estimate == (10 - 2) * 400

    # Fallback to general when an empty category is requested
    res_empty_cat = registry.select_tools_for_request("inspect ebpf lsm")
    assert res_empty_cat.active_category == "general"
    assert res_empty_cat.selected_count == 2

    # Default max_injected_tools (5) verification
    default_registry = DynamicToolRegistry()
    assert default_registry.max_injected_tools == 5
    for i in range(10):
        default_registry.register_tool(ToolDefinition(f"t_{i}", "system", "desc", "{}", "T1", False))
    res_def = default_registry.select_tools_for_request("inspect ebpf lsm process socket memory")
    assert res_def.selected_count == 5
    assert len(res_def.selected_tools) == 5
    assert res_def.tokens_saved_estimate == 5 * 400

    # Zero registered tools has zero tokens saved
    empty_reg = DynamicToolRegistry()
    res_zero = empty_reg.select_tools_for_request("anything")
    assert res_zero.total_registered == 0
    assert res_zero.selected_count == 0
    assert res_zero.tokens_saved_estimate == 0
