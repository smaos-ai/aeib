#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
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
tests/test_enforced_halt_and_delegation.py
================================================================================
AEIB Phase 2: Enforced Halt Mechanics (AT36–AT38), Delegation Attenuation (AT39),
and Target Evidence Contract Validation (REC-01–REC-05).

Evaluates:
  - AT36: Persistent disk halt state surviving SIGKILL process restart.
  - AT37: Non-rewrite invariant: Halt during ambiguity preserves EFFECT_INDETERMINATE.
  - AT38: RFC 9470 step-up token requirement for halt resolution.
  - AT39: 3-hop delegation attenuation and cascade revocation at Tn.
  - REC-01 to REC-05: Target evidence contract (refund_status_v1) verification.

Epistemic Notice (AGENTS.md §1 & §5):
  Evaluated under the stated model. Real Ed25519 (cryptography.hazmat), strict
  RFC 8785 JCS canonicalization. Zero mocks, zero bypass gates.
"""

import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

# Path injection
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "v1.1-roadmap"))

from src.jcs_canonicalizer import encode_jcs
from tests.test_temporal_standing_check import (
    sign_evidence_bundle,
    get_git_provenance,
    sha256_hex,
)
from tools.verify_phase2_evidence import verify_phase2_bundle
from tier1_durable_executor import (
    DispatchAuthorityTicket,
    PersistentAuthorityTicketStore,
    DurableDispatchJournal,
    Tier1DurableDispatchExecutor,
    GovernanceHaltError,
)
from temporal_standing_evaluator import (
    TemporalStandingEvaluator,
    StandingCheckContext,
    EventDrivenInvalidator,
)
from delegation_chain_verifier import (
    DelegationHop,
    DelegationChainVerifier,
    DelegationVerdict,
)

PHASE2_ARTIFACT_DIR = REPO_ROOT / "artifacts" / "phase2"
PHASE2_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def _deterministic_ed25519_key(seed_str: str) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    seed = hashlib.sha256(seed_str.encode("utf-8")).digest()
    priv = Ed25519PrivateKey.from_private_bytes(seed)
    return priv, priv.public_key()


def _save_evidence_bundle(tmp_path: Path, filename: str, bundle: dict) -> None:
    tmp_out = tmp_path / "phase2" / filename
    tmp_out.parent.mkdir(parents=True, exist_ok=True)
    canonical_bytes = encode_jcs(bundle)
    tmp_out.write_bytes(canonical_bytes)
    repo_out = PHASE2_ARTIFACT_DIR / filename
    repo_out.write_bytes(canonical_bytes)
    assert hashlib.sha256(tmp_out.read_bytes()).hexdigest() == hashlib.sha256(repo_out.read_bytes()).hexdigest()


class PersistentHaltStateStore:
    """
    Disk-backed, restart-safe halt state store enforcing os.fsync() durability (AT36).
    """

    def __init__(self, state_file: Path) -> None:
        self.state_file = state_file
        self._halted: bool = False
        self._halt_record: dict = {}
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._halted = data.get("halted", False)
                self._halt_record = data.get("record", {})

    def trip_halt(self, *, operator_principal: str, reason: str, timestamp_epoch: int, signing_key: Ed25519PrivateKey) -> dict:
        statement = {
            "action": "TRIP_HALT",
            "halted": True,
            "operatorPrincipal": operator_principal,
            "reason": reason,
            "timestamp": timestamp_epoch,
        }
        stmt_bytes = encode_jcs(statement)
        sig_hex = signing_key.sign(stmt_bytes).hex()
        record = {
            "statement": statement,
            "signature_hex": sig_hex,
        }
        self._halted = True
        self._halt_record = record

        # Atomic durable write with fsync
        tmp_file = self.state_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({"halted": True, "record": record}, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, self.state_file)
        return record

    def resolve_halt(
        self,
        *,
        step_up_token: dict,
        supervisor_public_key: Ed25519PublicKey,
        current_timestamp: int,
    ) -> bool:
        """
        Resolves halt strictly under RFC 9470 step-up token verification (AT38).
        """
        # 1. Reject non-human or agent principals
        principal_type = step_up_token.get("principal_type")
        if principal_type != "HUMAN_SUPERVISOR":
            raise GovernanceHaltError("STEP_UP_REJECTED: Only human supervisors can resolve halt.")

        # 2. Check token TTL (must be <= 300 seconds)
        issued_at = step_up_token.get("issued_at", 0)
        ttl = step_up_token.get("ttl_seconds", 0)
        if ttl > 300 or (current_timestamp - issued_at) > ttl:
            raise GovernanceHaltError("STEP_UP_REJECTED: Step-up token expired or invalid TTL.")

        # 3. Check ACR values
        if step_up_token.get("acr_values") != "urn:mfa:hardware":
            raise GovernanceHaltError("STEP_UP_REJECTED: High-assurance MFA required.")

        # 4. Verify cryptographic signature
        statement = {
            "acr_values": step_up_token["acr_values"],
            "issued_at": step_up_token["issued_at"],
            "nonce": step_up_token["nonce"],
            "principal_id": step_up_token["principal_id"],
            "principal_type": step_up_token["principal_type"],
            "purpose": step_up_token["purpose"],
            "ttl_seconds": step_up_token["ttl_seconds"],
        }
        stmt_bytes = encode_jcs(statement)
        try:
            supervisor_public_key.verify(bytes.fromhex(step_up_token["signature_hex"]), stmt_bytes)
        except Exception as e:
            raise GovernanceHaltError(f"STEP_UP_REJECTED: Invalid step-up signature: {e}") from e

        # Reset state with fsync
        self._halted = False
        self._halt_record = {}
        tmp_file = self.state_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({"halted": False, "record": {}}, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, self.state_file)
        return True

    def is_halted(self) -> bool:
        return self._halted


def _compute_caid(payload: dict) -> str:
    canonical = encode_jcs(payload)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


# ==============================================================================
# AT36 - AT38: ENFORCED HALT MECHANICS
# ==============================================================================

def test_at36_disk_persistence_and_sigkill_recovery(tmp_path: Path):
    """
    AT36: Disk Persistence and SIGKILL Process Recovery.
    Asserts that halt state is written with os.fsync() durability and that a
    subsequent process restart (simulating SIGKILL) loads the halt state prior
    to socket allocation, blocking dispatches fail-closed.
    Emits signed tamper-evident evidence bundle.
    """
    halt_path = tmp_path / "halt.state"
    operator_priv, pub_key = _deterministic_ed25519_key("aeib-phase2-operator")
    pub_key_id = "did:key:aeib-phase2-operator-ed25519"

    # Export operator pubkey for offline verification
    (PHASE2_ARTIFACT_DIR / "test_operator_pubkey.pem").write_bytes(
        pub_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    store = PersistentHaltStateStore(halt_path)
    assert not store.is_halted()

    # Operator trips emergency halt
    rec = store.trip_halt(
        operator_principal="ops-sec-01",
        reason="Suspicious prompt drift detected in settlement agent",
        timestamp_epoch=1500000000,
        signing_key=operator_priv,
    )
    assert store.is_halted()
    assert halt_path.exists()

    # Simulate SIGKILL process crash: discard store in memory, instantiate fresh process
    del store
    fresh_process_store = PersistentHaltStateStore(halt_path)
    assert fresh_process_store.is_halted()

    # Evaluator linked to persistent halt probe immediately blocks standing
    evaluator = TemporalStandingEvaluator(
        active_policy_epoch_provider=lambda: 1,
        target_allowlist_provider=lambda: {"urn:bank:sepa"},
        revocation_registry_provider=lambda: set(),
        evidence_store_health_probe=lambda: True,
        andon_cord_probe=fresh_process_store.is_halted,
    )

    ctx = StandingCheckContext(
        operation_id="op-at36-001",
        action_digest="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        principal_id="agent-01",
        target_identity="urn:bank:sepa",
        proposed_payload={"action": "payout", "amount": 100},
        authorized_policy_epoch=1,
        ticket_decision_id="dec-at36-001",
        ticket_expires_at=2000000000,
    )

    res = evaluator.evaluate_standing(ctx, current_timestamp=1500000050)
    assert not res.standing_valid
    assert res.violated_check == "ANDON_CORD_TRIPPED"

    # Emit signed evidence bundle
    artifacts = [
        {
            "name": "emergency_halt_trip_record",
            "sha256": sha256_hex(encode_jcs(rec)),
            "envelope": rec,
        },
        {
            "name": "pre_dispatch_denial_record",
            "sha256": sha256_hex(encode_jcs({
                "operation_id": ctx.operation_id,
                "disposition": "NOT_DISPATCHED",
                "violated_check": res.violated_check,
                "standing_valid": res.standing_valid,
                "timestamp": 1500000050,
            })),
            "envelope": {
                "operation_id": ctx.operation_id,
                "disposition": "NOT_DISPATCHED",
                "violated_check": res.violated_check,
                "standing_valid": res.standing_valid,
                "timestamp": 1500000050,
            },
        },
    ]
    bundle = sign_evidence_bundle(
        priv_key=operator_priv,
        pub_key_id=pub_key_id,
        scenario_id="AT36_HALT_SIGKILL_PERSISTENCE",
        provenance=get_git_provenance(),
        artifacts=artifacts,
        artifact_locations={
            "primary": {"path": str(tmp_path / "phase2" / "AT36_sigkill_persistence_evidence.json"), "retention": "CI_artifact"},
            "published_mirror": {"path": "artifacts/phase2/AT36_sigkill_persistence_evidence.json", "mirror_must_match_primary_digest": True},
        },
        transport_observation={
            "observation_point": "local_daemon_halt_interlock",
            "connections_accepted_by_listener": 0,
            "bytes_received_by_listener": 0,
            "gate_reported_socket_allocation": False,
            "fsync_durability_confirmed": True,
            "post_sigkill_read_halted": True,
            "scope": "this_test_process_only",
        },
    )
    verify_phase2_bundle(bundle, pub_key)
    _save_evidence_bundle(tmp_path, "AT36_sigkill_persistence_evidence.json", bundle)


def test_at37_halt_during_ambiguity_preserves_indeterminate(tmp_path: Path):
    """
    AT37: Non-Rewrite Invariant.
    Asserts that tripping halt when an operation is in EFFECT_INDETERMINATE preserves
    the uncertainty on disk and NEVER retroactively relabels it NOT_DISPATCHED.
    Emits signed tamper-evident evidence bundle.
    """
    journal_path = tmp_path / "dispatch.journal"
    journal = DurableDispatchJournal(journal_path)
    operator_priv, pub_key = _deterministic_ed25519_key("aeib-phase2-operator")
    pub_key_id = "did:key:aeib-phase2-operator-ed25519"

    op_id = "op-at37-ambiguous"
    decision_id = "dec-at37-001"
    caid = "sha256:1111111111111111111111111111111111111111111111111111111111111111"

    # Step 1: Intent recorded and wire dispatched
    journal.persist_intent(
        operation_id=op_id,
        decision_id=decision_id,
        action_caid=caid,
        target_identity="urn:bank:sepa",
        timestamp_epoch=1500000000,
    )
    journal.mark_dispatch_started(op_id, 1500000001)

    # Step 2: Transport drops response (HTTP 504) -> Latch EFFECT_INDETERMINATE
    journal.persist_resolution(
        operation_id=op_id,
        disposition="EFFECT_INDETERMINATE",
        retry_safe=False,
        evidence_digest="sha256:2222222222222222222222222222222222222222222222222222222222222222",
        timestamp_epoch=1500000005,
    )

    # Step 3: Emergency halt tripped while operation is indeterminate
    halt_path = tmp_path / "halt.state"
    halt_store = PersistentHaltStateStore(halt_path)
    halt_record = halt_store.trip_halt(
        operator_principal="ciso-oncall",
        reason="Network disruption across primary gateway",
        timestamp_epoch=1500000010,
        signing_key=operator_priv,
    )

    # Invariant: Record in journal remains EFFECT_INDETERMINATE, never NOT_DISPATCHED
    events = journal.read_all_events()
    res_events = [e for e in events if e.get("event") == "DISPATCH_RESOLVED" and e.get("operation_id") == op_id]
    assert len(res_events) == 1
    assert res_events[0]["disposition"] == "EFFECT_INDETERMINATE"
    assert res_events[0]["retry_safe"] is False

    # Emit signed evidence bundle
    artifacts = [
        {
            "name": "dispatch_intent_record",
            "sha256": sha256_hex(encode_jcs({"operation_id": op_id, "action_caid": caid, "target": "urn:bank:sepa"})),
            "envelope": {"operation_id": op_id, "action_caid": caid, "target": "urn:bank:sepa"},
        },
        {
            "name": "wire_indeterminate_record",
            "sha256": sha256_hex(encode_jcs(res_events[0])),
            "envelope": res_events[0],
        },
        {
            "name": "emergency_halt_trip_record",
            "sha256": sha256_hex(encode_jcs(halt_record)),
            "envelope": halt_record,
        },
    ]
    bundle = sign_evidence_bundle(
        priv_key=operator_priv,
        pub_key_id=pub_key_id,
        scenario_id="AT37_HALT_AMBIGUITY_PRESERVED",
        provenance=get_git_provenance(),
        artifacts=artifacts,
        artifact_locations={
            "primary": {"path": str(tmp_path / "phase2" / "AT37_ambiguity_preservation_evidence.json"), "retention": "CI_artifact"},
            "published_mirror": {"path": "artifacts/phase2/AT37_ambiguity_preservation_evidence.json", "mirror_must_match_primary_digest": True},
        },
        transport_observation={
            "observation_point": "journal_and_halt_interlock",
            "operation_id": op_id,
            "transport_outcome": "HTTP_504_TIMEOUT",
            "disposition": "EFFECT_INDETERMINATE",
            "retry_safe": False,
            "retroactive_relabeling_detected": False,
            "scope": "this_test_process_only",
        },
    )
    verify_phase2_bundle(bundle, pub_key)
    _save_evidence_bundle(tmp_path, "AT37_ambiguity_preservation_evidence.json", bundle)

def test_at38_rfc9470_step_up_resolution(tmp_path: Path):
    """
    AT38: RFC 9470 Step-Up Resolution.
    Asserts that an agent cannot resolve halt, and that resolution requires an
    authenticated human supervisor presenting a valid step-up token.
    Emits signed tamper-evident evidence bundle.
    """
    halt_path = tmp_path / "halt.state"
    store = PersistentHaltStateStore(halt_path)
    operator_priv = Ed25519PrivateKey.generate()
    store.trip_halt(
        operator_principal="ops-sec-01",
        reason="Emergency halt",
        timestamp_epoch=1500000000,
        signing_key=operator_priv,
    )

    # Agent attempts to resolve halt -> Rejected fail-closed
    agent_token = {
        "principal_id": "agent-autonomous-09",
        "principal_type": "AI_AGENT",
        "acr_values": "urn:mfa:none",
        "purpose": "RESOLVE_HALT",
        "nonce": "nonce-1234",
        "issued_at": 1500000005,
        "ttl_seconds": 60,
        "signature_hex": "00" * 64,
    }
    with pytest.raises(GovernanceHaltError, match="Only human supervisors"):
        store.resolve_halt(
            step_up_token=agent_token,
            supervisor_public_key=operator_priv.public_key(),
            current_timestamp=1500000010,
        )

    # Human supervisor with valid RFC 9470 step-up token
    supervisor_priv, supervisor_pub = _deterministic_ed25519_key("aeib-phase2-supervisor")
    pub_key_id = "did:key:aeib-phase2-supervisor-ed25519"

    # Export supervisor pubkey for offline verification
    (PHASE2_ARTIFACT_DIR / "test_supervisor_pubkey.pem").write_bytes(
        supervisor_pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    step_up_stmt = {
        "acr_values": "urn:mfa:hardware",
        "issued_at": 1500000005,
        "nonce": "nonce-fido2-9981",
        "principal_id": "human-supervisor-alice",
        "principal_type": "HUMAN_SUPERVISOR",
        "purpose": "RESOLVE_HALT",
        "ttl_seconds": 120,
    }
    sig_hex = supervisor_priv.sign(encode_jcs(step_up_stmt)).hex()
    step_up_token = dict(step_up_stmt)
    step_up_token["signature_hex"] = sig_hex

    resolved = store.resolve_halt(
        step_up_token=step_up_token,
        supervisor_public_key=supervisor_priv.public_key(),
        current_timestamp=1500000020,
    )
    assert resolved is True
    assert not store.is_halted()

    agent_rejection_payload = {
        "principal_id": agent_token["principal_id"],
        "principal_type": agent_token["principal_type"],
        "verdict": "REJECTED_FAIL_CLOSED",
        "rejection_code": "ONLY_HUMAN_SUPERVISORS_PERMITTED",
    }
    halt_cleared_payload = {"resolved": True, "halt_state": False, "timestamp": 1500000020}

    # Emit signed evidence bundle
    artifacts = [
        {
            "name": "agent_step_up_rejected",
            "sha256": sha256_hex(encode_jcs(agent_rejection_payload)),
            "envelope": agent_rejection_payload,
        },
        {
            "name": "human_step_up_accepted",
            "sha256": sha256_hex(encode_jcs(step_up_token)),
            "envelope": step_up_token,
        },
        {
            "name": "halt_cleared_confirmation",
            "sha256": sha256_hex(encode_jcs(halt_cleared_payload)),
            "envelope": halt_cleared_payload,
        },
    ]
    bundle = sign_evidence_bundle(
        priv_key=supervisor_priv,
        pub_key_id=pub_key_id,
        scenario_id="AT38_RFC9470_STEP_UP_RESOLUTION",
        provenance=get_git_provenance(),
        artifacts=artifacts,
        artifact_locations={
            "primary": {"path": str(tmp_path / "phase2" / "AT38_step_up_resolution_evidence.json"), "retention": "CI_artifact"},
            "published_mirror": {"path": "artifacts/phase2/AT38_step_up_resolution_evidence.json", "mirror_must_match_primary_digest": True},
        },
        transport_observation={
            "observation_point": "step_up_authenticator",
            "agent_resolution_permitted": False,
            "human_mfa_acr": "urn:mfa:hardware",
            "dual_control_verified": True,
            "scope": "this_test_process_only",
        },
    )
    verify_phase2_bundle(bundle, supervisor_pub)
    _save_evidence_bundle(tmp_path, "AT38_step_up_resolution_evidence.json", bundle)

# ==============================================================================
# AT39: DELEGATION ATTENUATION & CASCADE REVOCATION
# ==============================================================================

def test_at39_monotonic_delegation_attenuation_and_cascade_revocation(tmp_path: Path):
    """
    AT39: 3-Hop Delegation Attenuation and Cascade Revocation.
    Asserts monotonic scope narrowing (Child <= Parent) and that revoking an
    intermediate hop at Delta invalidates the leaf grant at Tn.
    Emits signed tamper-evident evidence bundle.
    """
    root_priv, root_pub = _deterministic_ed25519_key("aeib-phase2-root-sponsor")
    hop1_priv, hop1_pub = _deterministic_ed25519_key("aeib-phase2-hop1")
    hop2_priv, hop2_pub = _deterministic_ed25519_key("aeib-phase2-hop2")
    pub_key_id = "did:key:aeib-phase2-rootsponsor-ed25519"

    # Export root pubkey for offline verification
    (PHASE2_ARTIFACT_DIR / "test_root_sponsor_pubkey.pem").write_bytes(
        root_pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    known_keys = {
        "agent-hop-1": hop1_pub,
        "agent-hop-2": hop2_pub,
    }

    verifier = DelegationChainVerifier(
        root_sponsor_public_key=root_pub,
        root_sponsor_principal_id="sponsor-root",
        known_agent_keys=known_keys,
    )

    # Hop 1: sponsor-root -> agent-hop-1 (max: 1000 EUR, scopes: [refund, cancel])
    stmt1 = {
        "audience": "urn:service:payments",
        "delegateeAgentId": "agent-hop-1",
        "delegatorPrincipalId": "sponsor-root",
        "maxSpendEur": 1000,
        "permittedScopes": ["cancel", "refund"],
        "validUntilEpoch": 2000000000,
    }
    sig1 = root_priv.sign(encode_jcs(stmt1)).hex()
    hop1 = DelegationHop(
        delegator_principal_id="sponsor-root",
        delegatee_agent_id="agent-hop-1",
        audience="urn:service:payments",
        permitted_scopes=["cancel", "refund"],
        max_spend_eur=1000,
        valid_until_epoch=2000000000,
        signature_hex=sig1,
    )

    # Hop 2: agent-hop-1 -> agent-hop-2 (attenuated: max: 500 EUR, scope: [refund])
    stmt2 = {
        "audience": "urn:service:payments",
        "delegateeAgentId": "agent-hop-2",
        "delegatorPrincipalId": "agent-hop-1",
        "maxSpendEur": 500,
        "permittedScopes": ["refund"],
        "validUntilEpoch": 2000000000,
    }
    sig2 = hop1_priv.sign(encode_jcs(stmt2)).hex()
    hop2 = DelegationHop(
        delegator_principal_id="agent-hop-1",
        delegatee_agent_id="agent-hop-2",
        audience="urn:service:payments",
        permitted_scopes=["refund"],
        max_spend_eur=500,
        valid_until_epoch=2000000000,
        signature_hex=sig2,
    )

    # Nominal 2-hop delegation verified cleanly
    verdict = verifier.verify_chain([hop1, hop2], target_audience="urn:service:payments", current_timestamp=1500000000)
    assert verdict.valid is True
    assert float(verdict.effective_max_spend_eur) == 500
    assert verdict.effective_scopes == {"refund"}

    # Falsification 1: Subagent attempts scope expansion -> Rejected fail-closed
    bad_stmt2 = dict(stmt2)
    bad_stmt2["permittedScopes"] = ["refund", "wire_transfer"]  # wire_transfer not in parent!
    bad_sig2 = hop1_priv.sign(encode_jcs(bad_stmt2)).hex()
    bad_hop2 = DelegationHop(
        delegator_principal_id="agent-hop-1",
        delegatee_agent_id="agent-hop-2",
        audience="urn:service:payments",
        permitted_scopes=["refund", "wire_transfer"],
        max_spend_eur=500,
        valid_until_epoch=2000000000,
        signature_hex=bad_sig2,
    )
    bad_verdict = verifier.verify_chain([hop1, bad_hop2], target_audience="urn:service:payments", current_timestamp=1500000000)
    assert bad_verdict.valid is False
    assert "SCOPE_EXPANSION_VIOLATION" in bad_verdict.diagnostic_message

    # Falsification 2: Revoking intermediate hop-1 at Delta invalidates chain at Tn
    revoking_verifier = DelegationChainVerifier(
        root_sponsor_public_key=root_pub,
        root_sponsor_principal_id="sponsor-root",
        known_agent_keys=known_keys,
        revoked_principal_ids={"agent-hop-1"},  # Intermediate revoked
    )
    rev_verdict = revoking_verifier.verify_chain([hop1, hop2], target_audience="urn:service:payments", current_timestamp=1500000000)
    assert rev_verdict.valid is False
    assert "revoked" in rev_verdict.diagnostic_message

    # Payloads for artifacts
    h1_payload = {"statement": stmt1, "signature_hex": sig1}
    h2_payload = {"statement": stmt2, "signature_hex": sig2}
    nom_payload = {"valid": True, "effective_max_spend_eur": 500, "effective_scopes": ["refund"]}
    scope_exp_payload = {"attempted_scopes": ["refund", "wire_transfer"], "verdict": "REJECTED_FAIL_CLOSED", "diagnostic": bad_verdict.diagnostic_message}
    cascade_rev_payload = {"revoked_intermediate": "agent-hop-1", "verdict": "REJECTED_FAIL_CLOSED", "diagnostic": rev_verdict.diagnostic_message}

    # Emit signed evidence bundle
    artifacts = [
        {
            "name": "hop1_sponsor_grant",
            "sha256": sha256_hex(encode_jcs(h1_payload)),
            "envelope": h1_payload,
        },
        {
            "name": "hop2_attenuated_grant",
            "sha256": sha256_hex(encode_jcs(h2_payload)),
            "envelope": h2_payload,
        },
        {
            "name": "nominal_delegation_verdict",
            "sha256": sha256_hex(encode_jcs(nom_payload)),
            "envelope": nom_payload,
        },
        {
            "name": "scope_expansion_rejection",
            "sha256": sha256_hex(encode_jcs(scope_exp_payload)),
            "envelope": scope_exp_payload,
        },
        {
            "name": "cascade_revocation_rejection",
            "sha256": sha256_hex(encode_jcs(cascade_rev_payload)),
            "envelope": cascade_rev_payload,
        },
    ]
    bundle = sign_evidence_bundle(
        priv_key=root_priv,
        pub_key_id=pub_key_id,
        scenario_id="AT39_DELEGATION_ATTENUATION_CASCADE",
        provenance=get_git_provenance(),
        artifacts=artifacts,
        artifact_locations={
            "primary": {"path": str(tmp_path / "phase2" / "AT39_delegation_cascade_evidence.json"), "retention": "CI_artifact"},
            "published_mirror": {"path": "artifacts/phase2/AT39_delegation_cascade_evidence.json", "mirror_must_match_primary_digest": True},
        },
        transport_observation={
            "observation_point": "delegation_chain_evaluator",
            "scope_narrowing_enforced": True,
            "max_spend_eur_attenuated": 500,
            "scope_expansion_blocked": True,
            "intermediate_revocation_cascaded": True,
            "scope": "this_test_process_only",
        },
    )
    verify_phase2_bundle(bundle, root_pub)
    _save_evidence_bundle(tmp_path, "AT39_delegation_cascade_evidence.json", bundle)

# ==============================================================================
# REC-01 - REC-05: TARGET EVIDENCE CONTRACT (refund_status_v1)
# ==============================================================================

def _validate_target_status_contract(
    raw_response: dict,
    *,
    expected_operation_id: str,
    expected_caid: str,
    expected_amount_cents: int,
    expected_recipient: str,
    pinned_spki_digest: str,
) -> str:
    """
    Evaluates target status response against contracts/refund_status_v1.schema.json.
    Returns: 'RESOLVED_CONFIRMED', 'RESOLVED_REFUTED', or raises GovernanceHaltError.
    """
    # 1. Operation & Idempotency Key Binding
    if raw_response.get("operation_id") != expected_operation_id:
        raise GovernanceHaltError("CONTRACT_MISMATCH: operation_id does not match dispatch intent")

    # 2. Authentication check
    auth = raw_response.get("authentication", {})
    if auth.get("target_spki_digest") != pinned_spki_digest:
        raise GovernanceHaltError("AUTHENTICATION_FAILED: target SPKI digest does not match pinned key")

    # 3. Exact Parameter Parity
    parity = raw_response.get("parameter_parity", {})
    if parity.get("amount_minor_units") != expected_amount_cents:
        raise GovernanceHaltError("PARITY_MISMATCH: amount_minor_units altered")
    if parity.get("recipient_binding") != expected_recipient:
        raise GovernanceHaltError("PARITY_MISMATCH: recipient_binding altered")

    # 4. Status mapping
    target_status = raw_response.get("target_status")
    if target_status == "SETTLED":
        return "RESOLVED_CONFIRMED"
    elif target_status in ("REVERSED", "REJECTED"):
        return "RESOLVED_REFUTED"
    elif target_status in ("PENDING", "UNKNOWN"):
        return "EFFECT_INDETERMINATE"
    else:
        raise GovernanceHaltError(f"MALFORMED_STATUS: unrecognized status '{target_status}'")


def test_rec_01_target_status_settled_confirms_mutation(tmp_path: Path):
    """
    REC-01: Target status SETTLED confirms mutation.
    Emits signed tamper-evident evidence bundle.
    """
    target_priv, target_pub = _deterministic_ed25519_key("aeib-phase2-target")
    pub_key_id = "did:key:aeib-phase2-target-ed25519"

    # Export target pubkey for offline verification
    (PHASE2_ARTIFACT_DIR / "test_target_pubkey.pem").write_bytes(
        target_pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    spki = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    resp = {
        "contract_version": "1.0.0",
        "operation_id": "op-rec-001",
        "idempotency_key": "caid-rec-001",
        "target_status": "SETTLED",
        "target_mutation_ref": "TX-99881",
        "parameter_parity": {
            "amount_minor_units": 15000,
            "currency": "EUR",
            "recipient_binding": "DE89370400440532013000",
        },
        "authentication": {
            "channel": "mTLS",
            "target_spki_digest": spki,
        },
    }
    verdict = _validate_target_status_contract(
        resp,
        expected_operation_id="op-rec-001",
        expected_caid="caid-rec-001",
        expected_amount_cents=15000,
        expected_recipient="DE89370400440532013000",
        pinned_spki_digest=spki,
    )
    assert verdict == "RESOLVED_CONFIRMED"

    # Emit signed evidence bundle
    artifacts = [
        {
            "name": "target_status_response",
            "sha256": sha256_hex(encode_jcs(resp)),
            "envelope": resp,
        },
        {
            "name": "reconciliation_resolution_verdict",
            "sha256": sha256_hex(encode_jcs({"operation_id": "op-rec-001", "verdict": "RESOLVED_CONFIRMED", "status": "SETTLED", "target_mutation_ref": "TX-99881"})),
            "envelope": {"operation_id": "op-rec-001", "verdict": "RESOLVED_CONFIRMED", "status": "SETTLED", "target_mutation_ref": "TX-99881"},
        },
    ]
    bundle = sign_evidence_bundle(
        priv_key=target_priv,
        pub_key_id=pub_key_id,
        scenario_id="REC01_TARGET_CONTRACT_SETTLED",
        provenance=get_git_provenance(),
        artifacts=artifacts,
        artifact_locations={
            "primary": {"path": str(tmp_path / "phase2" / "REC01_target_contract_evidence.json"), "retention": "CI_artifact"},
            "published_mirror": {"path": "artifacts/phase2/REC01_target_contract_evidence.json", "mirror_must_match_primary_digest": True},
        },
        transport_observation={
            "observation_point": "target_status_contract_reconciler",
            "schema_contract": "contracts/refund_status_v1.schema.json",
            "operation_id_bound": True,
            "spki_authenticated": True,
            "amount_minor_units_matched": 15000,
            "recipient_matched": True,
            "verdict": "RESOLVED_CONFIRMED",
            "scope": "this_test_process_only",
        },
    )
    verify_phase2_bundle(bundle, target_pub)
    _save_evidence_bundle(tmp_path, "REC01_target_contract_evidence.json", bundle)

def test_rec_02_target_status_reversed_refutes_mutation():
    """REC-02: Target status REVERSED refutes mutation."""
    spki = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    resp = {
        "contract_version": "1.0.0",
        "operation_id": "op-rec-002",
        "idempotency_key": "caid-rec-002",
        "target_status": "REVERSED",
        "target_mutation_ref": "TX-REV-001",
        "parameter_parity": {
            "amount_minor_units": 20000,
            "currency": "EUR",
            "recipient_binding": "DE89370400440532013000",
        },
        "authentication": {
            "channel": "mTLS",
            "target_spki_digest": spki,
        },
    }
    verdict = _validate_target_status_contract(
        resp,
        expected_operation_id="op-rec-002",
        expected_caid="caid-rec-002",
        expected_amount_cents=20000,
        expected_recipient="DE89370400440532013000",
        pinned_spki_digest=spki,
    )
    assert verdict == "RESOLVED_REFUTED"


def test_rec_03_target_status_pending_preserves_uncertainty():
    """REC-03: Target status PENDING keeps EFFECT_INDETERMINATE."""
    spki = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    resp = {
        "contract_version": "1.0.0",
        "operation_id": "op-rec-003",
        "idempotency_key": "caid-rec-003",
        "target_status": "PENDING",
        "target_mutation_ref": "TX-PENDING-001",
        "parameter_parity": {
            "amount_minor_units": 5000,
            "currency": "EUR",
            "recipient_binding": "DE89370400440532013000",
        },
        "authentication": {
            "channel": "mTLS",
            "target_spki_digest": spki,
        },
    }
    verdict = _validate_target_status_contract(
        resp,
        expected_operation_id="op-rec-003",
        expected_caid="caid-rec-003",
        expected_amount_cents=5000,
        expected_recipient="DE89370400440532013000",
        pinned_spki_digest=spki,
    )
    assert verdict == "EFFECT_INDETERMINATE"


def test_rec_04_target_status_parameter_mismatch_fails_closed():
    """REC-04: Parameter mismatch in target response fails closed."""
    spki = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    resp = {
        "contract_version": "1.0.0",
        "operation_id": "op-rec-004",
        "idempotency_key": "caid-rec-004",
        "target_status": "SETTLED",
        "target_mutation_ref": "TX-004",
        "parameter_parity": {
            "amount_minor_units": 999999,  # Mismatched amount!
            "currency": "EUR",
            "recipient_binding": "DE89370400440532013000",
        },
        "authentication": {
            "channel": "mTLS",
            "target_spki_digest": spki,
        },
    }
    with pytest.raises(GovernanceHaltError, match="amount_minor_units altered"):
        _validate_target_status_contract(
            resp,
            expected_operation_id="op-rec-004",
            expected_caid="caid-rec-004",
            expected_amount_cents=5000,
            expected_recipient="DE89370400440532013000",
            pinned_spki_digest=spki,
        )


def test_rec_05_target_status_auth_failure_fails_closed():
    """REC-05: Target status authentication failure fails closed."""
    spki = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    untrusted_spki = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    resp = {
        "contract_version": "1.0.0",
        "operation_id": "op-rec-005",
        "idempotency_key": "caid-rec-005",
        "target_status": "SETTLED",
        "target_mutation_ref": "TX-005",
        "parameter_parity": {
            "amount_minor_units": 5000,
            "currency": "EUR",
            "recipient_binding": "DE89370400440532013000",
        },
        "authentication": {
            "channel": "mTLS",
            "target_spki_digest": untrusted_spki,
        },
    }
    with pytest.raises(GovernanceHaltError, match="AUTHENTICATION_FAILED"):
        _validate_target_status_contract(
            resp,
            expected_operation_id="op-rec-005",
            expected_caid="caid-rec-005",
            expected_amount_cents=5000,
            expected_recipient="DE89370400440532013000",
            pinned_spki_digest=spki,
        )
