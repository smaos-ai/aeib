#!/usr/bin/env python3
"""
Unit test suite for STAR / SMAOS Ghost Audit Scanner & Executive Decision Pack.
Validates:
  1. Discovery of un-sandboxed shell execution tools (bash, execve, curl).
  2. Discovery of plaintext API keys and credentials in environment files.
  3. Auditing of missing governance substrate (agentacct.db, pkcs11_hsm_enclave).
  4. Correct mathematical computation of Governance Intensity Index (GII).
  5. Posture classification and Annualized Loss Exposure (ALE) calculation.
  6. Board-ready Executive Decision Pack Markdown export.
"""

import os
import tempfile
import pytest

from ghost_audit_scanner import (
    GhostAuditScanner,
    GhostAuditReport,
    ScanFinding
)


@pytest.fixture
def mock_shadow_ai_env():
    """Creates a mock developer workspace with shadow AI deficits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Un-sandboxed MCP settings file
        mcp_path = os.path.join(tmpdir, "mcp_config.json")
        with open(mcp_path, "w") as f:
            f.write("""{
                "tools": [
                    {"name": "bash_runner", "command": "bash -c", "description": "Executes shell commands"},
                    {"name": "eval_script", "command": "eval", "description": "Runs arbitrary python code"}
                ]
            }""")

        # 2. Exposed API keys in .env
        env_path = os.path.join(tmpdir, ".env")
        with open(env_path, "w") as f:
            f.write("""
                OPENAI_API_KEY=sk-proj-1234567890abcdef1234567890abcdef1234
                GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz1234567890
            """)

        yield tmpdir


def test_shadow_ai_detection(mock_shadow_ai_env):
    scanner = GhostAuditScanner(target_dir=mock_shadow_ai_env)
    report = scanner.scan()

    assert report.total_files_scanned >= 2
    assert len(report.findings) >= 3

    categories = [f.category for f in report.findings]
    assert "TOOL_SANDBOXING" in categories
    assert "CREDENTIAL_EXPOSURE" in categories
    assert "AUDIT_TRACEABILITY" in categories  # No agentacct.db in mock dir

    # GII should be heavily penalized
    assert report.governance_intensity_index < 50.0
    assert report.risk_posture in ["CRITICAL_LIABILITY", "FRAGILE_COMPLIANCE"]
    assert report.estimated_annual_loss_exposure_eur > 0.0


def test_executive_pack_generation(mock_shadow_ai_env):
    scanner = GhostAuditScanner(target_dir=mock_shadow_ai_env)
    report = scanner.scan()

    out_file = os.path.join(mock_shadow_ai_env, "decision_pack.md")
    scanner.export_markdown_report(report, output_path=out_file)

    assert os.path.exists(out_file)
    with open(out_file, "r") as f:
        content = f.read()

    assert "Governance Intensity Index" in content
    assert "Annualized Loss Exposure" in content
    assert "Remediation Roadmap" in content
    assert "TOOL_SANDBOXING" in content


def test_clean_hardened_environment():
    """Validates that a fully hardened directory scores high GII."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create empty dummy files for audit substrate
        with open(os.path.join(tmpdir, "agentacct.db"), "w") as f: f.write("DB")
        with open(os.path.join(tmpdir, "pkcs11_hsm_enclave.py"), "w") as f: f.write("ENCLAVE")

        scanner = GhostAuditScanner(target_dir=tmpdir)
        report = scanner.scan()

        assert report.governance_intensity_index == 100.0
        assert report.risk_posture == "SOVEREIGN_FORTRESS"
        assert len(report.findings) == 0


if __name__ == "__main__":
    print("[*] Running Ghost Audit Scanner unit tests directly...")
    with tempfile.TemporaryDirectory() as tmpdir:
        mcp = os.path.join(tmpdir, "mcp.json")
        with open(mcp, "w") as f: f.write('{"command": "bash"}')
        env = os.path.join(tmpdir, ".env")
        with open(env, "w") as f: f.write('sk-123456789012345678901234567890')
        test_shadow_ai_detection(tmpdir)
        test_executive_pack_generation(tmpdir)
        test_clean_hardened_environment()
    print("✅ All unit tests in test_ghost_audit_scanner.py passed successfully!")
