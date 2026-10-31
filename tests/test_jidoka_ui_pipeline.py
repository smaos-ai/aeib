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
tests/test_jidoka_ui_pipeline.py
================================================================================
Verification and falsification suite for JidokaUIPipeline.
Tests closed-loop autonomous UI repair with real EO1 write-before-execute disk latches.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

import pytest

from src.constraint_compiler import ComponentConstraintSpec, ConstraintCompiler
from src.eo1_write_before_execute import EO1WriteBeforeExecuteLatch, LatchOutcome, LatchState
from src.jidoka_ui_pipeline import JidokaUIPipeline
from src.visual_regression_gate import VisualRegressionGate, VisualRegressionSpec


@pytest.fixture
def card_spec() -> ComponentConstraintSpec:
    return ComponentConstraintSpec(
        constraint_id="spec_card_v1",
        component_name="EnterpriseCard",
        required_design_tokens=("token.bg.surface", "token.text.primary"),
        forbidden_css_literals=("#ffffff", "12px"),
        required_accessibility_props=("role", "aria-labelledby"),
    )


def test_pipeline_forces_ai_compliance(card_spec: ComponentConstraintSpec) -> None:
    compiler = ConstraintCompiler(card_spec)

    def simulated_builder_llm(prompt: str, feedback: List[str]) -> str:
        if not feedback:
            # Non-compliant initial code
            return (
                "def EnterpriseCard(props):\n"
                "    return create_element('div', {\n"
                "        'background': '#ffffff',\n"  # VIOLATION: Forbidden literal
                "        'padding': '12px',\n"         # VIOLATION: Forbidden literal
                "        'role': 'card'\n"              # VIOLATION: Missing aria-labelledby
                "    })\n"
            )
        # Corrected code after receiving Andon Cord feedback
        return (
            "def EnterpriseCard(props):\n"
            "    return create_element('div', {\n"
            "        'background': 'token.bg.surface',\n"
            "        'text-color': 'token.text.primary',\n"
            "        'role': 'card',\n"
            "        'aria-labelledby': props.titleId\n"
            "    })\n"
        )

    with tempfile.TemporaryDirectory() as tmp:
        latch = EO1WriteBeforeExecuteLatch(Path(tmp))
        pipeline = JidokaUIPipeline(compiler, simulated_builder_llm, latch)

        success, final_code, receipt = pipeline.execute_regeneration("Create an EnterpriseCard")

        assert success is True
        assert "token.bg.surface" in final_code
        assert "#ffffff" not in final_code
        assert receipt.passed is True
        assert receipt.status_code == "OK_CONSTRAINTS_SATISFIED"


def test_pipeline_exhaustion_on_unfixed_violations(
    card_spec: ComponentConstraintSpec,
) -> None:
    compiler = ConstraintCompiler(card_spec)

    def stubborn_builder_llm(prompt: str, feedback: List[str]) -> str:
        return "def StubbornCard(props):\n    return create_element('div', {'color': '#ffffff'})\n"

    with tempfile.TemporaryDirectory() as tmp:
        latch = EO1WriteBeforeExecuteLatch(Path(tmp))
        pipeline = JidokaUIPipeline(compiler, stubborn_builder_llm, latch, max_retries=2)

        success, final_code, receipt = pipeline.execute_regeneration("Create a Card")

        assert success is False
        assert final_code == ""
        assert receipt.passed is False
        assert receipt.status_code == "HALT_COMPONENT_CONSTRAINT_VIOLATION"


def test_pipeline_eo1_latch_rejection(card_spec: ComponentConstraintSpec) -> None:
    compiler = ConstraintCompiler(card_spec)

    def clean_builder_llm(prompt: str, feedback: List[str]) -> str:
        return (
            "def EnterpriseCard(props):\n"
            "    return create_element('div', {\n"
            "        'background': 'token.bg.surface',\n"
            "        'text-color': 'token.text.primary',\n"
            "        'role': 'card',\n"
            "        'aria-labelledby': props.titleId\n"
            "    })\n"
        )

    class RejectingLatch(EO1WriteBeforeExecuteLatch):
        def execute(self, *args, **kwargs) -> LatchOutcome:  # type: ignore[no-untyped-def]
            return LatchOutcome(dispatched=False, state=LatchState.REJECTED, reason_code="DENIED_POLICY")

    with tempfile.TemporaryDirectory() as tmp:
        latch = RejectingLatch(Path(tmp))
        pipeline = JidokaUIPipeline(compiler, clean_builder_llm, latch)

        success, final_code, receipt = pipeline.execute_regeneration("Create an EnterpriseCard")
        assert success is False
        assert final_code == ""
        assert receipt.passed is True


