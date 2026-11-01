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
tests/test_border_policy.py
================================================================================
Comprehensive verification suite for pure predicates in `src/border_policy.py`
and durable orchestration in `src/durable_border_enforcer.py`.
"""

import time
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.border_policy import (
    BorderVerdict,
    CancelledAtState,
    PolicyManifest,
    SignedHumanActionWarrant,
    TaintTier,
    TaskEscortState,
    canonical_json_v1,
    compute_action_caid,
    evaluate_action_admissibility,
    evaluate_payment_limits,
    evaluate_taint_lattice,
    is_payment_shaped,
    issue_human_warrant,
    sha256_hex_prefixed,
)
from src.durable_border_enforcer import DurableBorderEnforcer


@pytest.fixture
def sample_policy() -> PolicyManifest:
    return PolicyManifest(
        policy_version="aeib_border_policy_v1",
        tenant_id="tenant-ua-pl-crossborder",
        agent_id="agent-settlement-escort",
        allowed=frozenset({"read_invoice", "classify_invoice", "draft_payment", "lookup_catalog"}),
        forbidden_without_human=frozenset({"execute_payment", "delete_record", "purge_ledger"}),
        forbidden_always=frozenset({"self_modify_policy", "bypass_approval", "exfiltrate_keys"}),
        max_amount_minor_units=100_000,
        allowed_currencies=frozenset({"EUR", "PLN", "UAH"}),
        pinned_recipients=frozenset({"ukrpost_clearing", "poczta_polska_hub", "vendor_77"}),
    )


@pytest.fixture
def human_keys() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    priv = Ed25519PrivateKey.generate()
    return priv, priv.public_key()


def test_1_canonical_json_and_caid_determinism() -> None:
    payload = {"z_key": 1, "a_key": "val", "nested": {"b": [1, 2], "a": "x"}}
    encoded1 = canonical_json_v1(payload)
    encoded2 = canonical_json_v1({"nested": {"a": "x", "b": [1, 2]}, "a_key": "val", "z_key": 1})
    assert encoded1 == encoded2
    assert sha256_hex_prefixed(encoded1) == sha256_hex_prefixed(encoded2)

    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"score": float("nan")})

    with pytest.raises(ValueError, match="ERR_NON_STRING_KEY"):
        canonical_json_v1({123: "invalid"})


def test_2_is_payment_shaped_keys() -> None:
    assert is_payment_shaped({"amount_minor": 100}) is True
    assert is_payment_shaped({"currency": "EUR"}) is True
    assert is_payment_shaped({"recipient_id": "r1"}) is True
    assert is_payment_shaped({"iban": "PL123"}) is True
    assert is_payment_shaped({"destination_account": "UA456"}) is True
    assert is_payment_shaped({"payee": "Alice"}) is True
    assert is_payment_shaped({"document_id": "doc_99", "format": "pdf"}) is False


def test_3_evaluate_taint_lattice(sample_policy: PolicyManifest) -> None:
    # 1. System/internal context with read-only query -> OK
    assert evaluate_taint_lattice("lookup_catalog", {}, sample_policy, TaintTier.TIER_0_SYSTEM) is None
    assert evaluate_taint_lattice("lookup_catalog", {}, sample_policy, TaintTier.TIER_1_INTERNAL) is None

    # 2. Untrusted external context with read-only query -> OK
    assert evaluate_taint_lattice("read_invoice", {"invoice_id": "i1"}, sample_policy, TaintTier.TIER_2_UNTRUSTED_EXTERNAL) is None

    # 3. Untrusted external context attempting payment-shaped draft -> BLOCKED
    taint_err = evaluate_taint_lattice(
        "draft_payment",
        {"amount_minor": 500, "currency": "EUR", "recipient_id": "vendor_77"},
        sample_policy,
        TaintTier.TIER_2_UNTRUSTED_EXTERNAL,
    )
    assert taint_err == "HALT_UNTRUSTED_CONTEXT_CANNOT_AUTHORIZE_MUTATION"

    # 4. Untrusted external context attempting forbidden_without_human -> BLOCKED
    taint_err2 = evaluate_taint_lattice("execute_payment", {}, sample_policy, TaintTier.TIER_2_UNTRUSTED_EXTERNAL)
    assert taint_err2 == "HALT_UNTRUSTED_CONTEXT_CANNOT_AUTHORIZE_MUTATION"


def test_4_evaluate_payment_limits(sample_policy: PolicyManifest) -> None:
    # 1. Non-payment shaped returns None
    assert evaluate_payment_limits("read_invoice", {"invoice_id": "123"}, sample_policy) is None

    # 2. Negative or out-of-bounds amounts
    assert evaluate_payment_limits("draft_payment", {"amount_minor": 0, "currency": "EUR", "recipient_id": "vendor_77"}, sample_policy) == "HALT_PAYMENT_AMOUNT_OUT_OF_BOUNDS"
    assert evaluate_payment_limits("draft_payment", {"amount_minor": -50, "currency": "EUR", "recipient_id": "vendor_77"}, sample_policy) == "HALT_PAYMENT_AMOUNT_OUT_OF_BOUNDS"
    assert evaluate_payment_limits("draft_payment", {"amount_minor": 200_000, "currency": "EUR", "recipient_id": "vendor_77"}, sample_policy) == "HALT_PAYMENT_AMOUNT_OUT_OF_BOUNDS"
    assert evaluate_payment_limits("draft_payment", {"amount_minor": True, "currency": "EUR", "recipient_id": "vendor_77"}, sample_policy) == "HALT_PAYMENT_AMOUNT_OUT_OF_BOUNDS"

    # 3. Disallowed currency
    assert evaluate_payment_limits("draft_payment", {"amount_minor": 500, "currency": "USD", "recipient_id": "vendor_77"}, sample_policy) == "HALT_PAYMENT_CURRENCY_NOT_ALLOWED"

    # 4. Unpinned recipient
    assert evaluate_payment_limits("draft_payment", {"amount_minor": 500, "currency": "EUR", "recipient_id": "unknown_hacker"}, sample_policy) == "HALT_PAYMENT_RECIPIENT_NOT_PINNED"

    # 5. Clean parameters return None
    assert evaluate_payment_limits("draft_payment", {"amount_minor": 500, "currency": "EUR", "recipient_id": "vendor_77"}, sample_policy) is None


def test_5_admissibility_pure_decision(
    sample_policy: PolicyManifest,
    human_keys: tuple[Ed25519PrivateKey, Ed25519PublicKey],
) -> None:
    priv, pub = human_keys
    now_ns = 1_000_000_000

    # 1. forbidden_always returns immediate HALT
    v_always = evaluate_action_admissibility("self_modify_policy", {}, sample_policy, now_ns)
    assert v_always.allowed is False
    assert "HALT_FORBIDDEN_ALWAYS_CAPABILITY" in v_always.reason_code

    # 2. Default-Deny for unlisted action
    v_unlisted = evaluate_action_admissibility("unlisted_backdoor", {}, sample_policy, now_ns)
    assert v_unlisted.allowed is False
    assert "DENY_DEFAULT_BORDER_POLICY" in v_unlisted.reason_code

    # 3. Allowlisted read-only
    v_read = evaluate_action_admissibility("read_invoice", {"invoice_id": "1"}, sample_policy, now_ns)
    assert v_read.allowed is True
    assert v_read.reason_code == "OK_ADMISSIBLE"

    # 4. execute_payment without warrant
    pay_args = {"amount_minor": 10_000, "currency": "UAH", "recipient_id": "ukrpost_clearing"}
    v_nowarrant = evaluate_action_admissibility("execute_payment", pay_args, sample_policy, now_ns)
    assert v_nowarrant.allowed is False
    assert "HALT_HUMAN_WARRANT_REQUIRED" in v_nowarrant.reason_code

    # 5. execute_payment with valid warrant
    caid = compute_action_caid("execute_payment", pay_args, sample_policy.tenant_id, sample_policy.agent_id)
    warrant = issue_human_warrant(
        warrant_id="w-01",
        nonce="nonce-001",
        tenant_id=sample_policy.tenant_id,
        action_name="execute_payment",
        action_caid=caid,
        expires_at_ns=now_ns + 5_000_000_000,
        human_priv_key=priv,
    )
    v_ok = evaluate_action_admissibility(
        "execute_payment",
        pay_args,
        sample_policy,
        now_ns,
        warrant=warrant,
        human_pub_key=pub,
    )
    assert v_ok.allowed is True
    assert v_ok.reason_code == "OK_ADMISSIBLE"

    # 6. execute_payment with burned nonce
    v_burned = evaluate_action_admissibility(
        "execute_payment",
        pay_args,
        sample_policy,
        now_ns,
        warrant=warrant,
        burned_nonces=frozenset({"nonce-001"}),
        human_pub_key=pub,
    )
    assert v_burned.allowed is False
    assert "HALT_WARRANT_NONCE_ALREADY_BURNED" in v_burned.reason_code

    # 7. Expired warrant
    v_expired = evaluate_action_admissibility(
        "execute_payment",
        pay_args,
        sample_policy,
        now_ns + 10_000_000_000,
        warrant=warrant,
        human_pub_key=pub,
    )
    assert v_expired.allowed is False
    assert "HALT_WARRANT_BINDING_OR_EXPIRY_INVALID" in v_expired.reason_code

    # 8. Warrant binding mismatches (action_caid, action_name, tenant_id)
    w_bad_caid = issue_human_warrant(
        "w-bad-caid", "n-2", sample_policy.tenant_id, "execute_payment", "sha256:0000", now_ns + 1000, priv
    )
    v_bad_caid = evaluate_action_admissibility("execute_payment", pay_args, sample_policy, now_ns, warrant=w_bad_caid, human_pub_key=pub)
    assert v_bad_caid.allowed is False
    assert v_bad_caid.reason_code == "HALT_WARRANT_BINDING_OR_EXPIRY_INVALID"

    w_bad_act = issue_human_warrant(
        "w-bad-act", "n-3", sample_policy.tenant_id, "delete_record", caid, now_ns + 1000, priv
    )
    v_bad_act = evaluate_action_admissibility("execute_payment", pay_args, sample_policy, now_ns, warrant=w_bad_act, human_pub_key=pub)
    assert v_bad_act.allowed is False
    assert v_bad_act.reason_code == "HALT_WARRANT_BINDING_OR_EXPIRY_INVALID"

    w_bad_tenant = issue_human_warrant(
        "w-bad-t", "n-4", "tenant-other", "execute_payment", caid, now_ns + 1000, priv
    )
    v_bad_tenant = evaluate_action_admissibility("execute_payment", pay_args, sample_policy, now_ns, warrant=w_bad_tenant, human_pub_key=pub)
    assert v_bad_tenant.allowed is False
    assert v_bad_tenant.reason_code == "HALT_WARRANT_BINDING_OR_EXPIRY_INVALID"

    # 9. Warrant with missing or corrupted signature or missing public key
    v_no_pk = evaluate_action_admissibility("execute_payment", pay_args, sample_policy, now_ns, warrant=warrant, human_pub_key=None)
    assert v_no_pk.allowed is False
    assert v_no_pk.reason_code == "HALT_WARRANT_SIGNATURE_INVALID"

    w_bad_sig = SignedHumanActionWarrant(
        warrant_id="w-bad", nonce="n-5", tenant_id=sample_policy.tenant_id, action_name="execute_payment",
        action_caid=caid, expires_at_ns=now_ns + 1000, signature_b64="bm90X2Ffc2lnbmF0dXJl"
    )
    v_bad_sig = evaluate_action_admissibility("execute_payment", pay_args, sample_policy, now_ns, warrant=w_bad_sig, human_pub_key=pub)
    assert v_bad_sig.allowed is False
    assert v_bad_sig.reason_code == "HALT_WARRANT_SIGNATURE_INVALID"

    w_empty_sig = SignedHumanActionWarrant(
        warrant_id="w-bad", nonce="n-6", tenant_id=sample_policy.tenant_id, action_name="execute_payment",
        action_caid=caid, expires_at_ns=now_ns + 1000, signature_b64=""
    )
    v_empty_sig = evaluate_action_admissibility("execute_payment", pay_args, sample_policy, now_ns, warrant=w_empty_sig, human_pub_key=pub)
    assert v_empty_sig.allowed is False
    assert v_empty_sig.reason_code == "HALT_WARRANT_SIGNATURE_INVALID"
    assert w_empty_sig.verify(pub) is False
    assert w_bad_sig.verify(pub) is False

    # 10. Taint and Payment limits through evaluate_action_admissibility
    v_taint_halt = evaluate_action_admissibility("draft_payment", pay_args, sample_policy, now_ns, taint_tier=TaintTier.TIER_2_UNTRUSTED_EXTERNAL)
    assert v_taint_halt.allowed is False
    assert v_taint_halt.reason_code == "HALT_UNTRUSTED_CONTEXT_CANNOT_AUTHORIZE_MUTATION"

    bad_pay_args = {"amount_minor": -10, "currency": "PLN", "recipient_id": "vendor_77"}
    v_limit_halt = evaluate_action_admissibility("draft_payment", bad_pay_args, sample_policy, now_ns)
    assert v_limit_halt.allowed is False
    assert v_limit_halt.reason_code == "HALT_PAYMENT_AMOUNT_OUT_OF_BOUNDS"


def test_8_canonical_json_unicode_and_float_guards() -> None:
    # Test ensure_ascii=False preservation of UTF-8 Cyrillic
    raw_utf8 = canonical_json_v1({"city": "Київ", "hub": "Warszawa"})
    assert "Київ".encode("utf-8") in raw_utf8

    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"inf": float("inf")})
    with pytest.raises(ValueError, match="ERR_NON_FINITE_FLOAT"):
        canonical_json_v1({"neg_inf": float("-inf")})


def test_6_durable_border_enforcer_flow(
    tmp_path: Path,
    sample_policy: PolicyManifest,
    human_keys: tuple[Ed25519PrivateKey, Ed25519PublicKey],
) -> None:
    priv, pub = human_keys
    enforcer = DurableBorderEnforcer(sample_policy, tmp_path / "ledger", pub)

    now_ns = 1_000_000
    pay_args = {"amount_minor": 20_000, "currency": "PLN", "recipient_id": "poczta_polska_hub"}
    caid = compute_action_caid("execute_payment", pay_args, sample_policy.tenant_id, sample_policy.agent_id)

    warrant = issue_human_warrant(
        warrant_id="w-02",
        nonce="nonce-002",
        tenant_id=sample_policy.tenant_id,
        action_name="execute_payment",
        action_caid=caid,
        expires_at_ns=now_ns + 1_000_000_000,
        human_priv_key=priv,
    )

    executed = False

    def dispatch() -> dict:
        nonlocal executed
        executed = True
        return {"status": "ok"}

    verdict = enforcer.evaluate_and_escort(
        "execute_payment",
        pay_args,
        now_ns,
        dispatch,
        warrant=warrant,
    )
    assert verdict.allowed is True
    assert verdict.reason_code == "OK_COMMITTED"
    assert verdict.escort_state == TaskEscortState.COMMITTED
    assert executed is True

    # Immediate in-memory re-dispatch is blocked as already committed
    v_dup = enforcer.evaluate_and_escort("execute_payment", pay_args, now_ns + 10, dispatch, warrant=warrant)
    assert v_dup.allowed is False
    assert v_dup.reason_code == "DENY_A2A_ALREADY_COMMITTED_IDEMPOTENT_BLOCK"


def test_7_t0_latency_benchmark(sample_policy: PolicyManifest) -> None:
    """Measures T0 fast-path evaluation latency dynamically; confirms < 10ms per evaluation."""
    now_ns = 1_000_000_000
    args = {"invoice_id": "inv_42"}

    # Warmup
    for _ in range(50):
        evaluate_action_admissibility("read_invoice", args, sample_policy, now_ns)

    timings_ns = []
    for _ in range(500):
        t0 = time.perf_counter_ns()
        v = evaluate_action_admissibility("read_invoice", args, sample_policy, now_ns)
        t1 = time.perf_counter_ns()
        timings_ns.append(t1 - t0)
        assert v.allowed is True

    timings_ns.sort()
    p99_ms = timings_ns[int(len(timings_ns) * 0.99)] / 1_000_000.0
    # Dynamic timing assertion: must complete well under 10 ms
    assert p99_ms < 10.0, f"Observed p99 latency {p99_ms}ms exceeded 10ms limit"


def test_compute_action_caid_exact() -> None:
    caid = compute_action_caid("test_action", {"k": "v"}, "tenant_1", "agent_1")
    assert isinstance(caid, str)
    assert caid.startswith("sha256:")
    assert len(caid) == 71
    # Canonical payload: {"action_name":"test_action","agent_id":"agent_1","args":{"k":"v"},"tenant_id":"tenant_1"}
    import hashlib
    expected_hash = hashlib.sha256(b'{"action_name":"test_action","agent_id":"agent_1","args":{"k":"v"},"tenant_id":"tenant_1"}').hexdigest()
    assert caid == f"sha256:{expected_hash}"


def test_border_policy_frozen_immutability(sample_policy: PolicyManifest) -> None:
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        sample_policy.max_amount_minor_units = 999  # type: ignore[misc]

    v = BorderVerdict(
        allowed=True,
        reason_code="OK_ADMISSIBLE",
        action_caid="sha256:0000",
        escort_state=TaskEscortState.READY,
        cancelled_at_state=CancelledAtState.NONE,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.allowed = False  # type: ignore[misc]

    w = SignedHumanActionWarrant(
        warrant_id="w-01",
        nonce="nonce-001",
        tenant_id="tenant-1",
        action_name="test_action",
        action_caid="sha256:0000",
        expires_at_ns=1000,
        signature_b64="c2ln",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        w.nonce = "nonce-002"  # type: ignore[misc]

