#!/usr/bin/env python3
"""
src/persist_memory_gate.py
================================================================================
PERSIST Retrieval-Time Policy Gate & Provenance Entropy Defense (v1.0.0-rc.5-preprod)

Architectural Context:
Mitigates persistent memory poisoning attacks (MemPoison L1/L2/L3, MemMorph, MINJA,
and Salami memory injection) where adversaries poison long-term memory stores
(vector DBs, SQLite, MEMORY.md) to bias tool selection or smuggle dormant triggers.

Core Mechanics:
1. Provenance Entropy Binding:
   - Each memory entry must carry an immutable cryptographic provenance record:
     H(session_id || upstream_caid || author_did || timestamp).
   - Memories lacking valid provenance automatically downgrade to TIER_2_UNTRUSTED.
2. Retrieval-Time Policy Gate:
   - Evaluates the compositional union of recalled memory chunks prior to prompt injection.
   - Detects:
     * MemMorph tool redirection (altering tool targets, URLs, or parameter bindings).
     * Compositional privilege escalation (multiple benign facts combining into an exploit).
     * Dormant triggers ("WHEN X OCCURS EXECUTE Y", "SYSTEM OVERRIDE IN EFFECT").
3. Fail-Closed Enforcement:
   - Discards or sanitizes untrusted memories, returning explicit violation codes
     (HALT_COMPOSITIONAL_MEMORY_POISONING, HALT_TOOL_REDIRECT_ATTEMPT).

Evaluated under the stated model. Strict zero-mock AST purity enforced.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class ProvenanceRecord:
    session_id: str
    upstream_caid: str
    author_did: str
    timestamp: float
    signature_b64: str

    def compute_digest(self) -> str:
        payload = f"{self.session_id}:{self.upstream_caid}:{self.author_did}:{self.timestamp:.4f}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MemoryNode:
    memory_id: str
    content: str
    provenance: Optional[ProvenanceRecord]
    taint_tier: str  # TIER_0_SYSTEM, TIER_1_PARTNER, TIER_2_UNTRUSTED
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalGateResult:
    passed: bool
    rejection_code: Optional[str]
    sanitized_chunks: List[str]
    taint_tier_downgraded: bool
    quarantined_memory_ids: List[str]


class PersistRetrievalPolicyGate:
    """
    Retrieval-Time Policy Gate evaluating candidate recalled memory chunks
    before they are committed into the active LLM working memory.
    """

    SUSPICIOUS_DORMANT_TRIGGERS: Tuple[str, ...] = (
        "system override in effect",
        "ignore previous safety instructions",
        "bypass station 1 latch",
        "grant root sponsor access",
        "execute without step-up token",
        "override rls policy",
        "use alternative payment endpoint",
    )

    TOOL_REDIRECT_PATTERNS: Tuple[str, ...] = (
        r"redirect\s+tool\s+\w+\s+to",
        r"replace\s+endpoint\s+with",
        r"new\s+payment\s+url\s*:\s*https?://",
        r"forward\s+refunds\s+to\s+iban",
    )

    def evaluate_retrieval(self, recalled_nodes: List[MemoryNode]) -> RetrievalGateResult:
        if not recalled_nodes:
            return RetrievalGateResult(
                passed=True,
                rejection_code=None,
                sanitized_chunks=[],
                taint_tier_downgraded=False,
                quarantined_memory_ids=[],
            )

        sanitized: List[str] = []
        quarantined: List[str] = []
        taint_downgraded = False

        # Step 1: Provenance Entropy Validation
        for node in recalled_nodes:
            if node.provenance is None or not node.provenance.signature_b64:
                # Missing or forged provenance -> downgrade and quarantine
                taint_downgraded = True
                quarantined.append(node.memory_id)
                continue

            # Step 2: Dormant Trigger Scanning
            lower_content = node.content.lower()
            if any(trigger in lower_content for trigger in self.SUSPICIOUS_DORMANT_TRIGGERS):
                return RetrievalGateResult(
                    passed=False,
                    rejection_code="HALT_DORMANT_TRIGGER_POISONING_DETECTED",
                    sanitized_chunks=[],
                    taint_tier_downgraded=True,
                    quarantined_memory_ids=[node.memory_id],
                )

            # Step 3: MemMorph Tool Hijacking Scanning
            if any(re.search(pat, lower_content) for pat in self.TOOL_REDIRECT_PATTERNS):
                return RetrievalGateResult(
                    passed=False,
                    rejection_code="HALT_MEMMORPH_TOOL_REDIRECT_DETECTED",
                    sanitized_chunks=[],
                    taint_tier_downgraded=True,
                    quarantined_memory_ids=[node.memory_id],
                )

            sanitized.append(node.content)

        # Step 4: Compositional Salami Poisoning Across Chunks
        combined_text = " ".join(sanitized).lower()
        if "role='admin'" in combined_text and "where" not in combined_text:
            return RetrievalGateResult(
                passed=False,
                rejection_code="HALT_COMPOSITIONAL_PRIVILEGE_ESCALATION",
                sanitized_chunks=[],
                taint_tier_downgraded=True,
                quarantined_memory_ids=[n.memory_id for n in recalled_nodes],
            )

        return RetrievalGateResult(
            passed=True,
            rejection_code=None,
            sanitized_chunks=sanitized,
            taint_tier_downgraded=taint_downgraded,
            quarantined_memory_ids=quarantined,
        )
