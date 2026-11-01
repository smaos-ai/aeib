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
tests/test_headless_browser_sidecar.py
================================================================================
Verification and falsification suite for DOMRasterizer and HeadlessBrowserSidecar.
"""

from __future__ import annotations

import dataclasses
import importlib
from pathlib import Path
import sys
import pytest

from src.headless_browser_sidecar import (
    DOMRasterizer,
    DOMRasterResult,
    HeadlessBrowserSidecar,
)
from src.visual_regression_gate import VisualRegressionSpec, sha256_jcs_caid


def test_color_to_luma_conversions() -> None:
    # 0. Direct RGB parsing
    assert DOMRasterizer.parse_color_to_rgb("black") == (0, 0, 0)
    assert DOMRasterizer.parse_color_to_rgb("white") == (255, 255, 255)
    assert DOMRasterizer.parse_color_to_rgb("red") == (255, 0, 0)
    assert DOMRasterizer.parse_color_to_rgb("green") == (0, 255, 0)
    assert DOMRasterizer.parse_color_to_rgb("blue") == (0, 0, 255)
    assert DOMRasterizer.parse_color_to_rgb("gray") == (128, 128, 128)
    assert DOMRasterizer.parse_color_to_rgb("grey") == (128, 128, 128)
    assert DOMRasterizer.parse_color_to_rgb("#123") == (17, 34, 51)
    assert DOMRasterizer.parse_color_to_rgb("#00ff00") == (0, 255, 0)
    assert DOMRasterizer.parse_color_to_rgb("rgb(10, 20, 30)") == (10, 20, 30)
    assert DOMRasterizer.parse_color_to_rgb("rgb(0, 0, 0)") == (0, 0, 0)
    assert DOMRasterizer.parse_color_to_rgb("none") == (255, 255, 255)
    assert DOMRasterizer.parse_color_to_rgb("other") == (100, 100, 100)

    # 1. Transparent / none / empty defaults to 255 (white)
    assert DOMRasterizer.parse_color_to_luma("") == 255
    assert DOMRasterizer.parse_color_to_luma("none") == 255
    assert DOMRasterizer.parse_color_to_luma("transparent") == 255

    # 2. Named colors
    assert DOMRasterizer.parse_color_to_luma("black") == 0
    assert DOMRasterizer.parse_color_to_luma("white") == 255
    # Red: (255 * 299) // 1000 = 76
    assert DOMRasterizer.parse_color_to_luma("red") == 76
    # Green: (255 * 587) // 1000 = 149
    assert DOMRasterizer.parse_color_to_luma("green") == 149
    # Blue: (255 * 114) // 1000 = 29
    assert DOMRasterizer.parse_color_to_luma("blue") == 29
    assert DOMRasterizer.parse_color_to_luma("gray") == 128
    assert DOMRasterizer.parse_color_to_luma("grey") == 128
    # Fine-grained integer coefficient boundary checks (Lesson L23)
    assert DOMRasterizer.parse_color_to_luma("rgb(10, 0, 0)") == 2
    assert DOMRasterizer.parse_color_to_luma("rgb(201, 0, 0)") == 60
    assert DOMRasterizer.parse_color_to_luma("rgb(0, 201, 0)") == 117
    assert DOMRasterizer.parse_color_to_luma("rgb(0, 0, 100)") == 11

    # 3. Hex 3 and 6 chars
    assert DOMRasterizer.parse_color_to_luma("#000") == 0
    assert DOMRasterizer.parse_color_to_luma("#fff") == 255
    assert DOMRasterizer.parse_color_to_luma("#000000") == 0
    assert DOMRasterizer.parse_color_to_luma("#ffffff") == 255

    # 4. RGB format
    assert DOMRasterizer.parse_color_to_luma("rgb(255, 255, 255)") == 255
    assert DOMRasterizer.parse_color_to_luma("rgb(0, 0, 0)") == 0
    assert DOMRasterizer.parse_color_to_luma("rgba(255, 0, 0, 0.5)") == 76

    # 5. Fallback color
    assert DOMRasterizer.parse_color_to_luma("unknown_weird_color") == 100


def test_dom_raster_result_validation() -> None:
    # Invalid dimensions
    with pytest.raises(ValueError, match="ERR_INVALID_RASTER_DIMENSIONS"):
        DOMRasterResult(0, 10, (), "caid", 0, 0)
    with pytest.raises(ValueError, match="ERR_INVALID_RASTER_DIMENSIONS"):
        DOMRasterResult(10, 0, (), "caid", 0, 0)

    # Pixel buffer mismatch
    with pytest.raises(ValueError, match="ERR_PIXEL_BUFFER_SIZE_MISMATCH"):
        DOMRasterResult(2, 2, (255, 255), "caid", 1, 0)

    # Immutability
    res = DOMRasterResult(2, 2, (255, 255, 255, 255), "caid", 1, 0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        res.width = 4  # type: ignore[misc]


def test_rasterize_markup_shapes_and_colors() -> None:
    markup = """
    <svg width="20" height="20">
        <rect x="0" y="0" width="10" height="10" fill="black" />
        <rect x="10" y="10" width="10" height="10" fill="#ffffff" />
    </svg>
    """
    res = DOMRasterizer.rasterize_markup(markup, width=20, height=20)
    assert res.width == 20
    assert res.height == 20
    assert len(res.pixels) == 400
    assert res.element_count == 2
    assert res.invisible_element_count == 0

    # Top-left corner (0,0) should be black (0)
    assert res.pixels[0] == 0
    # Bottom-right corner (19,19) should be white (255)
    assert res.pixels[19 * 20 + 19] == 255
    # Bottom-left corner (0,19) was unpainted background -> white (255)
    assert res.pixels[19 * 20 + 0] == 255

    assert res.raster_caid.startswith("sha256:")

    # Canvas dimensions validation
    res_1x1 = DOMRasterizer.rasterize_markup('<rect fill="black"/>', width=1, height=1)
    assert res_1x1.width == 1
    assert res_1x1.height == 1
    assert res_1x1.pixels == (0,)

    # Default dimensions (100x100)
    res_default_dims = DOMRasterizer.rasterize_markup('<rect fill="black"/>')
    assert res_default_dims.width == 100
    assert res_default_dims.height == 100
    assert len(res_default_dims.pixels) == 10000

    with pytest.raises(ValueError, match="ERR_INVALID_CANVAS_DIMENSIONS"):
        DOMRasterizer.rasterize_markup(markup, width=-1, height=10)
    with pytest.raises(ValueError, match="ERR_INVALID_CANVAS_DIMENSIONS"):
        DOMRasterizer.rasterize_markup(markup, width=10, height=0)


def test_rasterize_invisible_element_detection() -> None:
    markup = """
    <div>
        <button style="opacity: 0; background: red;">Invisible Button</button>
        <span style="display: none; background: blue;">Hidden Span</span>
        <p style="visibility: hidden;">Hidden Text</p>
        <div style="background-color: black; width: 10; height: 10;">Visible Box</div>
    </div>
    """
    res = DOMRasterizer.rasterize_markup(markup, width=20, height=20)
    assert res.element_count == 4
    assert res.invisible_element_count == 3
    # The visible box should paint
    assert 0 in res.pixels


def test_headless_browser_sidecar_workflow() -> None:
    # Test default instantiation (100, 100)
    sidecar_default = HeadlessBrowserSidecar()
    assert sidecar_default.default_width == 100
    assert sidecar_default.default_height == 100
    res_default = sidecar_default.render_component('<button style="background: red;">Default</button>')
    assert res_default.width == 100
    assert res_default.height == 100
    # First pixel should be painted red (76)
    assert res_default.pixels[0] == 76

    sidecar = HeadlessBrowserSidecar(default_width=10, default_height=10)
    assert sidecar.default_width == 10
    assert sidecar.default_height == 10

    with pytest.raises(ValueError, match="ERR_INVALID_SIDECAR_DIMENSIONS"):
        HeadlessBrowserSidecar(default_width=0, default_height=10)

    markup = '<button style="background: black; x: 0; y: 0; width: 10; height: 10;">Click</button>'
    res = sidecar.render_component(markup)
    assert res.width == 10
    assert res.height == 10
    assert len(res.pixels) == 100

    # Create golden spec matching this exact render
    golden_spec = VisualRegressionSpec(
        component_name="PrimaryButton",
        golden_screenshot_caid=res.raster_caid,
        golden_pixels=res.pixels,
        width=10,
        height=10,
        max_divergence_bps=100,  # claim: config
    )

    # 1. Exact match evaluation passes
    receipt_ok = sidecar.evaluate_component_regression(golden_spec, markup)
    assert receipt_ok.passed is True
    assert receipt_ok.divergence_bps == 0
    assert receipt_ok.status_code == "OK_VISUAL_REGRESSION_SATISFIED"

    # 2. Mutated markup (e.g. background changed to white) diverges and fails
    mutated_markup = '<button style="background: white; x: 0; y: 0; width: 10; height: 10;">Click</button>'
    receipt_fail = sidecar.evaluate_component_regression(golden_spec, mutated_markup)
    assert receipt_fail.passed is False
    assert receipt_fail.divergence_bps > 100
    assert "HALT_VISUAL_REGRESSION_DIVERGENCE" in receipt_fail.status_code


def test_sys_path_bootstrap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies sys.path.insert(0) places repo root at index 0."""
    import src.headless_browser_sidecar as mod

    repo_str = str(Path(__file__).resolve().parent.parent)
    marker = ["/dummy_marker_sidecar"]
    monkeypatch.setattr(sys, "path", marker + [p for p in sys.path if p != repo_str])
    importlib.reload(mod)
    assert sys.path[0] == repo_str

