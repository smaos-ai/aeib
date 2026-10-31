#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
tests/test_sovereign_dashboard_api.py
================================================================================
Verification suite for `src/sovereign_dashboard_api.py`.
Ensures:
  1. GET / returns valid HTML dashboard and handles missing file fallback.
  2. GET /epistemic-dashboard returns HTML and handles missing file fallback.
  3. GET /api/status returns INTERNAL_PREVIEW_COMMISSIONED with all metadata.
  4. GET /api/mutation-status returns kill ratio, secondary fallback, and missing report.
  5. GET /api/benchmark-results returns valid receipt body and handles missing file.
  6. GET /api/simulation-vectors returns 4-vector data and handles missing file.
  7. GET /api/regulatory-evidence returns DORA Art. 17 data and handles missing file.
  8. GET /api/policy-interception returns real suites, missing cases, and load errors.
  9. GET /api/receipt-replay returns validated ledger, missing ledger, and load errors.
  10. CLI main handles --check-only and full uvicorn execution.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

import src.sovereign_dashboard_api as api_mod
from src.sovereign_dashboard_api import create_app, main


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_1_get_dashboard_html_nominal_and_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SOVEREIGNNEXUS // EPISTEMIC HYGIENE DASHBOARD" in resp.text
    assert "The Surviving Mutant Post-Mortem" in resp.text
    assert "STATUS: INTERNAL PREVIEW COMMISSIONED" in resp.text

    # Missing file branch
    monkeypatch.setattr(api_mod, "_REPO_ROOT", tmp_path)
    fallback_client = TestClient(api_mod.create_app())
    resp_missing = fallback_client.get("/")
    assert resp_missing.status_code == 200
    assert resp_missing.text == "<h1>ERR_DASHBOARD_HTML_NOT_FOUND</h1>"


def test_2_get_epistemic_dashboard_html_nominal_and_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resp = client.get("/epistemic-dashboard")
    assert resp.status_code == 200
    assert "DOCTYPE html" in resp.text or "html" in resp.text
    assert len(resp.text) > 50

    # Missing file branch
    monkeypatch.setattr(api_mod, "_REPO_ROOT", tmp_path)
    fallback_client = TestClient(api_mod.create_app())
    resp_missing = fallback_client.get("/epistemic-dashboard")
    assert resp_missing.status_code == 200
    assert resp_missing.text == "<h1>ERR_EPISTEMIC_DASHBOARD_HTML_NOT_FOUND</h1>"


def test_3_get_api_status(client: TestClient) -> None:
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "INTERNAL_PREVIEW_COMMISSIONED"
    assert data["version"] == "v1.1.0-preview"
    assert data["platform"] == "Darwin Apple Silicon"
    assert "Evaluated under the stated model" in data["epistemic_scope"]
    assert data["banned_words_enforced"] is True
    assert data["zero_mock_ast_pure"] is True
    assert data["rfc8785_jcs_canonical"] is True


