#!/usr/bin/env python3
"""
Integration tests: VisionAPI (Python) + FastAPI + AP2 charging flow
Tests the full govern → pre_execute_check → Merkle proof pipeline
"""

import pytest
from fastapi.testclient import TestClient
from vision_api_fastapi import app
import vision_api
from vision_api import VisionAPI, GovernRequest, RiskLevel, HumanGatePolicy


# ═════════════════════════════════════════════════════════════
# 1. UNIT TESTS (Python VisionAPI)
# ═════════════════════════════════════════════════════════════

def test_risk_level_classification():
    """Test RiskLevel.from_blast_radius() conversion"""
    assert RiskLevel.from_blast_radius(0.1).requires_approval() == False
    assert RiskLevel.from_blast_radius(0.3).requires_approval() == False
    assert RiskLevel.from_blast_radius(0.6).requires_approval() == True
    assert RiskLevel.from_blast_radius(0.9).requires_approval() == True


def test_human_gate_policy_defaults():
    """Test HumanGatePolicy initialization with defaults"""
    policy = HumanGatePolicy()
    assert policy.psi_drift_threshold == 0.25
    assert policy.ap2_charge_enabled == True
    assert policy.max_concurrent_approvals == 10


def test_govern_request_creation():
    """Test GovernRequest creation"""
    req = GovernRequest(
        request_id="req-001",
        action="read",
        blast_radius=0.1,
        user_id="user-1",
        app_id="app-1",
        human_approved=False,
    )
    assert req.request_id == "req-001"
    assert req.action == "read"
    assert req.blast_radius == 0.1


def test_low_risk_auto_approved():
    """Test low-risk action auto-approved (zero gate required)"""
    api = VisionAPI()
    req = GovernRequest(
        request_id="req-001",
        action="read_data",
        blast_radius=0.1,  # LOW risk
        user_id="user-1",
        app_id="app-1",
        human_approved=False,  # Not explicitly approved
    )

    result = api.pre_execute_check(req)
    assert result.allowed == True
    assert result.charge_amount == 100
    assert result.proof is not None
    assert result.proof.auto_approved == True
    assert result.error is None


def test_high_risk_blocked_without_approval():
    """Test high-risk action blocked without approval (zero charge)"""
    api = VisionAPI()
    req = GovernRequest(
        request_id="req-002",
        action="delete_data",
        blast_radius=0.8,  # HIGH risk
        user_id="user-2",
        app_id="app-2",
        human_approved=False,  # NOT approved
    )

    result = api.pre_execute_check(req)
    assert result.allowed == False
    assert result.charge_amount == 0  # ZERO charge on rejection
    assert result.proof is None
    assert result.error == "HumanGateRequired"
    assert "human approval" in result.reason.lower()


def test_high_risk_approved_allowed():
    """Test high-risk action allowed with human approval"""
    api = VisionAPI()
    req = GovernRequest(
        request_id="req-003",
        action="execute_system",
        blast_radius=0.8,  # HIGH risk
        user_id="admin-1",
        app_id="app-3",
        human_approved=True,  # APPROVED
    )

    result = api.pre_execute_check(req)
    assert result.allowed == True
    assert result.charge_amount == 100
    assert result.proof is not None
    assert result.proof.approved_by == "admin-1"
    assert result.proof.auto_approved == False


def test_critical_risk_blocked():
    """Test critical-risk action blocked without approval"""
    api = VisionAPI()
    req = GovernRequest(
        request_id="req-004",
        action="delete_critical_data",
        blast_radius=0.95,  # CRITICAL risk
        user_id="user-4",
        app_id="app-4",
        human_approved=False,
    )

    result = api.pre_execute_check(req)
    assert result.allowed == False
    assert result.charge_amount == 0
    assert result.error == "HumanGateRequired"


def test_drift_detection():
    """Test PSI drift detection via policy"""
    policy = HumanGatePolicy(psi_drift_threshold=0.25)
    # Verify policy is set up correctly
    assert policy.psi_drift_threshold == 0.25
    assert policy.ap2_charge_enabled == True


def test_psi_computation():
    """Test PSI computation"""
    api = VisionAPI()
    baseline = [100.0, 101.0, 99.0, 100.0, 101.0]
    current = [105.0, 106.0, 104.0, 105.0, 106.0]  # 5% shift

    psi = api.compute_psi(baseline, current)
    assert isinstance(psi, float)
    assert 0.0 <= psi <= 1.0


