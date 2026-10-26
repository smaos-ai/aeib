"""Zero-egress web research quarantine router and multi-provider combination gate.

Prototype airlock between external web search / answer engines (Perplexity
Sonar, Exa, Tavily, Firecrawl, Jina Reader, SearXNG, multi-hop agentic search)
and an AEIB coding agent. This module performs no network I/O; it classifies
outbound queries and sanitizes typed provider responses handed to it.

Controls (each covered by tests/test_web_research_quarantine_router.py and the
red-team regressions added after commit 5ca565c3):

1. Query egress classifier: blocks credentials (vendor-prefixed tokens, JWTs,
   PEM headers, high-entropy strings) and routes workspace paths / stack traces
   to self-hosted ``SEARXNG_LOCAL`` or halts closed. Oversize queries halt.
2. Provider-layer routing by intent (primary literature, markdown extraction,
   multi-hop DAG traversal, synthesized triage, private metasearch).
3. Hidden-carrier removal: an HTMLParser-based visible-text extractor drops
   comments (including unclosed ones), script/style/template/noscript, and any
   subtree marked hidden (inline style, ``hidden`` attribute, aria-hidden);
   all remaining tags are removed. HTML entities are decoded before detection.
   Unicode format characters (category Cf: soft hyphen, zero-width, bidi
   controls, tag characters) are stripped and the text is NFKC-normalized.
4. Indirect prompt injection (IPI) denylist over a detection skeleton
   (NFKC + casefold + partial Cyrillic/Greek confusable fold). This is a
   heuristic denylist and is incomplete by construction; the structural
   control is item 6.
5. Epistemic tiering: synthesized answers (declared or from a known
   synthesizing provider) are capped at T1_SYNTHESIZED_LEAD. T2 requires an
   https URL on the primary-domain allowlist AND a primary span quote of at
   least ``MIN_PRIMARY_QUOTE_CHARS`` that is present in the sanitized text.
6. Taint pin and oracle binding: bundles are TIER_2_EXTERNAL_WEB. A bundle can
   authorize a code mutation only with an Ed25519-signed ``LocalOracleReceipt``
   from a trusted oracle key (distinct from the bundle signing key) bound to
   the same query and a specific subject digest.
7. POIROT echo collapse: items merge when they share a root-origin key, an
   identical normalized-content digest, or word 5-gram Jaccard similarity at
   or above ``NEAR_DUPLICATE_JACCARD_BPS``. Paraphrased syndication across
   domains is NOT detected (out of scope; open item).
8. Signed bundle over RFC 8785 JCS; verification recomputes every item digest
   from item fields so post-signing item edits fail verification.
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import html
import math
import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from src.jcs_canonicalizer import encode_jcs

BPS_FULL_SCALE: int = 10000
SYNTHESIZED_LEAD_CAP_BPS: int = 4500  # claim: config
SECONDARY_WEB_CAP_BPS: int = 6000  # claim: config
PRIMARY_VERIFIED_CAP_BPS: int = 9000  # claim: config
CORRELATED_DISCOUNT_BPS: int = 7500  # claim: config
MUTATION_AUTHORIZATION_FLOOR_BPS: int = 6000  # claim: config
NEAR_DUPLICATE_JACCARD_BPS: int = 8000  # claim: config
MIN_PRIMARY_QUOTE_CHARS: int = 24
MAX_QUERY_CHARS: int = 2048
MAX_RAW_TEXT_CHARS: int = 200_000
MAX_ITEMS_PER_BUNDLE: int = 256
SHINGLE_WORDS: int = 5
HIGH_ENTROPY_MIN_LEN: int = 32
HIGH_ENTROPY_MIN_MILLIBITS: int = 4000
UNICODE_TAG_START: int = 0xE0000
UNICODE_TAG_END: int = 0xE007F

PRIMARY_AUTHORITATIVE_DOMAINS: Tuple[str, ...] = (
    "arxiv.org",
    "datatracker.ietf.org",
    "ietf.org",
    "rfc-editor.org",
    "nvd.nist.gov",
    "csrc.nist.gov",
    "doi.org",
    "eur-lex.europa.eu",
    "nature.com",
    "science.org",
    "acm.org",
    "ieee.org",
    "openreview.net",
)

SYNTHESIZING_PROVIDERS: FrozenSet[str] = frozenset(
    {"perplexity", "perplexity_sonar", "tavily_answer", "exa_answer", "llm_summary"}
)

_SECRET_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"\bglpat-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"\bhf_[A-Za-z0-9]{24,}"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}"),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{16,}"),
)

_PROPRIETARY_PATH_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"/Users/[A-Za-z0-9_\-\.]+/"),
    re.compile(r"/home/[A-Za-z0-9_\-\.]+/"),
    re.compile(r"/root/"),
    re.compile(r"\b[A-Za-z]:\\Users\\", re.IGNORECASE),
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"\bFile \"[^\"]+\.py\", line \d+"),
)

_TOKEN_CANDIDATE_RE = re.compile(r"[A-Za-z0-9+/=_\-]{%d,}" % HIGH_ENTROPY_MIN_LEN)
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?(?:-->|\Z)")
_WORD_RE = re.compile(r"[a-z0-9]+")

_IPI_OVERRIDE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|directions|directives|context|rules)"),
    re.compile(r"disregard\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|system)\s+(?:instructions|directives|rules)"),
    re.compile(r"forget\s+(?:everything|all)\s+(?:above|before|previous|prior)"),
    re.compile(r"you\s+are\s+now\s+(?:in\s+)?(?:developer|dan|jailbreak|god)\s+mode"),
    re.compile(r"\bnew\s+instructions\s*:"),
    re.compile(r"<\s*/?\s*tool_call\s*>"),
    re.compile(r"\bsystem\s+override\s*:"),
    re.compile(r"execute\s+(?:the\s+following\s+)?shell\s+command"),
    re.compile(r"\bexfiltrate\b"),
    re.compile(r"do\s+not\s+(?:tell|inform|reveal\s+to)\s+the\s+user"),
)

# Partial confusable fold (Cyrillic / Greek lookalikes -> Latin). Not a full
# Unicode TR39 skeleton; documented as partial coverage.
_CONFUSABLE_FOLD: Dict[int, str] = {
    ord(src): dst
    for src, dst in (
        ("\u0430", "a"), ("\u0435", "e"), ("\u043e", "o"), ("\u0440", "p"),
        ("\u0441", "c"), ("\u0443", "y"), ("\u0445", "x"), ("\u0456", "i"),
        ("\u0458", "j"), ("\u0455", "s"), ("\u0501", "d"), ("\u04cf", "l"),
        ("\u0261", "g"), ("\u03bf", "o"), ("\u03b1", "a"), ("\u03b9", "i"),
        ("\u03bd", "v"), ("\u03b5", "e"), ("\u03ba", "k"), ("\u03c4", "t"),
        ("\u03c1", "p"), ("\u0442", "t"), ("\u043d", "h"), ("\u043c", "m"),
        ("\u0432", "b"), ("\u043a", "k"),
    )
}

_HIDDEN_STYLE_RE = re.compile(
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:\.0+)?\s*(?:;|$)|font-size\s*:\s*0(?:px|pt|em)?\s*(?:;|$))",
    re.IGNORECASE,
)
_ALWAYS_HIDDEN_TAGS: FrozenSet[str] = frozenset(
    {"script", "style", "template", "noscript", "head", "title", "meta"}
)
_VOID_TAGS: FrozenSet[str] = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
     "meta", "param", "source", "track", "wbr"}
)


class _VisibleTextExtractor(HTMLParser):
    """Collects text that a browser would render; drops hidden subtrees."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.stack: List[Tuple[str, bool]] = []
        self.hidden_depth = 0
        self.hidden_subtrees = 0

    def _is_hidden(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> bool:
        if tag in _ALWAYS_HIDDEN_TAGS:
            return True
        for name, value in attrs:
            lname = name.lower()
            val = value or ""
            if lname == "hidden":
                return True
            if lname == "aria-hidden" and val.strip().lower() == "true":
                return True
            if lname == "style" and _HIDDEN_STYLE_RE.search(val):
                return True
        return False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        hidden = self._is_hidden(tag, attrs)
        if tag in _VOID_TAGS:
            if hidden:
                self.hidden_subtrees += 1
            return
        if hidden:
            self.hidden_depth += 1
            self.hidden_subtrees += 1
        self.stack.append((tag, hidden))

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if self._is_hidden(tag, attrs):
            self.hidden_subtrees += 1

    def handle_endtag(self, tag: str) -> None:
        if not any(open_tag == tag for open_tag, _ in self.stack):
            return
        while self.stack:
            open_tag, hidden = self.stack.pop()
            if hidden:
                self.hidden_depth -= 1
            if open_tag == tag:
                break

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0:
            self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        self.hidden_subtrees += 1


@dataclass(frozen=True)
class SearchQueryRouteDecision:
    """Routing and egress verdict for an outbound research query."""

    allowed: bool
    reason_code: str
    selected_provider_layer: str
    fallback_provider_layer: str
    egress_tier: str
    max_epistemic_tier: str
    sanitized_query: str
    query_caid: str


@dataclass(frozen=True)
class RawWebEvidenceItem:
    """Untrusted evidence item returned by an external search or answer engine."""

    source_url: str
    provider: str
    raw_text: str
    is_llm_synthesized_answer: bool = False
    primary_span_quote: str = ""
    root_origin_id: str = ""
    claimed_confidence_bps: int = 7000  # claim: config


@dataclass(frozen=True)
class SanitizedWebEvidenceItem:
    """Sanitized and taint-tagged evidence item after airlock inspection."""

    source_url: str
    normalized_domain: str
    provider: str
    sanitized_text: str
    quarantined: bool
    quarantine_reason: str
    ipi_indicators_removed: int
    epistemic_tier: str
    effective_confidence_bps: int
    root_origin_key: str
    content_digest: str
    span_caid: str


@dataclass(frozen=True)
class LocalOracleReceipt:
    """Ed25519-signed verdict from a local deterministic oracle (tests / AST gate)."""

    oracle_id: str
    query_caid: str
    subject_digest: str
    verdict: str
    signature_b64: str


@dataclass(frozen=True)
class WebResearchQuarantineBundle:
    """Signed airlock quarantine receipt over a batch of web search results."""

    query_caid: str
    total_raw_items: int
    admitted_items_count: int
    quarantined_items_count: int
    duplicate_root_origins_collapsed: int
    unique_root_origins: int
    aggregate_confidence_bps: int
    taint_tier: str
    can_authorize_code_mutation: bool
    authorized_subject_digest: str
    mutation_denial_reason: str
    items: Tuple[SanitizedWebEvidenceItem, ...]
    bundle_caid: str
    signature_b64: str


def _strip_invisible_unicode(text: str) -> Tuple[str, int]:
    """Remove Unicode format characters (category Cf), including tag characters."""
    removed = 0
    out_chars: List[str] = []
    for ch in text:
        code = ord(ch)
        is_tag_char = UNICODE_TAG_START <= code <= UNICODE_TAG_END
        if is_tag_char or unicodedata.category(ch) == "Cf":
            removed += 1
        else:
            out_chars.append(ch)
    return "".join(out_chars), removed


def _detection_skeleton(text: str) -> str:
    """NFKC + casefold + partial confusable fold + whitespace collapse."""
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_CONFUSABLE_FOLD)
    return " ".join(folded.split())


