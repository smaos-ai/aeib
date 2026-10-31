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
tests/test_visual_regression_gate.py
================================================================================
Verification and falsification suite for VisualRegressionGate.
Evaluates pixel buffer divergence, perceptual tolerance thresholds, and receipt CAIDs.
"""

from __future__ import annotations

import dataclasses
import pytest

from src.visual_regression_gate import (
    VisualRegressionGate,
    VisualRegressionReceipt,
    VisualRegressionSpec,
    sha256_jcs_caid,
)


@pytest.fixture
def sample_spec() -> VisualRegressionSpec:
    # 4x4 image = 16 pixels
    golden_pixels = tuple([100] * 16)
    return VisualRegressionSpec(
        component_name="IconButton",
        golden_screenshot_caid="sha256:golden_icon_button_hash",
        golden_pixels=golden_pixels,
        width=4,
        height=4,
        max_divergence_bps=100,  # 1.00%
    )


def test_visual_regression_exact_bps_math() -> None:
    # 1x1 image
    spec = VisualRegressionSpec(
        component_name="Pixel",
        golden_screenshot_caid="caid_pixel",
        golden_pixels=(0,),
        width=1,
        height=1,
        max_divergence_bps=5000,
    )
    gate = VisualRegressionGate(spec)

    # 1. Total divergence: 255 diff out of 255 max -> exactly 10000 bps
    rcp_max = gate.evaluate_render([255])
    assert rcp_max.divergence_bps == 10000
    assert rcp_max.passed is False

    # 2. Exact fraction: 127 diff out of 255 max -> 127 * 10000 // 255 = 4980 bps <= 5000 -> passes!
    rcp_mid = gate.evaluate_render([127])
    assert rcp_mid.divergence_bps == 4980
    assert rcp_mid.passed is True

    # 3. Exactly 5000 bps boundary test
    # If max_divergence_bps is 4979, 4980 fails!
    gate_tight = VisualRegressionGate(
        VisualRegressionSpec(
            component_name="Pixel",
            golden_screenshot_caid="caid_pixel",
            golden_pixels=(0,),
            width=1,
            height=1,
            max_divergence_bps=4979,
        )
    )
    rcp_tight = gate_tight.evaluate_render([127])
    assert rcp_tight.divergence_bps == 4980
    assert rcp_tight.passed is False

    # 4. Single-pixel boundary precision test (Lesson L23 prime / non-trivial fraction)
    # 255 pixels, each gold=0. 1 pixel=1 -> total diff=1. max diff=255*255=65025.
    # 1 * 10000 // 65025 == 0 bps.
    # But for width=1, height=1: 1 diff out of 255 -> 1 * 10000 // 255 = 39 bps.
    # 2 diff out of 255 -> 2 * 10000 // 255 = 78 bps.
    gate_single = VisualRegressionGate(
        VisualRegressionSpec("P", "c", (0,), 1, 1, max_divergence_bps=100)
    )
    assert gate_single.evaluate_render([1]).divergence_bps == 39
    assert gate_single.evaluate_render([2]).divergence_bps == 78
    assert gate_single.evaluate_render([3]).divergence_bps == 117
    assert gate_single.evaluate_render([255]).divergence_bps == 10000


def test_visual_regression_nominal_pass(sample_spec: VisualRegressionSpec) -> None:
    gate = VisualRegressionGate(sample_spec)

    # Identical candidate pixels -> 0 bps divergence
    identical_pixels = [100] * 16
    receipt = gate.evaluate_render(identical_pixels)

    assert receipt.passed is True
    assert receipt.status_code == "OK_VISUAL_REGRESSION_SATISFIED"
    assert receipt.divergence_bps == 0
    assert receipt.golden_caid == "sha256:golden_icon_button_hash"
    assert receipt.receipt_caid.startswith("sha256:")
    assert isinstance(receipt.to_dict(), dict)

    # Invariant: frozen dataclass
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.passed = False  # type: ignore[misc]


def test_visual_regression_sub_threshold_drift_passes(
    sample_spec: VisualRegressionSpec,
) -> None:
    gate = VisualRegressionGate(sample_spec)

    # Max possible diff = 16 * 255 = 4080
    # A single pixel shifted by 10 units:
    # diff = 10 / 4080 = 24.5 bps (~24 bps <= 100 bps) -> passes!
    drift_pixels = [100] * 15 + [110]
    receipt = gate.evaluate_render(drift_pixels)

    assert receipt.passed is True
    assert receipt.status_code == "OK_VISUAL_REGRESSION_SATISFIED"
    assert receipt.divergence_bps > 0
    assert receipt.divergence_bps <= 100


def test_visual_regression_exceeding_threshold_halted(
    sample_spec: VisualRegressionSpec,
) -> None:
    gate = VisualRegressionGate(sample_spec)

    # Large difference: all pixels shifted from 100 to 200 (diff = 100 * 16 = 1600 / 4080 = ~3921 bps > 100 bps)
    divergent_pixels = [200] * 16
    receipt = gate.evaluate_render(divergent_pixels)

    assert receipt.passed is False
    assert "HALT_VISUAL_REGRESSION_DIVERGENCE" in receipt.status_code
    assert receipt.divergence_bps > 100


def test_visual_regression_dimension_mismatch(sample_spec: VisualRegressionSpec) -> None:
    gate = VisualRegressionGate(sample_spec)

    # Only 10 pixels instead of 16
    wrong_dimension_pixels = [100] * 10
    receipt = gate.evaluate_render(wrong_dimension_pixels)

    assert receipt.passed is False
    assert "HALT_RENDER_DIMENSION_MISMATCH" in receipt.status_code
    assert receipt.divergence_bps == 10000


def test_visual_regression_spec_validation() -> None:
    # CAID inputs
    assert sha256_jcs_caid(b"image_bytes").startswith("sha256:")
    assert sha256_jcs_caid("image_str").startswith("sha256:")

    # Default max_divergence_bps = 100
    spec_default = VisualRegressionSpec("Btn", "caid", (0, 0), 2, 1)
    assert spec_default.max_divergence_bps == 100

    # Explicit 0 bps is permitted
    spec_zero = VisualRegressionSpec("Btn", "caid", (0,), 1, 1, max_divergence_bps=0)
    assert spec_zero.max_divergence_bps == 0

    # Invariant: frozen spec
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec_default.width = 10  # type: ignore[misc]

    with pytest.raises(ValueError, match="ERR_INVALID_COMPONENT_NAME"):
        VisualRegressionSpec("", "caid", (0,), 1, 1)

    with pytest.raises(ValueError, match="ERR_INVALID_DIMENSIONS"):
        VisualRegressionSpec("Btn", "caid", (0,), 0, 1)

    with pytest.raises(ValueError, match="ERR_INVALID_DIMENSIONS"):
        VisualRegressionSpec("Btn", "caid", (0,), 1, -1)

    with pytest.raises(ValueError, match="ERR_PIXEL_BUFFER_DIMENSION_MISMATCH"):
        VisualRegressionSpec("Btn", "caid", (0, 0), 1, 1)

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_DIVERGENCE_BPS"):
        VisualRegressionSpec("Btn", "caid", (0,), 1, 1, max_divergence_bps=-1)

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_DIVERGENCE_BPS"):
        VisualRegressionSpec("Btn", "caid", (0,), 1, 1, max_divergence_bps=10001)
