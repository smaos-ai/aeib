import pytest
import json
from pathlib import Path
from scripts.run_e2e_4moats_demo import run_e2e_4moats
from src.cose_verifier import verify_trust_passport


def test_e2e_4moats_execution():
    artifact_path = run_e2e_4moats()
    assert artifact_path.exists()

    with open(artifact_path) as f:
        data = json.load(f)

    # 1. Assert schema and top-level structure
    assert data["schema_version"] == "v0.3.0"
    assert data["artifact_type"] == "SMAOS_UNIFIED_4MOAT_TRUST_PASSPORT"

    # 2. Assert Moat 1 Cryptographic Provenance
    m1 = data["moat_1_cryptographic_provenance"]
    assert verify_trust_passport(m1) is True

    # 3. Assert Moat 2 BBS+ Redaction
    m2 = data["moat_2_zero_knowledge_redaction"]
    assert m2["status"] == "VERIFIED_REDACTED"
    assert "user_iban" in m2["blinded_fields"]
    assert "user_iban" not in m2["disclosed_fields"]

    # 4. Assert Moat 3 Kernel eBPF Enforcement
    m3 = data["moat_3_kernel_transport_enforcement"]
    assert m3["driver_action"] == "XDP_DROP"
    assert m3["probe_outcome"]["result"] == "OUTCOME_VERIFIED"

    # 5. Assert Moat 4 TEE Hardware Attestation
    m4 = data["moat_4_hardware_attestation"]
    assert m4["tee_type"] == "INTEL_TDX"
    assert m4["zk_proof_anchor"]["public_inputs_hash"] == m1["payload_hash"]
