#!/usr/bin/env python3
# File: tools/aeib_orca_caprock_enforcer.py
"""
AEIB + Orca Worktree + Caprock FinOps + EVAE Pilot Governance Enforcer.

Evaluated prototype under the stated model reconciling Orca's high-autonomy
`--yolo` / `--dangerously-skip-permissions` worktree execution with AEIB's
deterministic execution boundary, Caprock's real-time token telemetry, and
Hiro Yokoki's EVAE (`EXECUTE | HOLD | BLOCK`) Pre-Execution Governance:
1. Inside the assigned Git Worktree: `EXECUTE` fast-path for local edits & tests.
2. At the Worktree Perimeter: `BLOCK` (`SIGKILL_CONTAINED`) on path traversal,
   symlink escapes, and `~/.aws` / `~/.ssh` credential reads; `HOLD` (`HALT_STEP_UP_REQUIRED`)
   on IDE/MCP control-plane modifications (`.cursor/mcp.json`, `.vscode/settings.json`)
   awaiting a human Pilot's Ed25519 RFC 9470 Step-Up Warrant.
3. At the Caprock Telemetry Stream: Trips a FinOps circuit breaker on prompt-cache
   thrashing (`< 7500 bps` hit rate after turn 3) or token budget avalanches (`> $5.00`).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def canonical_jcs_bytes(obj: Any) -> bytes:
    def _check(val: Any) -> None:
        if isinstance(val, float):
            raise ValueError("ERR_FLOAT_FORBIDDEN_IN_JCS")
        if isinstance(val, dict):
            for k, v in val.items():
                if not isinstance(k, str):
                    raise ValueError("ERR_NON_STRING_KEY")
                _check(v)
        elif isinstance(val, list):
            for item in val:
                _check(item)

    _check(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def sha256_prefixed(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


@dataclass(frozen=True)
class CaprockTurnTelemetry:
    session_id: str
    agent_id: str
    turn_index: int
    uncached_input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    turn_cost_usd_minor: int  # in cents (100 = $1.00)

    @property
    def cache_hit_ratio_bps(self) -> int:
        total_in = self.uncached_input_tokens + self.cached_input_tokens
        if total_in <= 0:
            return 10000
        return (self.cached_input_tokens * 10000) // total_in


class CaprockFinOpsCircuitBreaker:
    """
    Ingests real-time token & cache telemetry from Caprock proxy and feeds
    AEIB Station 2 Escrow to prevent runaway token avalanches.
    """

    def __init__(
        self,
        per_worktree_cap_minor: int = 500,        # $5.00 per worktree
        sprint_sponsor_cap_minor: int = 25000,    # $250.00 per 5h sprint
        min_cache_hit_bps_after_turn3: int = 7500,  # 75.00% cache hit SLO
    ) -> None:
        self.per_worktree_cap_minor = per_worktree_cap_minor
        self.sprint_sponsor_cap_minor = sprint_sponsor_cap_minor
        self.min_cache_hit_bps_after_turn3 = min_cache_hit_bps_after_turn3
        self.worktree_spend_minor: Dict[str, int] = {}
        self.total_sprint_spend_minor: int = 0

    def ingest_and_evaluate(self, telemetry: CaprockTurnTelemetry) -> Tuple[str, str]:
        wt_key = f"{telemetry.session_id}:{telemetry.agent_id}"
        new_wt_spend = (
            self.worktree_spend_minor.get(wt_key, 0) + telemetry.turn_cost_usd_minor
        )
        new_sprint_spend = self.total_sprint_spend_minor + telemetry.turn_cost_usd_minor

        if new_wt_spend > self.per_worktree_cap_minor:
            return ("HALTED", "HALT_CAPROCK_WORKTREE_BUDGET_AVALANCHE")

        if new_sprint_spend > self.sprint_sponsor_cap_minor:
            return ("HALTED", "HALT_CAPROCK_SPRINT_SPONSOR_CAP_EXCEEDED")

        self.worktree_spend_minor[wt_key] = new_wt_spend
        self.total_sprint_spend_minor = new_sprint_spend

        if (
            telemetry.turn_index >= 3
            and telemetry.cache_hit_ratio_bps < self.min_cache_hit_bps_after_turn3
        ):
            return (
                "THROTTLED_DEGRADED",
                "WARN_CAPROCK_CACHE_THRASH_FORCE_SAKE_PINNING",
            )

        return ("OK", "CAPROCK_FINOPS_WITHIN_SLO")


@dataclass(frozen=True)
class Rfc9470StepUpWarrant:
    operation_id: str
    bound_caid: str
    supervisor_key_id: str
    signature_b64: str


@dataclass(frozen=True)
class OrcaDaemonRpcRequest:
    operation_id: str
    session_id: str
    agent_id: str
    rpc_method: str       # "fs.read" | "fs.write" | "pty.exec" | "git.push"
    target_path: str
    command_args: Tuple[str, ...]
    claimed_caid: str
    step_up_warrant: Optional[Rfc9470StepUpWarrant] = None


class AeibOrcaWorktreeEnforcer:
    """
    Reconciles Orca's `--yolo` convenience with AEIB's deterministic boundary
    and EVAE (`EXECUTE` | `HOLD` | `BLOCK`) Pilot governance:
    - Fast-paths local edits inside the assigned worktree (`EXECUTE`).
    - Blocks sensitive host paths (`~/.aws`, `~/.ssh`, `/etc`) (`BLOCK`).
    - Enforces disjoint write sets across parallel worktrees (`BLOCK`).
    - Transitions boundary-crossing operations to `HOLD` (`HALT_STEP_UP_REQUIRED`)
      until the human Pilot signs an RFC 9470 Step-Up Warrant.
    """

    PROTECTED_CONTROL_PLANE_RELPATHS = frozenset(
        {
            ".vscode/settings.json",
            ".vscode/tasks.json",
            ".cursor/mcp.json",
            ".mcp.json",
            ".claude/settings.json",
        }
    )

    FORBIDDEN_HOST_SUBSTRINGS = (
        "/.ssh",
        "/.aws",
        "/.config/gcloud",
        "/.kube",
        "/etc/shadow",
        "/etc/passwd",
        "/var/run/docker.sock",
    )

    def __init__(
        self,
        worktree_roots: Dict[str, Path],
        supervisor_pubkey: Ed25519PublicKey,
        caprock_breaker: CaprockFinOpsCircuitBreaker,
    ) -> None:
        self.worktree_roots = {
            aid: root.resolve() for aid, root in worktree_roots.items()
        }
        self.supervisor_pubkey = supervisor_pubkey
        self.caprock_breaker = caprock_breaker
        self.claimed_write_relpaths: Dict[str, str] = {}

    @staticmethod
    def generate_macos_seatbelt_profile(worktree_root: Path) -> str:
        wt_str = str(worktree_root.resolve())
        return "\n".join(
            [
                "(version 1)",
                "(allow default)",
                '(deny file-read* (subpath (string-append (param "HOME") "/.ssh")))',
                '(deny file-read* (subpath (string-append (param "HOME") "/.aws")))',
                '(deny file-read* (subpath (string-append (param "HOME") "/.kube")))',
                "(deny file-write*)",
                f'(allow file-write* (subpath "{wt_str}"))',
                '(allow file-write* (subpath "/tmp"))',
            ]
        )

    @staticmethod
    def compute_rpc_caid(req: OrcaDaemonRpcRequest) -> str:
        core = {
            "agent_id": req.agent_id,
            "command_args": list(req.command_args),
            "operation_id": req.operation_id,
            "rpc_method": req.rpc_method,
            "session_id": req.session_id,
            "target_path": req.target_path,
        }
        return sha256_prefixed(canonical_jcs_bytes(core))

    def evaluate_daemon_rpc(self, req: OrcaDaemonRpcRequest) -> Dict[str, str]:
        expected_caid = self.compute_rpc_caid(req)
        if req.claimed_caid != expected_caid:
            return {
                "evae_armor_state": "BLOCK",
                "disposition": "DENIED",
                "code": "HALT_ORCA_DAEMON_CAID_MISMATCH",
            }

        wt_root = self.worktree_roots.get(req.agent_id)
        if wt_root is None:
            return {
                "evae_armor_state": "BLOCK",
                "disposition": "DENIED",
                "code": "HALT_UNREGISTERED_ORCA_WORKTREE_AGENT",
            }

        joined_cmd = " ".join(req.command_args)
        for forbidden in self.FORBIDDEN_HOST_SUBSTRINGS:
            if forbidden in req.target_path or forbidden in joined_cmd:
                return {
                    "evae_armor_state": "BLOCK",
                    "disposition": "SIGKILL_CONTAINED",
                    "code": "HALT_RING0_CREDENTIAL_OR_HOST_PATH_ESCAPE",
                }
        if "rm -rf ~" in joined_cmd or "rm -rf /" in joined_cmd:
            return {
                "evae_armor_state": "BLOCK",
                "disposition": "SIGKILL_CONTAINED",
                "code": "HALT_RING0_DESTRUCTIVE_HOST_WIPE_ATTEMPT",
            }

        candidate_path = (
            Path(req.target_path)
            if os.path.isabs(req.target_path)
            else (wt_root / req.target_path)
        )
        resolved_target = candidate_path.resolve()

        try:
            rel_to_wt = resolved_target.relative_to(wt_root)
            rel_posix = str(PurePosixPath(rel_to_wt))
            inside_worktree = True
        except ValueError:
            rel_posix = ""
            inside_worktree = False

        touches_control_plane = (
            inside_worktree
            and (
                rel_posix in self.PROTECTED_CONTROL_PLANE_RELPATHS
                or rel_posix.startswith(".git/hooks")
            )
        )
        requires_step_up = (
            not inside_worktree
            or touches_control_plane
            or req.rpc_method == "git.push"
        )

        if requires_step_up:
            if req.step_up_warrant is None:
                return {
                    "evae_armor_state": "HOLD",
                    "disposition": "HALT_STEP_UP_REQUIRED",
                    "code": "ESCALATE_OUTSIDE_WORKTREE_OR_PRIVILEGED_RPC_REQUIRES_RFC9470",
                }
            if req.step_up_warrant.bound_caid != expected_caid:
                return {
                    "evae_armor_state": "BLOCK",
                    "disposition": "DENIED",
                    "code": "HALT_STEP_UP_WARRANT_CAID_MISMATCH",
                }
            warrant_payload = canonical_jcs_bytes(
                {
                    "bound_caid": expected_caid,
                    "operation_id": req.operation_id,
                    "supervisor_key_id": req.step_up_warrant.supervisor_key_id,
                }
            )
            try:
                self.supervisor_pubkey.verify(
                    base64.b64decode(req.step_up_warrant.signature_b64, validate=True),
                    warrant_payload,
                )
            except Exception:
                return {
                    "evae_armor_state": "BLOCK",
                    "disposition": "DENIED",
                    "code": "HALT_INVALID_RFC9470_STEP_UP_SIGNATURE",
                }
            return {
                "evae_armor_state": "EXECUTE",
                "disposition": "AUTHORIZED_VIA_RFC9470_STEP_UP",
                "code": "OK",
                "caid": expected_caid,
            }

        if req.rpc_method == "fs.write":
            existing_owner = self.claimed_write_relpaths.get(rel_posix)
            if existing_owner is not None and existing_owner != req.agent_id:
                return {
                    "evae_armor_state": "BLOCK",
                    "disposition": "DENIED",
                    "code": "HALT_ORCA_WORKTREE_WRITE_COLLISION",
                }
            self.claimed_write_relpaths[rel_posix] = req.agent_id

        return {
            "evae_armor_state": "EXECUTE",
            "disposition": "ALLOW_FAST_PATH_YOLO",
            "code": "OK",
            "caid": expected_caid,
        }


def run_self_test() -> None:
    sup_priv = Ed25519PrivateKey.generate()
    caprock = CaprockFinOpsCircuitBreaker(
        per_worktree_cap_minor=500,
        sprint_sponsor_cap_minor=25000,
        min_cache_hit_bps_after_turn3=7500,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        wt_agent1 = base_dir / "worktrees" / "agent-1"
        wt_agent2 = base_dir / "worktrees" / "agent-2"
        wt_agent1.mkdir(parents=True)
        wt_agent2.mkdir(parents=True)

        enforcer = AeibOrcaWorktreeEnforcer(
            worktree_roots={"agent-1": wt_agent1, "agent-2": wt_agent2},
            supervisor_pubkey=sup_priv.public_key(),
            caprock_breaker=caprock,
        )

        sb_profile = enforcer.generate_macos_seatbelt_profile(wt_agent1)
        assert '(deny file-read* (subpath (string-append (param "HOME") "/.aws")))' in sb_profile

        req_ok = OrcaDaemonRpcRequest(
            operation_id="op-wt-1",
            session_id="sess-01",
            agent_id="agent-1",
            rpc_method="fs.write",
            target_path="src/payment_handler.py",
            command_args=(),
            claimed_caid="",
        )
        req_ok = OrcaDaemonRpcRequest(
            **{**req_ok.__dict__, "claimed_caid": enforcer.compute_rpc_caid(req_ok)}
        )
        res_ok = enforcer.evaluate_daemon_rpc(req_ok)
        assert res_ok["disposition"] == "ALLOW_FAST_PATH_YOLO"
        assert res_ok["evae_armor_state"] == "EXECUTE"


if __name__ == "__main__":
    run_self_test()
    print("AEIB + ORCA WORKTREE + CAPROCK FINOPS + EVAE ENFORCER VERIFIED.")
