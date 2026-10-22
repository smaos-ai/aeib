#!/usr/bin/env python3
# File: tests/test_deep_tech_tracks_alpha_beta_gamma_delta.py
"""
End-to-End Verification Suite for the 4 Deep-Tech Sprint Tracks:
- Track Alpha (`tools/zk_tlsnotary_integration.py`): ZK-TLS / Blind API Attestation
  proving `balance_minor > $100.00` (`100_00`) without exposing exact balance or PII.
- Track Beta (`compliance/tetragon_rapl_throttle.yaml` + `src/bpf_lsm_profile_compiler.py`):
  Static BPF_LSM profile compilation and linting of the thermodynamic & socket policy.
- Track Gamma (`docs/interop/china_bsn_did_mapping.md`): Cross-border BSN / CTID / PIPL
  zero-raw-PII mandate verification.
- Track Delta (`src/hybrid_pqc_scitt_anchor.rs`): Hybrid Ed25519 (`-8`) + ML-DSA-65 (`-49`)
  RFC 9964 / RFC 9942 SCITT transparency anchor invariants and clean-room banned-word audit.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.bpf_lsm_profile_compiler import (
    BPFLSMProfileCompiler,
    BPFLSMStaticLinter,
    parse_yaml_tracing_policy,
)
from tools.zk_tlsnotary_integration import (
    ZkTlsNotaryProxyPrototype,
    encode_jcs,
    sha256_prefixed,
)


def test_track_alpha_zk_tlsnotary_blind_balance_proof() -> None:
    notary_priv = Ed25519PrivateKey.generate()
    proxy = ZkTlsNotaryProxyPrototype(notary_priv)

    raw_api_payload = {
        "customer_name": "Chen Mingguang",
        "tax_id": "CN-9988776655",
        "balance_minor": 10500_00,
        "status": "approved",
    }
    receipt = proxy.attest_api_response_above_floor(
        operation_id="op-alpha-100",
        server_sni="api.settlement-bank.example",
        raw_json_response=raw_api_payload,
        strict_floor_minor=100_00,
        session_salt_hex="0123456789abcdef0123456789abcdef",
    )

    assert ZkTlsNotaryProxyPrototype.verify_blind_receipt_offline(
        receipt, notary_priv.public_key(), expected_min_floor_minor=100_00
    )
    dumped = json.dumps(receipt.__dict__)
    assert "1050000" not in dumped
    assert "Chen Mingguang" not in dumped
    assert "CN-9988776655" not in dumped

    # Balance equal to floor ($100.00) must fail strict `> $100.00` check
    with pytest.raises(ValueError, match="ERR_ZKTLS_BALANCE_NOT_STRICTLY_ABOVE_FLOOR"):
        proxy.attest_api_response_above_floor(
            operation_id="op-alpha-fail",
            server_sni="api.settlement-bank.example",
            raw_json_response={**raw_api_payload, "balance_minor": 100_00},
            strict_floor_minor=100_00,
            session_salt_hex="fedcba9876543210",
        )


def test_track_beta_tetragon_rapl_throttle_yaml_compiles_cleanly() -> None:
    yaml_path = Path("compliance/tetragon_rapl_throttle.yaml")
    assert yaml_path.exists()

    raw_yaml = yaml_path.read_text(encoding="utf-8")
    parsed = parse_yaml_tracing_policy(raw_yaml)
    linter = BPFLSMStaticLinter(parsed)
    lint_report = linter.validate()
    assert lint_report["metadata_name"] == "aeib-thermodynamic-and-egress-enforcer"
    assert lint_report["total_hooks"] == 3

    compiled = BPFLSMProfileCompiler.compile(yaml_path)
    assert compiled["format"] == "AEIB_BPF_LSM_SECURITY_PROFILE_V1"
    assert len(compiled["canonical_digest_sha256"]) == 64
    manifest = compiled["profile_manifest"]
    assert manifest["profile_name"] == "aeib-thermodynamic-and-egress-enforcer"
    hooks = {h["call"] for h in manifest["kernel_lsm_hooks"]}
    assert "security_socket_connect" in hooks
    assert "security_file_open" in hooks
    assert "bprm_check_security" in hooks


def test_track_gamma_and_delta_bsn_did_and_hybrid_pqc_scitt_artifacts() -> None:
    bsn_doc = Path("docs/interop/china_bsn_did_mapping.md")
    rs_file = Path("src/hybrid_pqc_scitt_anchor.rs")
    assert bsn_doc.exists()
    assert rs_file.exists()

    bsn_text = bsn_doc.read_text(encoding="utf-8")
    assert "BLIND_COMMITMENT_ONLY_ZERO_RAW_PII" in bsn_text
    assert "did:bsn:wenchang:" in bsn_text

    rs_text = rs_file.read_text(encoding="utf-8")
    assert "pub const COSE_ALG_EDDSA: i32 = -8;" in rs_text
    assert "pub const COSE_ALG_ML_DSA_65: i32 = -49;" in rs_text
    assert "pub const COSE_HEADER_VERIFIABLE_PROOFS: u32 = 394;" in rs_text

    # Verify zero banned promotional words across all 4 Deep-Tech track files
    banned = [
        "guaran" + "teed",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "unhack" + "able",
        "immun" + "e",
        "proven " + "universally",
    ]
    for fpath in (
        "tools/zk_tlsnotary_integration.py",
        "compliance/tetragon_rapl_throttle.yaml",
        "docs/interop/china_bsn_did_mapping.md",
        "src/hybrid_pqc_scitt_anchor.rs",
        "tests/test_deep_tech_tracks_alpha_beta_gamma_delta.py",
    ):
        content = Path(fpath).read_text(encoding="utf-8").lower()
        for word in banned:
            assert word not in content, f"Banned word '{word}' found in {fpath}"
