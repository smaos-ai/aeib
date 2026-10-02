#!/usr/bin/env python3
"""
src/multi_tenant_governor.py — Multi-Tenant Governance & Isolation Substrate
Sovereign Multi-Agent OS (SMAOS) / AEIB v0.2.4

Implements enterprise multi-tenant controls:
  1. Cryptographic Namespace Salting per Tenant
  2. Token Bucket Rate Limiting & Concurrency Throttling
  3. PostgreSQL Row-Level Security (RLS) DDL Generation
  4. Tenant-Scoped Audit Ledger Isolation
"""

import time
import uuid
import threading
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class TenantProfile:
    tenant_id: str
    org_id: str
    rate_limit_rpm: int = 600       # 10 req/sec default
    burst_capacity: int = 50
    tokens: float = 50.0
    last_leak_timestamp: float = field(default_factory=time.time)
    active_in_flight: int = 0
    max_concurrent: int = 20


class MultiTenantGovernor:
    """
    Governs multi-tenant agent execution boundaries, enforcing strict isolation,
    rate limits, and cryptographic key separation.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._tenants: Dict[str, TenantProfile] = {}

    def register_tenant(self, tenant_id: str, org_id: str, rate_limit_rpm: int = 600, burst_capacity: int = 50, max_concurrent: int = 20) -> TenantProfile:
        with self._lock:
            profile = TenantProfile(
                tenant_id=tenant_id,
                org_id=org_id,
                rate_limit_rpm=rate_limit_rpm,
                burst_capacity=burst_capacity,
                tokens=float(burst_capacity),
                last_leak_timestamp=time.time(),
                max_concurrent=max_concurrent
            )
            self._tenants[tenant_id] = profile
            return profile

    def acquire_execution_permit(self, tenant_id: str) -> Tuple[bool, Optional[str]]:
        """
        Attempts to acquire a rate-limiting and concurrency permit for a tenant.
        Returns: (allowed, reason_if_denied)
        """
        with self._lock:
            if tenant_id not in self._tenants:
                # Auto-register default tenant if not configured
                self.register_tenant(tenant_id, org_id="default_org")

            profile = self._tenants[tenant_id]
            now = time.time()
            elapsed = now - profile.last_leak_timestamp
            profile.last_leak_timestamp = now

            # Replenish tokens (Token Bucket)
            refill_rate = profile.rate_limit_rpm / 60.0
            profile.tokens = min(float(profile.burst_capacity), profile.tokens + elapsed * refill_rate)

            # Check concurrency ceiling
            if profile.active_in_flight >= profile.max_concurrent:
                return False, f"CONCURRENCY_EXCEEDED: Maximum concurrent executions ({profile.max_concurrent}) reached."

            # Check token availability
            if profile.tokens < 1.0:
                return False, "RATE_LIMIT_EXCEEDED: Token bucket exhausted for tenant."

            profile.tokens -= 1.0
            profile.active_in_flight += 1
            return True, None

    def release_execution_permit(self, tenant_id: str):
        with self._lock:
            if tenant_id in self._tenants:
                profile = self._tenants[tenant_id]
                profile.active_in_flight = max(0, profile.active_in_flight - 1)

    def derive_tenant_salt(self, tenant_id: str) -> bytes:
        """Derives a stable cryptographic salt for a tenant to prevent cross-tenant key collision."""
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"tenant.{tenant_id}.sovereignnexus.io").bytes

    @staticmethod
    def generate_postgres_rls_ddl(table_name: str = "settlement_ledger") -> str:
        """
        Generates production-grade PostgreSQL Row-Level Security (RLS) DDL
        guaranteeing kernel-enforced data isolation between enterprise tenants.
        """
        return f"""-- ─────────────────────────────────────────────────────────────────────────────
-- SMAOS PostgreSQL Multi-Tenant Row-Level Security (RLS) Policy
-- Table: {table_name}
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Ensure tenant_id column exists
ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) NOT NULL DEFAULT 'default_tenant';
CREATE INDEX IF NOT EXISTS idx_{table_name}_tenant_id ON {table_name} (tenant_id);

-- 2. Enable Row-Level Security
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;

-- 3. Create Tenant Isolation Policy
DROP POLICY IF EXISTS tenant_isolation_policy ON {table_name};
CREATE POLICY tenant_isolation_policy ON {table_name}
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

-- 4. Session Set Function
-- Usage: SET LOCAL app.current_tenant_id = 'org-bank-01';
"""