def test_pipeline_validation(card_spec: ComponentConstraintSpec) -> None:
    compiler = ConstraintCompiler(card_spec)
    with tempfile.TemporaryDirectory() as tmp:
        latch = EO1WriteBeforeExecuteLatch(Path(tmp))
        default_pipe = JidokaUIPipeline(compiler, lambda p, f: "", latch)
        assert default_pipe.max_retries == 3

        # max_retries = 1 is valid and succeeds
        pipe_1 = JidokaUIPipeline(compiler, lambda p, f: "", latch, max_retries=1)
        assert pipe_1.max_retries == 1

        with pytest.raises(ValueError, match="ERR_INVALID_MAX_RETRIES"):
            JidokaUIPipeline(compiler, lambda p, f: "", latch, max_retries=0)

        with pytest.raises(ValueError, match="ERR_INVALID_MAX_RETRIES"):
            JidokaUIPipeline(compiler, lambda p, f: "", latch, max_retries=-1)


def test_pipeline_reconciled_committed_latch_state(
    card_spec: ComponentConstraintSpec,
) -> None:
    compiler = ConstraintCompiler(card_spec)

    def clean_builder_llm(prompt: str, feedback: List[str]) -> str:
        return (
            "def EnterpriseCard(props):\n"
            "    return create_element('div', {\n"
            "        'background': 'token.bg.surface',\n"
            "        'text-color': 'token.text.primary',\n"
            "        'role': 'card',\n"
            "        'aria-labelledby': props.titleId\n"
            "    })\n"
        )

    class ReconciledLatch(EO1WriteBeforeExecuteLatch):
        def execute(self, *args, **kwargs) -> LatchOutcome:  # type: ignore[no-untyped-def]
            return LatchOutcome(
                dispatched=False,
                state=LatchState.RECONCILED_COMMITTED,
                reason_code="OK_RECONCILED",
            )

    with tempfile.TemporaryDirectory() as tmp:
        latch = ReconciledLatch(Path(tmp))
        pipeline = JidokaUIPipeline(compiler, clean_builder_llm, latch)

        success, final_code, receipt = pipeline.execute_regeneration("Create an EnterpriseCard")
        assert success is True
        assert receipt.passed is True


def test_pipeline_visual_regression_gate_integration(
    card_spec: ComponentConstraintSpec,
) -> None:
    """Verifies that VisualRegressionGate pulls the Andon cord on visual drift even if AST passes."""
    compiler = ConstraintCompiler(card_spec)
    golden_pixels = tuple([100] * 16)  # 4x4 image
    vis_spec = VisualRegressionSpec(
        component_name="EnterpriseCard",
        golden_screenshot_caid="sha256:golden_card_hash",
        golden_pixels=golden_pixels,
        width=4,
        height=4,
        max_divergence_bps=100,  # 1.00%
    )
    vis_gate = VisualRegressionGate(vis_spec)

    compliant_code_ast = (
        "def EnterpriseCard(props):\n"
        "    return create_element('div', {\n"
        "        'background': 'token.bg.surface',\n"
        "        'text-color': 'token.text.primary',\n"
        "        'role': 'card',\n"
        "        'aria-labelledby': props.titleId\n"
        "    })\n"
    )

    attempt_count = 0

    def mock_builder_with_visual_repair(prompt: str, feedback: List[str]) -> str:
        nonlocal attempt_count
        attempt_count += 1
        return compliant_code_ast

    def mock_renderer(code: str) -> List[int]:
        if attempt_count == 1:
            # First attempt: AST passes, but visual pixels are completely black (255 diff -> 10000 bps)
            return [0] * 16
        # Second attempt: AI repaired CSS layout, pixels match golden baseline exactly
        return [100] * 16

    with tempfile.TemporaryDirectory() as tmp:
        latch = EO1WriteBeforeExecuteLatch(Path(tmp))
        pipeline = JidokaUIPipeline(
            compiler=compiler,
            builder_llm_fn=mock_builder_with_visual_repair,
            eo1_latch=latch,
            max_retries=3,
            visual_gate=vis_gate,
            renderer_fn=mock_renderer,
        )

        success, final_code, receipt = pipeline.execute_regeneration("Regenerate EnterpriseCard")

        assert success is True
        assert attempt_count == 2
        assert final_code == compliant_code_ast
        assert receipt.passed is True
        assert pipeline.last_visual_receipt is not None
        assert pipeline.last_visual_receipt.passed is True
        assert pipeline.last_visual_receipt.divergence_bps == 0

