#!/usr/bin/env python3
"""
src/bpf_lsm_profile_compiler.py
================================================================================
Linux Kernel BPF_LSM Security Profile Compiler & Static Policy Linter.

Prototype / Pre-Production Scaffold evaluated under the stated model.
Preserves strict epistemic calibration and zero external dependencies.

Operational Scope:
  Parses Cilium Tetragon TracingPolicy YAML specifications, verifies compliance
  against Linux kernel BTF definitions and LSM hook constraints, detects
  permissive bypasses or type mismatches, and compiles valid configurations
  into an RFC 8785 canonical signed BPF_LSM Security Profile Manifest.

Failure Modes (Fails Closed):
  - HALT_INVALID_LSM_HOOK: Unknown or unvetted LSM hook call.
  - HALT_ARGUMENT_TYPE_MISMATCH: Argument index/type mismatch or missing selectors.
  - HALT_PERMISSIVE_BYPASS_DETECTED: Permissive wildcard egress or unrestricted write.
================================================================================
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

COMPILER_VERSION = "1.0.0-scaffold"

# ------------------------------------------------------------------------------
# 1. Deterministic Halt Codes & Custom Exceptions
# ------------------------------------------------------------------------------

HALT_INVALID_LSM_HOOK = "HALT_INVALID_LSM_HOOK"
HALT_ARGUMENT_TYPE_MISMATCH = "HALT_ARGUMENT_TYPE_MISMATCH"
HALT_PERMISSIVE_BYPASS_DETECTED = "HALT_PERMISSIVE_BYPASS_DETECTED"


class BPFLSMValidationError(Exception):
    """Raised when a Tetragon TracingPolicy violates kernel LSM safety constraints."""

    def __init__(self, halt_code: str, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(f"[{halt_code}] {message}")
        self.halt_code = halt_code
        self.message = message
        self.context = context or {}


# ------------------------------------------------------------------------------
# 2. Linux Kernel BTF Definitions & LSM Hook Specification
# ------------------------------------------------------------------------------

KNOWN_LSM_HOOKS: Dict[str, Dict[str, Any]] = {
    "security_socket_connect": {
        "description": "Kernel Socket Egress Trap",
        "btf_args": {
            0: ["sock", "struct socket *", "struct sock *"],
            1: ["sockaddr", "struct sockaddr *"],
            2: ["int"],
        },
        "requires_non_empty_selectors": True,
    },
    "security_file_open": {
        "description": "Kernel File Access & Policy Immutability Guard",
        "btf_args": {
            0: ["file", "struct file *"],
        },
        "requires_non_empty_selectors": True,
    },
    "bprm_check_security": {
        "description": "Binary Execution Verification Hook",
        "btf_args": {
            0: ["linux_binprm", "struct linux_binprm *"],
        },
        "requires_non_empty_selectors": True,
    },
    "file_mprotect": {
        "description": "Memory Page Protection Control Hook",
        "btf_args": {
            0: ["vm_area_struct", "struct vm_area_struct *"],
            1: ["unsigned long"],
            2: ["unsigned long"],
        },
        "requires_non_empty_selectors": True,
    },
    "task_alloc": {
        "description": "Task Allocation Hook",
        "btf_args": {
            0: ["task", "task_struct", "struct task_struct *"],
            1: ["unsigned long"],
        },
        "requires_non_empty_selectors": True,
    },
    "security_sb_mount": {
        "description": "Superblock Mount Hook",
        "btf_args": {
            0: ["string", "char", "const char *"],
            1: ["path", "struct path *", "const struct path *"],
        },
        "requires_non_empty_selectors": True,
    },
}

VALID_ARG_TYPES: Set[str] = {
    "sock",
    "sockaddr",
    "file",
    "linux_binprm",
    "vm_area_struct",
    "task",
    "task_struct",
    "string",
    "char",
    "path",
    "int",
    "unsigned long",
}

VALID_OPERATORS: Set[str] = {
    "In",
    "NotIn",
    "Prefix",
    "Postfix",
    "HasAny",
    "DAddr",
    "NotDAddr",
}

VALID_ACTIONS: Set[str] = {
    "Override",
    "Post",
    "Sigkill",
}


# ------------------------------------------------------------------------------
# 3. Pure Python YAML Parser for TracingPolicy Specifications
# ------------------------------------------------------------------------------

def parse_yaml_tracing_policy(text: str) -> Dict[str, Any]:
    """
    Parses a Cilium Tetragon TracingPolicy YAML document in pure Python.
    Avoids external dependencies like PyYAML.
    """
    raw_lines = text.splitlines()
    tokens: List[Tuple[int, str, int]] = []
    for line_num, raw in enumerate(raw_lines, 1):
        cleaned = ""
        in_quote = False
        quote_char = ""
        for ch in raw:
            if ch in ("\"", "'"):
                if in_quote and ch == quote_char:
                    in_quote = False
                elif not in_quote:
                    in_quote = True
                    quote_char = ch
            elif ch == "#" and not in_quote:
                break
            cleaned += ch
        stripped_line = cleaned.rstrip()
        if stripped_line.strip():
            indent = len(stripped_line) - len(stripped_line.lstrip(" "))
            tokens.append((indent, stripped_line.strip(), line_num))

    def _parse_scalar(val: str) -> Any:
        v = val.strip()
        if (v.startswith("\"") and v.endswith("\"")) or (v.startswith("'") and v.endswith("'")):
            return v[1:-1]
        if v.lower() == "true":
            return True
        if v.lower() == "false":
            return False
        if v.lower() in ("null", "~"):
            return None
        try:
            return int(v)
        except ValueError:
            pass
        try:
            return float(v)
        except ValueError:
            pass
        return v

    def _parse_list(idx: int, list_indent: int) -> Tuple[List[Any], int]:
        items: List[Any] = []
        while idx < len(tokens):
            ind, text_line, _ = tokens[idx]
            if ind < list_indent:
                break
            if ind == list_indent and text_line.startswith("-"):
                after_dash = text_line[1:].strip()
                idx += 1
                if not after_dash:
                    if idx < len(tokens):
                        sub_ind = tokens[idx][0]
                        val, idx = _parse_any(idx, sub_ind)
                        items.append(val)
                elif ":" in after_dash and not (after_dash.startswith("\"") or after_dash.startswith("'")):
                    k, v = after_dash.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    item_dict: Dict[str, Any] = {}
                    item_dict_indent = ind + 2
                    if v:
                        item_dict[k] = _parse_scalar(v)
                    else:
                        if idx < len(tokens) and tokens[idx][0] >= item_dict_indent:
                            sub_ind = tokens[idx][0]
                            val, idx = _parse_any(idx, sub_ind)
                            item_dict[k] = val
                        else:
                            item_dict[k] = None
                    while idx < len(tokens):
                        c_ind, c_text, _ = tokens[idx]
                        if c_ind < item_dict_indent:
                            break
                        if c_text.startswith("-"):
                            break
                        if ":" in c_text:
                            dk, dv = c_text.split(":", 1)
                            dk = dk.strip()
                            dv = dv.strip()
                            idx += 1
                            if dv:
                                item_dict[dk] = _parse_scalar(dv)
                            else:
                                if idx < len(tokens) and tokens[idx][0] > c_ind:
                                    sub_ind = tokens[idx][0]
                                    val, idx = _parse_any(idx, sub_ind)
                                    item_dict[dk] = val
                                else:
                                    item_dict[dk] = None
                        else:
                            break
                    items.append(item_dict)
                else:
                    items.append(_parse_scalar(after_dash))
            else:
                break
        return items, idx

    def _parse_dict(idx: int, dict_indent: int) -> Tuple[Dict[str, Any], int]:
        res: Dict[str, Any] = {}
        while idx < len(tokens):
            ind, text_line, _ = tokens[idx]
            if ind < dict_indent:
                break
            if ind == dict_indent and ":" in text_line and not text_line.startswith("-"):
                k, v = text_line.split(":", 1)
                k = k.strip()
                v = v.strip()
                idx += 1
                if v:
                    res[k] = _parse_scalar(v)
                else:
                    if idx < len(tokens) and tokens[idx][0] > ind:
                        sub_ind = tokens[idx][0]
                        val, idx = _parse_any(idx, sub_ind)
                        res[k] = val
                    else:
                        res[k] = None
            else:
                break
        return res, idx

    def _parse_any(idx: int, ind: int) -> Tuple[Any, int]:
        if idx >= len(tokens):
            return None, idx
        _, cur_text, _ = tokens[idx]
        if cur_text.startswith("-"):
            return _parse_list(idx, tokens[idx][0])
        else:
            return _parse_dict(idx, tokens[idx][0])

    parsed, _ = _parse_any(0, 0)
    if not isinstance(parsed, dict):
        raise BPFLSMValidationError(HALT_ARGUMENT_TYPE_MISMATCH, "TracingPolicy root must be a YAML mapping")
    return parsed


# ------------------------------------------------------------------------------
# 4. Pure Python RFC 8785 JCS Canonicalization & Ed25519 Math
# ------------------------------------------------------------------------------

def _jcs_utf16_sort(s: str) -> bytes:
    if not isinstance(s, str):
        raise TypeError(f"RFC 8785 requires object keys to be strings, got {type(s).__name__}")
    return s.encode("utf-16-be")


def _jcs_number(num: float) -> str:
    if math.isnan(num) or math.isinf(num):
        raise ValueError("RFC 8785 rejects NaN and Infinity")
    if num == 0.0:
        return "0"
    if num < 0:
        return "-" + _jcs_number(-num)
    rep = repr(num)
    if "e" in rep:
        mantissa, exp_str = rep.split("e")
        exp = int(exp_str)
    else:
        mantissa, exp = rep, 0
    if "." in mantissa:
        int_part, frac_part = mantissa.split(".")
        frac_part = frac_part.rstrip("0")
    else:
        int_part, frac_part = mantissa, ""
    int_part = int_part.lstrip("0")
    if int_part:
        digits = int_part + frac_part
        n = len(int_part) + exp
    else:
        leading_zeros = len(frac_part) - len(frac_part.lstrip("0"))
        digits = frac_part.lstrip("0")
        n = -leading_zeros + exp
    if not digits:
        return "0"
    k = len(digits)
    if k <= n <= 21:
        return digits + "0" * (n - k)
    elif 0 < n <= 21:
        return digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        return "0." + "0" * (-n) + digits
    # ECMA-262 7.1.12.1: positive exponents carry an explicit "+" (1e+21), matching
    # src/jcs_canonicalizer (kept local: this module has no repository imports).
    exp_sign = "+" if (n - 1) > 0 else ""
    if k == 1:
        return f"{digits}e{exp_sign}{n - 1}"
    return f"{digits[0]}.{digits[1:]}e{exp_sign}{n - 1}"


def _jcs_serialize(obj: Any) -> str:
    if obj is None:
        return "null"
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif isinstance(obj, int):
        return str(obj)
    elif isinstance(obj, float):
        return _jcs_number(obj)
    elif isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    elif isinstance(obj, (list, tuple)):
        return "[" + ",".join(_jcs_serialize(x) for x in obj) + "]"
    elif isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=_jcs_utf16_sort)
        parts = [
            f"{json.dumps(k, ensure_ascii=False)}:{_jcs_serialize(obj[k])}"
            for k in sorted_keys
        ]
        return "{" + ",".join(parts) + "}"
    raise TypeError(f"Type {type(obj).__name__} is not JSON serializable")


def encode_jcs(payload: Any) -> bytes:
    return _jcs_serialize(payload).encode("utf-8")


def compute_jcs_sha256(payload: Any) -> str:
    return hashlib.sha256(encode_jcs(payload)).hexdigest()


# Ed25519 Signing Primitives for Compiler Manifest
_FIELD_P = 2**255 - 19
_ORDER_L = 2**252 + 27742317777372353535851937790883648493
_CURVE_D = (-121665 * pow(121666, _FIELD_P - 2, _FIELD_P)) % _FIELD_P
_SQRT_M1 = pow(2, (_FIELD_P - 1) // 4, _FIELD_P)
_ID_PT = (0, 1, 1, 0)


def _finv(z: int) -> int:
    return pow(z, _FIELD_P - 2, _FIELD_P)


def _rec_x(y: int, s: int) -> Optional[int]:
    if y >= _FIELD_P:
        return None
    u = (y * y - 1) % _FIELD_P
    v = (_CURVE_D * y * y + 1) % _FIELD_P
    cand = (u * pow(v, 3, _FIELD_P) * pow(u * pow(v, 7, _FIELD_P), (_FIELD_P - 5) // 8, _FIELD_P)) % _FIELD_P
    if (v * cand * cand) % _FIELD_P == u:
        x = cand
    elif (v * cand * cand) % _FIELD_P == (-u) % _FIELD_P:
        x = (cand * _SQRT_M1) % _FIELD_P
    else:
        return None
    if (x % 2) != s:
        x = (_FIELD_P - x) % _FIELD_P
    return x


_y_b = (4 * _finv(5)) % _FIELD_P
_x_b = _rec_x(_y_b, 0)
_BASE_B = (_x_b, _y_b, 1, (_x_b * _y_b) % _FIELD_P)  # type: ignore


def _pt_add(p1: Tuple[int, int, int, int], p2: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    x1, y1, z1, t1 = p1
    x2, y2, z2, t2 = p2
    a = ((y1 - x1) * (y2 - x2)) % _FIELD_P
    b = ((y1 + x1) * (y2 + x2)) % _FIELD_P
    c = (2 * t1 * t2 * _CURVE_D) % _FIELD_P
    d = (2 * z1 * z2) % _FIELD_P
    e = (b - a) % _FIELD_P
    f = (d - c) % _FIELD_P
    g = (d + c) % _FIELD_P
    h = (b + a) % _FIELD_P
    return ((e * f) % _FIELD_P, (g * h) % _FIELD_P, (f * g) % _FIELD_P, (e * h) % _FIELD_P)


def _pt_mul(s: int, p: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    res = _ID_PT
    curr = p
    while s > 0:
        if s & 1:
            res = _pt_add(res, curr)
        curr = _pt_add(curr, curr)
        s >>= 1
    return res


def _compress_pt(p: Tuple[int, int, int, int]) -> bytes:
    x, y, z, _ = p
    z_inv = _finv(z)
    aff_x = (x * z_inv) % _FIELD_P
    aff_y = (y * z_inv) % _FIELD_P
    raw = bytearray(aff_y.to_bytes(32, "little"))
    if aff_x % 2:
        raw[31] |= 0x80
    return bytes(raw)


def ed25519_sign_manifest(seed_bytes: bytes, msg_bytes: bytes) -> Tuple[bytes, bytes]:
    """Signs manifest bytes with Ed25519 using pure Python field arithmetic."""
    if len(seed_bytes) != 32:
        raise ValueError("Seed must be 32 bytes")
    h = hashlib.sha512(seed_bytes).digest()
    a_bytes = bytearray(h[:32])
    a_bytes[0] &= 248
    a_bytes[31] &= 63
    a_bytes[31] |= 64
    a_scalar = int.from_bytes(a_bytes, "little")
    pt_a = _pt_mul(a_scalar, _BASE_B)
    pub_bytes = _compress_pt(pt_a)

    prefix = h[32:]
    r_scalar = int.from_bytes(hashlib.sha512(prefix + msg_bytes).digest(), "little") % _ORDER_L
    pt_r = _pt_mul(r_scalar, _BASE_B)
    r_bytes = _compress_pt(pt_r)

    k_scalar = int.from_bytes(hashlib.sha512(r_bytes + pub_bytes + msg_bytes).digest(), "little") % _ORDER_L
    s_scalar = (r_scalar + k_scalar * a_scalar) % _ORDER_L
    sig_bytes = r_bytes + s_scalar.to_bytes(32, "little")
    return pub_bytes, sig_bytes


# ------------------------------------------------------------------------------
# 5. Policy Static Linter & BTF Validator
# ------------------------------------------------------------------------------

class BPFLSMStaticLinter:
    """Performs static analysis and BTF type validation on Tetragon TracingPolicies."""

    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        self.diagnostics: List[Dict[str, Any]] = []

    def validate(self) -> Dict[str, Any]:
        """
        Validates policy and fails closed upon encountering any security deviation:
          - Unknown LSM hook -> HALT_INVALID_LSM_HOOK
          - Permissive bypass / wildcard -> HALT_PERMISSIVE_BYPASS_DETECTED
          - Argument type mismatch -> HALT_ARGUMENT_TYPE_MISMATCH
        """
        if not isinstance(self.policy, dict):
            raise BPFLSMValidationError(HALT_ARGUMENT_TYPE_MISMATCH, "Policy root must be a dictionary")

        kind = self.policy.get("kind")
        if kind != "TracingPolicy":
            raise BPFLSMValidationError(
                HALT_ARGUMENT_TYPE_MISMATCH,
                f"Expected kind 'TracingPolicy', observed '{kind}'"
            )

        spec = self.policy.get("spec")
        if not isinstance(spec, dict):
            raise BPFLSMValidationError(HALT_ARGUMENT_TYPE_MISMATCH, "Policy 'spec' block missing or not a dictionary")

        kprobes = spec.get("kprobes")
        if not isinstance(kprobes, list) or len(kprobes) == 0:
            raise BPFLSMValidationError(HALT_ARGUMENT_TYPE_MISMATCH, "TracingPolicy spec must contain at least one kprobe hook")

        validated_hooks: List[Dict[str, Any]] = []

        for hook_idx, hook in enumerate(kprobes):
            call_name = hook.get("call")
            if not call_name or not isinstance(call_name, str):
                raise BPFLSMValidationError(HALT_INVALID_LSM_HOOK, f"kprobe[{hook_idx}] missing required 'call' field")

            # Check 1: Known LSM Hook
            if call_name not in KNOWN_LSM_HOOKS:
                raise BPFLSMValidationError(
                    HALT_INVALID_LSM_HOOK,
                    f"Unknown or unvetted LSM hook '{call_name}'. Valid hooks: {sorted(list(KNOWN_LSM_HOOKS.keys()))}",
                    {"hook_index": hook_idx, "call": call_name},
                )

            hook_def = KNOWN_LSM_HOOKS[call_name]
            btf_spec = hook_def["btf_args"]

            # Check 2: Arguments and BTF types
            args = hook.get("args")
            if not isinstance(args, list) or len(args) == 0:
                raise BPFLSMValidationError(
                    HALT_ARGUMENT_TYPE_MISMATCH,
                    f"Hook '{call_name}' must declare BTF arguments list",
                    {"call": call_name},
                )

            normalized_args: List[Dict[str, Any]] = []
            for arg_entry in args:
                if not isinstance(arg_entry, dict):
                    raise BPFLSMValidationError(HALT_ARGUMENT_TYPE_MISMATCH, f"Hook '{call_name}' argument entry must be a dictionary")
                arg_idx = arg_entry.get("index")
                arg_type = arg_entry.get("type")

                if not isinstance(arg_idx, int) or not isinstance(arg_type, str):
                    raise BPFLSMValidationError(
                        HALT_ARGUMENT_TYPE_MISMATCH,
                        f"Hook '{call_name}' argument must specify integer 'index' and string 'type'",
                        {"call": call_name, "arg": arg_entry},
                    )

                if arg_type not in VALID_ARG_TYPES:
                    raise BPFLSMValidationError(
                        HALT_ARGUMENT_TYPE_MISMATCH,
                        f"Unknown argument type '{arg_type}' in hook '{call_name}'",
                        {"call": call_name, "type": arg_type},
                    )

                expected_types = btf_spec.get(arg_idx)
                if expected_types is None:
                    raise BPFLSMValidationError(
                        HALT_ARGUMENT_TYPE_MISMATCH,
                        f"Unexpected argument index {arg_idx} for hook '{call_name}'",
                        {"call": call_name, "index": arg_idx},
                    )

                if arg_type not in expected_types:
                    raise BPFLSMValidationError(
                        HALT_ARGUMENT_TYPE_MISMATCH,
                        f"Argument type mismatch for '{call_name}' index {arg_idx}: specified '{arg_type}', expected one of {expected_types}",
                        {"call": call_name, "index": arg_idx, "type": arg_type, "expected": expected_types},
                    )
                normalized_args.append({"index": arg_idx, "type": arg_type})

            # Check 3: Selectors and Permissive Bypass Detection
            selectors = hook.get("selectors")
            if not isinstance(selectors, list) or len(selectors) == 0:
                raise BPFLSMValidationError(
                    HALT_ARGUMENT_TYPE_MISMATCH,
                    f"Hook '{call_name}' missing required 'selectors' configuration",
                    {"call": call_name},
                )

            for sel_idx, sel in enumerate(selectors):
                if not isinstance(sel, dict):
                    raise BPFLSMValidationError(HALT_ARGUMENT_TYPE_MISMATCH, f"Selector[{sel_idx}] in '{call_name}' must be a dictionary")

                match_actions = sel.get("matchActions")
                if not isinstance(match_actions, list) or len(match_actions) == 0:
                    raise BPFLSMValidationError(
                        HALT_ARGUMENT_TYPE_MISMATCH,
                        f"Selector[{sel_idx}] in '{call_name}' must declare 'matchActions'",
                        {"call": call_name, "selector_index": sel_idx},
                    )

                has_enforcement_action = False
                for act in match_actions:
                    act_name = act.get("action")
                    if act_name not in VALID_ACTIONS:
                        raise BPFLSMValidationError(
                            HALT_ARGUMENT_TYPE_MISMATCH,
                            f"Invalid action '{act_name}' in selector. Valid: {VALID_ACTIONS}",
                        )
                    if act_name in ("Override", "Sigkill"):
                        has_enforcement_action = True

                # Specific Hook Permissive Bypass Checks
                if call_name == "security_socket_connect":
                    self._check_socket_connect_bypass(sel, sel_idx, has_enforcement_action)
                elif call_name == "security_file_open":
                    self._check_file_open_bypass(sel, sel_idx, has_enforcement_action)

            validated_hooks.append({
                "call": call_name,
                "description": hook_def["description"],
                "args": normalized_args,
                "selectors_count": len(selectors),
            })

        return {
            "metadata_name": self.policy.get("metadata", {}).get("name", "unnamed-policy"),
            "validated_hooks": validated_hooks,
            "total_hooks": len(validated_hooks),
        }

    def _check_socket_connect_bypass(
        self, selector: Dict[str, Any], sel_idx: int, has_enforcement: bool
    ) -> None:
        """Validates that socket connect trap does not permit unconfined outbound traffic."""
        match_args = selector.get("matchArgs", [])
        if not isinstance(match_args, list) or len(match_args) == 0:
            raise BPFLSMValidationError(
                HALT_PERMISSIVE_BYPASS_DETECTED,
                f"security_socket_connect selector[{sel_idx}] lacks matchArgs filter, creating unrestricted socket egress",
            )

        found_addr_filter = False
        for ma in match_args:
            op = ma.get("operator")
            vals = ma.get("values", [])
            if op not in VALID_OPERATORS:
                raise BPFLSMValidationError(HALT_ARGUMENT_TYPE_MISMATCH, f"Invalid operator '{op}' in matchArgs")
            if not isinstance(vals, list) or len(vals) == 0:
                raise BPFLSMValidationError(
                    HALT_PERMISSIVE_BYPASS_DETECTED,
                    f"security_socket_connect matchArgs has empty address values list",
                )

            # Detect wildcard 0.0.0.0/0 or unrestricted DAddr
            if op in ("DAddr", "NotDAddr"):
                found_addr_filter = True
                if "0.0.0.0" in vals or "0.0.0.0/0" in vals or "*" in vals:
                    raise BPFLSMValidationError(
                        HALT_PERMISSIVE_BYPASS_DETECTED,
                        f"security_socket_connect permits permissive wildcard IP {vals} via operator {op}",
                    )

        if not found_addr_filter:
            raise BPFLSMValidationError(
                HALT_PERMISSIVE_BYPASS_DETECTED,
                f"security_socket_connect selector[{sel_idx}] missing destination address restriction",
            )

        if not has_enforcement:
            raise BPFLSMValidationError(
                HALT_PERMISSIVE_BYPASS_DETECTED,
                f"security_socket_connect selector[{sel_idx}] only logs without active Override/Sigkill blocking",
            )

    def _check_file_open_bypass(
        self, selector: Dict[str, Any], sel_idx: int, has_enforcement: bool
    ) -> None:
        """Validates that file open guard protects sensitive AEIB policy directories."""
        match_args = selector.get("matchArgs", [])
        match_flags = selector.get("matchFlags", [])

        if not isinstance(match_args, list) or len(match_args) == 0:
            raise BPFLSMValidationError(
                HALT_PERMISSIVE_BYPASS_DETECTED,
                f"security_file_open selector[{sel_idx}] missing matchArgs path restrictions",
            )

        for ma in match_args:
            op = ma.get("operator")
            vals = ma.get("values", [])
            if op not in VALID_OPERATORS:
                raise BPFLSMValidationError(HALT_ARGUMENT_TYPE_MISMATCH, f"Invalid operator '{op}' in matchArgs")
            if not isinstance(vals, list) or len(vals) == 0:
                raise BPFLSMValidationError(
                    HALT_PERMISSIVE_BYPASS_DETECTED,
                    f"security_file_open matchArgs has empty path list",
                )

            # Permissive wildcard root or star
            for val_item in vals:
                s_val = str(val_item).strip()
                if s_val in ("/", "*", "/*", ""):
                    raise BPFLSMValidationError(
                        HALT_PERMISSIVE_BYPASS_DETECTED,
                        f"security_file_open contains permissive root wildcard path: '{s_val}'",
                    )

        # Check write flag interception
        has_write_flags = False
        if isinstance(match_flags, list):
            for mf in match_flags:
                vals = mf.get("values", [])
                if any(w in vals for w in ("O_WRONLY", "O_RDWR", "O_TRUNC", "O_CREAT")):
                    has_write_flags = True

        if has_write_flags and not has_enforcement:
            raise BPFLSMValidationError(
                HALT_PERMISSIVE_BYPASS_DETECTED,
                f"security_file_open selector[{sel_idx}] detects write mutation flags without Override/Sigkill enforcement",
            )


# ------------------------------------------------------------------------------
# 6. Profile Manifest Compiler
# ------------------------------------------------------------------------------

class BPFLSMProfileCompiler:
    """Compiles vetted TracingPolicies into canonical, signed BPF_LSM Security Profiles."""

    @staticmethod
    def compile(
        policy_path: Path,
        signing_seed_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        """
        Parses, lints, and compiles a TracingPolicy YAML file into a canonical
        signed BPF_LSM Profile Manifest.
        """
        if not policy_path.is_file():
            raise FileNotFoundError(f"Policy file not found: {policy_path}")

        raw_yaml = policy_path.read_text(encoding="utf-8")
        parsed_policy = parse_yaml_tracing_policy(raw_yaml)

        linter = BPFLSMStaticLinter(parsed_policy)
        lint_report = linter.validate()

        # Build Unsigned Manifest
        seed = signing_seed_bytes or hashlib.sha256(b"aeib_compiler_manifest_seed_default").digest()
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        unsigned_manifest = {
            "profile_version": COMPILER_VERSION,
            "profile_name": lint_report["metadata_name"],
            "compiled_at_utc": now_utc,
            "source_policy_file": str(policy_path.resolve()),
            "target_subsystem": "linux_bpf_lsm",
            "kernel_lsm_hooks": lint_report["validated_hooks"],
            "security_invariants": [
                "INVARIANT_EGRESS_CONFINEMENT",
                "INVARIANT_POLICY_IMMUTABILITY",
                "INVARIANT_FAIL_CLOSED_BTF",
            ],
        }

        # RFC 8785 JCS canonical digest computation
        canonical_bytes = encode_jcs(unsigned_manifest)
        canonical_digest = hashlib.sha256(canonical_bytes).hexdigest()

        # Asymmetric Ed25519 Signing
        pub_bytes, sig_bytes = ed25519_sign_manifest(seed, canonical_bytes)

        signed_profile = {
            "format": "AEIB_BPF_LSM_SECURITY_PROFILE_V1",
            "profile_manifest": unsigned_manifest,
            "canonical_digest_sha256": canonical_digest,
            "signature_envelope": {
                "algorithm": "Ed25519",
                "public_key_hex": pub_bytes.hex(),
                "signature_hex": sig_bytes.hex(),
            },
        }

        return signed_profile


# ------------------------------------------------------------------------------
# 7. Built-in Self-Test Suite (--self-test)
# ------------------------------------------------------------------------------

def run_compiler_self_test() -> bool:
    """
    Executes built-in validation checks:
      1. Positive verification of compliance/tetragon_aeib_enforcer.yaml.
      2. Falsification 1: Unknown LSM hook -> HALT_INVALID_LSM_HOOK.
      3. Falsification 2: Permissive wildcard write -> HALT_PERMISSIVE_BYPASS_DETECTED.
      4. Falsification 3: Argument type mismatch -> HALT_ARGUMENT_TYPE_MISMATCH.
    """
    enforcer_path = Path("compliance/tetragon_aeib_enforcer.yaml")
    if not enforcer_path.is_file():
        return False

    # 1. Positive Compilation Test
    try:
        compiled = BPFLSMProfileCompiler.compile(enforcer_path)
        if not compiled.get("canonical_digest_sha256"):
            return False
        if len(compiled["profile_manifest"]["kernel_lsm_hooks"]) != 2:
            return False
    except Exception:
        return False

    # 2. Falsification 1: Unknown LSM Hook
    bad_hook_yaml = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: bad-hook-test
spec:
  kprobes:
    - call: "security_unvetted_custom_syscall"
      args:
        - index: 0
          type: "sock"
      selectors:
        - matchActions:
            - action: Override
"""
    try:
        parsed_bad = parse_yaml_tracing_policy(bad_hook_yaml)
        BPFLSMStaticLinter(parsed_bad).validate()
        return False  # Must fail closed!
    except BPFLSMValidationError as exc:
        if exc.halt_code != HALT_INVALID_LSM_HOOK:
            return False

    # 3. Falsification 2: Permissive Wildcard Bypass
    permissive_yaml = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: permissive-test
