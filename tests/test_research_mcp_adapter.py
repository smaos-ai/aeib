import pytest
from src.research_mcp_adapter import ResearchMCPInterceptor, derive_caid

def test_figshare_mcp_action_preparation_and_caid():
    interceptor = ResearchMCPInterceptor()
    payload = {
        "title": "Quantum Decoherence in Living Cells",
        "authors": ["A. Leukhin"],
        "files": ["dataset_v1.tar.gz"],
        "size_bytes": 10485760
    }
    action = interceptor.prepare_mcp_action("figshare_stage_deposit", payload)
    
    assert action["status"] == "PREPARED"
    assert action["noun"] == "FIGSHARE"
    assert action["verb"] == "STAGE_DEPOSIT"
    assert len(action["caid"]) == 64
    # Deterministic invariance test
    caid2 = derive_caid("FIGSHARE", "STAGE_DEPOSIT", payload)
    assert action["caid"] == caid2

def test_mcp_timeout_lockout_and_suppression():
    interceptor = ResearchMCPInterceptor()
    payload = {"query": "synthetic bio-ontologies", "limit": 50}
    action = interceptor.prepare_mcp_action("dimensions_query_literature", payload)
    caid = action["caid"]
    
    assert not interceptor.should_suppress_retry(caid)
    
    # Simulate HTTP 504 Gateway Timeout during dispatch
    rec = interceptor.record_transport_drop(caid, "HTTP_504", "Gateway Timeout after 30s")
    assert rec["state"] == "DISPATCHED_UNCONFIRMED"
    assert interceptor.should_suppress_retry(caid)

def test_mcp_probe_reconciliation_paths():
    interceptor = ResearchMCPInterceptor()
    payload = {"deposit_id": "fig-9921", "checksum": "abc123"}
    action = interceptor.prepare_mcp_action("figshare_commit_deposit", payload)
    caid = action["caid"]
    
    interceptor.record_transport_drop(caid, "TCP_RST", "Connection reset by peer")
    
    # Path 1: Authoritative probe finds the record committed
    disp, ev = interceptor.reconcile_authoritative_probe(caid, {"exists": True, "caid": caid})
    assert disp == "OUTCOME_VERIFIED"
    assert not interceptor.should_suppress_retry(caid)  # Lockout lifted
    
    # Path 2: Unconfirmed drop with probe not found
    action2 = interceptor.prepare_mcp_action("figshare_commit_deposit", {"deposit_id": "fig-9922"})
    caid2 = action2["caid"]
    interceptor.record_transport_drop(caid2, "HTTP_504", "Timeout")
    disp2, ev2 = interceptor.reconcile_authoritative_probe(caid2, {"exists": False})
    assert disp2 == "RECONCILIATION_NOT_FOUND"
    
    # Path 3: Probe timeout (ambiguous probe)
    action3 = interceptor.prepare_mcp_action("figshare_commit_deposit", {"deposit_id": "fig-9923"})
    caid3 = action3["caid"]
    interceptor.record_transport_drop(caid3, "HTTP_504", "Timeout")
    disp3, ev3 = interceptor.reconcile_authoritative_probe(caid3, None)
    assert disp3 == "EFFECT_UNKNOWN"
    assert "Escalate" in ev3["human_action_required"]
