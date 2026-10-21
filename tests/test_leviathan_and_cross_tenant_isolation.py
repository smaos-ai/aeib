"""
tests/test_leviathan_and_cross_tenant_isolation.py
================================================================================
Test suite for AEIB Track D: Leviathan FTS5 Retrieval & Cross-Tenant Blast-Radius.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.context.leviathan_context_engine import LeviathanContextEngine
from src.governance.cross_tenant_sovereign_governor import (
    CrossTenantGovernor,
    SovereignDeploymentSpec,
)


def test_leviathan_fts5_bounded_cards_and_invariant_retention() -> None:
    engine = LeviathanContextEngine(":memory:")

    # Index sample documents across two tenants
    engine.index_document(
        doc_id="doc-t1-001",
        tenant_id="tenant-alpha",
        title="Payment Gate Policy",
        source_uri="file:///docs/payment_gate.md",
        body="All refunds require two-phase commit and an idempotency key bound to CAID.",
    )
    engine.index_document(
        doc_id="doc-t1-002",
        tenant_id="tenant-alpha",
        title="Audit Logging Specification",
        source_uri="file:///docs/audit_spec.md",
        body="Audit records are persisted to SQLite WAL and replicated to cold storage.",
    )
    engine.index_document(
        doc_id="doc-t2-secret",
        tenant_id="tenant-beta",
        title="Tenant Beta Secret Architecture",
        source_uri="file:///beta/architecture.md",
        body="Tenant Beta private API key and proprietary customer model.",
    )

    # 1. Tenant Alpha searches for 'refunds'
    cards_t1 = engine.query_evidence_cards(
        tenant_id="tenant-alpha",
        search_terms="refunds",
        limit=5,
    )
    assert len(cards_t1) >= 1
    assert cards_t1[0].doc_id == "doc-t1-001"
    assert cards_t1[0].token_count_estimate <= 450

    # 2. Cross-tenant leakage check: Tenant Alpha searching for 'secret architecture' finds NOTHING
    leak_cards = engine.query_evidence_cards(
        tenant_id="tenant-alpha",
        search_terms="secret architecture",
        limit=5,
    )
    assert len(leak_cards) == 0

    # 3. Context assembly retains 100% of pinned security invariants
    pinned_invariants = [
        "MANDATORY: Never dispatch payment without prior reservation receipt.",
        "MANDATORY: Consequential actions require explicit CAID warrant.",
    ]
    assembled = engine.assemble_governed_context(
        tenant_id="tenant-alpha",
        search_query="payment",
        pinned_invariants=pinned_invariants,
        max_context_tokens=1000,
    )
    assert assembled["pinned_invariants_count"] == 2
    assert assembled["total_tokens_used"] <= 1000
    assert "payment" in assembled["evidence_cards"][0]["title"].lower() or "audit" in assembled["evidence_cards"][0]["title"].lower()


def test_cross_tenant_governor_seven_isolation_properties() -> None:
    gov = CrossTenantGovernor(":memory:")

    # 1. Record transactions for Tenant A and Tenant B
    gov.record_tenant_act(
        tenant_id="tenant-alpha",
        agent_id="agent-a1",
        capability_id="cap-a1",
        amount_minor=100_00,
        action_type="refund.create",
        current_time=1767225600,
    )
    gov.record_tenant_act(
        tenant_id="tenant-beta",
        agent_id="agent-b1",
        capability_id="cap-b1",
        amount_minor=200_00,
        action_type="wire.dispatch",
        current_time=1767225600,
    )

    # 2. Ledger visibility: Tenant A cannot see Tenant B's ledger entries
    ledger_a = gov.query_tenant_ledger("tenant-alpha")
    assert len(ledger_a) == 1
    assert ledger_a[0]["tenant_id"] == "tenant-alpha"
    assert ledger_a[0]["amount_minor"] == 100_00

    ledger_b = gov.query_tenant_ledger("tenant-beta")
    assert len(ledger_b) == 1
    assert ledger_b[0]["tenant_id"] == "tenant-beta"
    assert ledger_b[0]["amount_minor"] == 200_00

    # 3. Cache isolation: Agent A cache entry not visible to Agent B
    gov.set_cache_entry("tenant-alpha", "agent-a1", "prompt_cache", "Alpha proprietary context")
    cached_val = gov.get_cache_entry("tenant-beta", "agent-b1", "prompt_cache")
    assert cached_val is None

    # 4. Blast-radius containment: Halting Tenant A does NOT disable Tenant B
    gov.trigger_tenant_halt("tenant-alpha", "HONEYPOT_DETECTED")
    assert gov.is_tenant_halted("tenant-alpha") is True
    assert gov.is_tenant_halted("tenant-beta") is False

    # Attempted act by Tenant A fails closed
    res_a_blocked = gov.record_tenant_act(
        tenant_id="tenant-alpha",
        agent_id="agent-a1",
        capability_id="cap-a1",
        amount_minor=50_00,
        action_type="refund.create",
        current_time=1767225610,
    )
    assert res_a_blocked["disposition"] == "REJECTED"
    assert "HALT_TENANT_SPECIFIC_CIRCUIT_BREAKER_ACTIVE" in res_a_blocked["code"]

    # Act by unaffected Tenant B succeeds
    res_b_ok = gov.record_tenant_act(
        tenant_id="tenant-beta",
        agent_id="agent-b1",
        capability_id="cap-b1",
        amount_minor=50_00,
        action_type="wire.dispatch",
        current_time=1767225610,
    )
    assert res_b_ok["disposition"] == "RECORDED"


if __name__ == "__main__":
    test_leviathan_fts5_bounded_cards_and_invariant_retention()
    test_cross_tenant_governor_seven_isolation_properties()
    print("TRACK D LEVIATHAN RETRIEVAL & CROSS-TENANT ISOLATION TESTS PASSED.")
