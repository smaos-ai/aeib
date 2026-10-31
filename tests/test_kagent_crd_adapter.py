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
tests/test_kagent_crd_adapter.py
================================================================================
Test suite for kagent Declarative Kubernetes CRD Adapter & AEIB Policy Validator.
Zero mocks, zero floats, deterministic validation.
"""

from __future__ import annotations

import pytest

from src.kagent_crd_adapter import CRDValidationResult, KagentCRDValidator


def _build_valid_manifest() -> dict:
    return {
        "apiVersion": "kagent.dev/v1alpha1",
        "kind": "Harness",
        "metadata": {
            "name": "sovereign-production-harness",
            "namespace": "sovereign-system",
        },
        "spec": {
            "runtime": {
                "sandboxClass": "gvisor",
            },
            "security": {
                "spiffeId": "spiffe://sovereign.nexus/ns/prod/actor/harness-lead-01",
            },
            "network": {
                "egressMode": "default-deny",
                "agentgatewayRef": "agentgateway-egress.sovereign-system.svc.cluster.local:443",
            },
            "env": [
                {"name": "STRIPE_API_KEY", "value": "{{VAULT:STRIPE_KEY}}"},
                {"name": "APP_ENV", "value": "production"},
            ],
            "lifecycle": {
                "eo1IntentLatch": True,
                "autopausePersistence": "sqlite-wal",
            },
            "governance": {
                "maxDriftThresholdBps": 3000,
                "maxBlastRadiusBps": 2500,
            },
        },
    }


def test_1_valid_kagent_crd_manifest_passes() -> None:
    validator = KagentCRDValidator()
    manifest = _build_valid_manifest()
    result = validator.validate_manifest(manifest)
    assert result.is_valid is True
    assert len(result.violations) == 0
    assert result.crd_kind == "Harness"
    assert result.metadata_name == "sovereign-production-harness"
    assert result.runtime_sandbox == "gvisor"
    assert result.spiffe_id == "spiffe://sovereign.nexus/ns/prod/actor/harness-lead-01"
    assert result.egress_enforced is True
    assert result.vault_blinded is True
    assert result.eo1_latch_enabled is True
    assert result.max_drift_bps == 3000  # claim: config

    d = result.to_dict()
    assert d["is_valid"] is True
    assert d["violations"] == []
    assert d["crd_kind"] == "Harness"
    assert d["metadata_name"] == "sovereign-production-harness"


def test_2_insecure_runtime_sandbox_is_rejected() -> None:
    validator = KagentCRDValidator()
    manifest = _build_valid_manifest()
    manifest["spec"]["runtime"]["sandboxClass"] = "docker-runc"
    result = validator.validate_manifest(manifest)
    assert result.is_valid is False
    assert any("REJECTED_INSECURE_RUNTIME_SANDBOX" in v for v in result.violations)

    # Missing runtime
    del manifest["spec"]["runtime"]["sandboxClass"]
    result_missing = validator.validate_manifest(manifest)
    assert result_missing.is_valid is False
    assert any("REJECTED_MISSING_RUNTIME_SANDBOX" in v for v in result_missing.violations)


def test_3_permitted_runtimes_all_accepted() -> None:
    validator = KagentCRDValidator()
    for rt in ("runsc", "cloud-hypervisor", "microvm", "kata"):
        manifest = _build_valid_manifest()
        manifest["spec"]["runtime"]["sandboxClass"] = rt
        res = validator.validate_manifest(manifest)
        assert res.is_valid is True, f"Runtime {rt} should be valid"
        assert res.runtime_sandbox == rt


def test_4_crd_kinds_variants_and_rejections() -> None:
    validator = KagentCRDValidator()
    for kind in ("AgentTemplate", "SandboxAgent"):
        manifest = _build_valid_manifest()
        manifest["kind"] = kind
        res = validator.validate_manifest(manifest)
        assert res.is_valid is True
        assert res.crd_kind == kind

    # Unknown kind
    manifest_bad = _build_valid_manifest()
    manifest_bad["kind"] = "Deployment"
    res_bad = validator.validate_manifest(manifest_bad)
    assert res_bad.is_valid is False
    assert any("REJECTED_UNKNOWN_CRD_KIND" in v for v in res_bad.violations)


def test_5_invalid_spiffe_identity_is_rejected() -> None:
    validator = KagentCRDValidator()
    manifest = _build_valid_manifest()
    manifest["spec"]["security"]["spiffeId"] = "invalid_not_a_spiffe_uri"
    result = validator.validate_manifest(manifest)
    assert result.is_valid is False
    assert any("REJECTED_INVALID_SPIFFE_FORMAT" in v for v in result.violations)

    # Missing SPIFFE
    manifest["spec"]["security"]["spiffeId"] = ""
    result_missing = validator.validate_manifest(manifest)
    assert result_missing.is_valid is False
    assert any("REJECTED_MISSING_SPIFFE_IDENTITY" in v for v in result_missing.violations)


def test_6_unlocked_egress_traffic_is_rejected() -> None:
    validator = KagentCRDValidator()
    manifest = _build_valid_manifest()
    manifest["spec"]["network"]["egressMode"] = "allow-all"
    result = validator.validate_manifest(manifest)
    assert result.is_valid is False
    assert any("REJECTED_UNENFORCED_EGRESS" in v for v in result.violations)

    # Missing agentgatewayRef
    manifest2 = _build_valid_manifest()
    manifest2["spec"]["network"]["agentgatewayRef"] = ""
    result2 = validator.validate_manifest(manifest2)
    assert result2.is_valid is False
    assert any("REJECTED_UNENFORCED_EGRESS" in v for v in result2.violations)


def test_7_raw_secret_leak_in_manifest_is_rejected() -> None:
    validator = KagentCRDValidator()
    # Baseline clean manifest has vault_blinded True
    clean_manifest = _build_valid_manifest()
    clean_manifest["spec"]["env"] = [{"name": "APP_ENV", "value": "production"}]
    clean_res = validator.validate_manifest(clean_manifest)
    assert clean_res.vault_blinded is True

    # Leaked raw secret strictly sets vault_blinded to False even if name is not an obvious credential keyword
    manifest = _build_valid_manifest()
    manifest["spec"]["env"] = [
        {"name": "APP_ENV", "value": "production"},
        {"name": "UNLABELED_PAYLOAD", "value": "sk-" + "abcdef1234567890abcdef1234567890"},
    ]
    result = validator.validate_manifest(manifest)
    assert result.is_valid is False
    assert result.vault_blinded is False
    assert any("REJECTED_RAW_SECRET_IN_MANIFEST" in v for v in result.violations)


def test_8_unblinded_secret_keywords_are_rejected() -> None:
    validator = KagentCRDValidator()
    for secret_name in ("MY_API_KEY", "AUTH_TOKEN", "CLIENT_SECRET", "DB_PASSWORD"):
        manifest = _build_valid_manifest()
        manifest["spec"]["env"] = [{"name": secret_name, "value": "plain_secret_string"}]
        result = validator.validate_manifest(manifest)
        assert result.is_valid is False
        assert result.vault_blinded is False
        assert any("REJECTED_UNBLINDED_CREDENTIAL" in v for v in result.violations)


def test_9_missing_eo1_or_autopause_persistence_is_rejected() -> None:
    validator = KagentCRDValidator()
    manifest = _build_valid_manifest()
    manifest["spec"]["lifecycle"]["eo1IntentLatch"] = False
    result = validator.validate_manifest(manifest)
    assert result.is_valid is False
    assert result.eo1_latch_enabled is False
    assert any("REJECTED_MISSING_EO1_AUTOPAUSE_INTERLOCK" in v for v in result.violations)

    # Missing eo1IntentLatch key defaults strictly to False
    manifest_omitted = _build_valid_manifest()
    del manifest_omitted["spec"]["lifecycle"]["eo1IntentLatch"]
    result_omitted = validator.validate_manifest(manifest_omitted)
    assert result_omitted.is_valid is False
    assert result_omitted.eo1_latch_enabled is False
    assert any("REJECTED_MISSING_EO1_AUTOPAUSE_INTERLOCK" in v for v in result_omitted.violations)

    manifest["spec"]["lifecycle"]["eo1IntentLatch"] = True
    manifest["spec"]["lifecycle"]["autopausePersistence"] = "memory-only"
    result2 = validator.validate_manifest(manifest)
    assert result2.is_valid is False
    assert any("REJECTED_MISSING_EO1_AUTOPAUSE_INTERLOCK" in v for v in result2.violations)


def test_10_drift_threshold_boundaries_and_types() -> None:
    validator = KagentCRDValidator()
    # Exactly 4000 is allowed
    m4000 = _build_valid_manifest()
    m4000["spec"]["governance"]["maxDriftThresholdBps"] = 4000
    res4000 = validator.validate_manifest(m4000)
    assert res4000.is_valid is True
    assert res4000.max_drift_bps == 4000  # claim: config

    # 4001 is rejected
    m4001 = _build_valid_manifest()
    m4001["spec"]["governance"]["maxDriftThresholdBps"] = 4001
    res4001 = validator.validate_manifest(m4001)
    assert res4001.is_valid is False
    assert any("REJECTED_DRIFT_CAP_EXCEEDED" in v for v in res4001.violations)

    # 0 is allowed
    m0 = _build_valid_manifest()
    m0["spec"]["governance"]["maxDriftThresholdBps"] = 0
    res0 = validator.validate_manifest(m0)
    assert res0.is_valid is True

    # Negative or >10000 or non-int
    for bad_drift in (-1, 10001, "3000", None, 3.5):
        mbad = _build_valid_manifest()
        mbad["spec"]["governance"]["maxDriftThresholdBps"] = bad_drift
        res_bad = validator.validate_manifest(mbad)
        assert res_bad.is_valid is False
        assert any("REJECTED_INVALID_DRIFT_BPS" in v for v in res_bad.violations)


def test_11_blast_radius_boundaries_and_types() -> None:
    validator = KagentCRDValidator()
    # Exactly 4500 is allowed
    m4500 = _build_valid_manifest()
    m4500["spec"]["governance"]["maxBlastRadiusBps"] = 4500
    res4500 = validator.validate_manifest(m4500)
    assert res4500.is_valid is True

    # 4501 is rejected
    m4501 = _build_valid_manifest()
    m4501["spec"]["governance"]["maxBlastRadiusBps"] = 4501
    res4501 = validator.validate_manifest(m4501)
    assert res4501.is_valid is False
    assert any("REJECTED_BLAST_CAP_EXCEEDED" in v for v in res4501.violations)

    # 0 is allowed
    m0 = _build_valid_manifest()
    m0["spec"]["governance"]["maxBlastRadiusBps"] = 0
    res0 = validator.validate_manifest(m0)
    assert res0.is_valid is True

    # Negative or >10000 or non-int
    for bad_blast in (-1, 10001, "2000", None, 2.5):
        mbad = _build_valid_manifest()
        mbad["spec"]["governance"]["maxBlastRadiusBps"] = bad_blast
        res_bad = validator.validate_manifest(mbad)
        assert res_bad.is_valid is False
        assert any("REJECTED_INVALID_BLAST_CAP_BPS" in v for v in res_bad.violations)


def test_12_validator_constructor_bounds() -> None:
    # Allowed at exact boundaries 0 and 10000
    v0 = KagentCRDValidator(default_max_drift_bps=0, max_allowed_blast_radius_bps=0)
    assert v0.default_max_drift_bps == 0
    assert v0.max_allowed_blast_radius_bps == 0

    v10k = KagentCRDValidator(default_max_drift_bps=10000, max_allowed_blast_radius_bps=10000)
    assert v10k.default_max_drift_bps == 10000
    assert v10k.max_allowed_blast_radius_bps == 10000

    # Outside bounds
    with pytest.raises(ValueError, match="default_max_drift_bps"):
        KagentCRDValidator(default_max_drift_bps=-1)
    with pytest.raises(ValueError, match="default_max_drift_bps"):
        KagentCRDValidator(default_max_drift_bps=10001)
    with pytest.raises(ValueError, match="max_allowed_blast_radius_bps"):
        KagentCRDValidator(max_allowed_blast_radius_bps=-1)
    with pytest.raises(ValueError, match="max_allowed_blast_radius_bps"):
        KagentCRDValidator(max_allowed_blast_radius_bps=10001)


def test_13_dataclass_immutability() -> None:
    res = CRDValidationResult(
        is_valid=True,
        crd_kind="Harness",
        metadata_name="demo",
        runtime_sandbox="gvisor",
        spiffe_id="spiffe://domain/ns/a/actor/b",
        egress_enforced=True,
        vault_blinded=True,
        eo1_latch_enabled=True,
        max_drift_bps=3000,
        violations=(),
    )
    with pytest.raises(Exception):
        res.is_valid = False  # type: ignore