def _shannon_millibits_per_char(token: str) -> int:
    """Shannon entropy of a token in millibits per character (integer)."""
    if not token:
        return 0
    counts: Dict[str, int] = {}
    for ch in token:
        counts[ch] = counts.get(ch, 0) + 1
    length = len(token)
    entropy = 0.0
    for c in counts.values():
        p = c / length
        entropy -= p * math.log2(p)
    return int(entropy * 1000)


def _contains_high_entropy_token(text: str) -> bool:
    """Detect long high-entropy strings that look like unprefixed credentials."""
    for match in _TOKEN_CANDIDATE_RE.finditer(text):
        token = match.group(0)
        has_digit = any(ch.isdigit() for ch in token)
        has_alpha = any(ch.isalpha() for ch in token)
        if has_digit and has_alpha and _shannon_millibits_per_char(token) >= HIGH_ENTROPY_MIN_MILLIBITS:
            return True
    return False


def _extract_normalized_domain(url: str) -> str:
    """Extract lowercase hostname without leading 'www.' from a URL."""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        return host[4:]
    return host


def _is_primary_authoritative_domain(domain: str) -> bool:
    """Check whether a domain belongs to the primary scientific/standards allowlist."""
    if not domain:
        return False
    for allowed in PRIMARY_AUTHORITATIVE_DOMAINS:
        if domain == allowed or domain.endswith("." + allowed):
            return True
    return False


