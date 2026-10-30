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
src/figma_mcp_connector.py
================================================================================
Figma MCP Server Ingress Adapter & Design Token Constraint Compiler.

Status: INTERNAL PREVIEW COMMISSIONED.
Evaluated under the stated model:
  - Ingests Figma Model Context Protocol (MCP) `get_variable_defs` and `get_design_context` payloads.
  - Compiles raw Figma variables and styles into canonical ComponentConstraintSpec instances.
  - Automatically derives forbidden raw CSS literals from resolved token values to prevent AI hardcoding.
  - Zero floats in RFC 8785 single-source JSON Canonicalization Scheme (JCS).
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.constraint_compiler import ComponentConstraintSpec
from src.hypersu_consistent_latent_gate import sha256_jcs_caid
from src.jcs_canonicalizer import encode_jcs


@dataclass(frozen=True)
class FigmaVariableToken:
    """Represents a normalized design token derived from Figma MCP get_variable_defs."""

    variable_id: str
    raw_name: str
    resolved_type: str
    canonical_token_key: str
    derived_forbidden_literals: Tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.variable_id or not self.raw_name:
            raise ValueError("ERR_INVALID_VARIABLE_IDENTIFIER")
        if not self.canonical_token_key:
            raise ValueError("ERR_INVALID_CANONICAL_TOKEN_KEY")


class FigmaMCPConnector:
    """Ingests Figma MCP server payloads and compiles them into Jidoka verification specs."""

    @staticmethod
    def normalize_token_name(raw_name: str) -> str:
        """Converts Figma slash/space naming (e.g. 'Color/Brand/Primary') into 'token.color.brand.primary'."""
        cleaned = re.sub(r"[\s/\\_-]+", ".", raw_name.strip().lower())
        cleaned = re.sub(r"\.+", ".", cleaned).strip(".")
        if not cleaned:
            return "token.unknown"
        if not cleaned.startswith("token."):
            return f"token.{cleaned}"
        return cleaned

    @classmethod
    def derive_forbidden_literals_from_value(
        cls, resolved_type: str, raw_value: Any
    ) -> Tuple[str, ...]:
        """Derives raw CSS literals that the AI must NOT hardcode in lieu of using the token."""
        literals: List[str] = []
        r_type = str(resolved_type).upper()

        if r_type == "COLOR":
            if isinstance(raw_value, dict):
                # RGB dict format (normalized 0..1 or 0..255)
                r = raw_value.get("r", 0)
                g = raw_value.get("g", 0)
                b = raw_value.get("b", 0)
                r_int = int(r * 255) if isinstance(r, float) and r <= 1.0 else int(r)
                g_int = int(g * 255) if isinstance(g, float) and g <= 1.0 else int(g)
                b_int = int(b * 255) if isinstance(b, float) and b <= 1.0 else int(b)
                hex_code = f"#{r_int:02x}{g_int:02x}{b_int:02x}"
                literals.append(hex_code.lower())
                literals.append(f"rgb({r_int},{g_int},{b_int})")
                literals.append(f"rgb({r_int}, {g_int}, {b_int})")
            elif isinstance(raw_value, str) and raw_value.startswith("#"):
                literals.append(raw_value.strip().lower())

        elif r_type in ("FLOAT", "NUMBER"):
            if isinstance(raw_value, (int, float)):
                val_int = int(raw_value)
                literals.append(f"{val_int}px")
                literals.append(f"{val_int}pt")

        return tuple(sorted(set(literals)))

    @classmethod
    def parse_variable_defs_payload(
        cls, payload: Dict[str, Any]
    ) -> Tuple[FigmaVariableToken, ...]:
        """Parses Figma MCP `get_variable_defs` JSON output into validated tokens."""
        if not isinstance(payload, dict):
            raise ValueError("ERR_INVALID_FIGMA_PAYLOAD_STRUCTURE")

        variables_raw = payload.get("variables", [])
        if not isinstance(variables_raw, (list, tuple)):
            raise ValueError("ERR_INVALID_VARIABLES_ARRAY")

        parsed_tokens: List[FigmaVariableToken] = []

        for item in variables_raw:
            if not isinstance(item, dict):
                continue
            var_id = str(item.get("id", "")).strip()
            name = str(item.get("name", "")).strip()
            resolved_type = str(item.get("resolvedType", item.get("type", "STRING"))).strip().upper()
            raw_val = item.get("valuesByMode", {}).get("default", item.get("value"))

            if not var_id or not name:
                continue

            token_key = cls.normalize_token_name(name)
            forbidden = cls.derive_forbidden_literals_from_value(resolved_type, raw_val)

            token = FigmaVariableToken(
                variable_id=var_id,
                raw_name=name,
                resolved_type=resolved_type,
                canonical_token_key=token_key,
                derived_forbidden_literals=forbidden,
            )
            parsed_tokens.append(token)

        return tuple(parsed_tokens)

    @classmethod
    def compile_to_constraint_spec(
        cls,
        component_name: str,
        variable_defs_payload: Dict[str, Any],
        design_context_payload: Optional[Dict[str, Any]] = None,
        required_accessibility_props: Sequence[str] = ("role", "aria-label"),
        max_cyclomatic_complexity: int = 10,
    ) -> ComponentConstraintSpec:
        """Transforms Figma MCP variable definitions into an enforced ComponentConstraintSpec."""
        if not component_name or not component_name.strip():
            raise ValueError("ERR_EMPTY_COMPONENT_NAME")

        tokens = cls.parse_variable_defs_payload(variable_defs_payload)
        required_tokens: List[str] = [t.canonical_token_key for t in tokens]
        forbidden_literals: List[str] = []

        for t in tokens:
            forbidden_literals.extend(t.derived_forbidden_literals)

        # Baseline forbidden style constructs
        forbidden_literals.extend(["px", "style=", "!important"])

        # Inspect design context for required interactive accessibility roles
        inferred_a11y_props: List[str] = list(required_accessibility_props)
        if design_context_payload and isinstance(design_context_payload, dict):
            node_type = str(design_context_payload.get("type", "")).upper()
            if "BUTTON" in node_type or "INPUT" in node_type:
                if "role" not in inferred_a11y_props:
                    inferred_a11y_props.append("role")
                if "aria-label" not in inferred_a11y_props:
                    inferred_a11y_props.append("aria-label")

        constraint_id = f"figma_spec_{component_name.strip().lower()}"

        return ComponentConstraintSpec(
            constraint_id=constraint_id,
            component_name=component_name.strip(),
            required_design_tokens=tuple(sorted(set(required_tokens))),
            forbidden_css_literals=tuple(sorted(set(forbidden_literals))),
            required_accessibility_props=tuple(sorted(set(inferred_a11y_props))),
            max_cyclomatic_complexity=max_cyclomatic_complexity,
        )
