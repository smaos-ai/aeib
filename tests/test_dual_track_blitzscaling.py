#!/usr/bin/env python3
"""
tests/test_dual_track_blitzscaling.py
================================================================================
Comprehensive Verification Suite for Dual-Track Blitzscaling:
  - Track 1 (Option A): Developer-Led Viral Launch & Distribution Asset (NPX / PyPI)
  - Track 2 (Option B): B2B FinOps Diagnostic Wedge (€2,500 Package & fix.patch)
  - Strict Epistemic Calibration (0 Banned Words).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "contextcart-mcp"))

from calculator import calculate_token_economics
from tools.generate_finops_remediation_patch import generate_patch


def test_track1_npx_package_manifest():
    """Verifies contextcart-mcp/package.json has valid name, version, and bin entry."""
    pkg_file = REPO_ROOT / "contextcart-mcp" / "package.json"
    assert pkg_file.exists()
    data = json.loads(pkg_file.read_text(encoding="utf-8"))
    assert data["name"] == "context-governor-mcp"
    assert data["version"] == "1.0.0"
    assert "bin" in data
    assert "context-governor-mcp" in data["bin"]
    bin_path = REPO_ROOT / "contextcart-mcp" / data["bin"]["context-governor-mcp"]
    assert bin_path.exists()


def test_track1_pyproject_toml():
    """Verifies contextcart-mcp/pyproject.toml has valid configuration and zero dependencies."""
    toml_file = REPO_ROOT / "contextcart-mcp" / "pyproject.toml"
    assert toml_file.exists()
    content = toml_file.read_text(encoding="utf-8")
    assert 'name = "contextcart-mcp"' in content
    assert 'dependencies = []' in content
    assert 'contextcart-mcp = "server:main"' in content


def test_track1_node_cli_help():
    """Verifies that node bin/context-governor-mcp.js --help executes cleanly."""
    bin_path = REPO_ROOT / "contextcart-mcp" / "bin" / "context-governor-mcp.js"
    res = subprocess.run(
        ["node", str(bin_path), "--help"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert res.returncode == 0
    assert "CONTEXT GOVERNOR MCP" in res.stdout
    assert "init" in res.stdout
    assert "scan" in res.stdout
    assert "audit" in res.stdout


def test_track1_node_cli_init_in_tmp(tmp_path):
    """Verifies that node bin/context-governor-mcp.js init configures local .mcp.json."""
    bin_path = REPO_ROOT / "contextcart-mcp" / "bin" / "context-governor-mcp.js"
    res = subprocess.run(
        ["node", str(bin_path), "init"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert res.returncode == 0
    assert "Configured contextcart MCP server" in res.stdout

    mcp_json = tmp_path / ".mcp.json"
    assert mcp_json.exists()
    cfg = json.loads(mcp_json.read_text(encoding="utf-8"))
    assert "mcpServers" in cfg
    assert "contextcart" in cfg["mcpServers"]
    assert cfg["mcpServers"]["contextcart"]["command"] == "python3"


def test_track1_node_cli_scan():
    """Verifies that node bin/context-governor-mcp.js scan executes against src directory."""
    bin_path = REPO_ROOT / "contextcart-mcp" / "bin" / "context-governor-mcp.js"
    res = subprocess.run(
        ["node", str(bin_path), "scan", str(REPO_ROOT / "src")],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert res.returncode == 0
    assert "Discovered" in res.stdout
    assert "Python source files" in res.stdout
    assert "Reclaimable Context Space" in res.stdout


def test_track1_calculator_api_and_cli():
    """Verifies token economics calculation and subprocess JSON export."""
    econ = calculate_token_economics(devs=50, monthly_spend_per_dev=200.0)
    assert econ["developer_headcount"] == 50
    assert econ["total_monthly_spend_usd"] == 10000.0
    assert econ["total_annual_spend_usd"] == 120000.0
    assert econ["monthly_reclaimable_spend_usd"] == 7500.0
    assert econ["annual_reclaimable_spend_usd"] == 90000.0
    assert econ["baseline_context_efficiency_score"] == 0.050
    assert econ["toxic_receipt_index_pct"] == "72.4%"

    # Run CLI
    calc_path = REPO_ROOT / "contextcart-mcp" / "calculator.py"
    res = subprocess.run(
        [sys.executable, str(calc_path), "--devs", "30", "--json"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    cli_data = json.loads(res.stdout)
    assert cli_data["developer_headcount"] == 30
    assert cli_data["total_monthly_spend_usd"] == 6000.0
    assert cli_data["monthly_reclaimable_spend_usd"] == 4500.0


def test_track2_ghost_audit_scanner_token_audit_exports(tmp_path):
    """Verifies ghost_audit_scanner.py emits fix.patch and executive decision pack."""
    patch_out = tmp_path / "fix.patch"
    pack_out = tmp_path / "executive_pack.md"
    scanner_py = REPO_ROOT / "ghost_audit_scanner.py"

    res = subprocess.run(
        [
            sys.executable,
            str(scanner_py),
            "--token-audit",
            "--devs",
            "50",
            "--emit-fix-patch",
            str(patch_out),
            "--export-decision-pack",
            str(pack_out),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert res.returncode == 0
    assert "1-Click Remediation fix.patch written" in res.stdout
    assert "1-Page FinOps Executive Decision Pack written" in res.stdout

    assert patch_out.exists()
    patch_text = patch_out.read_text(encoding="utf-8")
    assert "diff --git a/.mcp.json b/.mcp.json" in patch_text
    assert '"contextcart"' in patch_text

    assert pack_out.exists()
    pack_text = pack_out.read_text(encoding="utf-8")
    assert "Executive Decision Pack" in pack_text
    assert "50 Engineers" in pack_text
    assert "$10,000.00 USD" in pack_text
    assert "72.4%" in pack_text
    assert "0.050" in pack_text


def test_track2_generate_finops_remediation_patch(tmp_path):
    """Verifies tools/generate_finops_remediation_patch.py generates valid diff patch."""
    target_patch = tmp_path / "remediation.patch"
    content = generate_patch(str(target_patch))
    assert target_patch.exists()
    assert "diff --git a/.mcp.json" in content
    assert "diff --git a/.claude/settings.json" in content
    assert '"max_output_tokens": 1500' in content


def test_dual_track_zero_banned_words():
    """Scans all newly created files in Track 1 and Track 2 for banned words."""
    banned_words = [
        "guaran" + "teed",
        "guaran" + "tee",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "proven " + "universally",
        "unhack" + "able",
    ]

    target_files = [
        REPO_ROOT / "contextcart-mcp" / "package.json",
        REPO_ROOT / "contextcart-mcp" / "bin" / "context-governor-mcp.js",
        REPO_ROOT / "contextcart-mcp" / "pyproject.toml",
        REPO_ROOT / "contextcart-mcp" / "__init__.py",
        REPO_ROOT / "contextcart-mcp" / "calculator.py",
        REPO_ROOT / "docs" / "marketing" / "VIRAL_LAUNCH_STOP_FEEDING_40K_TOKEN_DUMPS_INTO_CLAUDE_CODE.md",
        REPO_ROOT / "docs" / "commercial" / "EXECUTIVE_DECISION_PACK_50_DEV_SQUAD.md",
        REPO_ROOT / "tools" / "generate_finops_remediation_patch.py",
        REPO_ROOT / "fix.patch",
    ]

    hits = []
    for tf in target_files:
        if tf.exists():
            txt = tf.read_text(encoding="utf-8", errors="replace")
            for bw in banned_words:
                if re.search(r"\b" + re.escape(bw) + r"\b", txt, re.IGNORECASE):
                    hits.append((str(tf), bw))

    assert not hits, f"Banned words observed in dual-track assets: {hits}"