def _shingles(skeleton: str) -> Set[str]:
    """Word 5-gram shingles of a detection skeleton."""
    words = _WORD_RE.findall(skeleton)
    if len(words) < SHINGLE_WORDS:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1)}


def _jaccard_bps(a: Set[str], b: Set[str]) -> int:
    """Jaccard similarity in integer basis points."""
    union = a | b
    if not union:
        return 0
    return (len(a & b) * BPS_FULL_SCALE) // len(union)


def _public_key_bytes(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw)


def compute_span_caid(item: SanitizedWebEvidenceItem) -> str:
    """SHA-256 over RFC 8785 JCS of every item field except span_caid."""
    payload = dataclasses.asdict(item)
    payload.pop("span_caid")
    return hashlib.sha256(encode_jcs(payload)).hexdigest()


def oracle_receipt_payload(oracle_id: str, query_caid: str, subject_digest: str, verdict: str) -> bytes:
    """Canonical bytes signed by a local oracle."""
    return encode_jcs(
        {
            "domain": "AEIB_WEB_RESEARCH_ORACLE_RECEIPT_V1",
            "oracle_id": oracle_id,
            "query_caid": query_caid,
            "subject_digest": subject_digest,
            "verdict": verdict,
        }
    )


def sign_oracle_receipt(
    oracle_key: Ed25519PrivateKey,
    oracle_id: str,
    query_caid: str,
    subject_digest: str,
    verdict: str,
) -> LocalOracleReceipt:
    """Issue an oracle receipt (used by the local test/AST oracle process)."""
    sig = oracle_key.sign(oracle_receipt_payload(oracle_id, query_caid, subject_digest, verdict))
    return LocalOracleReceipt(
        oracle_id=oracle_id,
        query_caid=query_caid,
        subject_digest=subject_digest,
        verdict=verdict,
        signature_b64=base64.b64encode(sig).decode("ascii"),
    )


