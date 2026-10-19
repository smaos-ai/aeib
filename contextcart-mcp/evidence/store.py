#!/usr/bin/env python3
"""
contextcart/evidence/store.py
================================================================================
Content-Addressed Immutable Local Evidence Store for Bounded Research Workflows.

Stores full raw research documents, web pages, and tool outputs out-of-band on disk,
allowing the parent agent context to receive only compact digests and citation links.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def sha256_prefixed(data: bytes) -> str:
    """Computes a sha256:-prefixed lowercase hex digest."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


class LocalEvidenceStore:
    """
    Manages local content-addressed storage for research sources and artifacts.
    Ensures zero raw dump to parent context while preserving full audit trails.
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        if base_dir is None:
            self.base_dir = Path.home() / ".contextcart" / "evidence"
        else:
            self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.base_dir / "index.json"
        self._init_index()

    def _init_index(self) -> None:
        if not self.index_file.exists():
            self.index_file.write_text("{}", encoding="utf-8")

    def _read_index(self) -> Dict[str, Any]:
        try:
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write_index(self, index_data: Dict[str, Any]) -> None:
        self.index_file.write_text(
            json.dumps(index_data, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def store_evidence(
        self,
        source_id: str,
        content: str | bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Stores raw evidence by content hash. Returns evidence metadata bundle.
        """
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
        digest = sha256_prefixed(raw_bytes)
        hex_suffix = digest.replace("sha256:", "")

        blob_path = self.base_dir / f"{hex_suffix}.blob"
        if not blob_path.exists():
            blob_path.write_bytes(raw_bytes)

        record = {
            "evidence_id": digest,
            "source_id": source_id,
            "path": str(blob_path.resolve()),
            "byte_count": len(raw_bytes),
            "stored_at": time.time(),
            "metadata": metadata or {},
        }

        index = self._read_index()
        index[digest] = record
        self._write_index(index)
        return record

    def get_evidence(self, evidence_id: str) -> Optional[bytes]:
        """Retrieves raw evidence bytes given evidence_id."""
        index = self._read_index()
        record = index.get(evidence_id)
        if not record:
            hex_suffix = evidence_id.replace("sha256:", "")
            blob_path = self.base_dir / f"{hex_suffix}.blob"
            if blob_path.exists():
                return blob_path.read_bytes()
            return None
        blob_path = Path(record["path"])
        if blob_path.exists():
            return blob_path.read_bytes()
        return None

    def list_evidence(self) -> List[Dict[str, Any]]:
        """Lists all stored evidence records."""
        index = self._read_index()
        return list(index.values())

    def create_citation_manifest(self, evidence_ids: List[str]) -> List[Dict[str, Any]]:
        """Constructs citation manifest for a set of evidence digests."""
        index = self._read_index()
        citations = []
        for eid in evidence_ids:
            if eid in index:
                rec = index[eid]
                citations.append(
                    {
                        "evidence_id": eid,
                        "source_id": rec.get("source_id", "unknown"),
                        "byte_count": rec.get("byte_count", 0),
                        "path": rec.get("path", ""),
                    }
                )
            else:
                citations.append(
                    {
                        "evidence_id": eid,
                        "source_id": "unindexed_source",
                        "byte_count": 0,
                        "path": "",
                    }
                )
        return citations
