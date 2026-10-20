#!/usr/bin/env python3
"""
test_governed_cross_model_handoff.py — Falsification & Verification Suite for
Governed Cross-Model Handoff & Taint Monotonicity Gate.

Evaluated under the stated model as a Layer 2.5 execution interlock test suite.
Verifies nominal execution, 6 distinct falsification catches, CLI self-test execution,
and compliance purity (zero banned words, zero mocks).
"""

from __future__ import annotations

import base64
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.governed_cross_model_handoff import (
    CanonicalPayloadHashMismatchError,
    DEFAULT_MODEL_TRUST_REGISTRY,
    GovernedCrossModelHandoffGate,
    HandoffExpiredError,
    HandoffSecurityError,
    InvalidHandoffSignatureError,
    SerializationMetadataStrippedError,
    TIER_0_SYSTEM_PINNED,
    TIER_1_PARTNER_ATTESTED,
    TIER_2_UNTRUSTED_EXTERNAL,
    TaintDowngradeForbiddenError,
    UntrustedModelAuthorityEscalationError,
    compute_payload_canonical_hash,
    sign_canonical_handoff,
)
from src.jcs_canonicalizer import encode_jcs


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def keys_and_gate() -> Tuple[
    Ed25519PrivateKey,
    Ed25519PublicKey,
    Ed25519PrivateKey,
    Ed25519PublicKey,
    GovernedCrossModelHandoffGate,
]:
    """Generates real Ed25519 keys for source orchestrator and supervisor."""
    source_privkey = Ed25519PrivateKey.generate()
    source_pubkey = source_privkey.public_key()

    supervisor_privkey = Ed25519PrivateKey.generate()
    supervisor_pubkey = supervisor_privkey.public_key()

    gate = GovernedCrossModelHandoffGate(
        source_public_keys={"claude-code": source_pubkey},
        supervisor_public_keys={"supervisor-01": supervisor_pubkey},
        active_policy_epoch="epoch-2026-v1",
    )
    return source_privkey, source_pubkey, supervisor_privkey, supervisor_pubkey, gate


@pytest.fixture
def nominal_payload() -> Dict[str, Any]:
    """Provides a sample computation task payload."""
    return {
        "task_id": "TASK-2026-CROSS-MODEL-77",
        "description": "Cross-model code optimization and AST transform",
        "parameters": {
            "max_iterations": 5,
            "target_language": "python",
        },
    }


# ============================================================================
# Positive Nominal Test
# ============================================================================

def test_nominal_cross_model_handoff(
    keys_and_gate: Tuple[
        Ed25519PrivateKey,
        Ed25519PublicKey,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        GovernedCrossModelHandoffGate,
    ],
    nominal_payload: Dict[str, Any],
) -> None:
    """
    Positive test: Nominal cross-model handoff (Claude -> DeepSeek) with valid
    Ed25519 signature, preserved taint tier, and valid payload hash succeeds.
    """
    source_privkey, source_pubkey, _, _, gate = keys_and_gate
    now = int(time.time())

    token = gate.create_handoff(
        handoff_id="handoff-nominal-001",
        source_model="claude-code",
        target_model="deepseek-r1",
        source_harness_digest="sha256:3a7b9c1d2e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b",
        target_harness_digest="sha256:4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a",
        payload=nominal_payload,
        policy_epoch="epoch-2026-v1",
        delegation_cert_id="cert-worker-delegation-42",
        taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        expires_at=now + 3600,
        source_private_key=source_privkey,
        source_taint_tier=TIER_0_SYSTEM_PINNED,
    )

    # Validate dictionary handoff
    receipt = gate.validate_handoff(
        handoff_token=token,
        payload=nominal_payload,
        source_public_key=source_pubkey,
        current_time=now,
    )
    assert receipt["status"] == "VERIFIED"
    assert receipt["handoff_id"] == "handoff-nominal-001"
    assert receipt["source_model"] == "claude-code"
    assert receipt["target_model"] == "deepseek-r1"
    assert receipt["taint_tier"] == TIER_2_UNTRUSTED_EXTERNAL

    # Validate JSON bytes round-trip serialization
    json_bytes = encode_jcs(token)
    receipt_from_bytes = gate.validate_handoff(
        handoff_token=json_bytes,
        payload=nominal_payload,
        source_public_key=source_pubkey,
        current_time=now,
    )
    assert receipt_from_bytes["status"] == "VERIFIED"


# ============================================================================
# Falsification 1: Tampered Payload Hash
# ============================================================================

