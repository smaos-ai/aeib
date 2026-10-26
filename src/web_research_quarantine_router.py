"""Zero-egress web research quarantine router and multi-provider combination gate.

Addresses four failure modes observed when connecting external web search or
answer engines (such as Perplexity Sonar, Exa, Tavily, Firecrawl, Jina Reader,
SearXNG, or multi-hop agentic search frameworks like Tongyi DeepResearch,
WebSailor, FlowSearch, and WebSwarm) to a high-assurance coding agent:

1. Query Confidentiality & Secret/Symbol Egress Protection:
   Blocks queries containing credentials or proprietary workspace paths/stack
   traces from leaking to third-party cloud search APIs, routing internal symbol
   queries strictly to self-hosted ``SEARXNG_LOCAL`` or halting closed.
2. Task-Specific Multi-Provider Layer Routing:
   Separates Answer Synthesis (``PERPLEXITY_SONAR_LEAD_ONLY``) from Semantic
   Primary Discovery (``EXA_SEMANTIC_PRIMARY``), Clean Markdown Extraction
   (``FIRECRAWL_JINA_READER``), Private Metasearch (``SEARXNG_LOCAL``), and
   Multi-Hop DAG Traversal (``TONGYI_WEBSWARM_DAG``).
3. Indirect Prompt Injection (IPI) & Hidden-Carrier Sanitization:
   Strips HTML comments, script/style tags, Unicode tag characters
   (U+E0000..U+E007F), zero-width joiners, and quarantines spans containing
   instruction-override or tool-call spoofing payloads.
4. POIROT Root-Origin Deduplication, DPI Synthesis Cap, & Bell-LaPadula Taint:
   Collapses syndicated clones sharing a ``root_origin_id``, caps unverified
   LLM-synthesized prose (e.g. raw Perplexity summaries without primary spans)
   at ``T1_SYNTHESIZED_LEAD`` (4500 bps), pins ``taint_tier="TIER_2_EXTERNAL_WEB"``,
   and signs the quarantine bundle with Ed25519 over RFC 8785 JCS.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple
from urllib.parse import urlparse

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.jcs_canonicalizer import encode_jcs

BPS_FULL_SCALE: int = 10000
SYNTHESIZED_LEAD_CAP_BPS: int = 4500  # claim: config
PRIMARY_VERIFIED_CAP_BPS: int = 9000  # claim: config
CORRELATED_DISCOUNT_BPS: int = 7500  # claim: config
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

_SECRET_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{16,}"),
)

_PROPRIETARY_PATH_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"/Users/[A-Za-z0-9_\-]+/"),
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"\bFile \"[^\"]+\.py\", line \d+"),
)

_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>[\s\S]*?</\1>", re.IGNORECASE
)
_HIDDEN_DOM_RE = re.compile(
    r"<[^>]+(?:display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0)[^>]*>[\s\S]*?</[^>]+>",
    re.IGNORECASE,
)

_IPI_OVERRIDE_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|system)\s+directives", re.IGNORECASE),
    re.compile(r"<\s*/?\s*tool_call\s*>", re.IGNORECASE),
    re.compile(r"\bsystem\s+override\s*:", re.IGNORECASE),
    re.compile(r"execute\s+shell\s+command", re.IGNORECASE),
)


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
    has_primary_span_quote: bool = False
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
    span_caid: str


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
    items: Tuple[SanitizedWebEvidenceItem, ...]
    bundle_caid: str
    signature_b64: str


def _strip_invisible_unicode(text: str) -> Tuple[str, int]:
    """Remove invisible Unicode tag characters and zero-width characters."""
    removed = 0
    out_chars: List[str] = []
    for ch in text:
        code = ord(ch)
        is_tag_char = UNICODE_TAG_START <= code <= UNICODE_TAG_END
        is_zero_width = code in (0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF)
        if is_tag_char or is_zero_width:
            removed += 1
        else:
            out_chars.append(ch)
    return "".join(out_chars), removed


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


class WebResearchQuarantineRouter:
    """Zero-egress query router, IPI sanitizer, and POIROT deduplication gate."""

    def __init__(self, local_searxng_available: bool = True) -> None:
        self._local_searxng_available = bool(local_searxng_available)

    def route_query(
        self,
        query: str,
        intent: str = "PRIMARY_LITERATURE",
        allow_cloud_egress: bool = True,
    ) -> SearchQueryRouteDecision:
        """Classify query confidentiality and route to the appropriate search layer."""
        cleaned_query = query.strip()
        payload = {
            "allow_cloud_egress": allow_cloud_egress,
            "intent": intent,
            "query": cleaned_query,
        }
        query_caid = hashlib.sha256(encode_jcs(payload)).hexdigest()

        if not cleaned_query:
            return SearchQueryRouteDecision(
                allowed=False,
                reason_code="HALT_EMPTY_SEARCH_QUERY",
                selected_provider_layer="NONE",
                fallback_provider_layer="NONE",
                egress_tier="BLOCKED",
                max_epistemic_tier="T0_NONE",
                sanitized_query="",
                query_caid=query_caid,
            )

        for secret_pat in _SECRET_PATTERNS:
            if secret_pat.search(cleaned_query):
                return SearchQueryRouteDecision(
                    allowed=False,
                    reason_code="HALT_SECRET_IN_SEARCH_QUERY",
                    selected_provider_layer="NONE",
                    fallback_provider_layer="NONE",
                    egress_tier="BLOCKED",
                    max_epistemic_tier="T0_NONE",
                    sanitized_query="[REDACTED_SECRET_QUERY]",
                    query_caid=query_caid,
                )

        has_proprietary_marker = any(
            pat.search(cleaned_query) for pat in _PROPRIETARY_PATH_PATTERNS
        )
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
            return SearchQueryRouteDecision(
                allowed=False,
                reason_code="HALT_PROPRIETARY_SYMBOL_CLOUD_LEAKAGE",
                selected_provider_layer="NONE",
                fallback_provider_layer="NONE",
                egress_tier="BLOCKED",
                max_epistemic_tier="T0_NONE",
                sanitized_query=cleaned_query,
                query_caid=query_caid,
            )

        if intent == "PRIMARY_LITERATURE":
            return SearchQueryRouteDecision(
                allowed=True,
                reason_code="ROUTED_PRIMARY_SEMANTIC_DISCOVERY",
                selected_provider_layer="EXA_SEMANTIC_PRIMARY",
                fallback_provider_layer="ARXIV_OPENALEX_API",
                egress_tier="CLOUD_PUBLIC_QUERY",
                max_epistemic_tier="T2_PRIMARY_VERIFIED",
                sanitized_query=cleaned_query,
                query_caid=query_caid,
            )

        if intent == "URL_MARKDOWN_EXTRACTION":
            return SearchQueryRouteDecision(
                allowed=True,
                reason_code="ROUTED_STRUCTURAL_MARKDOWN_EXTRACTOR",
                selected_provider_layer="FIRECRAWL_JINA_READER",
                fallback_provider_layer="SEARXNG_LOCAL",
                egress_tier="CLOUD_PUBLIC_QUERY",
                max_epistemic_tier="T2_PRIMARY_VERIFIED",
                sanitized_query=cleaned_query,
                query_caid=query_caid,
            )

        if intent == "DEEP_AGENTIC_TRAVERSAL":
            return SearchQueryRouteDecision(
                allowed=True,
                reason_code="ROUTED_MULTI_HOP_KNOWLEDGE_DAG",
                selected_provider_layer="TONGYI_WEBSWARM_DAG",
                fallback_provider_layer="EXA_SEMANTIC_PRIMARY",
                egress_tier="CLOUD_PUBLIC_QUERY",
                max_epistemic_tier="T2_PRIMARY_VERIFIED",
                sanitized_query=cleaned_query,
                query_caid=query_caid,
            )

        if intent == "FAST_SYNTHESIS_TRIAGE":
            return SearchQueryRouteDecision(
                allowed=True,
                reason_code="ROUTED_SYNTHESIS_LEAD_GENERATOR_ONLY",
                selected_provider_layer="PERPLEXITY_SONAR_LEAD_ONLY",
                fallback_provider_layer="TAVILY_FAST_SEARCH",
                egress_tier="CLOUD_PUBLIC_QUERY",
                max_epistemic_tier="T1_SYNTHESIZED_LEAD",
                sanitized_query=cleaned_query,
                query_caid=query_caid,
            )

        return SearchQueryRouteDecision(
            allowed=False,
            reason_code="HALT_UNKNOWN_SEARCH_INTENT",
            selected_provider_layer="NONE",
            fallback_provider_layer="NONE",
            egress_tier="BLOCKED",
            max_epistemic_tier="T0_NONE",
            sanitized_query=cleaned_query,
            query_caid=query_caid,
        )

    def sanitize_evidence_item(
        self, item: RawWebEvidenceItem
    ) -> SanitizedWebEvidenceItem:
        """Sanitize a single raw web evidence item and assign its epistemic tier."""
        text = item.raw_text
        removed_indicators = 0

        text, html_comments_n = _HTML_COMMENT_RE.subn("", text)
        removed_indicators += html_comments_n

        text, script_n = _SCRIPT_STYLE_RE.subn("", text)
        removed_indicators += script_n

        text, hidden_dom_n = _HIDDEN_DOM_RE.subn("", text)
        removed_indicators += hidden_dom_n

        text, unicode_n = _strip_invisible_unicode(text)
        removed_indicators += unicode_n

        cleaned_text = " ".join(text.split())
        domain = _extract_normalized_domain(item.source_url)
        root_key = (item.root_origin_id.strip().lower() or domain or item.source_url.strip().lower())

        has_ipi_override = any(
            pat.search(cleaned_text) for pat in _IPI_OVERRIDE_PATTERNS
        )
        if has_ipi_override:
            span_caid = hashlib.sha256(
                encode_jcs(
                    {
                        "quarantined": True,
                        "source_url": item.source_url,
                    }
                )
            ).hexdigest()
            return SanitizedWebEvidenceItem(
                source_url=item.source_url,
                normalized_domain=domain,
                provider=item.provider,
                sanitized_text="[QUARANTINED_INDIRECT_PROMPT_INJECTION_PAYLOAD]",
                quarantined=True,
                quarantine_reason="QUARANTINED_INDIRECT_PROMPT_INJECTION",
                ipi_indicators_removed=removed_indicators + 1,
                epistemic_tier="T0_QUARANTINED",
                effective_confidence_bps=0,
                root_origin_key=root_key,
                span_caid=span_caid,
            )

        if not cleaned_text:
            span_caid = hashlib.sha256(
                encode_jcs({"empty": True, "source_url": item.source_url})
            ).hexdigest()
            return SanitizedWebEvidenceItem(
                source_url=item.source_url,
                normalized_domain=domain,
                provider=item.provider,
                sanitized_text="",
                quarantined=True,
                quarantine_reason="QUARANTINED_EMPTY_AFTER_SANITIZATION",
                ipi_indicators_removed=removed_indicators,
                epistemic_tier="T0_QUARANTINED",
                effective_confidence_bps=0,
                root_origin_key=root_key,
                span_caid=span_caid,
            )

        bounded_claim_bps = max(0, min(BPS_FULL_SCALE, int(item.claimed_confidence_bps)))
        is_primary_domain = _is_primary_authoritative_domain(domain)

        # Data Processing Inequality (DPI) & Perplexity synthesis cap:
        # An LLM-synthesized prose answer without a direct primary span quote is
        # capped at T1_SYNTHESIZED_LEAD (4500 bps) and cannot be treated as T2.
        if item.is_llm_synthesized_answer and not item.has_primary_span_quote:
            epistemic_tier = "T1_SYNTHESIZED_LEAD"
            effective_bps = min(bounded_claim_bps, SYNTHESIZED_LEAD_CAP_BPS)
        elif is_primary_domain and item.has_primary_span_quote:
            epistemic_tier = "T2_PRIMARY_VERIFIED"
            effective_bps = min(bounded_claim_bps, PRIMARY_VERIFIED_CAP_BPS)
        else:
            epistemic_tier = "T1_SECONDARY_WEB"
            effective_bps = min(bounded_claim_bps, 6000)

        span_payload = {
            "domain": domain,
            "effective_bps": effective_bps,
            "epistemic_tier": epistemic_tier,
            "provider": item.provider,
            "root_origin_key": root_key,
            "sanitized_text": cleaned_text,
            "source_url": item.source_url,
        }
        span_caid = hashlib.sha256(encode_jcs(span_payload)).hexdigest()

        return SanitizedWebEvidenceItem(
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
            span_caid=span_caid,
        )

    def ingest_and_quarantine(
        self,
        query_caid: str,
        raw_items: Sequence[RawWebEvidenceItem],
        signing_key: Ed25519PrivateKey,
        verified_by_local_t4_oracle: bool = False,
    ) -> WebResearchQuarantineBundle:
        """Sanitize items, deduplicate syndicated root origins (POIROT), and sign receipt."""
        sanitized_items: List[SanitizedWebEvidenceItem] = []
        seen_roots: Dict[str, SanitizedWebEvidenceItem] = {}
        quarantined_count = 0
        duplicates_collapsed = 0

        for raw in raw_items:
            sanitized = self.sanitize_evidence_item(raw)
            if sanitized.quarantined:
                quarantined_count += 1
                sanitized_items.append(sanitized)
                continue

            existing = seen_roots.get(sanitized.root_origin_key)
            if existing is not None:
                duplicates_collapsed += 1
                if sanitized.effective_confidence_bps > existing.effective_confidence_bps:
                    seen_roots[sanitized.root_origin_key] = sanitized
                    idx = sanitized_items.index(existing)
                    sanitized_items[idx] = sanitized
                continue

            seen_roots[sanitized.root_origin_key] = sanitized
            sanitized_items.append(sanitized)

        admitted = [it for it in sanitized_items if not it.quarantined]
        unique_roots = len(seen_roots)

        if not admitted:
            aggregate_bps = 0
        else:
            # Correlated-error discounted aggregation across unique root origins only:
            # 1 - prod(1 - p_i * 0.75) in integer basis points
            residual_failure_bps = BPS_FULL_SCALE
            for it in admitted:
                discounted_bps = (
                    it.effective_confidence_bps * CORRELATED_DISCOUNT_BPS
                ) // BPS_FULL_SCALE
                residual_failure_bps = (
                    residual_failure_bps * (BPS_FULL_SCALE - discounted_bps)
                ) // BPS_FULL_SCALE
            aggregate_bps = BPS_FULL_SCALE - residual_failure_bps

        # Bell-LaPadula taint invariant: external web evidence is TIER_2_EXTERNAL_WEB
        # and can NEVER authorize a code mutation on its own without a local T4 oracle.
        can_mutate = bool(verified_by_local_t4_oracle and aggregate_bps >= 6000)

        bundle_payload: Dict[str, Any] = {
            "admitted_items_count": len(admitted),
            "aggregate_confidence_bps": aggregate_bps,
            "can_authorize_code_mutation": can_mutate,
            "duplicate_root_origins_collapsed": duplicates_collapsed,
            "item_span_caids": [it.span_caid for it in sanitized_items],
            "quarantined_items_count": quarantined_count,
            "query_caid": query_caid,
            "taint_tier": "TIER_2_EXTERNAL_WEB",
            "total_raw_items": len(raw_items),
            "unique_root_origins": unique_roots,
        }
        canonical_bytes = encode_jcs(bundle_payload)
        bundle_caid = hashlib.sha256(canonical_bytes).hexdigest()
        signature_b64 = base64.b64encode(signing_key.sign(canonical_bytes)).decode(
            "ascii"
        )

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
            items=tuple(sanitized_items),
            bundle_caid=bundle_caid,
            signature_b64=signature_b64,
        )

    @staticmethod
    def verify_bundle_signature(
        bundle: WebResearchQuarantineBundle,
        public_key: Ed25519PublicKey,
    ) -> bool:
        """Verify Ed25519 signature and RFC 8785 JCS digest of a quarantine bundle."""
        bundle_payload: Dict[str, Any] = {
            "admitted_items_count": bundle.admitted_items_count,
            "aggregate_confidence_bps": bundle.aggregate_confidence_bps,
            "can_authorize_code_mutation": bundle.can_authorize_code_mutation,
            "duplicate_root_origins_collapsed": bundle.duplicate_root_origins_collapsed,
            "item_span_caids": [it.span_caid for it in bundle.items],
            "quarantined_items_count": bundle.quarantined_items_count,
            "query_caid": bundle.query_caid,
            "taint_tier": bundle.taint_tier,
            "total_raw_items": bundle.total_raw_items,
            "unique_root_origins": bundle.unique_root_origins,
        }
        canonical_bytes = encode_jcs(bundle_payload)
        expected_caid = hashlib.sha256(canonical_bytes).hexdigest()
        if expected_caid != bundle.bundle_caid:
            return False
        try:
            sig = base64.b64decode(bundle.signature_b64)
            public_key.verify(sig, canonical_bytes)
            return True
        except Exception:
            return False
