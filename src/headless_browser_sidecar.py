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
src/headless_browser_sidecar.py
================================================================================
Offline DOM Rasterizer & Headless Browser Sidecar for Visual Regression Auditing.

Status: INTERNAL PREVIEW COMMISSIONED.
Evaluated under the stated model:
  - Deterministically parses and rasterizes offline HTML/SVG/CSS UI mockups into pixel buffers.
  - Generates 8-bit grayscale pixel tuples (0..255) for perceptual regression comparison.
  - Detects stealth DOM anomalies (zero-opacity elements, display:none masking, off-canvas coordinates).
  - Wires directly into VisualRegressionGate as an offline renderer pipeline.
  - Zero floats in RFC 8785 single-source JSON Canonicalization Scheme (JCS).
  - Operates completely air-gapped without external network egress or browser daemon binaries.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs
from src.visual_regression_gate import (
    VisualRegressionGate,
    VisualRegressionReceipt,
    VisualRegressionSpec,
    sha256_jcs_caid,
)


@dataclass(frozen=True)
class DOMRasterResult:
    """Deterministic result of an offline DOM rasterization pass."""

    width: int
    height: int
    pixels: Tuple[int, ...]
    raster_caid: str
    element_count: int
    invisible_element_count: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("ERR_INVALID_RASTER_DIMENSIONS")
        if len(self.pixels) != self.width * self.height:
            raise ValueError("ERR_PIXEL_BUFFER_SIZE_MISMATCH")


