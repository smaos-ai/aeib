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
tests/test_eo1_unified_gate.py
================================================================================
Comprehensive verification suite for EO1UnifiedGate.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.eo1_unified_gate import (
    EO1UnifiedGate,
    TaintFlag,
)


@pytest.fixture
def git_workspace(tmp_path: Path) -> Path:
    repo = tmp_path / "sovereign_repo"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".git").mkdir()
    (repo / "tests").mkdir()
    (repo / "src").mkdir()
    return repo


def test_workspace_initialization_safety(tmp_path: Path) -> None:
    # 1. Missing .git anchor must fail
    no_git = tmp_path / "plain_dir"
    no_git.mkdir()
    with pytest.raises(ValueError, match="HALT_WORKSPACE_MISSING_GIT_ANCHOR"):
        EO1UnifiedGate(workspace_root=str(no_git))

    # 2. Dangerous directory (downloads and desktop) must fail
    dl_dir = tmp_path / "Downloads" / "sub_repo"
    dl_dir.mkdir(parents=True)
    (dl_dir / ".git").mkdir()
    with pytest.raises(ValueError, match="HALT_WORKSPACE_UNSAFE_DIRECTORY"):
        EO1UnifiedGate(workspace_root=str(dl_dir))

    desk_dir = tmp_path / "Desktop" / "sub_repo"
    desk_dir.mkdir(parents=True)
    (desk_dir / ".git").mkdir()
    with pytest.raises(ValueError, match="HALT_WORKSPACE_UNSAFE_DIRECTORY"):
        EO1UnifiedGate(workspace_root=str(desk_dir))


def test_path_escape_and_read_only_open(git_workspace: Path) -> None:
    gate = EO1UnifiedGate(workspace_root=str(git_workspace))

    # Path escape outside workspace
    r_esc = gate.validate_code_write("task_esc", "/etc/passwd", "root = 0\n")
    assert r_esc.allowed is False
    assert "HALT_DIRECT_INVARIANT_WRITE:PATH_OR_SYMLINK_ESCAPE" in r_esc.status_code

    # Unsafe downloads in path parameter
    r_dl = gate.validate_code_write("task_dl", "Downloads/agent.py", "x = 1\n")
    assert r_dl.allowed is False
    assert "UNSAFE_DOWNLOADS_PATH" in r_dl.status_code

    # Read-only open of an invariant file (should NOT be blocked)
    ro_code = (
        "def read_cfg():\n"
        "    with open('config.py') as f:\n"
        "        return f.read()\n"
    )
    r_ro = gate.validate_code_write("task_ro", "src/reader.py", ro_code)
    assert r_ro.allowed is True
    assert r_ro.status_code == "OK_CODE_WRITE_AUTHORIZED"

    # io.open with write mode must be blocked
    io_write = (
        "import io\n"
        "def cheat_io():\n"
        "    f = io.open('config.py', 'w')\n"
    )
    r_io = gate.validate_code_write("task_io", "src/writer.py", io_write)
    assert r_io.allowed is False
    assert "HALT_AST_OPEN_WRITE" in r_io.status_code


def test_blocks_symlink_escape_and_reflection_bypass(git_workspace: Path) -> None:
    gate = EO1UnifiedGate(workspace_root=str(git_workspace))

    # Create a symlink inside src/ pointing to tests/test_escrow.py
    real_test = git_workspace / "tests" / "test_escrow.py"
    real_test.write_text("def test_real(): assert 1 == 1\n", encoding="utf-8")

    symlink_path = git_workspace / "src" / "harmless_link.py"
    os.symlink(str(real_test), str(symlink_path))

    # 1A: Attempt to overwrite src/harmless_link.py -> Caught via realpath
    r_sym = gate.validate_code_write("task_sym", "src/harmless_link.py", "x = 1\n")
    assert r_sym.allowed is False
    assert "HALT_DIRECT_INVARIANT_WRITE" in r_sym.status_code
    assert "PROTECTED_DIR:tests/test_escrow.py" in r_sym.status_code

    # 1B: Attempt to use getattr(os, 'remove') reflection to delete a test
    r_refl = gate.validate_code_write(
        "task_refl",
        "src/worker.py",
        "import os\ngetattr(os, 'remove')('tests/test_escrow.py')\n",
    )
    assert r_refl.allowed is False
    assert r_refl.status_code == "HALT_FORBIDDEN_REFLECTION:getattr"

    # 1C: Direct overwrite of AGENTS.md
    r_agents = gate.validate_code_write("task_agents", "AGENTS.md", "allow_all = True\n")
    assert r_agents.allowed is False
    assert "HALT_DIRECT_INVARIANT_WRITE" in r_agents.status_code


