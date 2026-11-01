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
tests/test_constraint_compiler.py
================================================================================
Falsification and verification suite for ConstraintCompiler.
Evaluates rejection of hardcoded literals, missing design tokens, dropped accessibility props,
and cyclomatic complexity explosion under zero mocks.
"""

from __future__ import annotations

import dataclasses
import pytest

from src.constraint_compiler import (
    ComponentConstraintSpec,
    ConstraintCompiler,
    ConstraintVerificationReceipt,
    sha256_jcs_caid,
)


@pytest.fixture
def button_spec() -> ComponentConstraintSpec:
    return ComponentConstraintSpec(
        constraint_id="spec_button_v1",
        component_name="DesignSystemButton",
        required_design_tokens=("token.color.primary", "token.spacing.md"),
        forbidden_css_literals=("#ff0000", "px", "rgb(255"),
        required_accessibility_props=("aria-label", "role"),
        max_cyclomatic_complexity=5,
    )


def test_1_compliant_component_passes(button_spec: ComponentConstraintSpec) -> None:
    compiler = ConstraintCompiler(button_spec)
    clean_code = (
        "def DesignSystemButton(props):\n"
        "    return create_element('button', {\n"
        "        'background': 'token.color.primary',\n"
        "        'padding': 'token.spacing.md',\n"
        "        'aria-label': props.label,\n"
        "        'role': 'button'\n"
        "    })\n"
    )
    receipt = compiler.verify_component_code(clean_code)
    assert receipt.passed is True
    assert receipt.status_code == "OK_CONSTRAINTS_SATISFIED"
    assert receipt.receipt_caid.startswith("sha256:")
    assert len(receipt.violations) == 0
    assert receipt.component_name == "DesignSystemButton"
    assert isinstance(receipt.to_dict(), dict)

    # Invariant: dataclasses are frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.passed = False  # type: ignore[misc]


def test_2_forbidden_literal_and_missing_token_tripped(
    button_spec: ComponentConstraintSpec,
) -> None:
    compiler = ConstraintCompiler(button_spec)
    non_compliant_code = (
        "def DesignSystemButton(props):\n"
        "    return create_element('button', {\n"
        "        'background': '#ff0000',\n"  # Forbidden hex literal
        "        'padding': '16px',\n"         # Forbidden 'px' literal and missing token
        "        'role': 'button'\n"           # Missing aria-label
        "    })\n"
    )
    receipt = compiler.verify_component_code(non_compliant_code)
    assert receipt.passed is False
    assert receipt.status_code == "HALT_COMPONENT_CONSTRAINT_VIOLATION"
    assert any("VIOLATION_FORBIDDEN_LITERAL:#ff0000" in v for v in receipt.violations)
    assert any("VIOLATION_MISSING_DESIGN_TOKEN:token.color.primary" in v for v in receipt.violations)
    assert any("VIOLATION_MISSING_ACCESSIBILITY_PROP:aria-label" in v for v in receipt.violations)


def test_3_syntax_error_and_empty_code_rejections(
    button_spec: ComponentConstraintSpec,
) -> None:
    compiler = ConstraintCompiler(button_spec)

    # Empty code
    rcp_empty = compiler.verify_component_code("   ")
    assert rcp_empty.passed is False
    assert rcp_empty.status_code == "HALT_EMPTY_SOURCE_CODE"
    assert "VIOLATION_EMPTY_SOURCE_CODE" in rcp_empty.violations

    # Syntax error
    rcp_syntax = compiler.verify_component_code("def broken( props: return 42")
    assert rcp_syntax.passed is False
    assert rcp_syntax.status_code == "HALT_SYNTAX_ERROR"
    assert any("VIOLATION_SYNTAX_ERROR" in v for v in rcp_syntax.violations)


def test_4_cyclomatic_complexity_rejection(button_spec: ComponentConstraintSpec) -> None:
    # Exact boundary test:
    # Base complexity with no branch: 1
    # Base with 1 branch: 2. With max_cyclomatic_complexity=2, it passes!
    spec_bound_2 = ComponentConstraintSpec(
        constraint_id="spec_bound",
        component_name="DesignSystemButton",
        required_design_tokens=("token.color.primary", "token.spacing.md"),
        forbidden_css_literals=(),
        required_accessibility_props=("role",),
        max_cyclomatic_complexity=2,
    )
    compiler_bound_2 = ConstraintCompiler(spec_bound_2)

    code_complexity_2 = (
        "def DesignSystemButton(props):\n"
        "    token_bg = 'token.color.primary'\n"
        "    token_pad = 'token.spacing.md'\n"
        "    if props.enabled:\n"
        "        pass\n"
        "    return create_element('button', role='button')\n"
    )
    rcp_pass_2 = compiler_bound_2.verify_component_code(code_complexity_2)
    assert rcp_pass_2.passed is True

    # With BoolOp 'and' (len(values) - 1 == 1), complexity becomes 1 + 1 (if) + 1 (and) = 3 > 2!
    code_complexity_3 = (
        "def DesignSystemButton(props):\n"
        "    token_bg = 'token.color.primary'\n"
        "    token_pad = 'token.spacing.md'\n"
        "    if props.enabled and props.visible:\n"
        "        pass\n"
        "    return create_element('button', role='button')\n"
    )
    rcp_fail_3 = compiler_bound_2.verify_component_code(code_complexity_3)
    assert rcp_fail_3.passed is False
    assert any("VIOLATION_CYCLOMATIC_COMPLEXITY:3_exceeds_2" in v for v in rcp_fail_3.violations)


def test_5_spec_validation() -> None:
    # Default complexity is 10
    default_spec = ComponentConstraintSpec("spec_default", "Button", (), (), ())
    assert default_spec.max_cyclomatic_complexity == 10

    # Invariant: ComponentConstraintSpec is frozen
    with pytest.raises(dataclasses.FrozenInstanceError):
        default_spec.max_cyclomatic_complexity = 20  # type: ignore[misc]

    # CAID inputs (bytes and string)
    assert sha256_jcs_caid(b"raw_bytes").startswith("sha256:")
    assert sha256_jcs_caid("string_payload").startswith("sha256:")

    # Dict with integer key (non-string key handled gracefully)
    code_int_key = (
        "def DesignSystemButton(props):\n"
        "    return create_element('button', {1: 'not_a_str'})\n"
    )
    rcp_int_key = ConstraintCompiler(default_spec).verify_component_code(code_int_key)
    assert rcp_int_key.passed is True

    with pytest.raises(ValueError, match="ERR_INVALID_SPEC_IDENTIFIERS"):
        ComponentConstraintSpec("", "Button", (), (), ())

    with pytest.raises(ValueError, match="ERR_INVALID_SPEC_IDENTIFIERS"):
        ComponentConstraintSpec("spec_1", "", (), (), ())

    # Explicit boundary test: max_cyclomatic_complexity=1 is allowed
    spec_min = ComponentConstraintSpec("spec_1", "Button", (), (), (), max_cyclomatic_complexity=1)
    assert spec_min.max_cyclomatic_complexity == 1

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_CYCLOMATIC_COMPLEXITY"):
        ComponentConstraintSpec("spec_1", "Button", (), (), (), max_cyclomatic_complexity=0)

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_CYCLOMATIC_COMPLEXITY"):
        ComponentConstraintSpec("spec_1", "Button", (), (), (), max_cyclomatic_complexity=-1)


def test_6_stealth_string_concatenation_detected(button_spec: ComponentConstraintSpec) -> None:
    compiler = ConstraintCompiler(button_spec)
    stealth_code = (
        "def DesignSystemButton(props):\n"
        "    color = '#ff' + '0000'\n"
        "    return create_element('button', {\n"
        "        'background': 'token.color.primary',\n"
        "        'padding': 'token.spacing.md',\n"
        "        'aria-label': 'btn',\n"
        "        'role': 'button'\n"
        "    })\n"
    )
    receipt = compiler.verify_component_code(stealth_code)
    assert receipt.passed is False
    assert any("VIOLATION_FORBIDDEN_LITERAL:#ff0000" in v for v in receipt.violations)

    clean_concat_code = (
        "def DesignSystemButton(props):\n"
        "    label = 'token.' + 'color.primary'\n"
        "    return create_element('button', {\n"
        "        'background': 'token.color.primary',\n"
        "        'padding': 'token.spacing.md',\n"
        "        'aria-label': 'btn',\n"
        "        'role': 'button'\n"
        "    })\n"
    )
    clean_rcp = compiler.verify_component_code(clean_concat_code)
    assert clean_rcp.passed is True
