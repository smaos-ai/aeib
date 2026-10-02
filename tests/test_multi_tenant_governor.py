#!/usr/bin/env python3
"""
tests/test_multi_tenant_governor.py — Zero-Mock Test Suite for Multi-Tenant Governor
Validates:
  1. Token bucket rate limiting per tenant.
  2. In-flight concurrency limits.
  3. Cryptographic salt derivation uniqueness.
  4. PostgreSQL Row-Level Security (RLS) DDL generation.
  5. Zero-mock AST purity.
"""

import ast
import sys
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.multi_tenant_governor import MultiTenantGovernor


def test_tenant_rate_limiting_and_refill():
    """Tests token bucket rate limiting per tenant."""
    gov = MultiTenantGovernor()
    gov.register_tenant("tenant_alpha", org_id="org_1", rate_limit_rpm=60, burst_capacity=3, max_concurrent=10)

    # First 3 should succeed immediately (within burst capacity)
    ok1, reason1 = gov.acquire_execution_permit("tenant_alpha")
    ok2, reason2 = gov.acquire_execution_permit("tenant_alpha")
    ok3, reason3 = gov.acquire_execution_permit("tenant_alpha")

    assert ok1 is True and reason1 is None
    assert ok2 is True and reason2 is None
    assert ok3 is True and reason3 is None

    # 4th immediately should fail (burst exhausted)
    ok4, reason4 = gov.acquire_execution_permit("tenant_alpha")
    assert ok4 is False
    assert "RATE_LIMIT_EXCEEDED" in reason4


def test_concurrency_ceiling():
    """Tests maximum active in-flight execution limits."""
    gov = MultiTenantGovernor()
    gov.register_tenant("tenant_beta", org_id="org_2", rate_limit_rpm=6000, burst_capacity=100, max_concurrent=2)

    ok1, _ = gov.acquire_execution_permit("tenant_beta")
    ok2, _ = gov.acquire_execution_permit("tenant_beta")
    assert ok1 is True and ok2 is True

    # 3rd should be rejected due to concurrency limit
    ok3, reason3 = gov.acquire_execution_permit("tenant_beta")
    assert ok3 is False
    assert "CONCURRENCY_EXCEEDED" in reason3

    # Release one permit and try again
    gov.release_execution_permit("tenant_beta")
    ok4, reason4 = gov.acquire_execution_permit("tenant_beta")
    assert ok4 is True
    assert reason4 is None


def test_tenant_cryptographic_salt_uniqueness():
    """Verifies that each tenant gets a unique, deterministic cryptographic salt."""
    gov = MultiTenantGovernor()
    salt_a = gov.derive_tenant_salt("bank_tenant_a")
    salt_a_again = gov.derive_tenant_salt("bank_tenant_a")
    salt_b = gov.derive_tenant_salt("bank_tenant_b")

    assert salt_a == salt_a_again
    assert salt_a != salt_b
    assert len(salt_a) == 16


def test_postgres_rls_ddl_generation():
    """Tests generation of valid PostgreSQL Row-Level Security DDL."""
    gov = MultiTenantGovernor()
    ddl = gov.generate_postgres_rls_ddl("custom_ledger")

    assert "ALTER TABLE custom_ledger ENABLE ROW LEVEL SECURITY;" in ddl
    assert "CREATE POLICY tenant_isolation_policy ON custom_ledger" in ddl
    assert "current_setting('app.current_tenant_id', true)" in ddl


def test_zero_mock_ast_purity():
    """Structural Gate: Asserts this test file contains zero mock imports."""
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) if node.module
    }
    banned = {"mock", "unittest.mock"}
    assert not (imported & banned)