spec:
  kprobes:
    - call: "security_file_open"
      args:
        - index: 0
          type: "file"
      selectors:
        - matchArgs:
            - index: 0
              operator: "Prefix"
              values:
                - "/"
          matchFlags:
            - index: 0
              operator: "HasAny"
              values:
                - "O_WRONLY"
          matchActions:
            - action: Override
"""
    try:
        parsed_perm = parse_yaml_tracing_policy(permissive_yaml)
        BPFLSMStaticLinter(parsed_perm).validate()
        return False  # Must fail closed!
    except BPFLSMValidationError as exc:
        if exc.halt_code != HALT_PERMISSIVE_BYPASS_DETECTED:
            return False

    # 4. Falsification 3: Argument Type Mismatch
    mismatch_yaml = """
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: mismatch-test
spec:
  kprobes:
    - call: "security_socket_connect"
      args:
        - index: 0
          type: "file"
      selectors:
        - matchActions:
            - action: Override
"""
    try:
        parsed_mismatch = parse_yaml_tracing_policy(mismatch_yaml)
        BPFLSMStaticLinter(parsed_mismatch).validate()
        return False  # Must fail closed!
    except BPFLSMValidationError as exc:
        if exc.halt_code != HALT_ARGUMENT_TYPE_MISMATCH:
            return False

    return True


# ------------------------------------------------------------------------------
# 8. Command-Line Interface (CLI)
# ------------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Linux Kernel BPF_LSM Security Profile Compiler & Static Policy Linter."
    )
    parser.add_argument(
        "--lint",
        type=Path,
        help="Path to Tetragon TracingPolicy YAML file to lint and validate.",
    )
    parser.add_argument(
        "--compile",
        type=Path,
        help="Path to Tetragon TracingPolicy YAML file to compile into canonical signed manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("bpf_lsm_profile.json"),
        help="Output path for compiled BPF_LSM Security Profile Manifest (default: bpf_lsm_profile.json).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Execute internal validation and falsification tests.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit output in structured JSON format.",
    )

    args = parser.parse_args()

    if args.self_test:
        success = run_compiler_self_test()
        if success:
            if args.json:
                print(json.dumps({"self_test": "VALID", "status_code": 0}))
            else:
                print("[VALID] BPF_LSM Compiler Self-Test: All positive and falsification vectors evaluated successfully.")
            sys.exit(0)
        else:
            if args.json:
                print(json.dumps({"self_test": "FAILED", "status_code": 1}))
            else:
                print("[FAIL] BPF_LSM Compiler Self-Test: Verification or falsification checks failed.", file=sys.stderr)
            sys.exit(1)

    if args.lint:
        if not args.lint.is_file():
            print(f"[FAIL] Policy file not found: {args.lint}", file=sys.stderr)
            sys.exit(2)
        try:
            parsed = parse_yaml_tracing_policy(args.lint.read_text(encoding="utf-8"))
            linter = BPFLSMStaticLinter(parsed)
            report = linter.validate()
            if args.json:
                print(json.dumps({"valid": True, "report": report}, indent=2))
            else:
                print(f"[VALID] Policy '{report['metadata_name']}' successfully validated against BTF & LSM invariants.")
                print(f"  Total LSM Hooks: {report['total_hooks']}")
                for h in report["validated_hooks"]:
                    print(f"  - {h['call']}: {h['description']} ({len(h['args'])} BTF args)")
            sys.exit(0)
        except BPFLSMValidationError as exc:
            if args.json:
                print(json.dumps({"valid": False, "halt_code": exc.halt_code, "error": exc.message}))
            else:
                print(f"[FAIL] {exc.halt_code}: {exc.message}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"[FAIL] Parsing or unexpected error: {exc}", file=sys.stderr)
            sys.exit(2)

    if args.compile:
        if not args.compile.is_file():
            print(f"[FAIL] Policy file not found: {args.compile}", file=sys.stderr)
            sys.exit(2)
        try:
            profile = BPFLSMProfileCompiler.compile(args.compile)
            out_bytes = encode_jcs(profile)
            args.output.write_bytes(out_bytes)
            if args.json:
                print(json.dumps({"valid": True, "output": str(args.output), "profile": profile}, indent=2))
            else:
                print(f"[VALID] Compiled BPF_LSM profile written to {args.output}")
                print(f"  Canonical Digest (SHA-256): {profile['canonical_digest_sha256']}")
                print(f"  Ed25519 Public Key: {profile['signature_envelope']['public_key_hex']}")
            sys.exit(0)
        except BPFLSMValidationError as exc:
            if args.json:
                print(json.dumps({"valid": False, "halt_code": exc.halt_code, "error": exc.message}))
            else:
                print(f"[FAIL] {exc.halt_code}: {exc.message}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"[FAIL] Compilation failed: {exc}", file=sys.stderr)
            sys.exit(2)

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
