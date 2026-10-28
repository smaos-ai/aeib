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
src/anti_gravity_context_cart.py
================================================================================
Local web-to-LLM evidence ingestion (prototype / scaffold).

Three stages, stdlib only, zero network egress:

1. ``LocalDOMExonSlicer`` -- strips boilerplate HTML (script, style, nav,
   header, footer, aside, noscript, svg, iframe, and elements whose class/id
   contains sidebar / cookie / ad-slot / popup) locally with ``html.parser``.
   No external reader proxy is used (a hosted proxy prefix would leak the
   fetch intent and the URL to a third party).
2. ``ContextCartVerifier`` -- mints a ``VerifiedContextCartSlice`` binding a
   source URI, the sha256 of the raw archive, and the sha256 of an exact byte
   span; ``verify_slice`` recomputes both digests and fails closed.
3. ``AntiGravityPromptBuilder`` -- renders slices into an HTML-escaped,
   HMAC-nonce-tagged evidence envelope and a ``bundle_caid`` computed as
   sha256 over RFC 8785 JCS (``src.jcs_canonicalizer.encode_jcs``) of integer
   and string-only manifest rows.

Limitations (under the stated model):
  * The negation-polarity guard is a lexical token heuristic. It does NOT
    detect paraphrased negation ("fails to", "absence of"), negation scope
    changes, number / unit changes, or a negation token re-attached to a
    different clause. Passing it is not evidence of semantic faithfulness.
  * The boundary nonce is visible in the rendered prompt; escaping is the
    primary breakout defense and the nonce is defense-in-depth only.
  * Boilerplate detection is a fixed tag / attribute-substring list; it will
    keep boilerplate it does not recognise and may drop content whose class
    or id happens to contain a marker substring.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from src.jcs_canonicalizer import encode_jcs

TAINT_TIER: str = "TIER_2_RAW_RAG_UNTRUSTED"
ALLOWED_URI_SCHEMES: Tuple[str, ...] = ("https://", "file://")
_CAID_RE = re.compile(r"\Asha256:[0-9a-f]{64}\Z")
_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")


