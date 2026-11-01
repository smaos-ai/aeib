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
tests/test_figma_mcp_connector.py
================================================================================
Verification and falsification suite for FigmaMCPConnector.
Tests Figma variable normalization, forbidden literal derivation, and constraint compilation.
"""

from __future__ import annotations

import dataclasses
import importlib
from pathlib import Path
import sys
import pytest

from src.figma_mcp_connector import FigmaMCPConnector, FigmaVariableToken


def test_figma_token_name_normalization() -> None:
    assert FigmaMCPConnector.normalize_token_name("Color/Brand/Primary") == "token.color.brand.primary"
    assert FigmaMCPConnector.normalize_token_name("Spacing / md-padding") == "token.spacing.md.padding"
    assert FigmaMCPConnector.normalize_token_name("token.radius.sm") == "token.radius.sm"
    assert FigmaMCPConnector.normalize_token_name("   ") == "token.unknown"


def test_derive_forbidden_literals_from_figma_variables() -> None:
    # 1. Color from float RGB (0..1)
    rgb_float = {"r": 1.0, "g": 0.0, "b": 0.0}
    lits_color = FigmaMCPConnector.derive_forbidden_literals_from_value("COLOR", rgb_float)
    assert "#ff0000" in lits_color
    assert "rgb(255,0,0)" in lits_color
    assert "rgb(255, 0, 0)" in lits_color

    # 1b. Color from 0..255 integer RGB and empty dict defaults
    rgb_int = {"r": 200, "g": 100, "b": 50}
    lits_int = FigmaMCPConnector.derive_forbidden_literals_from_value("COLOR", rgb_int)
    assert "#c86432" in lits_int
    assert "rgb(200, 100, 50)" in lits_int

    # 1c. Color from float RGB > 1.0 (raw unnormalized float values)
    rgb_float_large = {"r": 255.0, "g": 128.0, "b": 64.0}
    lits_large = FigmaMCPConnector.derive_forbidden_literals_from_value("COLOR", rgb_float_large)
    assert "#ff8040" in lits_large
    assert "rgb(255, 128, 64)" in lits_large

    # 1d. Color from mixed float and int RGB
    rgb_mixed = {"r": 0.5, "g": 100, "b": 200.0}
    lits_mixed = FigmaMCPConnector.derive_forbidden_literals_from_value("COLOR", rgb_mixed)
    assert "rgb(127, 100, 200)" in lits_mixed

    rgb_empty = {}
    lits_empty = FigmaMCPConnector.derive_forbidden_literals_from_value("COLOR", rgb_empty)
    assert "#000000" in lits_empty

    # 2. Color from hex string vs non-hex string
    lits_hex = FigmaMCPConnector.derive_forbidden_literals_from_value("COLOR", "#00ff00")
    assert "#00ff00" in lits_hex
    lits_named = FigmaMCPConnector.derive_forbidden_literals_from_value("COLOR", "transparent")
    assert len(lits_named) == 0

    # 3. Number/Float to px/pt literals
    lits_num = FigmaMCPConnector.derive_forbidden_literals_from_value("FLOAT", 16)
    assert "16px" in lits_num
    assert "16pt" in lits_num

    # 4. Unknown type returns empty
    lits_none = FigmaMCPConnector.derive_forbidden_literals_from_value("UNKNOWN_TYPE", "val")
    assert len(lits_none) == 0


def test_figma_variable_token_post_init_validation() -> None:
    with pytest.raises(ValueError, match="ERR_INVALID_VARIABLE_IDENTIFIER"):
        FigmaVariableToken("", "name", "COLOR", "token.color", ())

    with pytest.raises(ValueError, match="ERR_INVALID_VARIABLE_IDENTIFIER"):
        FigmaVariableToken("v1", "", "COLOR", "token.color", ())

    with pytest.raises(ValueError, match="ERR_INVALID_CANONICAL_TOKEN_KEY"):
        FigmaVariableToken("v1", "name", "COLOR", "", ())


def test_parse_variable_defs_and_validation() -> None:
    payload = {
        "variables": [
            {
                "id": "var_1",
                "name": "Color/Surface/Card",
                "resolvedType": "COLOR",
                "valuesByMode": {"default": {"r": 0.1, "g": 0.1, "b": 0.1}},
            },
            {
                "id": "var_2",
                "name": "Spacing/Gap/lg",
                "resolvedType": "FLOAT",
                "valuesByMode": {"default": 24},
            },
            {
                "id": "",  # Missing ID -> skipped
                "name": "Invalid",
            },
        ]
    }
    tokens = FigmaMCPConnector.parse_variable_defs_payload(payload)
    assert len(tokens) == 2
    assert tokens[0].canonical_token_key == "token.color.surface.card"
    assert tokens[1].canonical_token_key == "token.spacing.gap.lg"
    assert "24px" in tokens[1].derived_forbidden_literals

    # Invariant: dataclass is frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        tokens[0].canonical_token_key = "tampered"  # type: ignore[misc]

    # Malformed payload structure
    with pytest.raises(ValueError, match="ERR_INVALID_FIGMA_PAYLOAD_STRUCTURE"):
        FigmaMCPConnector.parse_variable_defs_payload("not_a_dict")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="ERR_INVALID_VARIABLES_ARRAY"):
        FigmaMCPConnector.parse_variable_defs_payload({"variables": "not_a_list"})


def test_compile_to_constraint_spec() -> None:
    var_payload = {
        "variables": [
            {
                "id": "v1",
                "name": "Color/Accent",
                "resolvedType": "COLOR",
                "valuesByMode": {"default": {"r": 0.0, "g": 0.5, "b": 1.0}},
            }
        ]
    }
    design_ctx = {
        "type": "FRAME_BUTTON_PRIMARY",
        "name": "SubmitButton",
    }

    spec = FigmaMCPConnector.compile_to_constraint_spec(
        component_name="SubmitButton",
        variable_defs_payload=var_payload,
        design_context_payload=design_ctx,
        required_accessibility_props=("role",),
        max_cyclomatic_complexity=8,
    )

    assert spec.component_name == "SubmitButton"
    assert spec.constraint_id == "figma_spec_submitbutton"
    assert "token.color.accent" in spec.required_design_tokens
    assert "#007fff" in spec.forbidden_css_literals
    assert "px" in spec.forbidden_css_literals
    assert "role" in spec.required_accessibility_props
    assert "aria-label" in spec.required_accessibility_props  # Inferred from BUTTON
    assert spec.max_cyclomatic_complexity == 8

    # Inferred accessibility props when base required props are empty
    spec_input = FigmaMCPConnector.compile_to_constraint_spec(
        component_name="SearchInput",
        variable_defs_payload=var_payload,
        design_context_payload={"type": "FRAME_INPUT_FIELD"},
        required_accessibility_props=(),
    )
    assert "role" in spec_input.required_accessibility_props
    assert "aria-label" in spec_input.required_accessibility_props

    with pytest.raises(ValueError, match="ERR_EMPTY_COMPONENT_NAME"):
        FigmaMCPConnector.compile_to_constraint_spec("", var_payload)


def test_sys_path_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies sys.path.insert(0) places repo root at index 0."""
    import src.figma_mcp_connector as mod

    repo_str = str(Path(__file__).resolve().parent.parent)
    marker = ["/dummy_marker_figma"]
    monkeypatch.setattr(sys, "path", marker + [p for p in sys.path if p != repo_str])
    importlib.reload(mod)
    assert sys.path[0] == repo_str

