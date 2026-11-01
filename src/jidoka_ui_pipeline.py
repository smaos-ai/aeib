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
src/jidoka_ui_pipeline.py
================================================================================
Jidoka UI Pipeline: Regeneration & Verification Protocol (RVP).

Status: INTERNAL PREVIEW COMMISSIONED.
Evaluated under the stated model:
  - Closed-loop autonomous regeneration of UI components.
  - Zero-token deterministic constraint verification before commit.
  - Jidoka Andon Cord: violations feed back directly into generator self-repair.
  - EO1 Write-Before-Execute Pre-Dispatch Interlock commits verified components to disk.
"""

from __future__ import annotations

import sys
from typing import Callable, List, Optional, Sequence, Tuple

from src.constraint_compiler import (
    ComponentConstraintSpec,
    ConstraintCompiler,
    ConstraintVerificationReceipt,
)
from src.eo1_write_before_execute import EO1WriteBeforeExecuteLatch, LatchState
from src.visual_regression_gate import VisualRegressionGate, VisualRegressionReceipt


class JidokaUIPipeline:
    """
    Coordinates autonomous UI component regeneration with deterministic AST verification,
    optional visual regression gate diffing, and EO1 write-before-execute latching.
    """

    def __init__(
        self,
        compiler: ConstraintCompiler,
        builder_llm_fn: Callable[[str, List[str]], str],
        eo1_latch: EO1WriteBeforeExecuteLatch,
        max_retries: int = 3,
        visual_gate: Optional[VisualRegressionGate] = None,
        renderer_fn: Optional[Callable[[str], Sequence[int]]] = None,
    ) -> None:
        if max_retries <= 0:
            raise ValueError("ERR_INVALID_MAX_RETRIES")
        self.compiler = compiler
        self.builder_llm_fn = builder_llm_fn
        self.eo1_latch = eo1_latch
        self.max_retries = max_retries
        self.visual_gate = visual_gate
        self.renderer_fn = renderer_fn
        self.last_visual_receipt: Optional[VisualRegressionReceipt] = None

    def execute_regeneration(
        self, prompt: str
    ) -> Tuple[bool, str, ConstraintVerificationReceipt]:
        """
        Executes bounded iterative repair loop (B <= max_retries) to satisfy constraints.
        """
        feedback: List[str] = []
        last_receipt: Optional[ConstraintVerificationReceipt] = None
        self.last_visual_receipt = None

        for _ in range(self.max_retries):
            # 1. Builder generates candidate component code
            raw_code = self.builder_llm_fn(prompt, feedback)

            # 2. Constraint Compiler verifies deterministically
            receipt = self.compiler.verify_component_code(raw_code)
            last_receipt = receipt

            if receipt.passed:
                # 2b. Optional Visual Regression Gate check
                if self.visual_gate is not None and self.renderer_fn is not None:
                    candidate_pixels = self.renderer_fn(raw_code)
                    vis_receipt = self.visual_gate.evaluate_render(candidate_pixels)
                    self.last_visual_receipt = vis_receipt
                    if not vis_receipt.passed:
                        feedback.append(f"VIOLATION_VISUAL_REGRESSION:{vis_receipt.status_code}")
                        continue

                # 3. EO1 Latch Commit (Write-Before-Execute)
                caid = f"ui-commit:{receipt.receipt_caid}"
                outcome = self.eo1_latch.execute(
                    tool_name="factory.merge_ui_component",
                    canonical_payload={
                        "code_hash": receipt.receipt_caid,
                        "component": self.compiler.spec.component_name,
                    },
                    dispatch_fn=lambda: {"status": "committed"},
                    intent_id=caid,
                )

                if outcome.dispatched or outcome.state in (
                    LatchState.COMMITTED,
                    LatchState.RECONCILED_COMMITTED,
                ):
                    return True, raw_code, receipt
                return False, "", receipt

            # Andon cord feedback
            feedback.extend(receipt.violations)

        assert last_receipt is not None
        return False, "", last_receipt
