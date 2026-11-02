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
tests/test_reality_substrate.py — Verification suite for Reality Substrate Modules.
Covers:
- src.reality.merkle_sync (Union-Path Merkle, orphan detection, Ed25519 receipts)
- src.reality.git_oracle (Git state classification, push failure capsules, L26 pre-push)
- src.reality.pointer_bus (Pointer-Pipe SQLite data plane, zero-token tool-to-tool pipe)
- src.reality.passport_compiler (Task-conditioned AST indexer, <800 token budget)
"""

import dataclasses
import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.reality.git_oracle import (
    STATUS_CLEAN_FAST_FORWARDABLE,
    STATUS_DIRTY_WORKING_TREE,
    STATUS_DIVERGED_BRANCH,
    STATUS_REMOTE_AHEAD_REBASE_REQUIRED,
    STATUS_UNTRACKED_REMOTE_REF,
    STATUS_UP_TO_DATE,
    GitStateOracle,
    verify_pre_push_invariants,
)
from src.reality.merkle_sync import (
    MODE_SSD_TO_WORKSPACE_RESTORE,
    MODE_VERIFY_ONLY,
    MODE_WORKSPACE_TO_SSD_BACKUP,
    build_manifest,
    compute_bidirectional_merkle,
    compute_merkle_root_from_entries,
    should_exclude_path,
    synchronize_workspace_and_ssd,
    verify_ssd_sync_receipt,
)
from src.reality.passport_compiler import (
    APPROX_CHARS_PER_TOKEN,
    DEFAULT_MAX_TOKEN_BUDGET,
    TaskConditionedPassportCompiler,
)
from src.reality.pointer_bus import (
    DEFAULT_POINTER_THRESHOLD_BYTES,
    DEFAULT_TTL_SECONDS,
    PointerBus,
)


def test_merkle_sync_empty_and_exclusions():
    """Tests empty entries, odd-count entries, and path exclusion logic."""
    empty_root = compute_merkle_root_from_entries([])
    assert empty_root == hashlib.sha256(b"EMPTY_MERKLE_TREE").hexdigest()

    # Odd count entries (tests line 105 i + 1 < len(current_level) odd level folding)
    odd_entries = [("a.txt", "11" * 32), ("b.txt", "22" * 32), ("c.txt", "33" * 32)]
    odd_root = compute_merkle_root_from_entries(odd_entries)
    assert len(odd_root) == 64

    # Build manifest on nonexistent dir returns empty dict
    nonexistent_manifest = build_manifest(Path("/nonexistent/directory/xyz"))
    assert nonexistent_manifest == {}

    assert should_exclude_path(".git/HEAD", [".git", "*.pyc"]) is True
    assert should_exclude_path("foo/bar.pyc", [".git", "*.pyc"]) is True
    assert should_exclude_path("src/core.py", [".git", "*.pyc"]) is False


def test_merkle_sync_detects_ssd_only_orphan_and_content_conflict(tmp_path: Path):
    """
    Verifies that the bidirectional Merkle oracle detects SSD-only orphan files
    and content conflicts, correctly calculating similarity_bps over the union.
    """
    ws = tmp_path / "workspace"
    ssd = tmp_path / "ssd"
    ws.mkdir()
    ssd.mkdir()

    # Matched file
    (ws / "matched.txt").write_text("Hello World", encoding="utf-8")
    (ssd / "matched.txt").write_text("Hello World", encoding="utf-8")

    # Workspace-only file
    (ws / "ws_only.txt").write_text("Local only content", encoding="utf-8")

    # SSD-only orphan file (critical bug test: must not be ignored!)
    (ssd / "old_orphan.txt").write_text("Stale deleted file", encoding="utf-8")

    # Content conflict (different content, same size)
    (ws / "conflict.txt").write_text("Version A", encoding="utf-8")
    (ssd / "conflict.txt").write_text("Version B", encoding="utf-8")

    diff = compute_bidirectional_merkle(ws, ssd)
    assert diff.total_workspace_files == 3
    assert diff.total_ssd_files == 3
    assert diff.total_union_files == 4  # matched, ws_only, old_orphan, conflict
    assert diff.matched_files == 1
    assert diff.workspace_only_files == 1
    assert diff.ssd_only_orphan_files == 1
    assert "old_orphan.txt" in diff.orphan_paths
    assert diff.content_conflict_files == 1
    assert "conflict.txt" in diff.conflict_paths
    assert diff.similarity_bps == 2500  # 1/4 = 2500 bps
    assert diff.is_perfect_match is False

    d = diff.to_dict()
    assert d["similarity_bps"] == 2500
    assert d["is_perfect_match"] is False
    assert len(d["orphan_paths"]) == 1


def test_merkle_sync_modes_and_receipt_verification(tmp_path: Path):
    """
    Tests WORKSPACE_TO_SSD_BACKUP, SSD_TO_WORKSPACE_RESTORE, VERIFY_ONLY modes,
    and Ed25519 receipt verification including tamper detection.
    """
    ws = tmp_path / "workspace"
    ssd = tmp_path / "ssd"
    ws.mkdir()
    ssd.mkdir()

    (ws / "data.json").write_text('{"status": "ok"}', encoding="utf-8")
    (ssd / "data.json").write_text('{"status": "no"}', encoding="utf-8")
    (ssd / "stale.log").write_text("old log", encoding="utf-8")

    key = Ed25519PrivateKey.generate()
    pub_hex = key.public_key().public_bytes_raw().hex()

    # 1. Invalid sync mode raises ValueError
    with pytest.raises(ValueError, match="ERR_INVALID_SYNC_MODE"):
        synchronize_workspace_and_ssd(ws, ssd, "INVALID_MODE", key)

    # 2. VERIFY_ONLY mode
    v_rec, v_diff = synchronize_workspace_and_ssd(ws, ssd, MODE_VERIFY_ONLY, key)
    assert v_rec.files_copied == 0
    assert v_rec.files_deleted == 0
    assert v_rec.sync_mode == MODE_VERIFY_ONLY
    assert (ssd / "data.json").read_text(encoding="utf-8") == '{"status": "no"}'

    # 3. Sync WORKSPACE_TO_SSD_BACKUP without prune
    receipt, diff = synchronize_workspace_and_ssd(
        ws, ssd, MODE_WORKSPACE_TO_SSD_BACKUP, key, allow_orphan_prune=False
    )
    assert receipt.files_copied == 1
    assert receipt.files_deleted == 0
    assert diff.matched_files == 1
    assert diff.ssd_only_orphan_files == 1
    assert (ssd / "data.json").read_text(encoding="utf-8") == '{"status": "ok"}'
    assert receipt.to_dict()["files_copied"] == 1

    # Verify receipt
    valid, reason = verify_ssd_sync_receipt(receipt, pub_hex)
    assert valid is True
    assert reason == "VERIFIED_SSD_SYNC_RECEIPT"

    # Tampered pubkey check
    valid_tamper, reason_tamper = verify_ssd_sync_receipt(receipt, "00" * 32)
    assert valid_tamper is False
    assert reason_tamper == "ERR_PUBKEY_PIN_MISMATCH"

    # Tampered CAID check
    tampered_rec = type(receipt)(
        receipt_id=receipt.receipt_id,
        workspace_root=receipt.workspace_root,
        ssd_root=receipt.ssd_root,
        sync_mode=receipt.sync_mode,
        similarity_bps=receipt.similarity_bps,
        files_copied=receipt.files_copied,
        files_deleted=receipt.files_deleted,
        union_merkle_root=receipt.union_merkle_root,
        operator_pubkey_hex=receipt.operator_pubkey_hex,
        signature_hex=receipt.signature_hex,
        receipt_caid="sha256:tampered_digest",
    )
    valid_caid, reason_caid = verify_ssd_sync_receipt(tampered_rec, pub_hex)
    assert valid_caid is False
    assert reason_caid == "ERR_RECEIPT_CAID_MISMATCH"

    # Tampered signature check
    tampered_sig = type(receipt)(
        receipt_id=receipt.receipt_id,
        workspace_root=receipt.workspace_root,
        ssd_root=receipt.ssd_root,
        sync_mode=receipt.sync_mode,
        similarity_bps=receipt.similarity_bps,
        files_copied=receipt.files_copied,
        files_deleted=receipt.files_deleted,
        union_merkle_root=receipt.union_merkle_root,
        operator_pubkey_hex=receipt.operator_pubkey_hex,
        signature_hex="ff" * 64,
        receipt_caid=receipt.receipt_caid,
    )
    valid_sig, reason_sig = verify_ssd_sync_receipt(tampered_sig, pub_hex)
    assert valid_sig is False
    assert reason_sig == "ERR_INVALID_ED25519_SIGNATURE"

    # 4. Sync with orphan prune
    receipt2, diff2 = synchronize_workspace_and_ssd(
        ws, ssd, MODE_WORKSPACE_TO_SSD_BACKUP, key, allow_orphan_prune=True
    )
    assert receipt2.files_deleted == 1
    assert not (ssd / "stale.log").exists()
    assert diff2.is_perfect_match is True
    assert diff2.similarity_bps == 10000

    # 4b. Test safety ceiling on orphan pruning
    (ssd / "orphan1.txt").write_text("1")
    (ssd / "orphan2.txt").write_text("2")
    with pytest.raises(RuntimeError, match="ERR_PRUNE_SAFETY_CEILING_EXCEEDED"):
        synchronize_workspace_and_ssd(
            ws, ssd, MODE_WORKSPACE_TO_SSD_BACKUP, key, allow_orphan_prune=True, max_orphan_prune_limit=1
        )
    # With override, prune succeeds
    receipt_override, _ = synchronize_workspace_and_ssd(
        ws, ssd, MODE_WORKSPACE_TO_SSD_BACKUP, key, allow_orphan_prune=True, max_orphan_prune_limit=1, force_prune_override=True
    )
    assert receipt_override.files_deleted == 2

    # 5. SSD_TO_WORKSPACE_RESTORE mode
    (ws / "data.json").unlink()
    assert not (ws / "data.json").exists()
    r_rec, r_diff = synchronize_workspace_and_ssd(ws, ssd, MODE_SSD_TO_WORKSPACE_RESTORE, key)
    assert r_rec.files_copied == 1
    assert (ws / "data.json").exists()
    assert r_diff.is_perfect_match is True


def test_pointer_bus_content_addressed_and_in_kernel_pipe():
    """
    Verifies PointerBus storage, ACL enforcement, TTL expiration, and zero-token piping.
    """
    assert DEFAULT_POINTER_THRESHOLD_BYTES == 2048
    assert DEFAULT_TTL_SECONDS == 86400

    bus = PointerBus(threshold_bytes=100)

    # 1. Put payload with default TTL and wildcard ACL
    payload = "Large payload data: " + ("X" * 300)
    handle = bus.put_payload(payload, mime_type="text/plain", acl_agent_id="agent_alpha")
    assert handle.size_bytes == len(payload)
    assert handle.acl_agent_id == "agent_alpha"
    assert handle.to_dict()["size_bytes"] == len(payload)

    # Immutability check on handle (kills frozen=True perturbation)
    with pytest.raises(dataclasses.FrozenInstanceError):
        handle.size_bytes = 999

    # 2. Retrieve payload with valid ACL
    retrieved = bus.get_payload(handle.ptr_sha256, requesting_agent_id="agent_alpha")
    assert retrieved == payload.encode("utf-8")

    # 3. Retrieve with wrong ACL raises PermissionError
    with pytest.raises(PermissionError, match="ERR_POINTER_ACL_DENIED"):
        bus.get_payload(handle.ptr_sha256, requesting_agent_id="agent_beta")

    # 4. In-kernel zero-token pipe: transform uppercase
    def uppercase_transformer(data: bytes) -> bytes:
        return data.upper()

    out_handle = bus.pipe_tool_to_tool(
        handle.ptr_sha256,
        uppercase_transformer,
        requesting_agent_id="agent_alpha",
    )
    out_data = bus.get_payload(out_handle.ptr_sha256, requesting_agent_id="agent_alpha")
    assert out_data is not None
    assert out_data.startswith(b"LARGE PAYLOAD DATA:")

    # Pipe with missing pointer raises KeyError
    with pytest.raises(KeyError, match="ERR_SRC_POINTER_NOT_FOUND"):
        bus.pipe_tool_to_tool("nonexistent", uppercase_transformer)

    # 5. Prune expired
    now = 1000_000_000_000
    expired_handle = bus.put_payload("will expire", ttl_seconds=10, now_ns=now)
    assert bus.get_payload(expired_handle.ptr_sha256, now_ns=now + 5_000_000_000) is not None
    assert bus.get_payload(expired_handle.ptr_sha256, now_ns=now + 15_000_000_000) is None
    pruned = bus.prune_expired(now_ns=now + 15_000_000_000)
    assert pruned >= 1
    bus.close()


def test_git_oracle_local_repo_diagnostics(tmp_path: Path):
    """
    Verifies GitStateOracle against a localized git repository.
    Tests:
    1. Untracked remote branch
    2. Tracking remote upstream: UP_TO_DATE, CLEAN_FAST_FORWARDABLE, REMOTE_AHEAD_REBASE_REQUIRED, DIVERGED_BRANCH
    3. Dirty working tree
    """
    remote_bare = tmp_path / "remote.git"
    remote_bare.mkdir()
    subprocess.run(["git", "-C", str(remote_bare), "init", "--bare"], check=True, capture_output=True)

    repo = tmp_path / "test_repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Tester"], check=True)

    # Initial commit
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Initial commit"], check=True)

    oracle = GitStateOracle(repo)
    branch = oracle.get_current_branch()
    assert branch == "main"
    assert oracle.get_upstream_branch() is None
    assert oracle.get_upstream_branch("main") is None

    # Error handling for non-git directory or invalid commands
    bad_oracle = GitStateOracle(tmp_path / "not_a_repo")
    assert bad_oracle.get_current_branch() == "UNKNOWN"
    with pytest.raises(RuntimeError, match="Git command failed"):
        oracle._run_git(["invalid-subcommand-xyz"], check=True)

    # 1. Untracked remote branch diagnosis
    capsule = oracle.diagnose_divergence(target_remote="origin")
    assert capsule.divergence_status == STATUS_UNTRACKED_REMOTE_REF
    assert capsule.local_ahead_count == 0
    assert capsule.remote_behind_count == 0
    assert "git push -u origin" in capsule.remediation_command
    assert capsule.to_dict()["divergence_status"] == STATUS_UNTRACKED_REMOTE_REF

    # Immutability check on capsule (kills frozen=True perturbation)
    with pytest.raises(dataclasses.FrozenInstanceError):
        capsule.local_ahead_count = 99

    # Setup remote and push with tracking
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote_bare)], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-u", "origin", "main"], check=True, capture_output=True)
    assert oracle.get_upstream_branch() == "origin/main"

    # 2. UP_TO_DATE status
    capsule_synced = oracle.diagnose_divergence()
    assert capsule_synced.divergence_status == STATUS_UP_TO_DATE
    assert capsule_synced.local_ahead_count == 0
    assert capsule_synced.remote_behind_count == 0

    # 3. Local commit -> CLEAN_FAST_FORWARDABLE
    (repo / "local.txt").write_text("local", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "local.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Local commit"], check=True)

    capsule_ahead = oracle.diagnose_divergence()
    assert capsule_ahead.divergence_status == STATUS_CLEAN_FAST_FORWARDABLE
    assert capsule_ahead.local_ahead_count == 1
    assert capsule_ahead.remote_behind_count == 0

    # Push local commit to remote
    subprocess.run(["git", "-C", str(repo), "push", "origin", "main"], check=True, capture_output=True)

    # 4. Clone to another repo, commit and push -> creates REMOTE_AHEAD
    other_repo = tmp_path / "other_repo"
    subprocess.run(["git", "clone", str(remote_bare), str(other_repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(other_repo), "config", "user.email", "other@example.com"], check=True)
    subprocess.run(["git", "-C", str(other_repo), "config", "user.name", "Other"], check=True)
    (other_repo / "remote_change.txt").write_text("from remote", encoding="utf-8")
    subprocess.run(["git", "-C", str(other_repo), "add", "remote_change.txt"], check=True)
    subprocess.run(["git", "-C", str(other_repo), "commit", "-m", "Remote change"], check=True)
    subprocess.run(["git", "-C", str(other_repo), "push", "origin", "main"], check=True, capture_output=True)

    # Fetch in local repo
    subprocess.run(["git", "-C", str(repo), "fetch", "origin"], check=True, capture_output=True)
    capsule_behind = oracle.diagnose_divergence()
    assert capsule_behind.divergence_status == STATUS_REMOTE_AHEAD_REBASE_REQUIRED
    assert capsule_behind.remote_behind_count == 1

    # 5. Local also adds a commit -> DIVERGED_BRANCH
    (repo / "local2.txt").write_text("local 2", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "local2.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "Local commit 2"], check=True)

    capsule_diverged = oracle.diagnose_divergence()
    assert capsule_diverged.divergence_status == STATUS_DIVERGED_BRANCH
    assert capsule_diverged.local_ahead_count == 1
    assert capsule_diverged.remote_behind_count == 1

    # 6. Dirty working tree diagnosis
    (repo / "dirty.txt").write_text("uncommitted", encoding="utf-8")
    capsule_dirty = oracle.diagnose_divergence()
    assert capsule_dirty.divergence_status == STATUS_DIRTY_WORKING_TREE
    assert capsule_dirty.is_dirty is True


def test_git_oracle_pre_push_invariants(tmp_path: Path):
    """
    Verifies verify_pre_push_invariants for credentials, large files, and 160000 gitlinks.
    """
    repo = tmp_path / "test_repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Tester"], check=True)

    # 1. Clean repo verification with multiple staged files to test largest_file
    (repo / "small1.txt").write_bytes(b"A" * 30)
    (repo / "small2.txt").write_bytes(b"B" * 70)
    subprocess.run(["git", "-C", str(repo), "add", "small1.txt", "small2.txt"], check=True)
    receipt_clean = verify_pre_push_invariants(repo, max_file_bytes=100)
    assert receipt_clean.verified is True
    assert receipt_clean.status_code == "PRE_PUSH_INVARIANTS_VERIFIED"
    assert receipt_clean.largest_file_bytes == 70
    assert len(receipt_clean.violations) == 0

    # Immutability check on receipt (kills frozen=True perturbation)
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt_clean.verified = False

    # 2. Staging forbidden .env file
    (repo / ".env").write_text("SECRET_KEY=12345\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", ".env"], check=True)

    receipt = verify_pre_push_invariants(repo)
    assert receipt.verified is False
    assert receipt.status_code == "HALT_PRE_PUSH_INVARIANT_VIOLATION"
    assert any("FORBIDDEN_FILE_STAGED: .env" in v for v in receipt.violations)
    assert receipt.to_dict()["verified"] is False

    # 3. Large file over threshold
    subprocess.run(["git", "-C", str(repo), "rm", "-f", ".env"], check=True)
    (repo / "big.bin").write_bytes(b"B" * 200)
    subprocess.run(["git", "-C", str(repo), "add", "big.bin"], check=True)
    receipt_large = verify_pre_push_invariants(repo, max_file_bytes=100)
    assert receipt_large.verified is False
    assert receipt_large.largest_file_bytes == 200
    assert any("LARGE_FILE_OVER_50MB: big.bin" in v for v in receipt_large.violations)


def test_task_conditioned_passport_compiler(tmp_path: Path):
    """
    Verifies that TaskConditionedPassportCompiler builds a bounded context passport (<800 tokens).
    """
    assert DEFAULT_MAX_TOKEN_BUDGET == 800
    assert APPROX_CHARS_PER_TOKEN == 4

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    long_doc = "X" * 150
    (src_dir / "auth.py").write_text(
        f'def verify_token(token: str) -> bool:\n    """{long_doc}"""\n    return len(token) > 0\n\n'
        "async def check_async_session() -> bool:\n    return True\n\n"
        "class TokenGuard:\n    pass\n",
        encoding="utf-8",
    )
    (src_dir / "database.py").write_text(
        "import src.auth\ndef connect_db(uri: str) -> None:\n    pass\n",
        encoding="utf-8",
    )
    (src_dir / "session.py").write_text(
        "def verify_session(token: str) -> bool:\n"
        '    """Session token verification."""\n'
        "    return len(token) > 0\n",
        encoding="utf-8",
    )
    (tests_dir / "test_auth.py").write_text(
        "import src.auth\ndef test_token():\n    assert src.auth.verify_token('xyz') is True\n",
        encoding="utf-8",
    )

    compiler = TaskConditionedPassportCompiler(tmp_path)
    passport = compiler.compile_passport(
        task_query="verify token auth guard",
        failing_test_path=str(tests_dir / "test_auth.py"),
        max_token_budget=DEFAULT_MAX_TOKEN_BUDGET,
    )

    # Immutability check on passport (kills frozen=True perturbation)
    with pytest.raises(dataclasses.FrozenInstanceError):
        passport.character_count = 9999

    # Verify docstring truncation to 100
    auth_summary = compiler._module_cache.get("src/auth.py")
    assert auth_summary is not None
    assert len(auth_summary.symbols[0].docstring) == 100

    # Verify reverse dependencies
    assert "src/database.py" in compiler._reverse_dependencies.get("src.auth", set())

    # High-ranking auth.py is first, session.py is second
    assert passport.selected_modules[0] == "src/auth.py"
    assert "src/session.py" in passport.selected_modules
    assert passport.estimated_tokens == passport.character_count // APPROX_CHARS_PER_TOKEN
    assert passport.character_count > 0
    assert any("def verify_token" in s for s in passport.condensed_signatures)
    assert any("async def check_async_session" in s for s in passport.condensed_signatures)
    assert any("class TokenGuard" in s for s in passport.condensed_signatures)
    assert passport.passport_caid.startswith("sha256:")
    assert passport.to_dict()["estimated_tokens"] <= DEFAULT_MAX_TOKEN_BUDGET

    # Small budget test clipping: budget enough for auth.py snippet (~150 chars, ~38 tokens), but not session.py
    # This exercises the `else: break` branch in accumulated_chars check
    exact_budget_passport = compiler.compile_passport(
        "verify token auth guard",
        failing_test_path=str(tests_dir / "test_auth.py"),
        max_token_budget=45,
    )
    assert "src/auth.py" in exact_budget_passport.selected_modules
    assert "src/session.py" not in exact_budget_passport.selected_modules

    # Unrelated query returns 0 modules (tests score > 0 check)
    empty_passport = compiler.compile_passport("unrelated_query_xyz_12345")
    assert len(empty_passport.selected_modules) == 0
    assert empty_passport.character_count == 0