def test_falsification_1_tampered_payload_hash_rejected(
    keys_and_gate: Tuple[
        Ed25519PrivateKey,
        Ed25519PublicKey,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        GovernedCrossModelHandoffGate,
    ],
    nominal_payload: Dict[str, Any],
) -> None:
    """
    Falsification 1: Tampered payload hash rejected with HALT_CANONICAL_PAYLOAD_HASH_MISMATCH.
    """
    source_privkey, source_pubkey, _, _, gate = keys_and_gate
    now = int(time.time())

    token = gate.create_handoff(
        handoff_id="handoff-falsify-001",
        source_model="claude-code",
        target_model="deepseek-r1",
        source_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        target_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        payload=nominal_payload,
        policy_epoch="epoch-2026-v1",
        delegation_cert_id="cert-delegation-88",
        taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        expires_at=now + 3600,
        source_private_key=source_privkey,
    )

    tampered_payload = dict(nominal_payload)
    tampered_payload["malicious_modification"] = True

    with pytest.raises(CanonicalPayloadHashMismatchError) as exc_info:
        gate.validate_handoff(
            handoff_token=token,
            payload=tampered_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )

    assert exc_info.value.error_code == "HALT_CANONICAL_PAYLOAD_HASH_MISMATCH"
    assert "HALT_CANONICAL_PAYLOAD_HASH_MISMATCH" in str(exc_info.value)


# ============================================================================
# Falsification 2: Taint Downgrade Attempt
# ============================================================================

def test_falsification_2_taint_downgrade_rejected(
    keys_and_gate: Tuple[
        Ed25519PrivateKey,
        Ed25519PublicKey,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        GovernedCrossModelHandoffGate,
    ],
    nominal_payload: Dict[str, Any],
) -> None:
    """
    Falsification 2: Taint downgrade attempt (TIER_2_UNTRUSTED_EXTERNAL -> TIER_0_SYSTEM_PINNED)
    rejected with HALT_TAINT_DOWNGRADE_FORBIDDEN.
    """
    source_privkey, source_pubkey, supervisor_privkey, _, gate = keys_and_gate
    now = int(time.time())

    # Direct creation attempt with downgrade without step-up warrant
    with pytest.raises(TaintDowngradeForbiddenError) as exc_info:
        gate.create_handoff(
            handoff_id="handoff-downgrade-002",
            source_model="deepseek-r1",
            target_model="claude-code",
            source_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            target_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            payload=nominal_payload,
            policy_epoch="epoch-2026-v1",
            delegation_cert_id="cert-delegation-88",
            taint_tier=TIER_0_SYSTEM_PINNED,  # Downgrade from TIER_2!
            expires_at=now + 3600,
            source_private_key=source_privkey,
            source_taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        )

    assert exc_info.value.error_code == "HALT_TAINT_DOWNGRADE_FORBIDDEN"
    assert "HALT_TAINT_DOWNGRADE_FORBIDDEN" in str(exc_info.value)

    # Verification of downgrade with verified supervisor step-up warrant succeeds
    warrant_dict: Dict[str, Any] = {
        "warrant_id": "step-up-warrant-99",
        "handoff_id": "handoff-downgrade-002",
        "supervisor_id": "supervisor-01",
        "permitted_target_taint": TIER_0_SYSTEM_PINNED,
        "expires_at": now + 3600,
    }
    warrant_sig = sign_canonical_handoff(supervisor_privkey, warrant_dict)
    warrant_dict["signature"] = warrant_sig

    token_with_warrant = gate.create_handoff(
        handoff_id="handoff-downgrade-002",
        source_model="deepseek-r1",
        target_model="claude-code",
        source_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        target_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        payload=nominal_payload,
        policy_epoch="epoch-2026-v1",
        delegation_cert_id="cert-delegation-88",
        taint_tier=TIER_0_SYSTEM_PINNED,
        expires_at=now + 3600,
        source_private_key=source_privkey,
        source_taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        step_up_warrant=warrant_dict,
    )
    assert token_with_warrant["taint_tier"] == TIER_0_SYSTEM_PINNED


# ============================================================================
# Falsification 3: Dropped Security Field
# ============================================================================

