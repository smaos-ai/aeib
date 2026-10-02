#!/usr/bin/env python3
"""
aeib_postgresql_probe/tests/test_unit_pg_probe.py
Zero-Mock Unit Tests for PostgresProbeAdapter and Canonical Serialization.
"""

import pytest
from aeib_postgresql_probe.adapter import (
    ProbeResult,
    ProbeOutcome,
    project_canonical_json,
)


def test_unit_canonical_json_determinism():
    """Validates deterministic serialization without claiming unexercised RFC 8785 edge cases."""
    rec1 = {"status": "COMMITTED", "intent_id": "abc", "amount": 100.0}
    rec2 = {"amount": 100.0, "status": "COMMITTED", "intent_id": "abc"}
    assert project_canonical_json(rec1) == project_canonical_json(rec2)


def test_unit_probe_outcome_data_structure():
    """Tests ProbeOutcome initialization and attributes."""
    evidence = {"tx_id": "TX-01", "row_hash": "abcdef123456"}
    outcome = ProbeOutcome(ProbeResult.OUTCOME_VERIFIED, evidence=evidence)
    assert outcome.result == ProbeResult.OUTCOME_VERIFIED
    assert outcome.evidence["tx_id"] == "TX-01"
    assert outcome.error_message == ""


def test_unit_probe_result_enum_members():
    """Tests all four probe result dispositions."""
    assert ProbeResult.OUTCOME_VERIFIED.value == "OUTCOME_VERIFIED"
    assert ProbeResult.RECONCILIATION_NOT_FOUND.value == "RECONCILIATION_NOT_FOUND"
    assert ProbeResult.RECONCILIATION_CONFLICT.value == "RECONCILIATION_CONFLICT"
    assert ProbeResult.PROBE_TIMEOUT.value == "PROBE_TIMEOUT"


def test_unit_zero_mock_ast_purity():
    """Structural Gate: Asserts this unit test contains zero mock imports."""
    from pathlib import Path
    import ast
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) if node.module
    }
    banned = {"mock", "unittest.mock"}
    assert not (imported & banned)
