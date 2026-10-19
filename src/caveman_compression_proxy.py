#!/usr/bin/env python3
"""
src/caveman_compression_proxy.py
================================================================================
Lossless-Audited Context Compression Proxy with Dual-Digest Taint (AT72).

Inspired by Julius Brussee's Caveman input-compression proxy and TrajAudit
saliency folding (arXiv:2605.26563).

Evaluates under the stated model:
  1. Compresses large verbose tool outputs, logs, and JSON payloads into concise
     saliency views for the agent's context window.
  2. Binds both raw_bytes_sha256 (forensic truth) and compressed_view_sha256 (prompt view).
  3. Strictly preserves provenance taint (e.g. TIER_2_UNTRUSTED_EXTERNAL) across
     the compressed boundary, preventing taint laundering.
  4. Stores raw bytes in an immutable content-addressed vault (vault/<sha256>.blob).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.jcs_canonicalizer import encode_jcs


def sha256_prefixed(data: bytes) -> str:
    """Computes a standard sha256: hex string."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class DualDigestCompressedContext:
    """Context block carrying both raw payload and compressed view digests."""

    block_id: str
    source_tier: str
    raw_bytes_sha256: str
    compressed_view_sha256: str
    compressed_text: str
    token_reduction_pct: float
    vault_blob_path: Optional[str] = None


def compress_and_seal_tool_output(
    block_id: str,
    source_tier: str,
    raw_json_log: Dict[str, Any],
    vault_dir: Optional[Path] = None,
) -> DualDigestCompressedContext:
    """
    Compresses tool output into a high-saliency summary while preserving raw auditability.
    """
    raw_bytes = encode_jcs(raw_json_log)
    raw_sha = sha256_prefixed(raw_bytes)

    vault_path_str: Optional[str] = None
    if vault_dir is not None:
        vault_dir.mkdir(parents=True, exist_ok=True)
        safe_name = raw_sha.replace("sha256:", "") + ".blob"
        blob_file = vault_dir / safe_name
        if not blob_file.exists():
            blob_file.write_bytes(raw_bytes)
        vault_path_str = str(blob_file)

    # Extract high-saliency keys for the LLM context window
    compact_view = {
        "status": raw_json_log.get("status"),
        "error_code": raw_json_log.get("error_code"),
        "summary": raw_json_log.get("summary"),
    }

    comp_bytes = encode_jcs(compact_view)
    comp_sha = sha256_prefixed(comp_bytes)
    reduction = round((1.0 - (len(comp_bytes) / max(len(raw_bytes), 1))) * 100.0, 2)

    return DualDigestCompressedContext(
        block_id=block_id,
        source_tier=source_tier,  # Strictly preserves taint
        raw_bytes_sha256=raw_sha,
        compressed_view_sha256=comp_sha,
        compressed_text=comp_bytes.decode("utf-8"),
        token_reduction_pct=reduction,
        vault_blob_path=vault_path_str,
    )