def verify_oracle_receipt(receipt: LocalOracleReceipt, trusted_key: Ed25519PublicKey) -> bool:
    """Verify an oracle receipt signature under a trusted oracle key."""
    try:
        sig = base64.b64decode(receipt.signature_b64, validate=True)
        trusted_key.verify(
            sig,
            oracle_receipt_payload(
                receipt.oracle_id, receipt.query_caid, receipt.subject_digest, receipt.verdict
            ),
        )
    except (InvalidSignature, ValueError):
        return False
    return True


def _bundle_payload(
    query_caid: str,
    total_raw_items: int,
    admitted: int,
    quarantined: int,
    collapsed: int,
    unique_roots: int,
    aggregate_bps: int,
    taint_tier: str,
    can_mutate: bool,
    subject_digest: str,
    denial_reason: str,
    span_caids: List[str],
) -> Dict[str, Any]:
    return {
        "admitted_items_count": admitted,
        "aggregate_confidence_bps": aggregate_bps,
        "authorized_subject_digest": subject_digest,
        "can_authorize_code_mutation": can_mutate,
        "domain": "AEIB_WEB_RESEARCH_QUARANTINE_BUNDLE_V2",
        "duplicate_root_origins_collapsed": collapsed,
        "item_span_caids": span_caids,
        "mutation_denial_reason": denial_reason,
        "quarantined_items_count": quarantined,
        "query_caid": query_caid,
        "taint_tier": taint_tier,
        "total_raw_items": total_raw_items,
        "unique_root_origins": unique_roots,
    }


