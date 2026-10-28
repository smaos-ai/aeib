"""
tests/test_tier2_delegation_and_profile.py
Tests verifying the Tier 2 Delegation Chain Verifier and Signed Deployment Profile:
  1. Delegation chain verification:
     - 1-hop valid delegation from root sponsor.
     - 3-hop valid attenuated delegation chain.
     - Scope expansion attack (child attempts to claim unapproved scope) -> fail-closed rejection.
     - Budget expansion attack (child attempts to increase spend ceiling) -> fail-closed rejection.
     - Broken chain linkage (delegator does not match prior delegatee) -> fail-closed rejection.
     - Invalid cryptographic signature on intermediate hop -> fail-closed rejection.
     - Expired hop or expiry expansion violation -> fail-closed rejection.
     - Revoked delegator in chain -> fail-closed rejection.
     - Target audience mismatch -> fail-closed rejection.
  2. Signed Deployment Profile evaluation:
     - Operator-signed profile verification and canonical digest derivation.
     - Tampered signature raises DeploymentProfileError at instantiation.
     - Unlisted target URL rejected fail-closed.
     - Explicitly denied action rejected fail-closed.
     - Spend limit exceeded rejected fail-closed.
     - Valid candidate action allowed with profile digest and epoch bound.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Dict, List

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.jcs_canonicalizer import encode_jcs

REPO_ROOT = Path(__file__).resolve().parents[1]
DELEGATION_PATH = REPO_ROOT / "v1.1-roadmap" / "delegation_chain_verifier.py"
PROFILE_PATH = REPO_ROOT / "v1.1-roadmap" / "signed_deployment_profile.py"

spec_del = importlib.util.spec_from_file_location("delegation_chain_verifier", DELEGATION_PATH)
assert spec_del is not None and spec_del.loader is not None
del_mod = importlib.util.module_from_spec(spec_del)
sys.modules["delegation_chain_verifier"] = del_mod
spec_del.loader.exec_module(del_mod)

spec_prof = importlib.util.spec_from_file_location("signed_deployment_profile", PROFILE_PATH)
assert spec_prof is not None and spec_prof.loader is not None
prof_mod = importlib.util.module_from_spec(spec_prof)
sys.modules["signed_deployment_profile"] = prof_mod
spec_prof.loader.exec_module(prof_mod)

DelegationChainVerifier = del_mod.DelegationChainVerifier
DelegationHop = del_mod.DelegationHop
SignedDeploymentProfile = prof_mod.SignedDeploymentProfile
DeploymentProfileEvaluator = prof_mod.DeploymentProfileEvaluator
DeploymentProfileError = prof_mod.DeploymentProfileError


def _mint_hop(
    signing_key: Ed25519PrivateKey,
    *,
    delegator_principal_id: str,
    delegatee_agent_id: str,
    audience: str,
    permitted_scopes: List[str],
    max_spend_eur: int,
    valid_until_epoch: int,
) -> DelegationHop:
    raw_stmt = {
        "audience": audience,
        "delegateeAgentId": delegatee_agent_id,
        "delegatorPrincipalId": delegator_principal_id,
        "maxSpendEur": max_spend_eur,
        "permittedScopes": sorted(permitted_scopes),
        "validUntilEpoch": valid_until_epoch,
    }
    stmt_bytes = encode_jcs(raw_stmt)
    sig_hex = signing_key.sign(stmt_bytes).hex()
    return DelegationHop(
        delegator_principal_id=delegator_principal_id,
        delegatee_agent_id=delegatee_agent_id,
        audience=audience,
        permitted_scopes=permitted_scopes,
        max_spend_eur=max_spend_eur,
        valid_until_epoch=valid_until_epoch,
        signature_hex=sig_hex,
    )


# ==============================================================================
# DELEGATION CHAIN VERIFIER TESTS
# ==============================================================================

def test_01_three_hop_valid_attenuated_delegation_chain() -> None:
    """1. Evaluates a valid 3-hop delegation chain with monotonic scope/spend attenuation."""
    root_key = Ed25519PrivateKey.generate()
    agent1_key = Ed25519PrivateKey.generate()
    agent2_key = Ed25519PrivateKey.generate()

    known_keys = {
        "agent_manager": agent1_key.public_key(),
        "agent_worker": agent2_key.public_key(),
    }

    verifier = DelegationChainVerifier(
        root_sponsor_public_key=root_key.public_key(),
        root_sponsor_principal_id="human_sponsor_root",
        known_agent_keys=known_keys,
    )

    # Hop 0: Root Sponsor -> Agent Manager
    hop0 = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="agent_manager",
        audience="https://api.bank.internal/transfer",
        permitted_scopes=["accounts:read", "transfers:write", "audit:log"],
        max_spend_eur=10000,
        valid_until_epoch=2000000000,
    )

    # Hop 1: Agent Manager -> Agent Worker (narrows scope and spend)
    hop1 = _mint_hop(
        agent1_key,
        delegator_principal_id="agent_manager",
        delegatee_agent_id="agent_worker",
        audience="https://api.bank.internal/transfer",
        permitted_scopes=["accounts:read", "transfers:write"],
        max_spend_eur=5000,
        valid_until_epoch=1999990000,
    )

    # Hop 2: Agent Worker -> Task Executor (narrows further)
    hop2 = _mint_hop(
        agent2_key,
        delegator_principal_id="agent_worker",
        delegatee_agent_id="task_executor_leaf",
        audience="https://api.bank.internal/transfer",
        permitted_scopes=["transfers:write"],
        max_spend_eur=500,
        valid_until_epoch=1999980000,
    )

    verdict = verifier.verify_chain(
        chain=[hop0, hop1, hop2],
        target_audience="https://api.bank.internal/transfer",
        current_timestamp=1000000000,
    )

    assert verdict.valid is True
    assert verdict.effective_scopes == {"transfers:write"}
    assert verdict.effective_max_spend_eur == 500
    assert verdict.delegation_depth == 3


def test_02_scope_expansion_attack_rejected_fail_closed() -> None:
    """2. Child attempting to grant unauthorized scope is rejected fail-closed."""
    root_key = Ed25519PrivateKey.generate()
    agent1_key = Ed25519PrivateKey.generate()

    verifier = DelegationChainVerifier(
        root_sponsor_public_key=root_key.public_key(),
        root_sponsor_principal_id="human_sponsor_root",
        known_agent_keys={"agent_1": agent1_key.public_key()},
    )

    hop0 = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="agent_1",
        audience="*",
        permitted_scopes=["read:only"],
        max_spend_eur=100,
        valid_until_epoch=2000000000,
    )

    # Child tries to expand to "admin:root_escalation"
    hop1 = _mint_hop(
        agent1_key,
        delegator_principal_id="agent_1",
        delegatee_agent_id="agent_2",
        audience="*",
        permitted_scopes=["read:only", "admin:root_escalation"],
        max_spend_eur=100,
        valid_until_epoch=2000000000,
    )

    verdict = verifier.verify_chain([hop0, hop1], target_audience="any_target", current_timestamp=1000)
    assert verdict.valid is False
    assert "SCOPE_EXPANSION_VIOLATION" in verdict.diagnostic_message


def test_03_budget_expansion_attack_rejected_fail_closed() -> None:
    """3. Child attempting to increase max spend ceiling is rejected fail-closed."""
    root_key = Ed25519PrivateKey.generate()
    agent1_key = Ed25519PrivateKey.generate()

    verifier = DelegationChainVerifier(
        root_sponsor_public_key=root_key.public_key(),
        root_sponsor_principal_id="human_sponsor_root",
        known_agent_keys={"agent_1": agent1_key.public_key()},
    )

    hop0 = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="agent_1",
        audience="*",
        permitted_scopes=["spend"],
        max_spend_eur=500,
        valid_until_epoch=2000000000,
    )

    # Child tries to increase spend to 1000 EUR
    hop1 = _mint_hop(
        agent1_key,
        delegator_principal_id="agent_1",
        delegatee_agent_id="agent_2",
        audience="*",
        permitted_scopes=["spend"],
        max_spend_eur=1000,
        valid_until_epoch=2000000000,
    )

    verdict = verifier.verify_chain([hop0, hop1], target_audience="any_target", current_timestamp=1000)
    assert verdict.valid is False
    assert "BUDGET_EXPANSION_VIOLATION" in verdict.diagnostic_message


def test_04_broken_chain_continuity_rejected() -> None:
    """4. Broken delegator-delegatee linkage is rejected."""
    root_key = Ed25519PrivateKey.generate()
    agent1_key = Ed25519PrivateKey.generate()

    verifier = DelegationChainVerifier(
        root_sponsor_public_key=root_key.public_key(),
        root_sponsor_principal_id="human_sponsor_root",
        known_agent_keys={"unrelated_agent": agent1_key.public_key()},
    )

    hop0 = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="agent_1",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2000000000,
    )

    # Hop 1 claims delegator is "unrelated_agent" instead of "agent_1"
    hop1 = _mint_hop(
        agent1_key,
        delegator_principal_id="unrelated_agent",
        delegatee_agent_id="agent_2",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2000000000,
    )

    verdict = verifier.verify_chain([hop0, hop1], target_audience="target", current_timestamp=1000)
    assert verdict.valid is False
    assert "CONTINUITY_BREAK" in verdict.diagnostic_message


def test_05_revoked_principal_rejected() -> None:
    """5. Revoked intermediate agent causes chain verification to fail closed."""
    root_key = Ed25519PrivateKey.generate()
    agent1_key = Ed25519PrivateKey.generate()

    verifier = DelegationChainVerifier(
        root_sponsor_public_key=root_key.public_key(),
        root_sponsor_principal_id="human_sponsor_root",
        known_agent_keys={"compromised_agent": agent1_key.public_key()},
        revoked_principal_ids={"compromised_agent"},
    )

    hop0 = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="compromised_agent",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2000000000,
    )

    hop1 = _mint_hop(
        agent1_key,
        delegator_principal_id="compromised_agent",
        delegatee_agent_id="agent_leaf",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2000000000,
    )

    verdict = verifier.verify_chain([hop0, hop1], target_audience="target", current_timestamp=1000)
    assert verdict.valid is False
    assert "REVOKED_DELEGATOR" in verdict.diagnostic_message


# ==============================================================================
# SIGNED DEPLOYMENT PROFILE TESTS
# ==============================================================================

def test_06_signed_deployment_profile_evaluation() -> None:
    """6. Validates operator-signed deployment profile rules and canonical digest derivation."""
    operator_key = Ed25519PrivateKey.generate()

    raw_profile = {
        "allowedTargets": ["https://api.bank.internal/wire", "mcp://core_banking"],
        "deniedActions": ["delete_audit_trail", "drop_database"],
        "maxSpendPerOpEur": 5000,
        "operatorPrincipalId": "secops_admin_01",
        "pinnedManifestDigest": "sha256:manifest_active_123",
        "policyEpoch": 42,
        "profileId": "prof_prod_2026",
        "validFromEpoch": 1000,
        "validUntilEpoch": 2000000000,
    }
    stmt_bytes = encode_jcs(raw_profile)
    sig_hex = operator_key.sign(stmt_bytes).hex()

    profile = SignedDeploymentProfile(
        profile_id="prof_prod_2026",
        policy_epoch=42,
        operator_principal_id="secops_admin_01",
        pinned_manifest_digest="sha256:manifest_active_123",
        allowed_targets=["https://api.bank.internal/wire", "mcp://core_banking"],
        denied_actions=["delete_audit_trail", "drop_database"],
        max_spend_per_op_eur=5000,
        valid_from_epoch=1000,
        valid_until_epoch=2000000000,
        signature_hex=sig_hex,
    )

    evaluator = DeploymentProfileEvaluator(
        operator_public_key=operator_key.public_key(),
        profile=profile,
    )

    # Permitted dispatch
    res1 = evaluator.evaluate_dispatch(
        target_identity="https://api.bank.internal/wire",
        action_name="execute_transfer",
        requested_spend_eur=1000,
        current_timestamp=5000,
    )
    assert res1.allowed is True
    assert res1.policy_epoch == 42
    assert res1.profile_digest.startswith("sha256:")

    # Denied action
    res2 = evaluator.evaluate_dispatch(
        target_identity="https://api.bank.internal/wire",
        action_name="delete_audit_trail",
        requested_spend_eur=0,
        current_timestamp=5000,
    )
    assert res2.allowed is False
    assert "ACTION_PROHIBITED" in res2.diagnostic_message

    # Unallowed target
    res3 = evaluator.evaluate_dispatch(
        target_identity="https://malicious.external.com/exfil",
        action_name="normal_read",
        requested_spend_eur=0,
        current_timestamp=5000,
    )
    assert res3.allowed is False
    assert "TARGET_NOT_ALLOWED" in res3.diagnostic_message

    # Spend limit exceeded
    res4 = evaluator.evaluate_dispatch(
        target_identity="https://api.bank.internal/wire",
        action_name="execute_transfer",
        requested_spend_eur=99999,
        current_timestamp=5000,
    )
    assert res4.allowed is False
    assert "SPEND_LIMIT_EXCEEDED" in res4.diagnostic_message


def test_07_tampered_profile_signature_raises_error() -> None:
    """7. Tampered profile signature is rejected during evaluator instantiation."""
    operator_key = Ed25519PrivateKey.generate()
    wrong_key = Ed25519PrivateKey.generate()

    raw_profile = {
        "allowedTargets": ["*"],
        "deniedActions": [],
        "maxSpendPerOpEur": 1000,
        "operatorPrincipalId": "secops",
        "pinnedManifestDigest": "sha256:0000",
        "policyEpoch": 1,
        "profileId": "prof_tampered",
        "validFromEpoch": 0,
        "validUntilEpoch": 2000000000,
    }
    stmt_bytes = encode_jcs(raw_profile)
    # Signed with wrong key
    sig_hex = wrong_key.sign(stmt_bytes).hex()

    profile = SignedDeploymentProfile(
        profile_id="prof_tampered",
        policy_epoch=1,
        operator_principal_id="secops",
        pinned_manifest_digest="sha256:0000",
        allowed_targets=["*"],
        denied_actions=[],
        max_spend_per_op_eur=1000,
        valid_from_epoch=0,
        valid_until_epoch=2000000000,
        signature_hex=sig_hex,
    )

    with pytest.raises(DeploymentProfileError, match="PROFILE_SIGNATURE_INVALID"):
        DeploymentProfileEvaluator(
            operator_public_key=operator_key.public_key(),
            profile=profile,
        )


def test_08_delegation_and_profile_exhaustive_boundary_and_error_variants() -> None:
    """8. Exhaustive boundary, frozen dataclass, sentinel, and error-path assertions."""
    import inspect

    root_key = Ed25519PrivateKey.generate()
    agent1_key = Ed25519PrivateKey.generate()
    wrong_key = Ed25519PrivateKey.generate()

    verifier = DelegationChainVerifier(
        root_sponsor_public_key=root_key.public_key(),
        root_sponsor_principal_id="human_sponsor_root",
        known_agent_keys={"agent_1": agent1_key.public_key()},
    )

    # Empty chain
    v_empty = verifier.verify_chain([], target_audience="aud", current_timestamp=1000)
    assert v_empty is not None
    assert v_empty.valid is False
    assert v_empty.effective_scopes == set()
    assert v_empty.effective_max_spend_eur == 0
    assert v_empty.delegation_depth == 0
    assert "CHAIN_EMPTY" in v_empty.diagnostic_message

    # Frozen dataclasses on DelegationHop and DelegationVerdict
    hop_base = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="agent_1",
        audience="https://api.bank.internal/transfer",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2000,
    )
    with pytest.raises(Exception):
        hop_base.max_spend_eur = 999  # type: ignore[misc]
    with pytest.raises(Exception):
        v_empty.valid = True  # type: ignore[misc]

    # Exact sentinel boundary (1 << 62) valid, (1 << 62) + 1 rejected
    sentinel_val = 1 << 62
    hop_sentinel_ok = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="agent_1",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=sentinel_val,
        valid_until_epoch=sentinel_val,
    )
    v_sent_ok = verifier.verify_chain([hop_sentinel_ok], target_audience="aud", current_timestamp=sentinel_val)
    assert v_sent_ok.valid is True
    assert v_sent_ok.effective_max_spend_eur == sentinel_val

    hop_sentinel_spend_over = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="agent_1",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=sentinel_val + 1,
        valid_until_epoch=sentinel_val,
    )
    v_sent_spend = verifier.verify_chain([hop_sentinel_spend_over], target_audience="aud", current_timestamp=1000)
    assert v_sent_spend.valid is False
    assert v_sent_spend.effective_max_spend_eur == 0
    assert v_sent_spend.delegation_depth == 0
    assert "BUDGET_EXPANSION_VIOLATION" in v_sent_spend.diagnostic_message

    hop_sentinel_exp_over = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="agent_1",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=sentinel_val + 1,
    )
    v_sent_exp = verifier.verify_chain([hop_sentinel_exp_over], target_audience="aud", current_timestamp=1000)
    assert v_sent_exp.valid is False
    assert v_sent_exp.effective_max_spend_eur == 0
    assert v_sent_exp.delegation_depth == 0
    assert "EXPIRY_EXPANSION_VIOLATION" in v_sent_exp.diagnostic_message

    # Hop expiration check (current_timestamp > valid_until_epoch)
    v_expired = verifier.verify_chain(
        [hop_base],
        target_audience="https://api.bank.internal/transfer",
        current_timestamp=2001,
    )
    assert v_expired is not None
    assert v_expired.valid is False
    assert v_expired.effective_max_spend_eur == 0
    assert v_expired.delegation_depth == 0
    assert "HOP_EXPIRED" in v_expired.diagnostic_message

    # Expiry expansion on hop 1
    hop1_exp_expand = _mint_hop(
        agent1_key,
        delegator_principal_id="agent_1",
        delegatee_agent_id="agent_2",
        audience="https://api.bank.internal/transfer",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2001,
    )
    v_exp_expand = verifier.verify_chain(
        [hop_base, hop1_exp_expand],
        target_audience="https://api.bank.internal/transfer",
        current_timestamp=1500,
    )
    assert v_exp_expand.valid is False
    assert v_exp_expand.effective_max_spend_eur == 0
    assert v_exp_expand.delegation_depth == 1
    assert "EXPIRY_EXPANSION_VIOLATION" in v_exp_expand.diagnostic_message

    # Audience mismatch
    v_aud = verifier.verify_chain(
        [hop_base],
        target_audience="https://wrong.audience.internal",
        current_timestamp=1500,
    )
    assert v_aud.valid is False
    assert v_aud.effective_max_spend_eur == 0
    assert v_aud.delegation_depth == 0
    assert "AUDIENCE_MISMATCH" in v_aud.diagnostic_message

    # Unknown signer key on hop 1
    hop0_unknown_delegate = _mint_hop(
        root_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="unregistered_agent",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2000,
    )
    hop1_from_unknown = _mint_hop(
        wrong_key,
        delegator_principal_id="unregistered_agent",
        delegatee_agent_id="leaf",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2000,
    )
    v_unknown_key = verifier.verify_chain(
        [hop0_unknown_delegate, hop1_from_unknown],
        target_audience="aud",
        current_timestamp=1500,
    )
    assert v_unknown_key.valid is False
    assert v_unknown_key.effective_max_spend_eur == 0
    assert v_unknown_key.delegation_depth == 1
    assert "UNKNOWN_SIGNER_KEY" in v_unknown_key.diagnostic_message

    # Invalid signature on hop 0
    hop_bad_sig = _mint_hop(
        wrong_key,
        delegator_principal_id="human_sponsor_root",
        delegatee_agent_id="agent_1",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2000,
    )
    v_bad_sig = verifier.verify_chain([hop_bad_sig], target_audience="aud", current_timestamp=1500)
    assert v_bad_sig.valid is False
    assert v_bad_sig.effective_max_spend_eur == 0
    assert v_bad_sig.delegation_depth == 0
    assert "SIGNATURE_INVALID" in v_bad_sig.diagnostic_message

    # Verify effective_max_spend_eur == 0 on continuity, scope, budget, and revocation errors
    hop1_continuity = _mint_hop(
        agent1_key,
        delegator_principal_id="wrong_delegator",
        delegatee_agent_id="agent_2",
        audience="*",
        permitted_scopes=["read"],
        max_spend_eur=100,
        valid_until_epoch=2000,
    )
    v_cont = verifier.verify_chain([hop_base, hop1_continuity], target_audience="https://api.bank.internal/transfer", current_timestamp=1500)
    assert v_cont.effective_max_spend_eur == 0
    assert v_cont.delegation_depth == 1

    hop1_scope = _mint_hop(
        agent1_key,
        delegator_principal_id="agent_1",
        delegatee_agent_id="agent_2",
        audience="https://api.bank.internal/transfer",
        permitted_scopes=["read", "write"],
        max_spend_eur=100,
        valid_until_epoch=2000,
    )
    v_scope = verifier.verify_chain([hop_base, hop1_scope], target_audience="https://api.bank.internal/transfer", current_timestamp=1500)
    assert v_scope.effective_max_spend_eur == 0
    assert v_scope.delegation_depth == 1

    hop1_budget = _mint_hop(
        agent1_key,
        delegator_principal_id="agent_1",
        delegatee_agent_id="agent_2",
        audience="https://api.bank.internal/transfer",
        permitted_scopes=["read"],
        max_spend_eur=200,
        valid_until_epoch=2000,
    )
    v_budget = verifier.verify_chain([hop_base, hop1_budget], target_audience="https://api.bank.internal/transfer", current_timestamp=1500)
    assert v_budget.effective_max_spend_eur == 0
    assert v_budget.delegation_depth == 1

    revoked_verifier = DelegationChainVerifier(
        root_sponsor_public_key=root_key.public_key(),
        root_sponsor_principal_id="human_sponsor_root",
        known_agent_keys={"agent_1": agent1_key.public_key()},
        revoked_principal_ids={"agent_1"},
    )
    v_rev = revoked_verifier.verify_chain([hop_base, hop1_scope], target_audience="https://api.bank.internal/transfer", current_timestamp=1500)
    assert v_rev.effective_max_spend_eur == 0
    assert v_rev.delegation_depth == 1

    # SignedDeploymentProfile frozen dataclass & temporal / default-spend boundaries
    op_key = Ed25519PrivateKey.generate()
    raw_zero_profile = {
        "allowedTargets": ["https://api.bank.internal/wire"],
        "deniedActions": ["forbidden_op"],
        "maxSpendPerOpEur": 0,
        "operatorPrincipalId": "secops_admin",
        "pinnedManifestDigest": "sha256:manifest_0",
        "policyEpoch": 7,
        "profileId": "prof_zero",
        "validFromEpoch": 1000,
        "validUntilEpoch": 2000,
    }
    sig_zero = op_key.sign(encode_jcs(raw_zero_profile)).hex()
    prof_zero = SignedDeploymentProfile(
        profile_id="prof_zero",
        policy_epoch=7,
        operator_principal_id="secops_admin",
        pinned_manifest_digest="sha256:manifest_0",
        allowed_targets=["https://api.bank.internal/wire"],
        denied_actions=["forbidden_op"],
        max_spend_per_op_eur=0,
        valid_from_epoch=1000,
        valid_until_epoch=2000,
        signature_hex=sig_zero,
    )
    with pytest.raises(Exception):
        prof_zero.policy_epoch = 8  # type: ignore[misc]

    eval_zero = DeploymentProfileEvaluator(
        operator_public_key=op_key.public_key(),
        profile=prof_zero,
    )
    assert inspect.signature(eval_zero.evaluate_dispatch).parameters["requested_spend_eur"].default == 0

    # Default requested_spend_eur=0 succeeds at boundary timestamps 1000 and 2000
    res_at_start = eval_zero.evaluate_dispatch(
        target_identity="https://api.bank.internal/wire",
        action_name="read_balance",
        current_timestamp=1000,
    )
    assert res_at_start is not None
    assert res_at_start.allowed is True
    with pytest.raises(Exception):
        res_at_start.allowed = False  # type: ignore[misc]

    res_at_end = eval_zero.evaluate_dispatch(
        target_identity="https://api.bank.internal/wire",
        action_name="read_balance",
        current_timestamp=2000,
    )
    assert res_at_end.allowed is True

    # Before valid_from_epoch -> PROFILE_NOT_YET_ACTIVE
    res_before = eval_zero.evaluate_dispatch(
        target_identity="https://api.bank.internal/wire",
        action_name="read_balance",
        current_timestamp=999,
    )
    assert res_before is not None
    assert res_before.allowed is False
    assert "PROFILE_NOT_YET_ACTIVE" in res_before.diagnostic_message

    # After valid_until_epoch -> PROFILE_EXPIRED
    res_after = eval_zero.evaluate_dispatch(
        target_identity="https://api.bank.internal/wire",
        action_name="read_balance",
        current_timestamp=2001,
    )
    assert res_after is not None
    assert res_after.allowed is False
    assert "PROFILE_EXPIRED" in res_after.diagnostic_message