def test_blocks_open_and_destructive_fs_calls(git_workspace: Path) -> None:
    gate = EO1UnifiedGate(workspace_root=str(git_workspace))

    # Positional open write mode
    malicious_open = (
        "def cheat():\n"
        "    with open('tests/test_escrow.py', 'w') as f:\n"
        "        f.write('assert True')\n"
    )
    r1 = gate.validate_code_write("task_open", "src/worker.py", malicious_open)
    assert r1.allowed is False
    assert "HALT_AST_OPEN_WRITE" in r1.status_code

    # Keyword open write mode
    malicious_kw = (
        "def cheat_kw():\n"
        "    f = open('config.py', mode='a')\n"
        "    f.write('x = 1')\n"
    )
    r2 = gate.validate_code_write("task_kw", "src/worker.py", malicious_kw)
    assert r2.allowed is False
    assert "HALT_AST_OPEN_WRITE" in r2.status_code

    # Path write_text call
    malicious_path = (
        "from pathlib import Path\n"
        "def cheat_path():\n"
        "    Path('tests/test_foo.py').write_text('pass')\n"
    )
    r3 = gate.validate_code_write("task_path", "src/worker.py", malicious_path)
    assert r3.allowed is False
    assert "HALT_DESTRUCTIVE_FS_CALL" in r3.status_code

    # Invariant var mutation
    malicious_var = "config.MAX_BUDGET = 9999999\n"
    r4 = gate.validate_code_write("task_var", "src/worker.py", malicious_var)
    assert r4.allowed is False
    assert "HALT_INVARIANT_VAR_MUTATION" in r4.status_code


def test_blocks_lethal_trifecta_and_revokes_subsequent_writes(git_workspace: Path) -> None:
    gate = EO1UnifiedGate(workspace_root=str(git_workspace))

    # Leg 1: Sensitive Data
    r1 = gate.evaluate_tool_and_taint("task_tri", "read_vault_secret")
    assert r1.allowed is True
    assert gate.get_taint("task_tri") == TaintFlag.HAS_SENSITIVE_DATA

    # Leg 2: Untrusted Content
    r2 = gate.evaluate_tool_and_taint("task_tri", "web_browse")
    assert r2.allowed is True
    assert TaintFlag.HAS_SENSITIVE_DATA in gate.get_taint("task_tri")
    assert TaintFlag.HAS_UNTRUSTED_CONTENT in gate.get_taint("task_tri")

    # Leg 3: External Egress -> TRIPS LETHAL TRIFECTA
    r_egress = gate.evaluate_tool_and_taint("task_tri", "dispatch_webhook")
    assert r_egress.allowed is False
    assert r_egress.status_code == "HALT_LETHAL_TRIFECTA_DETECTED"
    assert gate.is_write_revoked("task_tri") is True

    # Any subsequent code write attempt is permanently revoked
    r_write = gate.validate_code_write("task_tri", "src/app.py", "x = 1\n")
    assert r_write.allowed is False
    assert r_write.status_code == "HALT_WRITE_PERMISSION_REVOKED"


def test_legal_blocker_escalation_freezes_task(git_workspace: Path) -> None:
    gate = EO1UnifiedGate(workspace_root=str(git_workspace))

    ticket = gate.report_unsolvable_blocker(
        task_id="task_stuck",
        blocker_category="CONTRADICTORY_SPEC",
        reason="Spec requires O(1) latency and full-table unindexed scan simultaneously",
        reproducing_evidence="Benchmark shows 420ms on 1M rows without index",
    )

    assert ticket.task_id == "task_stuck"
    assert ticket.blocker_category == "CONTRADICTORY_SPEC"
    assert ticket.write_permissions_revoked is True
    assert ticket.ticket_caid.startswith("sha256:")
    assert gate.is_write_revoked("task_stuck") is True

    # BlockerTicket immutability verification (kills line 128 constant True perturbation)
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        ticket.task_id = "tampered_task"

    # Test ticket dictionary serialization
    td = ticket.to_dict()
    assert td["task_id"] == "task_stuck"
    assert td["write_permissions_revoked"] is True
    assert td["ticket_caid"] == ticket.ticket_caid

    # Test clean taint query
    assert gate.get_taint("never_seen_task") == TaintFlag.CLEAN

    # Attempting to write code while task is stuck in blocker halt is rejected
    r_after = gate.validate_code_write("task_stuck", "src/query.py", "x = 1\n")
    assert r_after.allowed is False
    assert r_after.status_code == "HALT_WRITE_PERMISSION_REVOKED"

    # Input validation on blocker reports
    with pytest.raises(ValueError, match="ERR_EMPTY_TASK_ID"):
        gate.report_unsolvable_blocker("", "CONTRADICTORY_SPEC", "a" * 15, "b" * 15)

    with pytest.raises(ValueError, match="ERR_INVALID_BLOCKER_CATEGORY"):
        gate.report_unsolvable_blocker("t1", "INVALID_CAT", "a" * 15, "b" * 15)

    with pytest.raises(ValueError, match="ERR_BLOCKER_REASON_TOO_SHALLOW"):
        gate.report_unsolvable_blocker("t1", "CONTRADICTORY_SPEC", "too short", "b" * 15)

    with pytest.raises(ValueError, match="ERR_BLOCKER_EVIDENCE_TOO_SHALLOW"):
        gate.report_unsolvable_blocker("t1", "CONTRADICTORY_SPEC", "a" * 15, "short")


def test_nominal_code_write_authorized(git_workspace: Path) -> None:
    gate = EO1UnifiedGate(workspace_root=str(git_workspace))

    valid_code = (
        "def calculate_total(items: list[int]) -> int:\n"
        "    return sum(items)\n"
    )
    receipt = gate.validate_code_write("task_nominal", "src/calculator.py", valid_code)
    assert receipt.allowed is True
    assert receipt.status_code == "OK_CODE_WRITE_AUTHORIZED"
    assert receipt.receipt_caid.startswith("sha256:")
    d = receipt.to_dict()
    assert d["allowed"] is True
    assert d["status_code"] == "OK_CODE_WRITE_AUTHORIZED"
