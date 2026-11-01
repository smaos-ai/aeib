# Copyright 2026 SovereignNexus Project
#
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
src/reality/merkle_sync.py — Union-Path Merkle Tree Physical Synchronization Oracle.

Solves the "Flash Explorer Paradox" and the "Orphan Path" synchronization defect:
1. Low-capability LLMs burn 80k-150k tokens sequentially listing directories and diffing.
   This oracle computes the exact physical reality difference at $0 cost and 0 LLM tokens.
2. Prior naive Merkle comparators checked only paths present in the workspace manifest.
   If an external backup SSD contained stale orphaned files, the previous comparator
   evaluated `ws_merkle == ssd_merkle` as True.
   This implementation builds a bidirectional Merkle tree over the UNION of all paths
   (workspace union SSD) and explicitly classifies paths into:
   - MATCHED: byte-identical in both locations.
   - WORKSPACE_ONLY: file exists locally but missing from backup.
   - SSD_ONLY_ORPHAN: stale file exists on SSD but was deleted from workspace.
   - CONTENT_CONFLICT: file exists in both but content digests differ.
3. Produces an RFC 8785 JCS canonical, Ed25519-signed SSDSyncReceipt with integer basis points.
"""

import fnmatch
import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from src.jcs_canonicalizer import encode_jcs

DEFAULT_EXCLUDE_PATTERNS: Tuple[str, ...] = (
    ".git",
    ".git/*",
    "*.git*",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".pytest_cache/*",
    ".DS_Store",
    "*.swp",
    ".mypy_cache",
    ".mypy_cache/*",
)

STATUS_MATCHED = "MATCHED"
STATUS_WORKSPACE_ONLY = "WORKSPACE_ONLY"
STATUS_SSD_ONLY_ORPHAN = "SSD_ONLY_ORPHAN"
STATUS_CONTENT_CONFLICT = "CONTENT_CONFLICT"

MODE_WORKSPACE_TO_SSD_BACKUP = "WORKSPACE_TO_SSD_BACKUP"
MODE_SSD_TO_WORKSPACE_RESTORE = "SSD_TO_WORKSPACE_RESTORE"
MODE_VERIFY_ONLY = "VERIFY_ONLY"

VALID_SYNC_MODES: Set[str] = {
    MODE_WORKSPACE_TO_SSD_BACKUP,
    MODE_SSD_TO_WORKSPACE_RESTORE,
    MODE_VERIFY_ONLY,
}


def compute_file_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Computes SHA-256 digest of a file in streaming chunks."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_merkle_root_from_entries(entries: Sequence[Tuple[str, str]]) -> str:
    """
    Computes a deterministic binary Merkle root from sorted (key, digest) tuples.
    If entries is empty, returns the SHA-256 digest of b"EMPTY_MERKLE_TREE".
    """
    if not entries:
        return hashlib.sha256(b"EMPTY_MERKLE_TREE").hexdigest()

    sorted_entries = sorted(entries, key=lambda x: x[0])
    current_level: List[bytes] = []
    for key, digest_hex in sorted_entries:
        leaf_payload = key.encode("utf-8") + b":" + digest_hex.encode("ascii")
        current_level.append(hashlib.sha256(leaf_payload).digest())

    while len(current_level) > 1:
        next_level: List[bytes] = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            next_level.append(hashlib.sha256(left + right).digest())
        current_level = next_level

    return current_level[0].hex()


def should_exclude_path(rel_path: str, exclude_patterns: Sequence[str]) -> bool:
    """Checks whether a relative path matches any exclusion glob pattern."""
    parts = rel_path.split(os.sep)
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False


def build_manifest(
    base_dir: Path,
    exclude_patterns: Sequence[str] = DEFAULT_EXCLUDE_PATTERNS,
) -> Dict[str, Tuple[int, str]]:
    """
    Walks base_dir and returns a mapping: rel_path -> (size_bytes, sha256_hex).
    Skips non-files and excluded path patterns.
    """
    manifest: Dict[str, Tuple[int, str]] = {}
    if not base_dir.exists() or not base_dir.is_dir():
        return manifest

    for root, dirs, files in os.walk(base_dir):
        # Exclude directories in-place to avoid unnecessary traversal
        dirs[:] = [
            d for d in dirs
            if not should_exclude_path(os.path.relpath(os.path.join(root, d), base_dir), exclude_patterns)
        ]
        for f in files:
            full_path = Path(root) / f
            rel_path = str(full_path.relative_to(base_dir))
            if should_exclude_path(rel_path, exclude_patterns):
                continue
            if full_path.is_file() and not full_path.is_symlink():
                try:
                    size = full_path.stat().st_size
                    digest = compute_file_sha256(full_path)
                    manifest[rel_path] = (size, digest)
                except (OSError, PermissionError):
                    continue
    return manifest


@dataclass(frozen=True)
class MerkleDiffReport:
    workspace_root: str
    ssd_root: str
    total_workspace_files: int
    total_ssd_files: int
    total_union_files: int
    matched_files: int
    workspace_only_files: int
    ssd_only_orphan_files: int
    content_conflict_files: int
    similarity_bps: int
    workspace_merkle_root: str
    ssd_merkle_root: str
    union_merkle_root: str
    is_perfect_match: bool
    orphan_paths: Tuple[str, ...]
    conflict_paths: Tuple[str, ...]
    report_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_root": self.workspace_root,
            "ssd_root": self.ssd_root,
            "total_workspace_files": self.total_workspace_files,
            "total_ssd_files": self.total_ssd_files,
            "total_union_files": self.total_union_files,
            "matched_files": self.matched_files,
            "workspace_only_files": self.workspace_only_files,
            "ssd_only_orphan_files": self.ssd_only_orphan_files,
            "content_conflict_files": self.content_conflict_files,
            "similarity_bps": self.similarity_bps,
            "workspace_merkle_root": self.workspace_merkle_root,
            "ssd_merkle_root": self.ssd_merkle_root,
            "union_merkle_root": self.union_merkle_root,
            "is_perfect_match": self.is_perfect_match,
            "orphan_paths": list(self.orphan_paths),
            "conflict_paths": list(self.conflict_paths),
            "report_caid": self.report_caid,
        }


def compute_bidirectional_merkle(
    workspace_dir: Path,
    ssd_dir: Path,
    exclude_patterns: Sequence[str] = DEFAULT_EXCLUDE_PATTERNS,
) -> MerkleDiffReport:
    """
    Computes bidirectional Merkle tree over the UNION of workspace and SSD paths.
    Evaluates exact file matching, orphan paths, and content conflicts.
    """
    ws_manifest = build_manifest(workspace_dir, exclude_patterns)
    ssd_manifest = build_manifest(ssd_dir, exclude_patterns)

    all_paths = sorted(set(ws_manifest.keys()) | set(ssd_manifest.keys()))
    matched_count = 0
    ws_only_count = 0
    ssd_orphan_count = 0
    conflict_count = 0

    orphan_paths: List[str] = []
    conflict_paths: List[str] = []
    union_entries: List[Tuple[str, str]] = []

    for path in all_paths:
        in_ws = path in ws_manifest
        in_ssd = path in ssd_manifest

        if in_ws and in_ssd:
            ws_size, ws_hash = ws_manifest[path]
            ssd_size, ssd_hash = ssd_manifest[path]
            if ws_size == ssd_size and ws_hash == ssd_hash:
                matched_count += 1
                union_entries.append((path, ws_hash))
            else:
                conflict_count += 1
                conflict_paths.append(path)
                combined_hash = hashlib.sha256((ws_hash + ":" + ssd_hash).encode("ascii")).hexdigest()
                union_entries.append((path, combined_hash))
        elif in_ws:
            ws_only_count += 1
            ws_size, ws_hash = ws_manifest[path]
            union_entries.append((path, "WS_ONLY:" + ws_hash))
        else:
            ssd_orphan_count += 1
            orphan_paths.append(path)
            ssd_size, ssd_hash = ssd_manifest[path]
            union_entries.append((path, "SSD_ORPHAN:" + ssd_hash))

    total_union = len(all_paths)
    similarity_bps = (matched_count * 10000) // max(1, total_union)
    is_perfect_match = (matched_count == total_union and total_union > 0)

    ws_entries = [(p, h) for p, (_, h) in ws_manifest.items()]
    ssd_entries = [(p, h) for p, (_, h) in ssd_manifest.items()]

    ws_merkle = compute_merkle_root_from_entries(ws_entries)
    ssd_merkle = compute_merkle_root_from_entries(ssd_entries)
    union_merkle = compute_merkle_root_from_entries(union_entries)

    summary_for_caid = {
        "workspace_root": str(workspace_dir.resolve()),
        "ssd_root": str(ssd_dir.resolve()),
        "total_workspace_files": len(ws_manifest),
        "total_ssd_files": len(ssd_manifest),
        "total_union_files": total_union,
        "matched_files": matched_count,
        "workspace_only_files": ws_only_count,
        "ssd_only_orphan_files": ssd_orphan_count,
        "content_conflict_files": conflict_count,
        "similarity_bps": similarity_bps,
        "workspace_merkle_root": ws_merkle,
        "ssd_merkle_root": ssd_merkle,
        "union_merkle_root": union_merkle,
        "is_perfect_match": is_perfect_match,
    }
    report_caid = "sha256:" + hashlib.sha256(encode_jcs(summary_for_caid)).hexdigest()

    return MerkleDiffReport(
        workspace_root=str(workspace_dir.resolve()),
        ssd_root=str(ssd_dir.resolve()),
        total_workspace_files=len(ws_manifest),
        total_ssd_files=len(ssd_manifest),
        total_union_files=total_union,
        matched_files=matched_count,
        workspace_only_files=ws_only_count,
        ssd_only_orphan_files=ssd_orphan_count,
        content_conflict_files=conflict_count,
        similarity_bps=similarity_bps,
        workspace_merkle_root=ws_merkle,
        ssd_merkle_root=ssd_merkle,
        union_merkle_root=union_merkle,
        is_perfect_match=is_perfect_match,
        orphan_paths=tuple(orphan_paths),
        conflict_paths=tuple(conflict_paths),
        report_caid=report_caid,
    )


@dataclass(frozen=True)
class SSDSyncReceipt:
    receipt_id: str
    workspace_root: str
    ssd_root: str
    sync_mode: str
    similarity_bps: int
    files_copied: int
    files_deleted: int
    union_merkle_root: str
    operator_pubkey_hex: str
    signature_hex: str
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "workspace_root": self.workspace_root,
            "ssd_root": self.ssd_root,
            "sync_mode": self.sync_mode,
            "similarity_bps": self.similarity_bps,
            "files_copied": self.files_copied,
            "files_deleted": self.files_deleted,
            "union_merkle_root": self.union_merkle_root,
            "operator_pubkey_hex": self.operator_pubkey_hex,
            "signature_hex": self.signature_hex,
            "receipt_caid": self.receipt_caid,
        }


def synchronize_workspace_and_ssd(
    workspace_dir: Path,
    ssd_dir: Path,
    sync_mode: str,
    operator_private_key: Ed25519PrivateKey,
    receipt_id: str = "REC-SSD-SYNC-001",
    allow_orphan_prune: bool = False,
    exclude_patterns: Sequence[str] = DEFAULT_EXCLUDE_PATTERNS,
) -> Tuple[SSDSyncReceipt, MerkleDiffReport]:
    """
    Executes synchronization according to mode and returns signed SSDSyncReceipt.
    Validates sync_mode against VALID_SYNC_MODES.
    """
    if sync_mode not in VALID_SYNC_MODES:
        raise ValueError(f"ERR_INVALID_SYNC_MODE: {sync_mode} not in {VALID_SYNC_MODES}")

    initial_diff = compute_bidirectional_merkle(workspace_dir, ssd_dir, exclude_patterns)
    files_copied = 0
    files_deleted = 0

    if sync_mode == MODE_WORKSPACE_TO_SSD_BACKUP:
        ssd_dir.mkdir(parents=True, exist_ok=True)
        # Copy workspace files that are missing or conflicted on SSD
        ws_manifest = build_manifest(workspace_dir, exclude_patterns)
        ssd_manifest = build_manifest(ssd_dir, exclude_patterns)

        for rel_path, (ws_size, ws_hash) in ws_manifest.items():
            ssd_stat = ssd_manifest.get(rel_path)
            needs_copy = False
            if ssd_stat is None:
                needs_copy = True
            elif ssd_stat[0] != ws_size or ssd_stat[1] != ws_hash:
                needs_copy = True

            if needs_copy:
                src_file = workspace_dir / rel_path
                dst_file = ssd_dir / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                files_copied += 1

        if allow_orphan_prune:
            for orphan_rel in initial_diff.orphan_paths:
                orphan_file = ssd_dir / orphan_rel
                if orphan_file.is_file():
                    orphan_file.unlink()
                    files_deleted += 1

    elif sync_mode == MODE_SSD_TO_WORKSPACE_RESTORE:
        workspace_dir.mkdir(parents=True, exist_ok=True)
        ws_manifest = build_manifest(workspace_dir, exclude_patterns)
        ssd_manifest = build_manifest(ssd_dir, exclude_patterns)

        for rel_path, (ssd_size, ssd_hash) in ssd_manifest.items():
            ws_stat = ws_manifest.get(rel_path)
            needs_copy = False
            if ws_stat is None:
                needs_copy = True
            elif ws_stat[0] != ssd_size or ws_stat[1] != ssd_hash:
                needs_copy = True

            if needs_copy:
                src_file = ssd_dir / rel_path
                dst_file = workspace_dir / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                files_copied += 1

    final_diff = compute_bidirectional_merkle(workspace_dir, ssd_dir, exclude_patterns)
    operator_pubkey_hex = operator_private_key.public_key().public_bytes_raw().hex()

    receipt_body = {
        "receipt_id": receipt_id,
        "workspace_root": str(workspace_dir.resolve()),
        "ssd_root": str(ssd_dir.resolve()),
        "sync_mode": sync_mode,
        "similarity_bps": final_diff.similarity_bps,
        "files_copied": files_copied,
        "files_deleted": files_deleted,
        "union_merkle_root": final_diff.union_merkle_root,
        "operator_pubkey_hex": operator_pubkey_hex,
    }
    canonical_bytes = encode_jcs(receipt_body)
    signature = operator_private_key.sign(canonical_bytes)
    signature_hex = signature.hex()
    receipt_caid = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()

    receipt = SSDSyncReceipt(
        receipt_id=receipt_id,
        workspace_root=str(workspace_dir.resolve()),
        ssd_root=str(ssd_dir.resolve()),
        sync_mode=sync_mode,
        similarity_bps=final_diff.similarity_bps,
        files_copied=files_copied,
        files_deleted=files_deleted,
        union_merkle_root=final_diff.union_merkle_root,
        operator_pubkey_hex=operator_pubkey_hex,
        signature_hex=signature_hex,
        receipt_caid=receipt_caid,
    )
    return receipt, final_diff


def verify_ssd_sync_receipt(
    receipt: SSDSyncReceipt,
    expected_pubkey_hex: str,
) -> Tuple[bool, str]:
    """
    Verifies cryptographic validity of an SSDSyncReceipt:
    - Enforces expected pinned public key
    - Verifies Ed25519 signature over RFC 8785 canonical body
    - Recomputes receipt_caid
    """
    if receipt.operator_pubkey_hex != expected_pubkey_hex:
        return False, "ERR_PUBKEY_PIN_MISMATCH"

    receipt_body = {
        "receipt_id": receipt.receipt_id,
        "workspace_root": receipt.workspace_root,
        "ssd_root": receipt.ssd_root,
        "sync_mode": receipt.sync_mode,
        "similarity_bps": receipt.similarity_bps,
        "files_copied": receipt.files_copied,
        "files_deleted": receipt.files_deleted,
        "union_merkle_root": receipt.union_merkle_root,
        "operator_pubkey_hex": receipt.operator_pubkey_hex,
    }
    canonical_bytes = encode_jcs(receipt_body)
    expected_caid = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
    if receipt.receipt_caid != expected_caid:
        return False, "ERR_RECEIPT_CAID_MISMATCH"

    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(receipt.operator_pubkey_hex))
        public_key.verify(bytes.fromhex(receipt.signature_hex), canonical_bytes)
    except (InvalidSignature, ValueError):
        return False, "ERR_INVALID_ED25519_SIGNATURE"

    return True, "VERIFIED_SSD_SYNC_RECEIPT"