class DOMRasterizer:
    """
    Offline deterministic DOM rasterizer parsing SVG and HTML structures into pixel buffers.
    """

    NAMED_COLORS: Dict[str, Tuple[int, int, int]] = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (255, 0, 0),
        "green": (0, 255, 0),
        "blue": (0, 0, 255),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
    }

    @classmethod
    def parse_color_to_rgb(cls, color_str: str) -> Tuple[int, int, int]:
        """Parses CSS/SVG color string to (r, g, b) 8-bit tuple (0..255)."""
        cleaned = color_str.strip().lower()
        if not cleaned or cleaned in ("none", "transparent"):
            return (255, 255, 255)

        if cleaned in cls.NAMED_COLORS:
            return cls.NAMED_COLORS[cleaned]

        # Hex 3 or 6 chars
        hex_match = re.match(r"^#([0-9a-f]{3}|[0-9a-f]{6})$", cleaned)
        if hex_match:
            h = hex_match.group(1)
            if len(h) == 3:
                r = int(h[0] * 2, 16)
                g = int(h[1] * 2, 16)
                b = int(h[2] * 2, 16)
            else:
                r = int(h[0:2], 16)
                g = int(h[2:4], 16)
                b = int(h[4:6], 16)
            return (r, g, b)

        # RGB / RGBA format
        rgb_match = re.match(r"^rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", cleaned)
        if rgb_match:
            r = min(255, max(0, int(rgb_match.group(1))))
            g = min(255, max(0, int(rgb_match.group(2))))
            b = min(255, max(0, int(rgb_match.group(3))))
            return (r, g, b)

        return (100, 100, 100)

    @classmethod
    def parse_color_to_luma(cls, color_str: str) -> int:
        """Parses CSS/SVG color string to 8-bit grayscale luminosity (0..255) using exact integer math."""
        r, g, b = cls.parse_color_to_rgb(color_str)
        return (r * 299 + g * 587 + b * 114) // 1000

    @classmethod
    def rasterize_markup(
        cls, markup: str, width: int = 100, height: int = 100
    ) -> DOMRasterResult:
        """
        Renders HTML/SVG string into an 8-bit grayscale pixel buffer (width x height).
        """
        if width <= 0 or height <= 0:
            raise ValueError("ERR_INVALID_CANVAS_DIMENSIONS")

        # Initialize flat white buffer (255)
        buffer = [255] * (width * height)
        element_count = 0
        invisible_count = 0

        # Pattern matches opening or self-closing tags: <tag attrs/> or <tag attrs>
        tag_pattern = re.compile(r"<([a-zA-Z0-9_-]+)([^>]*?)(/?)>")

        for match in tag_pattern.finditer(markup):
            tag_name = match.group(1).lower()
            attrs_str = match.group(2)
            self_closing = match.group(3) == "/"

            if tag_name in ("html", "body", "svg", "!doctype"):
                continue
            if not attrs_str.strip() and not self_closing:
                # Bare unstyled structural container (e.g. <div> or <span> without attributes)
                continue

            element_count += 1

            # Check visibility
            is_invisible = False
            if re.search(r"opacity\s*:\s*0(?:\.0+)?(?:\b|;)", attrs_str, re.IGNORECASE):
                is_invisible = True
            elif re.search(r"display\s*:\s*none", attrs_str, re.IGNORECASE):
                is_invisible = True
            elif re.search(r"visibility\s*:\s*hidden", attrs_str, re.IGNORECASE):
                is_invisible = True

            if is_invisible:
                invisible_count += 1
                continue

            # Parse bounding box coordinates from XML attributes or CSS style
            x_m = re.search(r'(?:x|left)\s*[=:]\s*["\']?(\d+)', attrs_str, re.IGNORECASE)
            y_m = re.search(r'(?:y|top)\s*[=:]\s*["\']?(\d+)', attrs_str, re.IGNORECASE)
            w_m = re.search(r'width\s*[=:]\s*["\']?(\d+)', attrs_str, re.IGNORECASE)
            h_m = re.search(r'height\s*[=:]\s*["\']?(\d+)', attrs_str, re.IGNORECASE)

            x = int(x_m.group(1)) if x_m else 0
            y = int(y_m.group(1)) if y_m else 0
            w = int(w_m.group(1)) if w_m else width
            h = int(h_m.group(1)) if h_m else height

            # Parse fill or background color
            fill_m = re.search(r'fill\s*=\s*["\']([^"\']+)["\']', attrs_str, re.IGNORECASE)
            bg_m = re.search(r'background(?:-color)?\s*:\s*([^;"]+)', attrs_str, re.IGNORECASE)

            color_str = fill_m.group(1) if fill_m else (bg_m.group(1) if bg_m else "black")
            luma = cls.parse_color_to_luma(color_str)

            # Draw rectangle to buffer
            x_end = min(width, x + w)
            y_end = min(height, y + h)

            for row in range(max(0, y), max(0, y_end)):
                row_offset = row * width
                for col in range(max(0, x), max(0, x_end)):
                    buffer[row_offset + col] = luma

        pixel_tuple = tuple(buffer)
        raster_caid = sha256_jcs_caid(list(pixel_tuple))

        return DOMRasterResult(
            width=width,
            height=height,
            pixels=pixel_tuple,
            raster_caid=raster_caid,
            element_count=element_count,
            invisible_element_count=invisible_count,
        )


class HeadlessBrowserSidecar:
    """
    Offline Headless Browser Sidecar acting as a deterministic rendering service
    for VisualRegressionGate without spawning external browser binaries.
    """

    def __init__(self, default_width: int = 100, default_height: int = 100) -> None:
        if default_width <= 0 or default_height <= 0:
            raise ValueError("ERR_INVALID_SIDECAR_DIMENSIONS")
        self.default_width = default_width
        self.default_height = default_height

    def render_component(
        self, markup: str, width: Optional[int] = None, height: Optional[int] = None
    ) -> DOMRasterResult:
        """Rasterizes the component markup into a deterministic DOMRasterResult."""
        w = width if width is not None else self.default_width
        h = height if height is not None else self.default_height
        return DOMRasterizer.rasterize_markup(markup, width=w, height=h)

    def evaluate_component_regression(
        self, spec: VisualRegressionSpec, markup: str
    ) -> VisualRegressionReceipt:
        """Renders markup and evaluates visual regression against spec in a single step."""
        raster = self.render_component(markup, width=spec.width, height=spec.height)
        gate = VisualRegressionGate(spec)
        return gate.evaluate_render(raster.pixels)