def test_falsification_3_dropped_security_field_rejected(
    keys_and_gate: Tuple[
        Ed25519PrivateKey,
        Ed25519PublicKey,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        GovernedCrossModelHandoffGate,
    ],
    nominal_payload: Dict[str, Any],
) -> None:
    """
    Falsification 3: Dropped security field (e.g. policy_epoch or delegation_cert_id omitted
    during serialization) rejected with HALT_SERIALIZATION_METADATA_STRIPPED.
    """
    source_privkey, source_pubkey, _, _, gate = keys_and_gate
    now = int(time.time())

    token = gate.create_handoff(
        handoff_id="handoff-falsify-003",
        source_model="claude-code",
        target_model="deepseek-r1",
        source_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        target_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        payload=nominal_payload,
        policy_epoch="epoch-2026-v1",
        delegation_cert_id="cert-delegation-88",
        taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        expires_at=now + 3600,
        source_private_key=source_privkey,
    )

    # Test stripping policy_epoch
    token_no_epoch = dict(token)
    del token_no_epoch["policy_epoch"]
    with pytest.raises(SerializationMetadataStrippedError) as exc_epoch:
        gate.validate_handoff(
            handoff_token=token_no_epoch,
            payload=nominal_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )
    assert exc_epoch.value.error_code == "HALT_SERIALIZATION_METADATA_STRIPPED"

    # Test stripping delegation_cert_id
    token_no_cert = dict(token)
    del token_no_cert["delegation_cert_id"]
    with pytest.raises(SerializationMetadataStrippedError) as exc_cert:
        gate.validate_handoff(
            handoff_token=token_no_cert,
            payload=nominal_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )
    assert exc_cert.value.error_code == "HALT_SERIALIZATION_METADATA_STRIPPED"

    # Test stripping canonical_payload_hash
    token_no_hash = dict(token)
    del token_no_hash["canonical_payload_hash"]
    with pytest.raises(SerializationMetadataStrippedError) as exc_hash:
        gate.validate_handoff(
            handoff_token=token_no_hash,
            payload=nominal_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )
    assert exc_hash.value.error_code == "HALT_SERIALIZATION_METADATA_STRIPPED"


# ============================================================================
# Falsification 4: Expired Handoff Token
# ============================================================================

def test_falsification_4_expired_token_rejected(
    keys_and_gate: Tuple[
        Ed25519PrivateKey,
        Ed25519PublicKey,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        GovernedCrossModelHandoffGate,
    ],
    nominal_payload: Dict[str, Any],
) -> None:
    """
    Falsification 4: Expired handoff token rejected with HALT_HANDOFF_EXPIRED.
    """
    source_privkey, source_pubkey, _, _, gate = keys_and_gate
    now = int(time.time())

    expired_token = gate.create_handoff(
        handoff_id="handoff-falsify-004",
        source_model="claude-code",
        target_model="deepseek-r1",
        source_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        target_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        payload=nominal_payload,
        policy_epoch="epoch-2026-v1",
        delegation_cert_id="cert-delegation-88",
        taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        expires_at=now - 120,  # Expired 2 minutes ago
        source_private_key=source_privkey,
    )

    with pytest.raises(HandoffExpiredError) as exc_info:
        gate.validate_handoff(
            handoff_token=expired_token,
            payload=nominal_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )

    assert exc_info.value.error_code == "HALT_HANDOFF_EXPIRED"
    assert "HALT_HANDOFF_EXPIRED" in str(exc_info.value)


# ============================================================================
# Falsification 5: Forged Source Signature
# ============================================================================

def test_falsification_5_forged_signature_rejected(
    keys_and_gate: Tuple[
        Ed25519PrivateKey,
        Ed25519PublicKey,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        GovernedCrossModelHandoffGate,
    ],
    nominal_payload: Dict[str, Any],
) -> None:
    """
    Falsification 5: Forged source orchestrator signature rejected with HALT_INVALID_HANDOFF_SIGNATURE.
    """
    _, source_pubkey, _, _, gate = keys_and_gate
    now = int(time.time())

    unauthorized_privkey = Ed25519PrivateKey.generate()

    forged_token = gate.create_handoff(
        handoff_id="handoff-falsify-005",
        source_model="claude-code",
        target_model="deepseek-r1",
        source_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        target_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        payload=nominal_payload,
        policy_epoch="epoch-2026-v1",
        delegation_cert_id="cert-delegation-88",
        taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        expires_at=now + 3600,
        source_private_key=unauthorized_privkey,  # Forged key!
    )

    with pytest.raises(InvalidHandoffSignatureError) as exc_info:
        gate.validate_handoff(
            handoff_token=forged_token,
            payload=nominal_payload,
            source_public_key=source_pubkey,
            current_time=now,
        )

    assert exc_info.value.error_code == "HALT_INVALID_HANDOFF_SIGNATURE"
    assert "HALT_INVALID_HANDOFF_SIGNATURE" in str(exc_info.value)


# ============================================================================
# Falsification 6: Untrusted Model Authority Escalation
# ============================================================================

