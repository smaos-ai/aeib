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
src/eo1_unified_gate.py
================================================================================
EO1 Unified Pre-Execution Latch & Invariant Core Boundary Engine.

Evaluated under the stated model:
  - PCI Lethal Trifecta dynamic taint tracking (Sensitive Data + Untrusted Content + External Egress).
  - Workspace .git Root & Symlink Realpath Confinement (Blocks ~/Downloads & symlink escapes).
  - Hardened AST Invariant Core Guard (Blocks direct overwrite, open/Path/os writes, and eval/getattr reflection).
  - Anti-Reward-Hacking Escalation Channel (`report_unsolvable_blocker`).
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from enum import Flag, auto
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs


def sha256_jcs_caid(payload: Any) -> str:
    """Computes deterministic SHA-256 CAID over RFC 8785 canonical bytes."""
    raw = payload if isinstance(payload, bytes) else encode_jcs(payload)
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


class TaintFlag(Flag):
    """Dynamic taint flags tracking Lethal Trifecta exposure."""

    CLEAN = 0
    HAS_SENSITIVE_DATA = auto()     # Access to vaults, PII, financial DBs
    HAS_UNTRUSTED_CONTENT = auto()  # Web browse, user chat, email ingest
    HAS_EXTERNAL_EGRESS = auto()    # Sockets, webhooks, outbound API dispatch


INVARIANT_FILES: FrozenSet[str] = frozenset(
    {
        "config.py",
        "security_rules.yaml",
        "agents.md",
        "claude.md",
        ".env",
        "eo1_latch_config.json",
    }
)

INVARIANT_DIRS: Tuple[str, ...] = (
    ".git",
    "tests",
    "src/monitor_ai",
    "compliance",
)

DESTRUCTIVE_FS_METHODS: FrozenSet[str] = frozenset(
    {
        "write_text",
        "write_bytes",
        "remove",
        "unlink",
        "replace",
        "rename",
        "rmtree",
        "copy",
        "copyfile",
        "move",
    }
)

FORBIDDEN_REFLECTION_CALLS: FrozenSet[str] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "delattr",
    }
)


@dataclass(frozen=True)
class EO1GateReceipt:
    """RFC 8785 canonical authorization receipt emitted by EO1."""

    allowed: bool
    status_code: str
    task_id: str
    target: str
    active_taint: str
    receipt_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_taint": self.active_taint,
            "allowed": self.allowed,
            "receipt_caid": self.receipt_caid,
            "status_code": self.status_code,
            "target": self.target,
            "task_id": self.task_id,
        }


@dataclass(frozen=True)
class BlockerTicket:
    """Option A: Structured ticket generated when Builder AI summons human help."""

    task_id: str
    blocker_category: str
    reason: str
    reproducing_evidence: str
    write_permissions_revoked: bool
    ticket_caid: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocker_category": self.blocker_category,
            "reason": self.reason,
            "reproducing_evidence": self.reproducing_evidence,
            "task_id": self.task_id,
            "ticket_caid": self.ticket_caid,
            "write_permissions_revoked": self.write_permissions_revoked,
        }


