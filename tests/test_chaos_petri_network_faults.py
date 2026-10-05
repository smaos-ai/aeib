"""
AEIB Network Fault & Chaos Petri Testbed (Zone 1 Prototype)
Evaluates edge failure conditions: post-commit 504 drops, pre-commit socket resets,
replica lag split-brain, cascading probe timeouts, and signature corruption.
"""

import pytest
import hashlib
import json
from src.research_mcp_adapter import ResearchMCPInterceptor, derive_caid

def test_scenario_1_post_commit_504_drop():
    """Server committed write, but response dropped mid-flight with HTTP 504."""
    interceptor = ResearchMCPInterceptor()
    payload = {"dataset_id": "ds-881", "action": "publish"}
    action = interceptor.prepare_mcp_action("figshare_publish", payload)
    caid = action["caid"]

    # 1. Transport fails with 504
    interceptor.record_transport_drop(caid, "HTTP_504", "Gateway Timeout")
    assert interceptor.should_suppress_retry(caid)

    # 2. Probe queries authoritative DB and finds the record
    probe_response = {"exists": True, "caid": caid, "committed_at": "2026-10-05T05:00:00Z"}
    disposition, evidence = interceptor.reconcile_authoritative_probe(caid, probe_response)
    
    assert disposition == "OUTCOME_VERIFIED"
    assert not interceptor.should_suppress_retry(caid)  # Lockout resolved safely

def test_scenario_2_pre_commit_tcp_reset():
    """Socket drops before DB transaction commits."""
    interceptor = ResearchMCPInterceptor()
    payload = {"dataset_id": "ds-882", "action": "publish"}
    action = interceptor.prepare_mcp_action("figshare_publish", payload)
    caid = action["caid"]

    # 1. Transport fails with TCP RST
    interceptor.record_transport_drop(caid, "TCP_RST", "Connection reset by peer")
    assert interceptor.should_suppress_retry(caid)

    # 2. Probe queries authoritative DB and finds NO record
    probe_response = {"exists": False}
    disposition, evidence = interceptor.reconcile_authoritative_probe(caid, probe_response)
    
    assert disposition == "RECONCILIATION_NOT_FOUND"
    assert "Authorize clean recovery" in evidence["human_action_required"]

def test_scenario_3_replica_lag_probe_escalation():
    """Probe hits a lagging replica that returns null/ambiguous state."""
    interceptor = ResearchMCPInterceptor()
    payload = {"dataset_id": "ds-883", "action": "publish"}
    action = interceptor.prepare_mcp_action("figshare_publish", payload)
    caid = action["caid"]

    interceptor.record_transport_drop(caid, "HTTP_504", "Gateway Timeout")
    
    # Replica returns None / timeout
    disposition, evidence = interceptor.reconcile_authoritative_probe(caid, None)
    
    assert disposition == "EFFECT_UNKNOWN"
    assert "Escalate" in evidence["human_action_required"]
    assert interceptor.should_suppress_retry(caid)  # Stays locked down

def test_scenario_4_conflicting_authority_mismatch():
    """Probe returns a record with a mismatched CAID (data corruption / collision)."""
    interceptor = ResearchMCPInterceptor()
    payload = {"dataset_id": "ds-884", "action": "publish"}
    action = interceptor.prepare_mcp_action("figshare_publish", payload)
    caid = action["caid"]

    interceptor.record_transport_drop(caid, "HTTP_504", "Gateway Timeout")
    
    # Probe returns corrupted CAID
    probe_response = {"exists": True, "caid": "different_corrupted_caid_9999"}
    disposition, evidence = interceptor.reconcile_authoritative_probe(caid, probe_response)
    
    assert disposition == "EFFECT_UNKNOWN"
    assert "Escalate" in evidence["human_action_required"]
