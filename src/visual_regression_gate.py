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
src/visual_regression_gate.py
================================================================================
Visual Regression & Perceptual Diff Gate (RVP - Regeneration & Verification Protocol).

Status: INTERNAL PREVIEW COMMISSIONED.
Evaluated under the stated model:
  - Compares rendered UI component pixel buffers against golden screenshots stored in HyperSU.
  - Computes deterministic perceptual pixel divergence in integer basis points (0..10000 bps).
  - Pulls the Jidoka Andon Cord when pixel divergence exceeds the configured threshold (default: 100 bps / 1.00%).
  - Zero floats RFC 8785 single-source JSON Canonicalization Scheme (JCS).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs


def sha256_jcs_caid(payload: Any) -> str:
    """Compute RFC 8785 SHA-256 CAID for bytes, string, or JSON-serializable structure."""
    if isinstance(payload, bytes):
        raw = payload
    elif isinstance(payload, str):
        raw = payload.encode("utf-8")
    else:
        raw = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


@dataclass(frozen=True)
class VisualRegressionSpec:
    """Specification of visual regression constraints for a UI component."""

    component_name: str
    golden_screenshot_caid: str
    golden_pixels: Tuple[int, ...]  # 8-bit grayscale values (0..255)
    width: int
    height: int
    max_divergence_bps: int = 100  # claim: config (Default 1.00% / 100 basis points)

    def __post_init__(self) -> None:
        if not self.component_name:
            raise ValueError("ERR_INVALID_COMPONENT_NAME")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ERR_INVALID_DIMENSIONS")
        expected_len = self.width * self.height
        if len(self.golden_pixels) != expected_len:
            raise ValueError("ERR_PIXEL_BUFFER_DIMENSION_MISMATCH")
        if self.max_divergence_bps < 0 or self.max_divergence_bps > 10000:
            raise ValueError("ERR_INVALID_MAX_DIVERGENCE_BPS")


@dataclass(frozen=True)
class VisualRegressionReceipt:
    """Deterministic cryptographic receipt for visual regression verification."""

    passed: bool
    status_code: str
    component_name: str
    divergence_bps: int
    golden_caid: str
    candidate_caid: str
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_caid": self.candidate_caid,
            "component_name": self.component_name,
            "divergence_bps": self.divergence_bps,
            "golden_caid": self.golden_caid,
            "passed": self.passed,
            "receipt_caid": self.receipt_caid,
            "status_code": self.status_code,
        }


class VisualRegressionGate:
    """
    Evaluates rendered component pixel buffers against golden baselines without external dependencies.
    """

    def __init__(self, spec: VisualRegressionSpec) -> None:
        self.spec = spec

    def evaluate_render(
        self, candidate_pixels: Sequence[int]
    ) -> VisualRegressionReceipt:
        expected_len = self.spec.width * self.spec.height
        if len(candidate_pixels) != expected_len:
            candidate_caid = "ERR_DIMENSION_MISMATCH"
            return self._mint(
                passed=False,
                status_code=f"HALT_RENDER_DIMENSION_MISMATCH:{len(candidate_pixels)}_expected_{expected_len}",
                divergence_bps=10000,  # claim: config
                candidate_caid=candidate_caid,
            )

        # Compute candidate CAID
        candidate_tuple = tuple(int(p) for p in candidate_pixels)
        candidate_caid = sha256_jcs_caid(list(candidate_tuple))

        # Absolute pixel difference across all coordinates
        total_abs_diff = 0
        for gold, cand in zip(self.spec.golden_pixels, candidate_tuple):
            total_abs_diff += abs(gold - cand)

        max_possible_diff = expected_len * 255
        diff_fraction = Fraction(total_abs_diff, max_possible_diff)
        divergence_bps = int(diff_fraction * 10000)

        passed = divergence_bps <= self.spec.max_divergence_bps
        if passed:
            status_code = "OK_VISUAL_REGRESSION_SATISFIED"
        else:
            status_code = f"HALT_VISUAL_REGRESSION_DIVERGENCE:{divergence_bps}_bps_exceeds_{self.spec.max_divergence_bps}_bps"

        return self._mint(
            passed=passed,
            status_code=status_code,
            divergence_bps=divergence_bps,
            candidate_caid=candidate_caid,
        )

    def _mint(
        self,
        passed: bool,
        status_code: str,
        divergence_bps: int,
        candidate_caid: str,
    ) -> VisualRegressionReceipt:
        payload = {
            "candidate_caid": candidate_caid,
            "component_name": self.spec.component_name,
            "divergence_bps": divergence_bps,
            "golden_caid": self.spec.golden_screenshot_caid,
            "passed": passed,
            "status_code": status_code,
        }
        return VisualRegressionReceipt(
            passed=passed,
            status_code=status_code,
            component_name=self.spec.component_name,
            divergence_bps=divergence_bps,
            golden_caid=self.spec.golden_screenshot_caid,
            candidate_caid=candidate_caid,
            receipt_caid=sha256_jcs_caid(payload),
        )
