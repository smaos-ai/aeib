# File: src/sources/__init__.py
"""
Biological evidence source adapters for AEIB Bio-Digital Evidence Gate.
"""

from __future__ import annotations

from src.sources.alphagenome import AlphaGenomeAdapter
from src.sources.base import (
    BaseBioSourceAdapter,
    SourceHaltCode,
    SourceQueryResult,
    compute_lookup_digest,
    query_result_to_evidence_record,
)
from src.sources.dbsnp import DbSnpAdapter
from src.sources.encode import EncodeCcreAdapter

__all__ = [
    "AlphaGenomeAdapter",
    "BaseBioSourceAdapter",
    "DbSnpAdapter",
    "EncodeCcreAdapter",
    "SourceHaltCode",
    "SourceQueryResult",
    "compute_lookup_digest",
    "query_result_to_evidence_record",
]