class EO1UnifiedGate:
    """
    Physical-boundary pre-execution latch enforcing invariant core protection,
    dynamic taint tracking, and workspace root confinement.
    """

    DANGEROUS_DIRS: FrozenSet[str] = frozenset({"downloads", "desktop"})
    VALID_BLOCKER_CATEGORIES: FrozenSet[str] = frozenset(
        {
            "CONTRADICTORY_SPEC",
            "BROKEN_UPSTREAM_TEST",
            "MISSING_CAPABILITY",
            "EXTERNAL_DEPENDENCY",
        }
    )

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = os.path.realpath(workspace_root)
        parts = set(self.workspace_root.lower().split(os.sep))
        if parts.intersection(self.DANGEROUS_DIRS):
            raise ValueError("HALT_WORKSPACE_UNSAFE_DIRECTORY")
        if not os.path.exists(os.path.join(self.workspace_root, ".git")):
            raise ValueError("HALT_WORKSPACE_MISSING_GIT_ANCHOR")

        self._taint: Dict[str, TaintFlag] = {}
        self._revoked_tasks: Dict[str, str] = {}

    def get_taint(self, task_id: str) -> TaintFlag:
        return self._taint.get(task_id, TaintFlag.CLEAN)

    def is_write_revoked(self, task_id: str) -> bool:
        return task_id in self._revoked_tasks

    def _resolve_and_check_invariant(self, filepath: str) -> Tuple[bool, str]:
        """Resolves target paths through symlinks via realpath and checks protection rules."""
        raw_norm = filepath.replace("\\", "/").lower()
        if "downloads" in raw_norm.split("/"):
            return True, "UNSAFE_DOWNLOADS_PATH"

        candidate = (
            filepath
            if os.path.isabs(filepath)
            else os.path.join(self.workspace_root, filepath)
        )
        real_target = os.path.realpath(candidate)

        # Check path or symlink escape outside the workspace root
        if not (
            real_target == self.workspace_root
            or real_target.startswith(self.workspace_root + os.sep)
        ):
            return True, f"PATH_OR_SYMLINK_ESCAPE:{filepath}"

        rel_path = os.path.relpath(real_target, self.workspace_root).replace("\\", "/")
        if os.path.basename(real_target).lower() in INVARIANT_FILES:
            return True, f"PROTECTED_FILE:{rel_path}"

        for inv_dir in INVARIANT_DIRS:
            if rel_path == inv_dir or rel_path.startswith(inv_dir + "/"):
                return True, f"PROTECTED_DIR:{rel_path}"

        return False, rel_path

    def evaluate_tool_and_taint(self, task_id: str, tool_name: str) -> EO1GateReceipt:
        """
        Dynamically tracks agent capability exposure.
        If Sensitive Data, Untrusted Content, and External Egress converge,
        the Lethal Trifecta trips fail-closed and write permissions are permanently revoked.
        """
        curr = self._taint.get(task_id, TaintFlag.CLEAN)

        if tool_name in ("query_database", "read_vault_secret", "read_customer_pii"):
            curr |= TaintFlag.HAS_SENSITIVE_DATA
        elif tool_name in ("web_browse", "read_untrusted_input", "fetch_external_url"):
            curr |= TaintFlag.HAS_UNTRUSTED_CONTENT
        elif tool_name in ("http_post", "send_email", "dispatch_webhook"):
            curr |= TaintFlag.HAS_EXTERNAL_EGRESS

        self._taint[task_id] = curr

        if (
            (TaintFlag.HAS_SENSITIVE_DATA in curr)
            and (TaintFlag.HAS_UNTRUSTED_CONTENT in curr)
            and (TaintFlag.HAS_EXTERNAL_EGRESS in curr)
        ):
            self._revoked_tasks[task_id] = "LETHAL_TRIFECTA"
            return self._mint(False, "HALT_LETHAL_TRIFECTA_DETECTED", task_id, tool_name, curr)

        return self._mint(True, "OK_TOOL_AUTHORIZED", task_id, tool_name, curr)

    def validate_code_write(
        self, task_id: str, file_path: str, proposed_code: str
    ) -> EO1GateReceipt:
        """
        Pre-execution gate for proposed code mutations:
        1. Verifies write permissions have not been revoked for task_id.
        2. Resolves realpath to defeat symlink bypasses targeting invariant files.
        3. Parses AST to block reflection, open/write on invariants, and fs destructive methods.
        """
        curr_taint = self._taint.get(task_id, TaintFlag.CLEAN)

        if task_id in self._revoked_tasks:
            return self._mint(
                False, "HALT_WRITE_PERMISSION_REVOKED", task_id, file_path, curr_taint
            )

        # 1. Check target file path & symlink resolution
        is_inv, reason = self._resolve_and_check_invariant(file_path)
        if is_inv:
            self._revoked_tasks[task_id] = reason
            return self._mint(
                False, f"HALT_DIRECT_INVARIANT_WRITE:{reason}", task_id, file_path, curr_taint
            )

        # 2. Parse AST of proposed code
        try:
            tree = ast.parse(proposed_code, filename=file_path)
        except SyntaxError:
            return self._mint(False, "HALT_SYNTAX_ERROR", task_id, file_path, curr_taint)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Block dynamic reflection/eval bypasses
                if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_REFLECTION_CALLS:
                    self._revoked_tasks[task_id] = f"REFLECTION:{node.func.id}"
                    return self._mint(
                        False,
                        f"HALT_FORBIDDEN_REFLECTION:{node.func.id}",
                        task_id,
                        file_path,
                        curr_taint,
                    )

                # Block open() / io.open() writes to invariant files
                is_open = (
                    (isinstance(node.func, ast.Name) and node.func.id == "open")
                    or (
                        isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "io"
                        and node.func.attr == "open"
                    )
                )
                if is_open and node.args and isinstance(node.args[0], ast.Constant):
                    target_arg = str(node.args[0].value)
                    mode_val = "r"
                    if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                        mode_val = str(node.args[1].value)
                    for kw in node.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            mode_val = str(kw.value.value)

                    inv_hit, inv_why = self._resolve_and_check_invariant(target_arg)
                    if inv_hit and any(m in mode_val for m in ("w", "a", "+", "x")):
                        self._revoked_tasks[task_id] = inv_why
                        return self._mint(
                            False,
                            f"HALT_AST_OPEN_WRITE:{inv_why}",
                            task_id,
                            target_arg,
                            curr_taint,
                        )

                # Block Path.write_text / os.remove / shutil calls on invariant files
                if isinstance(node.func, ast.Attribute) and node.func.attr in DESTRUCTIVE_FS_METHODS:
                    paths: List[str] = [
                        str(a.value)
                        for a in node.args
                        if isinstance(a, ast.Constant) and isinstance(a.value, str)
                    ]
                    if (
                        isinstance(node.func.value, ast.Call)
                        and node.func.value.args
                        and isinstance(node.func.value.args[0], ast.Constant)
                    ):
                        paths.append(str(node.func.value.args[0].value))

                    for p_str in paths:
                        inv_hit, inv_why = self._resolve_and_check_invariant(p_str)
                        if inv_hit:
                            self._revoked_tasks[task_id] = inv_why
                            return self._mint(
                                False,
                                f"HALT_DESTRUCTIVE_FS_CALL:{inv_why}",
                                task_id,
                                p_str,
                                curr_taint,
                            )

            elif isinstance(node, ast.Assign):
                for t_node in node.targets:
                    if isinstance(t_node, ast.Attribute) and isinstance(t_node.value, ast.Name):
                        var_name = f"{t_node.value.id}.{t_node.attr}"
                        if var_name.startswith(("config.", "security.")):
                            self._revoked_tasks[task_id] = f"INVARIANT_VAR:{var_name}"
                            return self._mint(
                                False,
                                f"HALT_INVARIANT_VAR_MUTATION:{var_name}",
                                task_id,
                                file_path,
                                curr_taint,
                            )

        return self._mint(True, "OK_CODE_WRITE_AUTHORIZED", task_id, file_path, curr_taint)

    def report_unsolvable_blocker(
        self,
        task_id: str,
        blocker_category: str,
        reason: str,
        reproducing_evidence: str,
    ) -> BlockerTicket:
        """
        Option A: Anti-Reward-Hacking Escalation Channel.
        Allows Builder AI to legitimately pull the Andon cord when facing broken specs,
        freezing the task and minting a verifiable BlockerTicket.
        """
        if not task_id.strip():
            raise ValueError("ERR_EMPTY_TASK_ID")
        if blocker_category not in self.VALID_BLOCKER_CATEGORIES:
            raise ValueError(f"ERR_INVALID_BLOCKER_CATEGORY:{blocker_category}")
        if len(reason.strip()) < 10:
            raise ValueError("ERR_BLOCKER_REASON_TOO_SHALLOW")
        if len(reproducing_evidence.strip()) < 10:
            raise ValueError("ERR_BLOCKER_EVIDENCE_TOO_SHALLOW")

        payload = {
            "blocker_category": blocker_category,
            "reason": reason.strip(),
            "reproducing_evidence": reproducing_evidence.strip(),
            "status": "ESCALATED_BLOCKER_HALT",
            "task_id": task_id.strip(),
            "write_permissions_revoked": True,
        }
        caid = sha256_jcs_caid(payload)
        self._revoked_tasks[task_id.strip()] = caid

        return BlockerTicket(
            task_id=task_id.strip(),
            blocker_category=blocker_category,
            reason=reason.strip(),
            reproducing_evidence=reproducing_evidence.strip(),
            write_permissions_revoked=True,
            ticket_caid=caid,
        )

    @staticmethod
    def _mint(
        allowed: bool, status_code: str, task_id: str, target: str, taint: TaintFlag
    ) -> EO1GateReceipt:
        payload = {
            "active_taint": str(taint),
            "allowed": allowed,
            "status_code": status_code,
            "target": target,
            "task_id": task_id,
        }
        return EO1GateReceipt(
            allowed=allowed,
            status_code=status_code,
            task_id=task_id,
            target=target,
            active_taint=str(taint),
            receipt_caid=sha256_jcs_caid(payload),
        )