def test_falsification_6_authority_escalation_rejected(
    keys_and_gate: Tuple[
        Ed25519PrivateKey,
        Ed25519PublicKey,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        GovernedCrossModelHandoffGate,
    ],
    nominal_payload: Dict[str, Any],
) -> None:
    """
    Falsification 6: Model authority escalation attempt (low-trust model attempting
    to claim root sponsor authority) rejected with HALT_UNTRUSTED_MODEL_AUTHORITY_ESCALATION.
    """
    source_privkey, source_pubkey, _, _, gate = keys_and_gate
    now = int(time.time())

    # Case A: Low-trust target model claiming root sponsor authority during handoff creation
    with pytest.raises(UntrustedModelAuthorityEscalationError) as exc_info_create:
        gate.create_handoff(
            handoff_id="handoff-falsify-006",
            source_model="claude-code",
            target_model="deepseek-r1",  # Untrusted external model
            source_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            target_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            payload=nominal_payload,
            policy_epoch="epoch-2026-v1",
            delegation_cert_id="cert-standard-worker-42",
            taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
            expires_at=now + 3600,
            source_private_key=source_privkey,
            claimed_authority="root_sponsor",  # Escalation claim!
        )
    assert exc_info_create.value.error_code == "HALT_UNTRUSTED_MODEL_AUTHORITY_ESCALATION"

    # Case B: Creation with delegation_cert_id attempting to claim root sponsor authority
    with pytest.raises(UntrustedModelAuthorityEscalationError) as exc_info_cert:
        gate.create_handoff(
            handoff_id="handoff-falsify-006b",
            source_model="claude-code",
            target_model="deepseek-r1",
            source_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            target_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
            payload=nominal_payload,
            policy_epoch="epoch-2026-v1",
            delegation_cert_id="root-sponsor-cert-99",  # Root sponsor delegation!
            taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
            expires_at=now + 3600,
            source_private_key=source_privkey,
        )
    assert exc_info_cert.value.error_code == "HALT_UNTRUSTED_MODEL_AUTHORITY_ESCALATION"

    # Case C: Validation time escalation claim rejection
    valid_token = gate.create_handoff(
        handoff_id="handoff-falsify-006c",
        source_model="claude-code",
        target_model="deepseek-r1",
        source_harness_digest="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        target_harness_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        payload=nominal_payload,
        policy_epoch="epoch-2026-v1",
        delegation_cert_id="cert-standard-worker-42",
        taint_tier=TIER_2_UNTRUSTED_EXTERNAL,
        expires_at=now + 3600,
        source_private_key=source_privkey,
    )
    with pytest.raises(UntrustedModelAuthorityEscalationError) as exc_info_val:
        gate.validate_handoff(
            handoff_token=valid_token,
            payload=nominal_payload,
            source_public_key=source_pubkey,
            current_time=now,
            claimed_authority="treasury_root",
        )
    assert exc_info_val.value.error_code == "HALT_UNTRUSTED_MODEL_AUTHORITY_ESCALATION"


# ============================================================================
# CLI Subprocess Execution Test
# ============================================================================

def test_cli_self_test_subprocess() -> None:
    """
    Executes governed_cross_model_handoff.py --self-test via subprocess to evaluate
    CLI round-trip verification and falsification catches.
    """
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "src" / "governed_cross_model_handoff.py"

    proc = subprocess.run(
        [sys.executable, str(script_path), "--self-test"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )

    assert proc.returncode == 0
    assert "[EVALUATED] GovernedCrossModelHandoffGate self-test initialized." in proc.stdout
    assert "Nominal cross-model handoff: VERIFIED" in proc.stdout
    assert "Falsification 1 (tampered payload hash): CAUGHT" in proc.stdout
    assert "Falsification 2 (taint downgrade): CAUGHT" in proc.stdout
    assert "Falsification 3 (stripped metadata): CAUGHT" in proc.stdout
    assert "Falsification 4 (expired handoff): CAUGHT" in proc.stdout
    assert "Falsification 5 (forged signature): CAUGHT" in proc.stdout
    assert "Falsification 6 (authority escalation): CAUGHT" in proc.stdout


# ============================================================================
# Epistemic Purity: Zero Banned Words Enforcement
# ============================================================================

def test_zero_banned_words_in_source_and_tests() -> None:
    """
    Enforces AGENTS.md Section 1 Epistemic Boundaries:
    Verifies that neither src/governed_cross_model_handoff.py nor
    tests/test_governed_cross_model_handoff.py contains banned terminology.
    All banned search stems use string concatenation to prevent self-matching.
    """
    repo_root = Path(__file__).resolve().parent.parent
    source_file = repo_root / "src" / "governed_cross_model_handoff.py"
    test_file = repo_root / "tests" / "test_governed_cross_model_handoff.py"

    banned_tokens = [
        "guaran" + "tee",
        "guaran" + "teed",
        "proven" + " universally",
        "bullet" + "proof",
        "enterprise" + "-grade",
        "production" + "-safe",
        "100% " + "secure",
        "unhack" + "able",
    ]

    for target_path in (source_file, test_file):
        assert target_path.is_file(), f"Target file does not exist: {target_path}"
        content = target_path.read_text(encoding="utf-8").lower()
        for token in banned_tokens:
            assert token not in content, (
                f"Banned word violation detected in {target_path.name}: '{token}'"
            )