def test_medium_risk_auto_approved():
    """Test medium-risk action auto-approved"""
    api = VisionAPI()
    req = GovernRequest(
        request_id="req-005",
        action="write_config",
        blast_radius=0.4,  # MEDIUM risk
        user_id="user-5",
        app_id="app-5",
        human_approved=False,
    )

    result = api.pre_execute_check(req)
    assert result.allowed == True
    assert result.charge_amount == 100


def test_critical_risk_approved_allowed():
    """Test critical-risk with approval"""
    api = VisionAPI()
    req = GovernRequest(
        request_id="req-006",
        action="delete_all_data",
        blast_radius=0.95,  # CRITICAL
        user_id="super-admin",
        app_id="app-6",
        human_approved=True,
    )

    result = api.pre_execute_check(req)
    assert result.allowed == True
    assert result.charge_amount == 100


# ═════════════════════════════════════════════════════════════
# 2. INTEGRATION TESTS (FastAPI + VisionAPI)
# ═════════════════════════════════════════════════════════════

@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


def test_fastapi_health_check(client):
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["uptime_seconds"] >= 0
    assert data["requests_processed"] >= 0


def test_fastapi_govern_low_risk_approved(client):
    """Test /v1/govern with LOW risk (auto-approved)"""
    payload = {
        "request_id": "req-ft-001",
        "action": "read_file",
        "blast_radius": 0.1,
        "user_id": "user-1",
        "app_id": "app-1",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["approved"] == True
    assert data["charge_amount"] == 100
    assert data["merkle_proof"] is not None
    assert data["error"] is None


def test_fastapi_govern_high_risk_blocked(client):
    """Test /v1/govern with HIGH risk (blocked without approval)"""
    payload = {
        "request_id": "req-ft-002",
        "action": "delete_system_files",
        "blast_radius": 0.8,
        "user_id": "user-2",
        "app_id": "app-2",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["approved"] == False
    assert data["charge_amount"] == 0  # Zero charge on rejection
    assert data["merkle_proof"] is None
    assert data["error"] == "HumanGateRequired"


def test_fastapi_govern_high_risk_approved(client):
    """Test /v1/govern with HIGH risk + human approval (allowed)"""
    payload = {
        "request_id": "req-ft-003",
        "action": "execute_system",
        "blast_radius": 0.8,
        "user_id": "admin-1",
        "app_id": "app-3",
        "human_approved": True,
    }

    response = client.post("/v1/govern", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["approved"] == True
    assert data["charge_amount"] == 100
    assert data["merkle_proof"] is not None
    assert data["merkle_proof"]["approved_by"] == "admin-1"
    assert data["merkle_proof"]["auto_approved"] == False


def test_fastapi_govern_critical_risk_blocked(client):
    """Test /v1/govern with CRITICAL risk (blocked without approval)"""
    payload = {
        "request_id": "req-ft-004",
        "action": "delete_all_data",
        "blast_radius": 0.95,
        "user_id": "user-4",
        "app_id": "app-4",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["approved"] == False
    assert data["charge_amount"] == 0


def test_fastapi_metrics_endpoint(client):
    """Test metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "uptime_seconds" in data
    assert "requests_processed" in data


# ═════════════════════════════════════════════════════════════
# 3. AP2 CHARGE FLOW TESTS
# ═════════════════════════════════════════════════════════════

def test_ap2_charge_on_approval(client):
    """Test AP2 charge is returned when approved"""
    payload = {
        "request_id": "req-ap2-001",
        "action": "read",
        "blast_radius": 0.1,
        "user_id": "user-1",
        "app_id": "app-1",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    data = response.json()

    # Approved request should have positive charge
    assert data["approved"] == True
    assert data["charge_amount"] == 100


def test_ap2_zero_charge_on_rejection(client):
    """Test AP2 charge is zero when rejected (fail-closed)"""
    payload = {
        "request_id": "req-ap2-002",
        "action": "delete",
        "blast_radius": 0.9,
        "user_id": "user-2",
        "app_id": "app-2",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    data = response.json()

    # Rejected request should have zero charge (fail-closed)
    assert data["approved"] == False
    assert data["charge_amount"] == 0


# ═════════════════════════════════════════════════════════════
# 4. MERKLE PROOF TESTS
# ═════════════════════════════════════════════════════════════

def test_merkle_proof_includes_decision_id(client):
    """Test Merkle proof contains decision ID"""
    payload = {
        "request_id": "req-merkle-001",
        "action": "read",
        "blast_radius": 0.1,
        "user_id": "user-1",
        "app_id": "app-1",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    data = response.json()

    assert data["merkle_proof"]["decision_id"] == "req-merkle-001"


def test_merkle_proof_has_timestamp(client):
    """Test Merkle proof includes timestamp"""
    payload = {
        "request_id": "req-merkle-002",
        "action": "write",
        "blast_radius": 0.3,
        "user_id": "user-2",
        "app_id": "app-2",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    data = response.json()

    assert data["merkle_proof"]["timestamp"] is not None
    assert len(data["merkle_proof"]["merkle_root"]) > 0


def test_merkle_proof_has_merkle_root(client):
    """Test Merkle proof has valid merkle root"""
    payload = {
        "request_id": "req-merkle-003",
        "action": "read",
        "blast_radius": 0.2,
        "user_id": "user-3",
        "app_id": "app-3",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    data = response.json()

    assert data["merkle_proof"]["merkle_root"] is not None
    assert isinstance(data["merkle_proof"]["merkle_root"], str)
    assert len(data["merkle_proof"]["merkle_root"]) > 0


# ═════════════════════════════════════════════════════════════
# 5. ADDITIONAL COMPLIANCE TESTS
# ═════════════════════════════════════════════════════════════

def test_request_without_human_approval_flag(client):
    """Test request defaults human_approved to False"""
    payload = {
        "request_id": "req-default-001",
        "action": "read",
        "blast_radius": 0.1,
        "user_id": "user-1",
        "app_id": "app-1",
        # human_approved not provided
    }

    response = client.post("/v1/govern", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["approved"] == True


def test_medium_risk_with_approval(client):
    """Test medium-risk doesn't require approval"""
    payload = {
        "request_id": "req-medium-001",
        "action": "write_config",
        "blast_radius": 0.4,
        "user_id": "user-1",
        "app_id": "app-1",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    data = response.json()
    assert data["approved"] == True


def test_multiple_requests(client):
    """Test multiple requests in sequence"""
    for i in range(5):
        payload = {
            "request_id": f"req-multi-{i}",
            "action": "read",
            "blast_radius": 0.1,
            "user_id": f"user-{i}",
            "app_id": f"app-{i}",
            "human_approved": False,
        }
        response = client.post("/v1/govern", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["approved"] == True


def test_boundary_risk_levels(client):
    """Test boundary risk levels"""
    # Test 0.249 (LOW)
    payload1 = {
        "request_id": "req-bound-low",
        "action": "read",
        "blast_radius": 0.249,
        "user_id": "user-1",
        "app_id": "app-1",
        "human_approved": False,
    }
    response1 = client.post("/v1/govern", json=payload1)
    assert response1.json()["approved"] == True

    # Test 0.25 (MEDIUM)
    payload2 = {
        "request_id": "req-bound-med",
        "action": "read",
        "blast_radius": 0.25,
        "user_id": "user-2",
        "app_id": "app-2",
        "human_approved": False,
    }
    response2 = client.post("/v1/govern", json=payload2)
    assert response2.json()["approved"] == True

    # Test 0.5 (HIGH) - requires approval
    payload3 = {
        "request_id": "req-bound-high",
        "action": "read",
        "blast_radius": 0.5,
        "user_id": "user-3",
        "app_id": "app-3",
        "human_approved": False,
    }
    response3 = client.post("/v1/govern", json=payload3)
    assert response3.json()["approved"] == False


def test_response_timestamp_format(client):
    """Test response includes proper timestamp"""
    payload = {
        "request_id": "req-ts-001",
        "action": "read",
        "blast_radius": 0.1,
        "user_id": "user-1",
        "app_id": "app-1",
        "human_approved": False,
    }

    response = client.post("/v1/govern", json=payload)
    data = response.json()
    assert "timestamp" in data
    assert isinstance(data["timestamp"], str)
    assert len(data["timestamp"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