class WebResearchQuarantineRouter:
    """Zero-egress query router, hidden-carrier sanitizer, and POIROT collapse gate."""

    def __init__(self, local_searxng_available: bool = True) -> None:
        self._local_searxng_available = bool(local_searxng_available)

    def _blocked(self, reason: str, sanitized_query: str, query_caid: str) -> SearchQueryRouteDecision:
        return SearchQueryRouteDecision(
            allowed=False,
            reason_code=reason,
            selected_provider_layer="NONE",
            fallback_provider_layer="NONE",
            egress_tier="BLOCKED",
            max_epistemic_tier="T0_NONE",
            sanitized_query=sanitized_query,
            query_caid=query_caid,
        )

    def route_query(
        self,
        query: str,
        intent: str = "PRIMARY_LITERATURE",
        allow_cloud_egress: bool = True,
    ) -> SearchQueryRouteDecision:
        """Classify query confidentiality and route to the appropriate search layer."""
        if len(query) > MAX_QUERY_CHARS:
            oversize_caid = hashlib.sha256(
                encode_jcs({"intent": intent, "oversize_len": len(query)})
            ).hexdigest()
            return self._blocked("HALT_QUERY_OVERSIZE", "", oversize_caid)

        stripped, _ = _strip_invisible_unicode(query)
        cleaned_query = " ".join(unicodedata.normalize("NFKC", stripped).split())
        query_caid = hashlib.sha256(
            encode_jcs(
                {
                    "allow_cloud_egress": allow_cloud_egress,
                    "intent": intent,
                    "query": cleaned_query,
                }
            )
        ).hexdigest()

        if not cleaned_query:
            return self._blocked("HALT_EMPTY_SEARCH_QUERY", "", query_caid)

        if any(p.search(cleaned_query) for p in _SECRET_PATTERNS) or _contains_high_entropy_token(cleaned_query):
            return self._blocked("HALT_SECRET_IN_SEARCH_QUERY", "[REDACTED_SECRET_QUERY]", query_caid)

        has_proprietary_marker = any(p.search(cleaned_query) for p in _PROPRIETARY_PATH_PATTERNS)
        if has_proprietary_marker or not allow_cloud_egress or intent == "PRIVATE_METASEARCH":
            if self._local_searxng_available:
                return SearchQueryRouteDecision(
                    allowed=True,
                    reason_code="ROUTED_LOCAL_ZERO_SAAS_EGRESS",
                    selected_provider_layer="SEARXNG_LOCAL",
                    fallback_provider_layer="LOCAL_ARXIV_MIRROR",
                    egress_tier="LOCAL_SELF_HOSTED",
                    max_epistemic_tier="T2_PRIMARY_FETCHABLE",
                    sanitized_query=cleaned_query,
                    query_caid=query_caid,
                )
            return self._blocked("HALT_PROPRIETARY_SYMBOL_CLOUD_LEAKAGE", cleaned_query, query_caid)

        routes = {
            "PRIMARY_LITERATURE": ("ROUTED_PRIMARY_SEMANTIC_DISCOVERY", "EXA_SEMANTIC_PRIMARY", "ARXIV_OPENALEX_API", "T2_PRIMARY_VERIFIED"),
            "URL_MARKDOWN_EXTRACTION": ("ROUTED_STRUCTURAL_MARKDOWN_EXTRACTOR", "FIRECRAWL_JINA_READER", "SEARXNG_LOCAL", "T2_PRIMARY_VERIFIED"),
            "DEEP_AGENTIC_TRAVERSAL": ("ROUTED_MULTI_HOP_KNOWLEDGE_DAG", "TONGYI_WEBSWARM_DAG", "EXA_SEMANTIC_PRIMARY", "T2_PRIMARY_VERIFIED"),
            "FAST_SYNTHESIS_TRIAGE": ("ROUTED_SYNTHESIS_LEAD_GENERATOR_ONLY", "PERPLEXITY_SONAR_LEAD_ONLY", "TAVILY_FAST_SEARCH", "T1_SYNTHESIZED_LEAD"),
        }
        route = routes.get(intent)
        if route is None:
            return self._blocked("HALT_UNKNOWN_SEARCH_INTENT", cleaned_query, query_caid)
        reason, layer, fallback, tier = route
        return SearchQueryRouteDecision(
            allowed=True,
            reason_code=reason,
            selected_provider_layer=layer,
            fallback_provider_layer=fallback,
            egress_tier="CLOUD_PUBLIC_QUERY",
            max_epistemic_tier=tier,
            sanitized_query=cleaned_query,
            query_caid=query_caid,
        )

    @staticmethod
    def _finalize(item: SanitizedWebEvidenceItem) -> SanitizedWebEvidenceItem:
        return dataclasses.replace(item, span_caid=compute_span_caid(item))

    def _quarantine(
        self,
        raw: RawWebEvidenceItem,
        domain: str,
        root_key: str,
        reason: str,
        indicators: int,
        text: str,
    ) -> SanitizedWebEvidenceItem:
        return self._finalize(
            SanitizedWebEvidenceItem(
                source_url=raw.source_url,
                normalized_domain=domain,
                provider=raw.provider,
                sanitized_text=text,
                quarantined=True,
                quarantine_reason=reason,
                ipi_indicators_removed=indicators,
                epistemic_tier="T0_QUARANTINED",
                effective_confidence_bps=0,
                root_origin_key=root_key,
                content_digest="",
                span_caid="",
            )
        )

    def sanitize_evidence_item(self, item: RawWebEvidenceItem) -> SanitizedWebEvidenceItem:
        """Sanitize a single raw web evidence item and assign its epistemic tier."""
        domain = _extract_normalized_domain(item.source_url)
        root_key = item.root_origin_id.strip().lower() or domain or item.source_url.strip().lower()

        if len(item.raw_text) > MAX_RAW_TEXT_CHARS:
            return self._quarantine(item, domain, root_key, "QUARANTINED_OVERSIZE_PAYLOAD", 0, "")

        # Decode entities once up front so encoded markup (&lt;!-- ... --&gt;) is
        # parsed as markup rather than surviving as visible text.
        decoded = html.unescape(item.raw_text)
        without_comments, comment_n = _HTML_COMMENT_RE.subn("", decoded)

        extractor = _VisibleTextExtractor()
        extractor.feed(without_comments)
        extractor.close()
        visible = "".join(extractor.parts)
        removed_indicators = comment_n + extractor.hidden_subtrees

        visible, unicode_n = _strip_invisible_unicode(visible)
        removed_indicators += unicode_n
        cleaned_text = " ".join(unicodedata.normalize("NFKC", visible).split())

        skeleton = _detection_skeleton(cleaned_text)
        if any(p.search(skeleton) for p in _IPI_OVERRIDE_PATTERNS):
            return self._quarantine(
                item,
                domain,
                root_key,
                "QUARANTINED_INDIRECT_PROMPT_INJECTION",
                removed_indicators + 1,
                "[QUARANTINED_INDIRECT_PROMPT_INJECTION_PAYLOAD]",
            )

        if not cleaned_text:
            return self._quarantine(
                item, domain, root_key, "QUARANTINED_EMPTY_AFTER_SANITIZATION", removed_indicators, ""
            )

        bounded_claim_bps = max(0, min(BPS_FULL_SCALE, int(item.claimed_confidence_bps)))
        scheme = urlparse(item.source_url.strip()).scheme.lower()
        is_synthesized = item.is_llm_synthesized_answer or item.provider.strip().lower() in SYNTHESIZING_PROVIDERS
        quote_skeleton = _detection_skeleton(item.primary_span_quote)
        quote_present = len(quote_skeleton) >= MIN_PRIMARY_QUOTE_CHARS and quote_skeleton in skeleton

        if is_synthesized:
            # Data Processing Inequality cap: synthesized prose is a lead, never T2,
            # even when it quotes a span (the quote itself is unverified).
            epistemic_tier = "T1_SYNTHESIZED_LEAD"
            effective_bps = min(bounded_claim_bps, SYNTHESIZED_LEAD_CAP_BPS)
        elif scheme == "https" and _is_primary_authoritative_domain(domain) and quote_present:
            epistemic_tier = "T2_PRIMARY_VERIFIED"
            effective_bps = min(bounded_claim_bps, PRIMARY_VERIFIED_CAP_BPS)
        else:
            epistemic_tier = "T1_SECONDARY_WEB"
            effective_bps = min(bounded_claim_bps, SECONDARY_WEB_CAP_BPS)

        return self._finalize(
            SanitizedWebEvidenceItem(
                source_url=item.source_url,
                normalized_domain=domain,
                provider=item.provider,
                sanitized_text=cleaned_text,
                quarantined=False,
                quarantine_reason="ADMITTED_SANITIZED",
                ipi_indicators_removed=removed_indicators,
                epistemic_tier=epistemic_tier,
                effective_confidence_bps=effective_bps,
                root_origin_key=root_key,
                content_digest=hashlib.sha256(skeleton.encode("utf-8")).hexdigest(),
                span_caid="",
            )
        )

    def ingest_and_quarantine(
        self,
        query_caid: str,
        raw_items: Sequence[RawWebEvidenceItem],
        signing_key: Ed25519PrivateKey,
        oracle_receipt: Optional[LocalOracleReceipt] = None,
        trusted_oracle_key: Optional[Ed25519PublicKey] = None,
    ) -> WebResearchQuarantineBundle:
        """Sanitize, collapse echo clusters, bind optional oracle receipt, and sign."""
        if len(raw_items) > MAX_ITEMS_PER_BUNDLE:
            raise ValueError("ERR_BUNDLE_OVERSIZE")

        slots: List[SanitizedWebEvidenceItem] = []
        cluster_shingles: Dict[int, Set[str]] = {}
        root_to_cluster: Dict[str, int] = {}
        digest_to_cluster: Dict[str, int] = {}
        quarantined_count = 0
        duplicates_collapsed = 0

        for raw in raw_items:
            sanitized = self.sanitize_evidence_item(raw)
            if sanitized.quarantined:
                quarantined_count += 1
                slots.append(sanitized)
                continue

            shingles = _shingles(_detection_skeleton(sanitized.sanitized_text))
            match = root_to_cluster.get(sanitized.root_origin_key)
            if match is None:
                match = digest_to_cluster.get(sanitized.content_digest)
            if match is None:
                for rep, rep_shingles in cluster_shingles.items():
                    if _jaccard_bps(shingles, rep_shingles) >= NEAR_DUPLICATE_JACCARD_BPS:
                        match = rep
                        break

            if match is not None:
                duplicates_collapsed += 1
                root_to_cluster[sanitized.root_origin_key] = match
                digest_to_cluster[sanitized.content_digest] = match
                if sanitized.effective_confidence_bps > slots[match].effective_confidence_bps:
                    slots[match] = sanitized
                continue

            idx = len(slots)
            slots.append(sanitized)
            cluster_shingles[idx] = shingles
            root_to_cluster[sanitized.root_origin_key] = idx
            digest_to_cluster[sanitized.content_digest] = idx

        admitted = [s for s in slots if not s.quarantined]
        unique_roots = len(cluster_shingles)

        aggregate_bps = 0
        if admitted:
            residual_failure_bps = BPS_FULL_SCALE
            for it in admitted:
                discounted_bps = (it.effective_confidence_bps * CORRELATED_DISCOUNT_BPS) // BPS_FULL_SCALE
                residual_failure_bps = (residual_failure_bps * (BPS_FULL_SCALE - discounted_bps)) // BPS_FULL_SCALE
            aggregate_bps = BPS_FULL_SCALE - residual_failure_bps

        can_mutate, subject_digest, denial = self._evaluate_oracle(
            query_caid, aggregate_bps, signing_key, oracle_receipt, trusted_oracle_key
        )

        span_caids = [s.span_caid for s in slots]
        payload = _bundle_payload(
            query_caid, len(raw_items), len(admitted), quarantined_count, duplicates_collapsed,
            unique_roots, aggregate_bps, "TIER_2_EXTERNAL_WEB", can_mutate, subject_digest,
            denial, span_caids,
        )
        canonical_bytes = encode_jcs(payload)
        return WebResearchQuarantineBundle(
            query_caid=query_caid,
            total_raw_items=len(raw_items),
            admitted_items_count=len(admitted),
            quarantined_items_count=quarantined_count,
            duplicate_root_origins_collapsed=duplicates_collapsed,
            unique_root_origins=unique_roots,
            aggregate_confidence_bps=aggregate_bps,
            taint_tier="TIER_2_EXTERNAL_WEB",
            can_authorize_code_mutation=can_mutate,
            authorized_subject_digest=subject_digest,
            mutation_denial_reason=denial,
            items=tuple(slots),
            bundle_caid=hashlib.sha256(canonical_bytes).hexdigest(),
            signature_b64=base64.b64encode(signing_key.sign(canonical_bytes)).decode("ascii"),
        )

    @staticmethod
    def _evaluate_oracle(
        query_caid: str,
        aggregate_bps: int,
        signing_key: Ed25519PrivateKey,
        receipt: Optional[LocalOracleReceipt],
        trusted_key: Optional[Ed25519PublicKey],
    ) -> Tuple[bool, str, str]:
        """Return (can_mutate, subject_digest, denial_reason); fails closed."""
        if receipt is None or trusted_key is None:
            return False, "", "DENY_NO_ORACLE_RECEIPT"
        if _public_key_bytes(trusted_key) == _public_key_bytes(signing_key.public_key()):
            return False, "", "DENY_ORACLE_KEY_EQUALS_BUNDLE_KEY"
        if not verify_oracle_receipt(receipt, trusted_key):
            return False, "", "DENY_ORACLE_SIGNATURE_INVALID"
        if receipt.query_caid != query_caid:
            return False, "", "DENY_ORACLE_QUERY_MISMATCH"
        if receipt.verdict != "PASS":
            return False, "", "DENY_ORACLE_VERDICT_NOT_PASS"
        if aggregate_bps < MUTATION_AUTHORIZATION_FLOOR_BPS:
            return False, "", "DENY_AGGREGATE_BELOW_FLOOR"
        return True, receipt.subject_digest, "AUTHORIZED_WITH_ORACLE_RECEIPT"

    @staticmethod
    def verify_bundle_signature(
        bundle: WebResearchQuarantineBundle,
        public_key: Ed25519PublicKey,
    ) -> bool:
        """Verify Ed25519 signature, JCS digest, and every item's recomputed digest."""
        for item in bundle.items:
            if compute_span_caid(item) != item.span_caid:
                return False
        payload = _bundle_payload(
            bundle.query_caid, bundle.total_raw_items, bundle.admitted_items_count,
            bundle.quarantined_items_count, bundle.duplicate_root_origins_collapsed,
            bundle.unique_root_origins, bundle.aggregate_confidence_bps, bundle.taint_tier,
            bundle.can_authorize_code_mutation, bundle.authorized_subject_digest,
            bundle.mutation_denial_reason, [it.span_caid for it in bundle.items],
        )
        canonical_bytes = encode_jcs(payload)
        if hashlib.sha256(canonical_bytes).hexdigest() != bundle.bundle_caid:
            return False
        try:
            public_key.verify(base64.b64decode(bundle.signature_b64, validate=True), canonical_bytes)
        except (InvalidSignature, ValueError):
            return False
        return True
