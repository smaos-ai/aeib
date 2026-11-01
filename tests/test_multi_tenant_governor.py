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

from src.multi_tenant_governor import MultiTenantGovernor, TenantProfile


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


def test_defaults_and_release_boundaries():
    # 1. TenantProfile defaults
    prof = TenantProfile("t_def", "org_def")
    assert prof.rate_limit_rpm == 600
    assert prof.burst_capacity == 50
    assert prof.tokens == 50.0
    assert prof.active_in_flight == 0
    assert prof.max_concurrent == 20

    # 2. Default DDL generation table name
    default_ddl = MultiTenantGovernor.generate_postgres_rls_ddl()
    assert "ALTER TABLE settlement_ledger ENABLE ROW LEVEL SECURITY;" in default_ddl

    # 3. Auto-registration on unknown tenant
    gov = MultiTenantGovernor()
    ok, err = gov.acquire_execution_permit("unknown_t")
    assert ok is True
    assert err is None
    assert "unknown_t" in gov._tenants
    registered_prof = gov._tenants["unknown_t"]
    assert registered_prof.org_id == "default_org"
    assert registered_prof.max_concurrent == 20
    assert registered_prof.rate_limit_rpm == 600
    assert registered_prof.active_in_flight == 1

    # Release permit
    gov.release_execution_permit("unknown_t")
    assert registered_prof.active_in_flight == 0

    # Release again at 0 remains 0
    gov.release_execution_permit("unknown_t")
    assert registered_prof.active_in_flight == 0

    # Release on non-existent tenant does not raise error
    gov.release_execution_permit("completely_unregistered_tenant")

    # 4. register_tenant return value and burst_capacity default
    reg_ret = gov.register_tenant("t_ret", "org_ret")
    assert isinstance(reg_ret, TenantProfile)
    assert reg_ret.tenant_id == "t_ret"
    assert reg_ret.burst_capacity == 50

    # 5. Exact decrementation from 2 to 1 in-flight
    gov.register_tenant("t_decr", "org", burst_capacity=10, max_concurrent=5)
    gov.acquire_execution_permit("t_decr")
    gov.acquire_execution_permit("t_decr")
    assert gov._tenants["t_decr"].active_in_flight == 2
    gov.release_execution_permit("t_decr")
    assert gov._tenants["t_decr"].active_in_flight == 1  # Exactly 1, not 0!

    # 6. Token replenishment multiplication test
    import time
    gov.register_tenant("t_refill", "org", rate_limit_rpm=120, burst_capacity=50)  # refill_rate = 2.0/s
    gov._tenants["t_refill"].tokens = 0.0
    gov._tenants["t_refill"].last_leak_timestamp = time.time() - 10.0  # 10s elapsed
    ok_refill, _ = gov.acquire_execution_permit("t_refill")
    assert ok_refill is True
    # 10.0 * 2.0 = 20.0 tokens refilled, minus 1.0 acquired = ~19.0 remaining
    assert 18.0 <= gov._tenants["t_refill"].tokens <= 20.0