def test_4_get_api_mutation_status(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 1. Nominal from on-disk report
    resp = client.get("/api/mutation-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert 9999 < int(data["kill_ratio_bps"]) < 10001
    assert 29 < int(data["mutants_sampled"]) < 31
    assert 29 < int(data["killed"]) < 31
    assert int(data["survived"]) == 0
    assert float(data["elapsed_total_s"]) >= 0.0
    assert data["baseline_suite_passed"] is True
    assert "historical_survivor_postmortem" in data
    assert 315 < int(data["historical_survivor_postmortem"]["line"]) < 317
    assert data["historical_survivor_postmortem"]["operator"] == "CONST_PERTURB"
    assert "remediation" in data["historical_survivor_postmortem"]

    # 2. Secondary fallback path from mutants.json (omits optional keys to test default args)
    mock_epistemic_data = tmp_path / "epistemic-dashboard" / "data"
    mock_epistemic_data.mkdir(parents=True, exist_ok=True)
    mutants_json = mock_epistemic_data / "mutants.json"
    mutants_json.write_text(
        json.dumps({
            "target_file": "src/sample_module.py",
            "kill_ratio": 0.95,
            "mutants_sampled": 20,
            "killed": 20,
            "elapsed_total_s": 4.5,
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(api_mod, "_REPO_ROOT", tmp_path)
    client_secondary = TestClient(api_mod.create_app())
    resp_secondary = client_secondary.get("/api/mutation-status")
    assert resp_secondary.status_code == 200
    data_sec = resp_secondary.json()
    assert data_sec["status"] == "SUCCESS"
    assert 9499 < int(data_sec["kill_ratio_bps"]) < 9501
    assert 19 < int(data_sec["mutants_sampled"]) < 21
    assert 19 < int(data_sec["killed"]) < 21
    assert int(data_sec["survived"]) == 0
    assert data_sec["baseline_suite_passed"] is True

    # 3. Missing file completely -> NO_REPORT_ON_DISK fallback
    mutants_json.unlink()
    resp_none = client_secondary.get("/api/mutation-status")
    assert resp_none.status_code == 200
    data_none = resp_none.json()
    assert data_none["status"] == "NO_REPORT_ON_DISK"
    assert 9999 < int(data_none["kill_ratio_bps"]) < 10001
    assert 29 < int(data_none["mutants_sampled"]) < 31
    assert 29 < int(data_none["killed"]) < 31
    assert int(data_none["survived"]) == 0


def test_5_get_api_benchmark_results(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resp = client.get("/api/benchmark-results")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["receipt_caid"].startswith("sha256:")
    assert "metrics_bps" in data["receipt_body"]

    # Missing file branch
    monkeypatch.setattr(api_mod, "_REPO_ROOT", tmp_path)
    client_missing = TestClient(api_mod.create_app())
    resp_missing = client_missing.get("/api/benchmark-results")
    assert resp_missing.status_code == 200
    data_missing = resp_missing.json()
    assert data_missing["status"] == "NO_RECEIPT_FOUND"
    assert data_missing["receipt_body"] == {}


def test_6_get_api_simulation_vectors(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resp = client.get("/api/simulation-vectors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["simulation_caid"].startswith("sha256:")
    assert isinstance(data["vectors"], dict)

    # Missing file branch
    monkeypatch.setattr(api_mod, "_REPO_ROOT", tmp_path)
    client_missing = TestClient(api_mod.create_app())
    resp_missing = client_missing.get("/api/simulation-vectors")
    assert resp_missing.status_code == 200
    data_missing = resp_missing.json()
    assert data_missing["status"] == "NO_SIMULATION_RECEIPT_FOUND"
    assert data_missing["vectors"] == {}


def test_7_get_api_regulatory_evidence(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    resp = client.get("/api/regulatory-evidence")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["dossier_caid"].startswith("sha256:")
    assert data["dora_art17_status"] == "COMPLIANT_CONTAINED"
    assert data["eu_ai_act_art14_status"] == "COMPLIANT_HUMAN_OVERSIGHT_PINNED"

    # Missing file branch
    monkeypatch.setattr(api_mod, "_REPO_ROOT", tmp_path)
    client_missing = TestClient(api_mod.create_app())
    resp_missing = client_missing.get("/api/regulatory-evidence")
    assert resp_missing.status_code == 200
    data_missing = resp_missing.json()
    assert data_missing["status"] == "NO_DOSSIER_FOUND"
    assert data_missing["dossier"] == {}


def test_8_get_api_policy_interception(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 1. Nominal
    resp = client.get("/api/policy-interception")
    assert resp.status_code == 200
    data = resp.json()
    assert "receipt_caid" in data
    assert data["receipt_caid"].startswith("sha256:")
    assert data["receipt_body"]["suite_name"] == "EO1-Policy-Interception-Suite-v1"
    assert 29 < int(data["receipt_body"]["metrics_bps"]["total_cases"]) < 31

    # 2. Missing cases file
    monkeypatch.setattr(api_mod, "_REPO_ROOT", tmp_path)
    client_missing = TestClient(api_mod.create_app())
    resp_missing = client_missing.get("/api/policy-interception")
    assert resp_missing.status_code == 200
    assert resp_missing.json()["status"] == "NO_CASES_FOUND"

    # 3. Spec load failure
    cases_dir = tmp_path / "epistemic-dashboard" / "data"
    cases_dir.mkdir(parents=True, exist_ok=True)
    (cases_dir / "policy_cases.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *a, **k: None)
    resp_err = client_missing.get("/api/policy-interception")
    assert resp_err.status_code == 200
    assert resp_err.json()["status"] == "ERR_LOAD_FAILED"


def test_9_get_api_receipt_replay(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 1. Nominal
    resp = client.get("/api/receipt-replay")
    assert resp.status_code == 200
    data = resp.json()
    assert 4 < int(data["total_receipts"]) < 6
    assert 4 < int(data["valid_caids"]) < 6
    assert 9999 < int(data["caid_validity_bps"]) < 10001
    assert 9999 < int(data["signature_validity_bps"]) < 10001

    # 2. Missing ledger file
    monkeypatch.setattr(api_mod, "_REPO_ROOT", tmp_path)
    client_missing = TestClient(api_mod.create_app())
    resp_missing = client_missing.get("/api/receipt-replay")
    assert resp_missing.status_code == 200
    assert resp_missing.json()["status"] == "NO_RECEIPTS_FOUND"

    # 3. Spec load failure
    ledger_dir = tmp_path / "epistemic-dashboard" / "data"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    (ledger_dir / "receipts.jsonl").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *a, **k: None)
    resp_err = client_missing.get("/api/receipt-replay")
    assert resp_err.status_code == 200
    assert resp_err.json()["status"] == "ERR_LOAD_FAILED"


def test_10_cli_check_only_and_run(monkeypatch: pytest.MonkeyPatch) -> None:
    # Check-only nominal
    exit_code = main(["--check-only"])
    assert exit_code == 0

    # Full execution with mocked uvicorn runner
    import uvicorn
    calls: List[Dict[str, Any]] = []

    def fake_run(app_path: str, host: str, port: int, reload: bool) -> None:
        calls.append({"app": app_path, "host": host, "port": port, "reload": reload})

    monkeypatch.setattr(uvicorn, "run", fake_run)
    run_exit = main(["--host", "127.0.0.1", "--port", "8888"])
    assert run_exit == 0
    assert len(calls) == 1
    call = calls[0]
    assert call["app"] == "src.sovereign_dashboard_api:app"
    assert call["host"] == "127.0.0.1"
    assert 8887 < int(call["port"]) < 8889
    assert call["reload"] is False
