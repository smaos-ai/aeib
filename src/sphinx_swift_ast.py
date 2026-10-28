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
sphinx_swift_ast.py — Sphinx reviewer-attestation extractor for Swift (Wave 8 prototype).

Evaluated under the stated model: a single-pass lexer blanks Swift comments
(including NESTED block comments, which Swift allows) and string literals
("...", multi-line triple-quoted, and raw #"..."# strings) before extracting
function names, guard/throw/throws/fatalError keywords and integer literals
with >= 2 digits (0..9 are skipped as noise).

This is NOT a Swift parser (no swift-syntax / tree-sitter dependency is added,
per AGENTS.md §3). Known gaps: string interpolations containing nested quotes
("\\(f("x"))"), extended raw delimiters with more than one '#', and
underscored/hex literals (1_000, 0x1F) are not fully handled. The expected
answers are computable by anyone running this extractor, so a matching
attestation shows the reviewer filled it in against the real code; it does
NOT measure human comprehension.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs


@dataclass(frozen=True)
class SwiftAstChallenge:
    challenge_caid: str
    extracted_func_names: Tuple[str, ...]
    extracted_guard_throws: Tuple[str, ...]
    extracted_timeout_ints: Tuple[int, ...]


class SphinxSwiftASTParser:
    _FUNC_RE = re.compile(r"\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)\s*[<(]")
    _GUARD_THROW_RE = re.compile(r"\b(guard|throw|throws|fatalError)\b")
    _INT_LITERAL_RE = re.compile(r"(?<![\w.])([0-9]{2,})(?![\w.])")

    @staticmethod
    def strip_comments_and_strings(source: str) -> str:
        """Replace comments and string literals with spaces (newlines kept)."""
        out = []
        i, n = 0, len(source)
        while i < n:
            two = source[i:i + 2]
            if two == "//":
                j = source.find("\n", i)
                j = n if j == -1 else j
                out.append(" " * (j - i))
                i = j
            elif two == "/*":
                depth, j = 1, i + 2
                while j < n and depth:
                    if source.startswith("/*", j):
                        depth, j = depth + 1, j + 2
                    elif source.startswith("*/", j):
                        depth, j = depth - 1, j + 2
                    else:
                        j += 1
                out.append(re.sub(r"[^\n]", " ", source[i:j]))
                i = j
            elif source.startswith('#"', i):
                j = source.find('"#', i + 2)
                j = n if j == -1 else j + 2
                out.append(re.sub(r"[^\n]", " ", source[i:j]))
                i = j
            elif source.startswith('"""', i):
                j = source.find('"""', i + 3)
                j = n if j == -1 else j + 3
                out.append(re.sub(r"[^\n]", " ", source[i:j]))
                i = j
            elif source[i] == '"':
                j = i + 1
                while j < n and source[j] not in '"\n':
                    j += 2 if source[j] == "\\" else 1
                j = min(j + 1, n)
                out.append(re.sub(r"[^\n]", " ", source[i:j]))
                i = j
            else:
                out.append(source[i])
                i += 1
        return "".join(out)

    @classmethod
    def extract_challenge(cls, swift_source: str) -> SwiftAstChallenge:
        if not isinstance(swift_source, str):
            raise TypeError("ERR_SWIFT_SOURCE_NOT_TEXT")
        clean = cls.strip_comments_and_strings(swift_source)
        funcs = tuple(sorted(set(cls._FUNC_RE.findall(clean))))
        guards = tuple(sorted(set(cls._GUARD_THROW_RE.findall(clean))))
        ints = tuple(sorted({int(m) for m in cls._INT_LITERAL_RE.findall(clean)}))
        payload: Dict[str, Any] = {
            "extracted_func_names": list(funcs),
            "extracted_guard_throws": list(guards),
            "extracted_timeout_ints": list(ints),
            "source_sha256": hashlib.sha256(swift_source.encode("utf-8")).hexdigest(),
        }
        return SwiftAstChallenge(
            challenge_caid=f"sha256:{hashlib.sha256(encode_jcs(payload)).hexdigest()}",
            extracted_func_names=funcs,
            extracted_guard_throws=guards,
            extracted_timeout_ints=ints,
        )

    @classmethod
    def verify_reviewer_attestation(
        cls,
        challenge: SwiftAstChallenge,
        attested_funcs: Sequence[str],
        attested_guards: Sequence[str],
        attested_ints: Sequence[int],
    ) -> Tuple[bool, str]:
        if any(type(v) is not int for v in attested_ints):
            return False, "HALT_COGNITIVE_DEBT_INT_CONSTANT_MISMATCH"
        if tuple(sorted(set(attested_funcs))) != challenge.extracted_func_names:
            return False, "HALT_COGNITIVE_DEBT_FUNCTION_MISMATCH"
        if tuple(sorted(set(attested_guards))) != challenge.extracted_guard_throws:
            return False, "HALT_COGNITIVE_DEBT_GUARD_MISMATCH"
        if tuple(sorted(set(attested_ints))) != challenge.extracted_timeout_ints:
            return False, "HALT_COGNITIVE_DEBT_INT_CONSTANT_MISMATCH"
        return True, "OK_REVIEWER_ATTESTATION_MATCHES_AST"