def sha256_caid(data: bytes) -> str:
    """Return ``"sha256:" + hex`` of ``data``."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"HALT_NON_INTEGER_{name}")
    return value


# ============================================================================
# 1. Local HTML intron stripper
# ============================================================================


class _IntronStrippingHTMLParser(HTMLParser):
    INTRON_TAGS: FrozenSet[str] = frozenset(
        {"script", "style", "nav", "header", "footer", "aside", "noscript", "svg", "iframe"}
    )
    NOISE_MARKERS: Tuple[str, ...] = ("sidebar", "cookie", "ad-slot", "popup")
    VOID_TAGS: FrozenSet[str] = frozenset(
        {
            "area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr",
        }
    )
    BLOCK_TAGS: FrozenSet[str] = frozenset(
        {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "code", "div", "tr", "br"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        # Stack of open tag names inside a skipped subtree. The subtree ends
        # when the tag that opened it is closed, whatever its name (fixes the
        # pasted bug where a skipped <div class="sidebar"> never decremented).
        self._skip_stack: List[str] = []
        self._chunks: List[str] = []

    def _is_noise(self, attrs: List[Tuple[str, Optional[str]]]) -> bool:
        for key, value in attrs:
            if key in ("class", "id") and value:
                lowered = value.lower()
                if any(marker in lowered for marker in self.NOISE_MARKERS):
                    return True
        return False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        if self._skip_stack:
            if t not in self.VOID_TAGS:
                self._skip_stack.append(t)
            return
        if t in self.INTRON_TAGS or self._is_noise(attrs):
            if t not in self.VOID_TAGS:
                self._skip_stack.append(t)
            return
        if t in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t not in self._skip_stack:
            return
        # Pop up to and including the most recent matching open tag; this
        # tolerates unclosed children (<div class=sidebar><p>x</div>).
        while self._skip_stack:
            if self._skip_stack.pop() == t:
                break

    def handle_data(self, data: str) -> None:
        if self._skip_stack:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self._chunks.append(cleaned + " ")

    def exon_text(self) -> str:
        lines = [line.strip() for line in "".join(self._chunks).splitlines()]
        return "\n".join(line for line in lines if line)


@dataclass(frozen=True)
class ExonExtraction:
    exon_text: str
    raw_bytes: int
    exon_bytes: int
    saved_bps: int  # integer basis points 0..10000


class LocalDOMExonSlicer:
    """Extracts readable text from raw HTML locally, without network calls."""

    @staticmethod
    def extract_exons(raw_html: str) -> ExonExtraction:
        if not isinstance(raw_html, str):
            raise ValueError("HALT_RAW_HTML_NOT_STR")
        parser = _IntronStrippingHTMLParser()
        parser.feed(raw_html)
        parser.close()
        text = parser.exon_text()
        raw_len = len(raw_html.encode("utf-8"))
        exon_len = len(text.encode("utf-8"))
        if raw_len == 0:
            saved_bps = 0
        else:
            # exon_len >= 0 bounds this above by 10000; clamp below at 0.
            saved_bps = max(0, ((raw_len - exon_len) * 10000) // raw_len)
        return ExonExtraction(
            exon_text=text, raw_bytes=raw_len, exon_bytes=exon_len, saved_bps=saved_bps
        )


# ============================================================================
# 2. Byte-span bound, negation-guarded ContextCart slice
# ============================================================================


@dataclass(frozen=True)
class VerifiedContextCartSlice:
    source_uri: str
    archive_caid: str
    span_caid: str
    start_byte: int
    end_byte: int
    exon_payload: str
    limitations: str
    taint_tier: str = TAINT_TIER


class ContextCartVerifier:
    """
    Binds an exon payload to an exact byte span of a raw archive.

    Checks (fail closed, typed ``ValueError`` codes):
      * source URI scheme is https:// or file://;
      * 0 <= start_byte < end_byte <= len(raw_archive_bytes);
      * the span decodes as strict UTF-8 (``HALT_SPAN_NOT_UTF8``);
      * negation-polarity guard: every negation token present in the span
        must also appear in ``exon_payload``
        (``HALT_NEGATION_POLARITY_STRIPPED:<tokens>``).

    The negation guard is a lexical heuristic only. It does not detect
    paraphrased negation, scope changes, number changes, or a token that is
    kept but moved to a different clause. It is a limitation-bounded tripwire,
    not a semantic faithfulness check.
    """

    NEGATION_TOKENS: FrozenSet[str] = frozenset(
        {
            "not", "never", "no", "nor", "cannot", "can't", "don't", "doesn't",
            "isn't", "refutes", "refuted", "false", "forbid", "forbidden", "without",
        }
    )

    @classmethod
    def _negation_tokens(cls, text: str) -> FrozenSet[str]:
        normalized = text.lower().replace("\u2019", "'")
        return frozenset(_WORD_RE.findall(normalized)) & cls.NEGATION_TOKENS

    @staticmethod
    def _check_span(raw_archive_bytes: bytes, start_byte: int, end_byte: int) -> bytes:
        if not isinstance(raw_archive_bytes, (bytes, bytearray)):
            raise ValueError("HALT_ARCHIVE_NOT_BYTES")
        start = _require_int("START_BYTE", start_byte)
        end = _require_int("END_BYTE", end_byte)
        if start < 0 or end > len(raw_archive_bytes) or start >= end:
            raise ValueError("HALT_INVALID_BYTE_SPAN_BOUNDS")
        return bytes(raw_archive_bytes[start:end])

    @classmethod
    def _check_polarity(cls, span_bytes: bytes, exon_payload: str) -> None:
        try:
            span_text = span_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("HALT_SPAN_NOT_UTF8") from exc
        missing = cls._negation_tokens(span_text) - cls._negation_tokens(exon_payload)
        if missing:
            raise ValueError("HALT_NEGATION_POLARITY_STRIPPED:" + ",".join(sorted(missing)))

    @classmethod
    def mint_verified_slice(
        cls,
        source_uri: str,
        raw_archive_bytes: bytes,
        start_byte: int,
        end_byte: int,
        exon_payload: str,
        limitations: str,
    ) -> VerifiedContextCartSlice:
        if not isinstance(source_uri, str) or not source_uri.startswith(ALLOWED_URI_SCHEMES):
            raise ValueError("HALT_UNTRUSTED_OR_MALFORMED_SOURCE_URI")
        if not isinstance(exon_payload, str) or not exon_payload.strip():
            raise ValueError("HALT_EMPTY_EXON_PAYLOAD")
        if not isinstance(limitations, str):
            raise ValueError("HALT_LIMITATIONS_NOT_STR")
        span_bytes = cls._check_span(raw_archive_bytes, start_byte, end_byte)
        cls._check_polarity(span_bytes, exon_payload)
        return VerifiedContextCartSlice(
            source_uri=source_uri,
            archive_caid=sha256_caid(bytes(raw_archive_bytes)),
            span_caid=sha256_caid(span_bytes),
            start_byte=start_byte,
            end_byte=end_byte,
            exon_payload=exon_payload,
            limitations=limitations,
            taint_tier=TAINT_TIER,
        )

    @classmethod
    def verify_slice(
        cls, slice_: VerifiedContextCartSlice, raw_archive_bytes: bytes
    ) -> VerifiedContextCartSlice:
        """Recompute archive and span digests and the polarity guard; fail closed."""
        if not isinstance(slice_, VerifiedContextCartSlice):
            raise ValueError("HALT_NOT_A_CONTEXT_CART_SLICE")
        if slice_.taint_tier != TAINT_TIER:
            raise ValueError("HALT_TAINT_TIER_MISMATCH")
        span_bytes = cls._check_span(raw_archive_bytes, slice_.start_byte, slice_.end_byte)
        if not hmac.compare_digest(sha256_caid(bytes(raw_archive_bytes)), slice_.archive_caid):
            raise ValueError("HALT_ARCHIVE_CAID_MISMATCH")
        if not hmac.compare_digest(sha256_caid(span_bytes), slice_.span_caid):
            raise ValueError("HALT_SPAN_CAID_MISMATCH")
        cls._check_polarity(span_bytes, slice_.exon_payload)
        return slice_


# ============================================================================
# 3. Escaped, nonce-tagged evidence prompt builder
# ============================================================================


@dataclass(frozen=True)
class AntiGravityBundleResult:
    rendered_prompt: str
    boundary_tag_nonce: str
    bundle_caid: str
    taint_tier: str
    source_count: int


class AntiGravityPromptBuilder:
    """
    Renders verified slices into an evidence envelope for an LLM prompt.

    Every untrusted string (payload, URI, limitations) is passed through
    ``html.escape(quote=True)``, so embedded ``</source...>`` or ``<system>``
    text cannot form a tag. Each turn uses an HMAC-SHA256(session_secret,
    turn_seq) derived tag name. The nonce is visible in the rendered prompt,
    so escaping is the primary breakout defense; the nonce is
    defense-in-depth only (it limits cross-turn replay of a known tag).
    Slices are ordered by (source_uri, start_byte, end_byte, span_caid).
    """

    MIN_SESSION_SECRET_BYTES: int = 16  # claim: config
    NONCE_HEX_LEN: int = 32  # claim: config

    @classmethod
    def turn_nonce(cls, session_secret: bytes, turn_seq: int) -> str:
        if not isinstance(session_secret, (bytes, bytearray)):
            raise ValueError("HALT_SESSION_SECRET_NOT_BYTES")
        if len(session_secret) < cls.MIN_SESSION_SECRET_BYTES:
            raise ValueError("HALT_SESSION_SECRET_TOO_SHORT")
        seq = _require_int("TURN_SEQ", turn_seq)
        if seq < 0:
            raise ValueError("HALT_NEGATIVE_TURN_SEQ")
        mac = hmac.new(bytes(session_secret), b"anti_gravity_turn:" + str(seq).encode("ascii"), hashlib.sha256)
        return mac.hexdigest()[: cls.NONCE_HEX_LEN]

    @staticmethod
    def _check_slice(s: Any) -> VerifiedContextCartSlice:
        if not isinstance(s, VerifiedContextCartSlice):
            raise ValueError("HALT_NOT_A_CONTEXT_CART_SLICE")
        if s.taint_tier != TAINT_TIER:
            raise ValueError("HALT_TAINT_TIER_MISMATCH")
        if not _CAID_RE.match(s.archive_caid) or not _CAID_RE.match(s.span_caid):
            raise ValueError("HALT_MALFORMED_CAID")
        _require_int("START_BYTE", s.start_byte)
        _require_int("END_BYTE", s.end_byte)
        return s

    @classmethod
    def build_bounded_evidence_prompt(
        cls,
        slices: Sequence[VerifiedContextCartSlice],
        session_secret: bytes,
        turn_seq: int,
    ) -> AntiGravityBundleResult:
        if not slices:
            raise ValueError("HALT_EMPTY_CONTEXT_CART_BUNDLE")
        nonce = cls.turn_nonce(session_secret, turn_seq)
        checked = [cls._check_slice(s) for s in slices]
        ordered = sorted(
            checked, key=lambda s: (s.source_uri, s.start_byte, s.end_byte, s.span_caid)
        )
        tag = "source_" + nonce
        lines: List[str] = [f'<evidence_bundle_{nonce} taint="{TAINT_TIER}">']
        manifest_rows: List[Dict[str, Any]] = []
        for idx, s in enumerate(ordered):
            lines.append(
                f'<{tag} id="{idx}" uri="{html.escape(s.source_uri, quote=True)}" '
                f'archive_caid="{s.archive_caid}" span_caid="{s.span_caid}" '
                f'bytes="{s.start_byte}:{s.end_byte}" '
                f'limitations="{html.escape(s.limitations, quote=True)}">'
            )
            lines.append(html.escape(s.exon_payload, quote=True))
            lines.append(f"</{tag}>")
            manifest_rows.append(
                {
                    "archive_caid": s.archive_caid,
                    "end_byte": s.end_byte,
                    "id": idx,
                    "payload_caid": sha256_caid(s.exon_payload.encode("utf-8")),
                    "source_uri": s.source_uri,
                    "span_caid": s.span_caid,
                    "start_byte": s.start_byte,
                    "taint_tier": TAINT_TIER,
                }
            )
        lines.append(f"</evidence_bundle_{nonce}>")
        return AntiGravityBundleResult(
            rendered_prompt="\n".join(lines),
            boundary_tag_nonce=nonce,
            bundle_caid=sha256_caid(encode_jcs(manifest_rows)),
            taint_tier=TAINT_TIER,
            source_count=len(ordered),
        )
