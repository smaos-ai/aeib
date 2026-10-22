# File: tests/test_opencode_codemode_hotreload.py
"""
Verification suite for AT67 (MCP Code Mode Composite Script Taint),
AT68 (Mid-Session Self-Authored Hot-Reload Plugin Block), and
AT69 (Zero-Token System-1 Decision Governance).
"""
from tests.test_opencode_codemode_and_hotreload import (
    test_at67_and_at68_opencode_codemode_and_mid_session_hotreload,
    test_at69_zero_token_system1_decision_and_4d_accountability_binding,
)


def test_at67_at68_at69_codemode_hotreload_and_system1_gates() -> None:
    test_at67_and_at68_opencode_codemode_and_mid_session_hotreload()
    test_at69_zero_token_system1_decision_and_4d_accountability_binding()
