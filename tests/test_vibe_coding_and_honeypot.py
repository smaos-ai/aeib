# File: tests/test_vibe_coding_and_honeypot.py
"""
Verification suite for Vibe Coding Row-Level Security (RLS) AST Enforcement,
GitAI Differential Bisect, and IAPS Honeypot Tripwire Deterrence.
"""
from tests.test_vibe_coding_and_long_horizon_guard import (
    test_gitai_bisect_isolates_breaking_patch,
    test_iaps_agent_honeypot_detection_and_deterrence,
    test_vibe_coding_missing_auth_and_rls_detection,
)


def test_vibe_coding_rls_and_iaps_honeypot_suite() -> None:
    test_vibe_coding_missing_auth_and_rls_detection()
    test_gitai_bisect_isolates_breaking_patch()
    test_iaps_agent_honeypot_detection_and_deterrence()
