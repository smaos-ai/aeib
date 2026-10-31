#!/usr/bin/env python3
"""
SovereignNexus Compact State Baton Exporter (tools/export_state_baton.py).

Evaluated under the stated model to emit a compact (<300 token) RFC 8785 canonical
state handoff capsule (state/STATE_BATON.json) for cross-session continuity without
context-window bloat.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs


def build_state_baton(
    directive: str,
    repo_root: Path = _REPO_ROOT,
) -> Dict[str, Any]:
    """Build compact deterministic state baton with git HEAD and verified modules."""
    head_res = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    head_sha = head_res.stdout.strip() if head_res.returncode == 0 else "unknown"

    branch_res = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    branch_name = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"

    core_modules: List[str] = [
        "src/temporal_authority_guard.py",
        "src/crypto_delegation_graph.py",
        "src/temporal_graph_router.py",
        "src/sovereign_token_decree.py",
        "src/token_decree_dispatch_interlock.py",
        "src/autonomous_pr_webhook_dispatcher.py",
        "src/hypergraph_blast_radius.py",
        "src/substrate_cube_interlock.py",
        "src/a2a_trajectory_interlock.py",
        "tools/pre_push_integrity_gate.py",
    ]
    present_modules = [m for m in core_modules if (repo_root / m).is_file()]

    baton_core: Dict[str, Any] = {
        "active_branch": branch_name,
        "directive": directive,
        "head_commit": head_sha,
        "status_label": "INTERNAL_PREVIEW_COMMISSIONED",
        "verified_module_count": len(present_modules),
        "verified_modules": present_modules,
    }
    canonical_bytes = encode_jcs(baton_core)
    baton_caid = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"
    baton_full = dict(baton_core)
    baton_full["baton_caid"] = baton_caid
    baton_full["serialized_byte_length"] = len(encode_jcs(baton_full))
    return baton_full


def main() -> None:
    parser = argparse.ArgumentParser(description="Export compact RFC 8785 STATE_BATON.json")
    parser.add_argument(
        "--directive",
        type=str,
        default="Temporal Authority, Delegation DAG & Token Decree verified",
        help="Summary directive for the state baton.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="state/STATE_BATON.json",
        help="Output path relative to repo root.",
    )
    args = parser.parse_args()

    baton = build_state_baton(directive=args.directive, repo_root=_REPO_ROOT)
    out_path = _REPO_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_bytes = encode_jcs(baton)
    out_path.write_bytes(out_bytes + b"\n")
    print(
        f"[state-baton] path={args.out} bytes={len(out_bytes)} caid={baton['baton_caid']}"
    )


if __name__ == "__main__":
    main()
