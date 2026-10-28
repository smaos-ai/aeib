#!/usr/bin/env python3
"""
aeib_session_integrity_adapter.py
================================================================================
AEIB Session Store Adapter for agent-runtime-integrity-bench (ARIB).
Implements the ARIB async adapter contract (add, get_all, close).
Enforces invariant ARIB-REPLAY-001 ('redelivered batch is visible exactly once')
using RFC 8785 JCS CAID deduplication. Zero mocks.
"""

import hashlib
import json
from typing import Dict, Any, List, Optional

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[2]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs

def canonical_json_bytes(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) deterministic subset."""
    return _reference_encode_jcs(obj)

class AEIBSessionStoreAdapter:
    """
    ARIB-compliant Session Store Adapter wrapped with AEIB RFC 8785 JCS
    deterministic deduplication to enforce ARIB-REPLAY-001.
    """
    name = "aeib-session-store"

    def __init__(self, tmpdir: Optional[str] = None):
        self.tmpdir = tmpdir
        self.committed_caids = set()
        self.items: List[Dict[str, Any]] = []

    async def add(self, items: List[Dict[str, Any]]):
        """Appends items, suppressing duplicate deliveries via RFC 8785 CAID."""
        for item in items:
            caid = hashlib.sha256(canonical_json_bytes(item)).hexdigest()
            if caid not in self.committed_caids:
                self.committed_caids.add(caid)
                self.items.append(dict(item))

    async def get_all(self) -> List[Dict[str, Any]]:
        """Returns full visible conversation history."""
        return [dict(i) for i in self.items]

    async def close(self):
        """Closes store and marks inactive."""
        self.is_closed = True
        return True

