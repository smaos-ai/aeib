#!/usr/bin/env python3
"""
tests/test_coinbase_x402_agent_gateway.py
================================================================================
Comprehensive test suite for Coinbase Developer Platform (CDP) & x402 Hardened
Agent Gateway under the stated model.

Evaluates:
  - Pre-socket escrow reservation and balance accounting
  - SIWx cryptographic target URL and method binding verification
  - HTTP 504 transport timeout latching to EFFECT_INDETERMINATE
  - Idempotency interlock blocking duplicate CAID retries during indeterminate hold
  - Multi-agent smurfing defenses and integer basis-point velocity quotas
  - Out-of-band reconciliation settling or refunding indeterminate escrow
  - RFC 8785 canonical JSON Ed25519 SCITT receipt emission and verification
  - CLI runners and default configurations
  - Epistemic boundary audit ensuring zero forbidden terms in owned files
  - Red-team regressions: amount validation, SIWx signer allow-set, nonce replay
    and derived CAIDs, gateway-clock epochs with skew bound, URL canonicalization
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.coinbase_x402_agent_gateway import (
    DISPOSITION_CONFIRMED,
    DISPOSITION_EFFECT_INDETERMINATE,
    DISPOSITION_REFUTED,
    DISPOSITION_REJECTED,
    DISPOSITION_TRY_RESERVED,
    CoinbaseX402AgentGateway,
    GatewayConfig,
    PaymentIntent,
    SIWxBinding,
    _fsync_fd,
    main,
    run_self_test,
    run_simulate_504_timeout,
)
from src.jcs_canonicalizer import encode_jcs

CLOCK_START = 1700000000


class ManualClock:
    """Injectable deterministic clock: a callable returning integer epoch seconds."""

    def __init__(self, start: int) -> None:
        self.now = start

    def __call__(self) -> int:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += seconds


def pubkey_hex(key: ed25519.Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes_raw().hex()


@pytest.fixture
def test_env(tmp_path: Path):
    """Creates an isolated test gateway environment."""
    journal_path = tmp_path / "gateway_test_journal.jsonl"
    init_bal = 12_000_000
    config = GatewayConfig(
        journal_path=journal_path,
        initial_balance_micro_usdc=init_bal,
        epoch_duration_seconds=1800,
        max_velocity_bps=2000,
        single_tx_max_bps=400,
        max_tx_per_epoch=10,
        timeout_ms=3000,
    )
    gateway_key = ed25519.Ed25519PrivateKey.generate()
    agent_key = ed25519.Ed25519PrivateKey.generate()
    clock = ManualClock(CLOCK_START)
    trusted = [pubkey_hex(agent_key)]
    gateway = CoinbaseX402AgentGateway(
        config=config,
        private_key=gateway_key,
        trusted_signer_pubkeys_hex=trusted,
        clock=clock,
    )

    return {
        "clock": clock,
        "trusted": trusted,
        "gateway": gateway,
        "config": config,
        "gateway_key": gateway_key,
        "agent_key": agent_key,
        "journal_path": journal_path,
        "tmp_path": tmp_path,
        "init_bal": init_bal,
    }


def make_intent(
    label: str = "test_001",
    agent_id: str = "subagent_alpha",
    amount_micro_usdc: int = 15_000,
    target_url: str = "https://api.merchant-service.org/v1/compute/eval",
    target_method: str = "POST",
    payee: str = "0x71C8000000000000000000000000000000000099",
    timestamp: int = CLOCK_START,
    nonce: str = "",
) -> PaymentIntent:
    """Builds an intent with a derived caid; label seeds a unique nonce."""
    return PaymentIntent.build(
        agent_id=agent_id,
        payee_address=payee,
        amount_micro_usdc=amount_micro_usdc,
        target_url=target_url,
        target_method=target_method,
        chain_id=8453,
        nonce=nonce or f"nonce_{label}",
        timestamp_epoch=timestamp,
    )


def make_gateway(env: Dict[str, Any], journal_name: str, **cfg: Any) -> CoinbaseX402AgentGateway:
    """Extra gateway sharing the fixture clock and signer allow-set."""
    return CoinbaseX402AgentGateway(
        config=GatewayConfig(journal_path=env["tmp_path"] / journal_name, **cfg),
        trusted_signer_pubkeys_hex=env["trusted"],
        clock=env["clock"],
    )


def test_gateway_config_defaults(tmp_path: Path):
    """Evaluates GatewayConfig default parameters and field initialization."""
    default_cfg = GatewayConfig(journal_path=tmp_path / "def.jsonl")
    expected_init_bal = 10_000_000
    expected_epoch = 3600
    expected_vel_bps = 2500
    expected_single_bps = 500
    expected_max_tx = 50
    expected_timeout = 5000

    assert default_cfg.initial_balance_micro_usdc == expected_init_bal
    assert default_cfg.epoch_duration_seconds == expected_epoch
    assert default_cfg.max_velocity_bps == expected_vel_bps
    assert default_cfg.single_tx_max_bps == expected_single_bps
    assert default_cfg.max_tx_per_epoch == expected_max_tx
    assert default_cfg.timeout_ms == expected_timeout
    expected_skew = 300
    assert default_cfg.max_clock_skew_seconds == expected_skew

    # Also evaluate gateway init with default private key generation
    gw_default = CoinbaseX402AgentGateway(config=default_cfg)
    assert gw_default.private_key is not None
    assert len(gw_default.pubkey_hex) == 64


def test_payment_intent_and_binding_canonical_dicts(test_env):
    """Evaluates canonical dictionary conversion for payment intent and SIWx binding."""
    intent = make_intent()
    # Verify frozen immutability
    with pytest.raises((Exception, AttributeError)):
        intent.caid = "mutated_caid"

    intent_dict = intent.to_canonical_dict()
    assert intent_dict["caid"] == intent.caid
    assert intent_dict["amount_micro_usdc"] == intent.amount_micro_usdc
    assert intent_dict["target_method"] == "POST"

    gateway = test_env["gateway"]
    binding = gateway.create_siwx_binding(intent, test_env["agent_key"])
    binding_dict = binding.to_canonical_dict()
    assert binding_dict["caid"] == intent.caid
    assert binding_dict["target_host"] == "api.merchant-service.org"
    assert binding_dict["target_path"] == "/v1/compute/eval"
    assert binding_dict["signature_hex"] == binding.signature_hex
    # SIWx bindings are frozen: signed fields cannot be mutated after signing
    with pytest.raises((Exception, AttributeError)):
        binding.amount_micro_usdc = 1


def test_nominal_payment_reservation_and_execution(test_env):
    """Evaluates nominal pre-socket escrow reservation and settlement."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    test_amt = 20_000
    intent = make_intent(label="caid_nom_01", amount_micro_usdc=test_amt)
    binding = gateway.create_siwx_binding(intent, agent_key)

    # 1. Pre-socket escrow reservation
    res_reserve = gateway.reserve_escrow(intent, binding)
    assert res_reserve["status"] == "RESERVED"
    assert res_reserve["amount_micro_usdc"] == test_amt
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(res_reserve["receipt"])

    bal_reserved = gateway.get_balances()
    assert bal_reserved["reserved_micro_usdc"] == test_amt
    assert bal_reserved["available_micro_usdc"] == test_env["init_bal"] - test_amt
    assert bal_reserved["settled_micro_usdc"] == 0

    # Verify journal key sorting
    journal_lines = test_env["journal_path"].read_text(encoding="utf-8").strip().split("\n")
    first_raw = journal_lines[0]
    expected_sorted = json.dumps(json.loads(first_raw), sort_keys=True)
    assert first_raw == expected_sorted

    # 2. Dispatch payment nominal
    def mock_http_ok(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        assert method == "POST"
        assert "Authorization" in headers
        assert "X-CAID" in headers
        return {"status_code": 200, "tx_hash": "0xbase_tx_receipt_nom_01"}

    res_dispatch = gateway.dispatch_payment(intent, binding, http_client=mock_http_ok)
    assert res_dispatch["status"] == DISPOSITION_CONFIRMED
    assert res_dispatch["tx_hash"] == "0xbase_tx_receipt_nom_01"
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(res_dispatch["receipt"])

    bal_settled = gateway.get_balances()
    assert bal_settled["settled_micro_usdc"] == test_amt
    assert bal_settled["reserved_micro_usdc"] == 0
    assert bal_settled["available_micro_usdc"] == test_env["init_bal"] - test_amt

    # Verify journal key sorting on second entry with dynamic keys
    settle_raw = test_env["journal_path"].read_text(encoding="utf-8").strip().split("\n")[1]
    expected_settle_sorted = json.dumps(json.loads(settle_raw), sort_keys=True)
    assert settle_raw == expected_settle_sorted

    # Attempting duplicate reservation on confirmed CAID must be rejected
    with pytest.raises(RuntimeError) as exc_dup_conf:
        gateway.reserve_escrow(intent, binding)
    assert "ERR_DUPLICATE_CAID_ALREADY_CONFIRMED" in str(exc_dup_conf.value)

    # Attempting duplicate dispatch on confirmed CAID must also be rejected
    with pytest.raises(RuntimeError) as exc_disp_conf:
        gateway.dispatch_payment(intent, binding)
    assert "ERR_DUPLICATE_CAID_ALREADY_CONFIRMED" in str(exc_disp_conf.value)


def test_journal_reload_persisted_entries(test_env):
    """Evaluates journal reload from stable storage on subsequent startup."""
    gateway1 = test_env["gateway"]
    agent_key = test_env["agent_key"]
    test_amt = 11_000
    intent = make_intent(label="caid_persisted_01", amount_micro_usdc=test_amt)
    binding = gateway1.create_siwx_binding(intent, agent_key)
    gateway1.reserve_escrow(intent, binding)

    # Re-initialize second gateway instance pointing to the same journal
    gateway2 = CoinbaseX402AgentGateway(config=test_env["config"], private_key=test_env["gateway_key"])
    assert intent.caid in gateway2._journal_entries
    assert gateway2._consumed_nonces[intent.nonce] == intent.caid
    assert gateway2.get_balances()["reserved_micro_usdc"] == test_amt


def test_dispatch_201_created(test_env):
    """Evaluates dispatch returning HTTP 201 Created settling successfully."""
    gateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    test_amt = 8000
    intent = make_intent(label="caid_201_created", amount_micro_usdc=test_amt)
    binding = gateway.create_siwx_binding(intent, agent_key)

    def client_201(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return {"status_code": 201, "tx_hash": "0xcreated_201"}

    res = gateway.dispatch_payment(intent, binding, http_client=client_201)
    assert res["status"] == DISPOSITION_CONFIRMED
    expected_created = 201
    assert res["status_code"] == expected_created


def test_duplicate_caid_in_flight_rejection(test_env):
    """Evaluates duplicate reservation rejection while in active TRY_RESERVED state."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    intent = make_intent(label="caid_in_flight_dup", amount_micro_usdc=14_000)
    binding = gateway.create_siwx_binding(intent, agent_key)

    gateway.reserve_escrow(intent, binding)
    with pytest.raises(RuntimeError) as exc:
        gateway.reserve_escrow(intent, binding)
    assert "ERR_DUPLICATE_CAID_IN_FLIGHT" in str(exc.value)


def test_dispatch_without_prior_reservation_auto_reserves(test_env):
    """Evaluates dispatch auto-reserving when not previously reserved."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    test_amt = 10_000
    long_caid = "caid_auto_res_0123456789abcdef"
    intent = make_intent(label=long_caid, amount_micro_usdc=test_amt)
    binding = gateway.create_siwx_binding(intent, agent_key)

    res_dispatch = gateway.dispatch_payment(intent, binding)
    assert res_dispatch["status"] == DISPOSITION_CONFIRMED
    expected_ok_status = 200
    assert res_dispatch["status_code"] == expected_ok_status
    assert res_dispatch["tx_hash"] == f"0xbase_{intent.caid[:16]}"
    bal = gateway.get_balances()
    assert bal["settled_micro_usdc"] == test_amt


def test_504_timeout_transitions_to_indeterminate_hold_and_blocks_retry(test_env):
    """Evaluates HTTP 504 timeout latching into EFFECT_INDETERMINATE and blocking retry."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    test_amt = 35_000
    intent = make_intent(label="caid_timeout_504", amount_micro_usdc=test_amt)
    binding = gateway.create_siwx_binding(intent, agent_key)

    def mock_http_timeout(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return {"status_code": 504, "error": "Gateway Timeout from upstream node"}

    res_dispatch = gateway.dispatch_payment(intent, binding, http_client=mock_http_timeout)
    assert res_dispatch["status"] == DISPOSITION_EFFECT_INDETERMINATE
    assert "indeterminate hold" in res_dispatch["error"]
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(res_dispatch["receipt"])

    # Escrow must remain held
    bal_latched = gateway.get_balances()
    assert bal_latched["reserved_micro_usdc"] == test_amt
    assert bal_latched["settled_micro_usdc"] == 0

    # Retrying dispatch on same CAID must fail closed
    with pytest.raises(RuntimeError) as exc_dispatch:
        gateway.dispatch_payment(intent, binding)
    assert "ERR_DUPLICATE_CAID_LATCHED_INDETERMINATE" in str(exc_dispatch.value)

    # Retrying reservation on same CAID must also fail closed
    with pytest.raises(RuntimeError) as exc_reserve:
        gateway.reserve_escrow(intent, binding)
    assert "ERR_DUPLICATE_CAID_LATCHED_INDETERMINATE" in str(exc_reserve.value)


def test_missing_status_code_defaults_to_504_indeterminate(test_env):
    """Evaluates client responses missing status_code defaulting to 504 latch."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    intent = make_intent(label="caid_no_status_key", amount_micro_usdc=12_000)
    binding = gateway.create_siwx_binding(intent, agent_key)

    def mock_empty_response(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return {}

    res = gateway.dispatch_payment(intent, binding, http_client=mock_empty_response)
    assert res["status"] == DISPOSITION_EFFECT_INDETERMINATE


def test_network_exception_transitions_to_indeterminate_hold(test_env):
    """Evaluates socket / network exceptions latching into EFFECT_INDETERMINATE."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    test_amt = 18_000
    intent = make_intent(label="caid_net_exc", amount_micro_usdc=test_amt)
    binding = gateway.create_siwx_binding(intent, agent_key)

    def mock_http_raise(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        raise TimeoutError("TCP connection timed out during TLS handshake")

    res = gateway.dispatch_payment(intent, binding, http_client=mock_http_raise)
    assert res["status"] == DISPOSITION_EFFECT_INDETERMINATE
    assert gateway.get_balances()["reserved_micro_usdc"] == test_amt


def test_http_4xx_refunds_escrow(test_env):
    """Evaluates HTTP 400 terminal rejection refunding reserved escrow to available."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    intent = make_intent(label="caid_refute_400", amount_micro_usdc=22_000)
    binding = gateway.create_siwx_binding(intent, agent_key)

    def mock_http_bad_request(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return {"status_code": 400, "error": "Bad Request: schema invalid"}

    res = gateway.dispatch_payment(intent, binding, http_client=mock_http_bad_request)
    assert res["status"] == DISPOSITION_REFUTED
    bal = gateway.get_balances()
    assert bal["reserved_micro_usdc"] == 0
    assert bal["settled_micro_usdc"] == 0
    assert bal["available_micro_usdc"] == test_env["init_bal"]


def test_siwx_url_and_method_mismatch_rejection(test_env):
    """Evaluates SIWx target URL, host, path, and method binding mismatch rejection."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    intent = make_intent(
        label="caid_siwx_mismatch",
        target_url="https://api.valid-host.org/v1/resource",
        target_method="POST",
    )
    binding = gateway.create_siwx_binding(intent, agent_key)

    # 1. Host mismatch
    with pytest.raises(ValueError) as exc_host:
        gateway.verify_siwx_binding(
            binding,
            target_url="https://api.malicious-host.org/v1/resource",
            target_method="POST",
        )
    assert "ERR_SIWX_TARGET_URL_MISMATCH: host mismatch" in str(exc_host.value)

    # 2. Path mismatch
    with pytest.raises(ValueError) as exc_path:
        gateway.verify_siwx_binding(
            binding,
            target_url="https://api.valid-host.org/v1/drain_funds",
            target_method="POST",
        )
    assert "ERR_SIWX_TARGET_URL_MISMATCH: path mismatch" in str(exc_path.value)

    # 3. Method mismatch
    with pytest.raises(ValueError) as exc_method:
        gateway.verify_siwx_binding(
            binding,
            target_url="https://api.valid-host.org/v1/resource",
            target_method="DELETE",
        )
    assert "ERR_SIWX_TARGET_URL_MISMATCH: method mismatch" in str(exc_method.value)

    # 4. Digest tampering
    tampered_binding = SIWxBinding(
        caid=binding.caid,
        target_scheme=binding.target_scheme,
        target_host=binding.target_host,
        target_path=binding.target_path,
        target_query=binding.target_query,
        target_method=binding.target_method,
        payee_address=binding.payee_address,
        amount_micro_usdc=binding.amount_micro_usdc,
        chain_id=binding.chain_id,
        nonce=binding.nonce,
        timestamp_epoch=binding.timestamp_epoch,
        siwx_digest="00" * 32,
        signature_hex=binding.signature_hex,
        signer_pubkey_hex=binding.signer_pubkey_hex,
    )
    with pytest.raises(ValueError) as exc_digest:
        gateway.verify_siwx_binding(
            tampered_binding,
            target_url=intent.target_url,
            target_method=intent.target_method,
        )
    assert "ERR_SIWX_DIGEST_MISMATCH" in str(exc_digest.value)

    # 5. Invalid signature
    attacker_key = ed25519.Ed25519PrivateKey.generate()
    forged_sig = attacker_key.sign(b"forged_message").hex()
    forged_binding = SIWxBinding(
        caid=binding.caid,
        target_scheme=binding.target_scheme,
        target_host=binding.target_host,
        target_path=binding.target_path,
        target_query=binding.target_query,
        target_method=binding.target_method,
        payee_address=binding.payee_address,
        amount_micro_usdc=binding.amount_micro_usdc,
        chain_id=binding.chain_id,
        nonce=binding.nonce,
        timestamp_epoch=binding.timestamp_epoch,
        siwx_digest=binding.siwx_digest,
        signature_hex=forged_sig,
        signer_pubkey_hex=binding.signer_pubkey_hex,
    )
    with pytest.raises(ValueError) as exc_sig:
        gateway.verify_siwx_binding(
            forged_binding,
            target_url=intent.target_url,
            target_method=intent.target_method,
        )
    assert "ERR_SIWX_SIGNATURE_INVALID" in str(exc_sig.value)


def test_velocity_quota_blocks_smurfing(test_env):
    """Evaluates smurfing and velocity quota controls across micro-transactions."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    total_bal = test_env["init_bal"]

    # 1. Single transaction cap: 400 bps = 4% = 480,000 micro-USDC
    excess_single = (total_bal * 400 // 10000) + 1000
    intent_excess = make_intent(label="caid_single_exceeded", amount_micro_usdc=excess_single)
    binding_excess = gateway.create_siwx_binding(intent_excess, agent_key)
    with pytest.raises(ValueError) as exc_single:
        gateway.reserve_escrow(intent_excess, binding_excess)
    assert "ERR_SINGLE_TX_BPS_EXCEEDED" in str(exc_single.value)

    # Test exact velocity cap boundary check and epoch_spent = 0
    gw_boundary = make_gateway(
        test_env,
        "bound.jsonl",
        initial_balance_micro_usdc=10_000_000,
        single_tx_max_bps=10000,
        max_velocity_bps=2000,
    )
    exact_cap = 10_000_000 * 2000 // 10000
    gw_boundary.check_velocity_and_quota("agent_b", exact_cap)
    with pytest.raises(ValueError):
        gw_boundary.check_velocity_and_quota("agent_b", exact_cap + 1)

    # 2. Cumulative velocity quota: 2000 bps = 20% = 2,400,000 micro-USDC
    # Perform 5 transactions of 400,000 each = 2,000,000
    tx_amt = 400_000
    epoch_time = 1700000000
    for i in range(5):
        intent = make_intent(
            label=f"caid_burst_{i}",
            amount_micro_usdc=tx_amt,
            timestamp=epoch_time,
        )
        binding = gateway.create_siwx_binding(intent, agent_key)
        res = gateway.reserve_escrow(intent, binding)
        assert res["status"] == "RESERVED"

    # Next transaction of 450,000 would push total to 2,450,000 > 2,400,000 cap
    intent_over_cap = make_intent(
        label="caid_burst_over",
        amount_micro_usdc=450_000,
        timestamp=epoch_time,
    )
    binding_over_cap = gateway.create_siwx_binding(intent_over_cap, agent_key)
    with pytest.raises(ValueError) as exc_velocity:
        gateway.reserve_escrow(intent_over_cap, binding_over_cap)
    assert "ERR_VELOCITY_QUOTA_EXCEEDED: cumulative epoch spend 2450000 exceeds cap 2400000" in str(
        exc_velocity.value
    )

    # In next epoch of the gateway clock (time + 3600), quota resets
    test_env["clock"].advance(3600)
    next_epoch_time = epoch_time + 3600
    intent_next_epoch = make_intent(
        label="caid_next_epoch",
        amount_micro_usdc=tx_amt,
        timestamp=next_epoch_time,
    )
    binding_next_epoch = gateway.create_siwx_binding(intent_next_epoch, agent_key)
    res_next = gateway.reserve_escrow(intent_next_epoch, binding_next_epoch)
    assert res_next["status"] == "RESERVED"


def test_frequency_limit_blocks_high_frequency_micro_transactions(test_env):
    """Evaluates transaction count limit per epoch (max 10 in fixture)."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    epoch_time = 1700050000
    test_env["clock"].now = epoch_time

    # Run 10 micro transactions of 1,000 micro-USDC
    for i in range(10):
        intent = make_intent(
            label=f"caid_freq_{i}",
            amount_micro_usdc=1000,
            timestamp=epoch_time,
        )
        binding = gateway.create_siwx_binding(intent, agent_key)
        gateway.reserve_escrow(intent, binding)

    # 11th transaction in same epoch should be rejected
    intent_11 = make_intent(
        label="caid_freq_11",
        amount_micro_usdc=1000,
        timestamp=epoch_time,
    )
    binding_11 = gateway.create_siwx_binding(intent_11, agent_key)
    with pytest.raises(ValueError) as exc_freq:
        gateway.reserve_escrow(intent_11, binding_11)
    assert "ERR_SMURFING_FREQUENCY_EXCEEDED: transaction count 11 exceeds epoch limit 10" in str(exc_freq.value)

    # Entries lacking a gateway-clock stamp (reserved_at_epoch) are counted in the
    # current epoch (fail closed), irrespective of the clock value.
    gw_ep0 = make_gateway(
        test_env,
        "ep0.jsonl",
        initial_balance_micro_usdc=10_000_000,
        epoch_duration_seconds=1,
        max_tx_per_epoch=1,
    )
    gw_ep0._journal_entries["legacy_no_ts"] = {
        "disposition": "TRY_RESERVED",
        "amount_micro_usdc": 1000,
    }
    with pytest.raises(ValueError, match="transaction count 2 exceeds epoch limit 1"):
        gw_ep0.check_velocity_and_quota("agent_0", 100)


def test_insufficient_funds_rejection(test_env):
    """Evaluates rejection when requested amount exceeds available balance."""
    gateway = make_gateway(
        test_env,
        "gateway_low_funds.jsonl",
        initial_balance_micro_usdc=100_000,
        single_tx_max_bps=10000,
        max_velocity_bps=30000,
    )
    agent_key = test_env["agent_key"]

    # First transaction reserves 80_000 out of 100_000
    intent1 = make_intent(label="caid_fund_1", amount_micro_usdc=80_000)
    binding1 = gateway.create_siwx_binding(intent1, agent_key)
    gateway.reserve_escrow(intent1, binding1)

    # Second transaction attempts 30_000 when only 20_000 remains available
    intent2 = make_intent(label="caid_fund_2", amount_micro_usdc=30_000)
    binding2 = gateway.create_siwx_binding(intent2, agent_key)
    with pytest.raises(ValueError) as exc_bal:
        gateway.reserve_escrow(intent2, binding2)
    assert "ERR_INSUFFICIENT_FUNDS" in str(exc_bal.value)


def test_out_of_band_reconciliation_resolves_indeterminate_hold(test_env):
    """Evaluates out-of-band reconciliation settling or refunding indeterminate hold."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]

    # Setup indeterminate transaction 1: will be CONFIRMED
    recon_amt_1 = 28_000
    intent_conf = make_intent(label="caid_recon_conf", amount_micro_usdc=recon_amt_1)
    binding_conf = gateway.create_siwx_binding(intent_conf, agent_key)

    def mock_504(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return {"status_code": 504, "error": "Gateway Timeout"}

    gateway.dispatch_payment(intent_conf, binding_conf, http_client=mock_504)
    assert gateway.get_balances()["reserved_micro_usdc"] == recon_amt_1

    recon_res_conf = gateway.reconcile(
        caid=intent_conf.caid,
        authoritative_disposition=DISPOSITION_CONFIRMED,
        probe_receipt={"probe_type": "chain_receipt", "tx_hash": "0xconf_base_1"},
    )
    assert recon_res_conf["status"] == DISPOSITION_CONFIRMED
    assert recon_res_conf["reconciliation_id"].startswith(f"recon_{intent_conf.caid[:12]}_")
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(recon_res_conf["receipt"])

    bal_after_conf = gateway.get_balances()
    assert bal_after_conf["reserved_micro_usdc"] == 0
    assert bal_after_conf["settled_micro_usdc"] == recon_amt_1

    # Setup indeterminate transaction 2: will be REFUTED
    recon_amt_2 = 33_000
    intent_ref = make_intent(label="caid_recon_ref", amount_micro_usdc=recon_amt_2)
    binding_ref = gateway.create_siwx_binding(intent_ref, agent_key)
    gateway.dispatch_payment(intent_ref, binding_ref, http_client=mock_504)
    assert gateway.get_balances()["reserved_micro_usdc"] == recon_amt_2

    recon_res_ref = gateway.reconcile(
        caid=intent_ref.caid,
        authoritative_disposition=DISPOSITION_REFUTED,
    )
    assert recon_res_ref["status"] == DISPOSITION_REFUTED
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(recon_res_ref["receipt"])

    bal_after_ref = gateway.get_balances()
    assert bal_after_ref["reserved_micro_usdc"] == 0
    assert bal_after_ref["settled_micro_usdc"] == recon_amt_1
    assert bal_after_ref["available_micro_usdc"] == test_env["init_bal"] - recon_amt_1


def test_reconciliation_error_conditions(test_env):
    """Evaluates error cases during reconciliation."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]

    # 1. Non-existent CAID
    with pytest.raises(ValueError) as exc_none:
        gateway.reconcile("caid_not_found", DISPOSITION_CONFIRMED)
    assert "ERR_CAID_NOT_FOUND" in str(exc_none.value)

    # 2. Reconciling a non-indeterminate transaction
    agent_key = test_env["agent_key"]
    intent = make_intent(label="caid_non_indet", amount_micro_usdc=10_000)
    binding = gateway.create_siwx_binding(intent, agent_key)
    gateway.reserve_escrow(intent, binding)
    with pytest.raises(ValueError) as exc_state:
        gateway.reconcile(intent.caid, DISPOSITION_CONFIRMED)
    assert "ERR_CANNOT_RECONCILE_NON_INDETERMINATE" in str(exc_state.value)

    # 3. Invalid disposition argument
    # Force an indeterminate state
    def mock_504(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return {"status_code": 504, "error": "Gateway Timeout"}

    gateway.dispatch_payment(intent, binding, http_client=mock_504)
    with pytest.raises(ValueError) as exc_disp:
        gateway.reconcile(intent.caid, "INVALID_DISPOSITION")
    assert "ERR_INVALID_RECONCILIATION_DISPOSITION" in str(exc_disp.value)


def test_scitt_receipt_verification_and_tampering(test_env):
    """Evaluates Ed25519 signature checks and tampering rejection on SCITT receipts."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    receipt = gateway.emit_scitt_receipt(
        caid="caid_scitt_test",
        agent_id="agent_gamma",
        payee_address="0x71C8000000000000000000000000000000000005",
        amount_micro_usdc=5000,
        target_url="https://api.gateway.org/v1/query",
        target_method="GET",
        disposition=DISPOSITION_CONFIRMED,
        timestamp_epoch=1700000000,
        siwx_digest="01" * 32,
    )
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(receipt) is True

    # 1. Corrupted payload field
    tampered_payload = dict(receipt["payload"])
    tampered_payload["amount_micro_usdc"] = 999_999
    corrupted_receipt = dict(receipt)
    corrupted_receipt["payload"] = tampered_payload
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(corrupted_receipt) is False

    # 2. Corrupted signature
    bad_sig_receipt = dict(receipt)
    bad_sig_receipt["signature_hex"] = "ff" * 64
    assert CoinbaseX402AgentGateway.verify_scitt_receipt(bad_sig_receipt) is False

    # 3. Missing fields
    assert CoinbaseX402AgentGateway.verify_scitt_receipt({}) is False


def test_parse_url_host_and_path_variations():
    """Evaluates URL host and path parser across ports and paths."""
    h1, p1 = CoinbaseX402AgentGateway.parse_url_host_and_path("https://api.example.com:8443/v1/test")
    assert h1 == "api.example.com:8443"
    assert p1 == "/v1/test"

    h2, p2 = CoinbaseX402AgentGateway.parse_url_host_and_path("https://SUB.DOMAIN.ORG")
    assert h2 == "sub.domain.org"
    assert p2 == "/"


def test_fsync_helper(tmp_path: Path):
    """Evaluates platform-safe file descriptor flush."""
    p = tmp_path / "sync_test.txt"
    fd = os.open(str(p), os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, b"durability test under stated model")
        _fsync_fd(fd)
    finally:
        os.close(fd)
    assert p.read_bytes() == b"durability test under stated model"


def test_cli_runners(tmp_path: Path):
    """Evaluates CLI helper entrypoints --self-test and --simulate-504-timeout."""
    code_self = run_self_test(tmp_path)
    assert code_self == 0

    code_sim = run_simulate_504_timeout(tmp_path)
    assert code_sim == 0


def test_main_cli_arguments(monkeypatch, tmp_path: Path):
    """Evaluates main() CLI dispatch with mock arguments."""
    import shutil
    isolated_dir = Path("/tmp/aeib_coinbase_isolated")
    if isolated_dir.exists():
        shutil.rmtree(isolated_dir, ignore_errors=True)
    assert not isolated_dir.exists()

    # First run creates parent and child (kills parents=False mutant)
    monkeypatch.setattr(sys, "argv", ["gateway", "--self-test"])
    with pytest.raises(SystemExit) as exc_self:
        main()
    assert exc_self.value.code == 0

    # Second run with existing directory (kills exist_ok=False mutant)
    with pytest.raises(SystemExit) as exc_self2:
        main()
    assert exc_self2.value.code == 0

    monkeypatch.setattr(sys, "argv", ["gateway", "--simulate-504-timeout"])
    with pytest.raises(SystemExit) as exc_sim:
        main()
    assert exc_sim.value.code == 0

    # Clean up
    if isolated_dir.exists():
        shutil.rmtree(isolated_dir, ignore_errors=True)


def test_epistemic_boundary_zero_forbidden_words():
    """
    Epistemic boundary check: verifies zero forbidden promotional claims
    in Track Gamma owned files.
    """
    forbidden_terms = [
        "guar" + "antee",
        "guar" + "anteed",
        "bullet" + "proof",
        "enterprise" + "-grade",
        "production" + "-safe",
        "100%" + " secure",
        "unass" + "ailable",
        "im" + "mune",
        "unhack" + "able",
        "bank" + "-grade",
        "production" + "-ready",
        "proven " + "universally",
    ]

    owned_files = [
        REPO_ROOT / "src" / "coinbase_x402_agent_gateway.py",
        REPO_ROOT / "tests" / "test_coinbase_x402_agent_gateway.py",
        REPO_ROOT / "docs" / "grants" / "COINBASE_CDP_X402_AGENTIC_COMMERCE_GRANT.md",
    ]

    violations = []
    for file_path in owned_files:
        if not file_path.exists():
            continue
        text = file_path.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            if term.lower() in text:
                violations.append(f"{file_path.name} contains forbidden term: '{term}'")

    assert len(violations) == 0, f"Epistemic boundary violations: {violations}"


# =============================================================================
# Red-team regressions (premarket audit a3_x402_gateway findings 1-5)
# =============================================================================


def _raw_intent(amount: Any, nonce: str = "nonce_raw", timestamp: int = CLOCK_START) -> PaymentIntent:
    return PaymentIntent(
        caid="",
        agent_id="agent-1",
        payee_address="0xpayee",
        amount_micro_usdc=amount,
        target_url="https://api.example.com/pay",
        target_method="POST",
        chain_id=8453,
        nonce=nonce,
        timestamp_epoch=timestamp,
    )


def _dispatch_504(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
    return {"status_code": 504, "error": "Gateway Timeout"}


# --- Finding 1: negative / zero / bool / float amounts ---------------------


@pytest.mark.parametrize("bad_amount", [-5_000_000, -1, 0, True, False, 100.5, "1000", None])
def test_regression_f1_invalid_amounts_rejected_everywhere(test_env, bad_amount):
    """Finding 1: amounts must be exact positive ints at every ingress point."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    before = gateway.get_balances()

    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT"):
        _raw_intent(bad_amount)
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT"):
        gateway.check_velocity_and_quota("agent-1", bad_amount)
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT"):
        gateway.emit_scitt_receipt(
            caid="c", agent_id="a", payee_address="p", amount_micro_usdc=bad_amount,
            target_url="https://api.example.com/pay", target_method="POST",
            disposition=DISPOSITION_CONFIRMED, timestamp_epoch=CLOCK_START, siwx_digest="00",
        )
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT"):
        SIWxBinding(
            caid="c", target_scheme="https", target_host="h", target_path="/",
            target_query="", target_method="POST",
            payee_address="p", amount_micro_usdc=bad_amount, chain_id=8453, nonce="n",
            timestamp_epoch=CLOCK_START, siwx_digest="00", signature_hex="00",
            signer_pubkey_hex="00",
        )
    assert gateway.get_balances() == before


def test_regression_f1_minimum_amount_and_journal_amount_validation(test_env):
    """Finding 1: amount 1 is accepted; tampered journal amounts fail closed on load and append."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    intent_min = make_intent(label="min_amount", amount_micro_usdc=1)
    res = gateway.reserve_escrow(intent_min, gateway.create_siwx_binding(intent_min, test_env["agent_key"]))
    assert res["amount_micro_usdc"] == 1
    assert gateway.get_balances()["available_micro_usdc"] == test_env["init_bal"] - 1

    # Settlement/reconcile path: a tampered in-memory amount is refused at append
    intent_rec = make_intent(label="recon_tamper", amount_micro_usdc=5000)
    binding_rec = gateway.create_siwx_binding(intent_rec, test_env["agent_key"])
    gateway.dispatch_payment(intent_rec, binding_rec, http_client=_dispatch_504)
    gateway._journal_entries[intent_rec.caid]["amount_micro_usdc"] = -5000
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT"):
        gateway.reconcile(intent_rec.caid, DISPOSITION_REFUTED)

    # Startup path: a negative amount written to disk blocks journal load
    tampered = dict(json.loads(test_env["journal_path"].read_text(encoding="utf-8").splitlines()[0]))
    tampered.update({"caid": "tampered", "nonce": "tampered_nonce", "amount_micro_usdc": -5_000_000})
    with open(test_env["journal_path"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps(tampered, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="ERR_INVALID_AMOUNT"):
        CoinbaseX402AgentGateway(config=test_env["config"])


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"chain_id": 0}, "ERR_INVALID_CHAIN_ID"),
        ({"chain_id": True}, "ERR_INVALID_CHAIN_ID"),
        ({"timestamp_epoch": -1}, "ERR_INVALID_TIMESTAMP"),
        ({"timestamp_epoch": 1.5}, "ERR_INVALID_TIMESTAMP"),
        ({"nonce": ""}, "ERR_INVALID_NONCE"),
        ({"nonce": 7}, "ERR_INVALID_NONCE"),
        ({"caid": None}, "ERR_INVALID_CAID"),
    ],
)
def test_regression_intent_field_types_fail_closed(kwargs, code):
    """Intent identity fields are type-checked so derived CAIDs are well defined."""
    base = dict(
        caid="", agent_id="a", payee_address="p", amount_micro_usdc=10,
        target_url="https://api.example.com/pay", target_method="POST",
        chain_id=8453, nonce="n", timestamp_epoch=0,
    )
    PaymentIntent(**base)  # boundary values chain_id=1-like and timestamp 0 accepted
    PaymentIntent(**{**base, "chain_id": 1})
    base.update(kwargs)
    with pytest.raises(ValueError, match=code):
        PaymentIntent(**base)


# --- Finding 2: SIWx signer allow-set --------------------------------------


def test_regression_f2_untrusted_and_empty_signer_allow_set_fail_closed(test_env):
    """Finding 2: bindings from keys outside the configured allow-set are rejected."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    intent = make_intent(label="untrusted_signer", amount_micro_usdc=1000)
    rogue_binding = gateway.create_siwx_binding(intent, ed25519.Ed25519PrivateKey.generate())
    with pytest.raises(ValueError, match="ERR_SIWX_SIGNER_NOT_TRUSTED"):
        gateway.reserve_escrow(intent, rogue_binding)
    assert gateway.get_balances()["reserved_micro_usdc"] == 0
    assert intent.nonce not in gateway._consumed_nonces

    empty_gw = CoinbaseX402AgentGateway(
        config=GatewayConfig(journal_path=test_env["tmp_path"] / "empty_allow.jsonl"),
        clock=test_env["clock"],
    )
    assert empty_gw.trusted_signer_pubkeys_hex == frozenset()
    good_binding = empty_gw.create_siwx_binding(intent, test_env["agent_key"])
    with pytest.raises(ValueError, match="ERR_SIWX_NO_TRUSTED_SIGNERS"):
        empty_gw.reserve_escrow(intent, good_binding)


def test_regression_f2_allow_set_hex_case_and_validation(test_env):
    """Allow-set entries are validated Ed25519 keys and compared case-insensitively."""
    agent_key = test_env["agent_key"]
    upper_gw = CoinbaseX402AgentGateway(
        config=GatewayConfig(journal_path=test_env["tmp_path"] / "upper.jsonl"),
        trusted_signer_pubkeys_hex=[pubkey_hex(agent_key).upper()],
        clock=test_env["clock"],
    )
    intent = make_intent(label="upper_case", amount_micro_usdc=1000)
    binding = upper_gw.create_siwx_binding(intent, agent_key)
    upper_binding = SIWxBinding(**{**binding.__dict__, "signer_pubkey_hex": binding.signer_pubkey_hex.upper()})
    assert upper_gw.verify_siwx_binding(upper_binding, intent.target_url, intent.target_method) is True

    for bad in ("zz", "00" * 31, None):
        with pytest.raises(ValueError, match="ERR_INVALID_TRUSTED_SIGNER_PUBKEY"):
            CoinbaseX402AgentGateway(
                config=GatewayConfig(journal_path=test_env["tmp_path"] / "bad_allow.jsonl"),
                trusted_signer_pubkeys_hex=[bad],
            )


# --- Finding 3: nonce replay and derived CAID ------------------------------


def test_regression_f3_nonce_replay_in_instance_and_across_restart(test_env):
    """Finding 3: a consumed nonce cannot be reused under a different CAID, even after restart."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    first = make_intent(label="r1", amount_micro_usdc=1000, nonce="dup")
    gateway.reserve_escrow(first, gateway.create_siwx_binding(first, agent_key))

    replay = make_intent(label="r2", amount_micro_usdc=1001, nonce="dup")
    assert replay.caid != first.caid
    replay_binding = gateway.create_siwx_binding(replay, agent_key)
    with pytest.raises(RuntimeError, match="ERR_NONCE_REPLAY"):
        gateway.reserve_escrow(replay, replay_binding)

    restarted = CoinbaseX402AgentGateway(
        config=test_env["config"],
        trusted_signer_pubkeys_hex=test_env["trusted"],
        clock=test_env["clock"],
    )
    with pytest.raises(RuntimeError, match="ERR_NONCE_REPLAY"):
        restarted.reserve_escrow(replay, replay_binding)
    assert restarted.get_balances()["reserved_micro_usdc"] == 1000


def test_regression_f3_refuted_caid_cannot_be_replayed_or_redispatched(test_env):
    """A refunded (REFUTED) CAID keeps its nonce consumed and has no dispatchable escrow."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    intent = make_intent(label="refuted_replay", amount_micro_usdc=2000)
    binding = gateway.create_siwx_binding(intent, test_env["agent_key"])

    def client_400(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        return {"status_code": 400, "error": "Bad Request"}

    assert gateway.dispatch_payment(intent, binding, http_client=client_400)["status"] == DISPOSITION_REFUTED
    with pytest.raises(RuntimeError, match="ERR_NONCE_REPLAY"):
        gateway.reserve_escrow(intent, binding)
    with pytest.raises(RuntimeError, match="ERR_CAID_NOT_DISPATCHABLE"):
        gateway.dispatch_payment(intent, binding)
    assert gateway.get_balances()["settled_micro_usdc"] == 0


def test_regression_f3_caid_is_derived_from_rfc8785_jcs(test_env):
    """CAID = sha256(JCS(intent)); a mismatching caller caid fails closed, empty caid is derived."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    intent = make_intent(label="derived", amount_micro_usdc=3000)
    expected = hashlib.sha256(encode_jcs({
        "agent_id": intent.agent_id,
        "amount_micro_usdc": intent.amount_micro_usdc,
        "chain_id": intent.chain_id,
        "domain": "aeib.x402.payment_intent.v1",
        "nonce": intent.nonce,
        "payee_address": intent.payee_address,
        "target_method": "POST",
        "target_url": intent.target_url,
        "timestamp_epoch": intent.timestamp_epoch,
    })).hexdigest()
    assert intent.caid == expected

    forged = PaymentIntent(**{**intent.__dict__, "caid": "caller_chosen_caid"})
    with pytest.raises(ValueError, match="ERR_CAID_MISMATCH"):
        gateway.create_siwx_binding(forged, agent_key)
    with pytest.raises(ValueError, match="ERR_CAID_MISMATCH"):
        gateway.reserve_escrow(forged, gateway.create_siwx_binding(intent, agent_key))
    with pytest.raises(ValueError, match="ERR_CAID_MISMATCH"):
        gateway.dispatch_payment(forged, gateway.create_siwx_binding(intent, agent_key))

    unnamed = PaymentIntent(**{**intent.__dict__, "caid": ""})
    res = gateway.reserve_escrow(unnamed, gateway.create_siwx_binding(unnamed, agent_key))
    assert res["caid"] == expected
    entry = gateway._journal_entries[expected]
    assert entry["nonce"] == intent.nonce


def test_regression_f3_binding_must_match_intent(test_env):
    """A valid binding for one intent cannot authorize a different intent to the same URL."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    small = make_intent(label="bind_small", amount_micro_usdc=100)
    large = make_intent(label="bind_large", amount_micro_usdc=400_000)
    small_binding = gateway.create_siwx_binding(small, agent_key)
    with pytest.raises(ValueError, match="ERR_SIWX_INTENT_MISMATCH"):
        gateway.reserve_escrow(large, small_binding)

    # Re-verification on dispatch of an existing TRY_RESERVED escrow
    gateway.reserve_escrow(small, small_binding)
    rogue = gateway.create_siwx_binding(small, ed25519.Ed25519PrivateKey.generate())
    with pytest.raises(ValueError, match="ERR_SIWX_SIGNER_NOT_TRUSTED"):
        gateway.dispatch_payment(small, rogue)
    with pytest.raises(ValueError, match="ERR_SIWX_INTENT_MISMATCH"):
        gateway.dispatch_payment(small, gateway.create_siwx_binding(large, agent_key))
    assert gateway.dispatch_payment(small, small_binding)["status"] == DISPOSITION_CONFIRMED


@pytest.mark.parametrize(
    "entries, code",
    [
        ([{"caid": "c1", "amount_micro_usdc": 5}], "ERR_JOURNAL_ENTRY_MALFORMED"),
        ([{"nonce": "n1", "amount_micro_usdc": 5}], "ERR_JOURNAL_ENTRY_MALFORMED"),
        (
            [
                {"caid": "c1", "nonce": "n1", "amount_micro_usdc": 5},
                {"caid": "c2", "nonce": "n1", "amount_micro_usdc": 5},
            ],
            "ERR_JOURNAL_NONCE_CONFLICT",
        ),
    ],
)
def test_regression_f3_malformed_journal_fails_closed(tmp_path: Path, entries: List[Dict[str, Any]], code: str):
    """Journal rebuild refuses entries without caid/nonce and nonce reuse across CAIDs."""
    journal = tmp_path / "bad.jsonl"
    journal.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    with pytest.raises(ValueError, match=code):
        CoinbaseX402AgentGateway(config=GatewayConfig(journal_path=journal))


# --- Finding 4: gateway clock epochs and timestamp skew --------------------


def test_regression_f4_backdated_timestamps_cannot_bypass_velocity(test_env):
    """Finding 4: backdating timestamp_epoch by whole epochs no longer yields fresh quota."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    cap = test_env["init_bal"] * 400 // 10000
    accepted = 0
    for k in range(10):
        intent = make_intent(
            label=f"smurf_{k}", amount_micro_usdc=cap,
            timestamp=CLOCK_START - k * test_env["config"].epoch_duration_seconds,
        )
        try:
            gateway.reserve_escrow(intent, gateway.create_siwx_binding(intent, agent_key))
            accepted += 1
        except ValueError as exc:
            assert "ERR_TIMESTAMP_SKEW" in str(exc)
    assert accepted == 1
    assert gateway.get_balances()["reserved_micro_usdc"] == cap


def test_regression_f4_skew_boundaries(test_env):
    """|timestamp - gateway clock| <= max_clock_skew_seconds is accepted; beyond is rejected."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    agent_key = test_env["agent_key"]
    skew = test_env["config"].max_clock_skew_seconds
    for label, offset, ok in (("m", -skew, True), ("p", skew, True), ("mm", -skew - 1, False), ("pp", skew + 1, False)):
        intent = make_intent(label=f"skew_{label}", amount_micro_usdc=1000, timestamp=CLOCK_START + offset)
        binding = gateway.create_siwx_binding(intent, agent_key)
        if ok:
            assert gateway.reserve_escrow(intent, binding)["status"] == "RESERVED"
        else:
            with pytest.raises(ValueError, match="ERR_TIMESTAMP_SKEW"):
                gateway.reserve_escrow(intent, binding)


def test_regression_f4_epoch_assigned_from_gateway_clock(test_env):
    """Intent timestamps across an epoch boundary (within skew) do not reset the quota."""
    gateway = make_gateway(
        test_env, "clock_epoch.jsonl",
        initial_balance_micro_usdc=10_000_000, epoch_duration_seconds=1800,
        single_tx_max_bps=1000, max_velocity_bps=2000,
    )
    agent_key = test_env["agent_key"]
    clock = test_env["clock"]
    clock.now = 944445 * 1800 - 10  # 10 s before an epoch boundary
    cap = 1_000_000
    for i in range(2):
        intent = make_intent(label=f"edge_{i}", amount_micro_usdc=cap, timestamp=clock.now + 200)
        gateway.reserve_escrow(intent, gateway.create_siwx_binding(intent, agent_key))
        assert gateway._journal_entries[intent.caid]["reserved_at_epoch"] == clock.now
    over = make_intent(label="edge_over", amount_micro_usdc=1, timestamp=clock.now + 200)
    with pytest.raises(ValueError, match="ERR_VELOCITY_QUOTA_EXCEEDED"):
        gateway.reserve_escrow(over, gateway.create_siwx_binding(over, agent_key))

    clock.advance(20)  # gateway clock crosses into the next epoch
    nxt = make_intent(label="edge_next", amount_micro_usdc=cap, timestamp=clock.now)
    assert gateway.reserve_escrow(nxt, gateway.create_siwx_binding(nxt, agent_key))["status"] == "RESERVED"


# --- Finding 5: URL binding canonicalization --------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com/a/../pay",
        "https://api.example.com/./pay",
        "https://api.example.com/pay/..",
        "https://api.example.com/%2e%2e/pay",
        "https://api.example.com/%2E/pay",
        "https://api.example.com/a%2Fb",
        "https://api.example.com/a%5cb",
        "https://api.example.com/a\\b",
        "https://api.example.com./p",
        "https://api..example.com/p",
        "https://user@api.example.com/p",
        "https://api.example.com@evil.test/p",
        "ftp://api.example.com/p",
        "https:///p",
        "https://\uff45xample.com/p",
        "https://" + "\u00e9" * 70 + ".com/p",
    ],
)
def test_regression_f5_non_canonical_urls_fail_closed(test_env, url):
    """Finding 5: dot segments, encoded separators, host tricks and IDNA drift are rejected."""
    with pytest.raises(ValueError, match="ERR_URL_NOT_CANONICAL"):
        CoinbaseX402AgentGateway.parse_url_host_and_path(url)
    intent = make_intent(label="bad_url", target_url=url)
    with pytest.raises(ValueError, match="ERR_URL_NOT_CANONICAL"):
        test_env["gateway"].create_siwx_binding(intent, test_env["agent_key"])


def test_regression_f5_canonical_forms(test_env):
    """Scheme/host are lowercased, IDNA-stable hosts become A-labels, path case is kept."""
    parse = CoinbaseX402AgentGateway.parse_url_host_and_path
    assert parse("HTTPS://API.Example.COM/V1/Pay") == ("api.example.com", "/V1/Pay")
    assert parse("http://api.example.com:8080/a.b/c..d") == ("api.example.com:8080", "/a.b/c..d")
    # Single-script IDN label -> A-label; mixed-script (Latin + Cyrillic) is rejected (Wave 5)
    idn_host, _ = parse("https://\u043f\u0440\u0438\u043c\u0435\u0440.example.com/p")
    assert idn_host.isascii() and idn_host.startswith("xn--") and idn_host.endswith(".example.com")
    with pytest.raises(ValueError, match="ERR_URL_CONFUSABLE_HOST"):
        parse("https://\u0430pi.example.com/p")

    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    intent = make_intent(label="dot_bypass", target_url="https://api.example.com/pay")
    binding = gateway.create_siwx_binding(intent, test_env["agent_key"])
    with pytest.raises(ValueError, match="ERR_URL_NOT_CANONICAL"):
        gateway.verify_siwx_binding(binding, "https://api.example.com/a/../pay", "POST")


# =============================================================================
# Wave 4 regressions: query binding, scheme downgrade, multi-process journal race
# =============================================================================

import subprocess  # noqa: E402

import src.coinbase_x402_agent_gateway as gw_mod  # noqa: E402

CHARGE_URL = "https://api.example.com/v1/charge?to=alice&tier=basic"


def _gateway(env: Dict[str, Any], name: str, **kwargs: Any) -> CoinbaseX402AgentGateway:
    return CoinbaseX402AgentGateway(
        config=GatewayConfig(journal_path=env["tmp_path"] / name),
        trusted_signer_pubkeys_hex=env["trusted"],
        clock=env["clock"],
        **kwargs,
    )


@pytest.mark.parametrize(
    "presented, code",
    [
        ("https://api.example.com/v1/charge?to=mallory&tier=basic", "query mismatch"),
        ("https://api.example.com/v1/charge", "query mismatch"),
        ("https://api.example.com/v1/charge?to=alice&tier=basic&extra=1", "query mismatch"),
        ("https://api.example.com/v1/charge?tier=basic&to=alice", "query mismatch"),
        ("https://api.example.com/v1/charge?to=alice&tier=basic#&to=mallory", "ERR_URL_NOT_CANONICAL"),
        ("https://api.example.com/v1/charge#?to=alice&tier=basic", "ERR_URL_NOT_CANONICAL"),
    ],
)
def test_wave4_query_string_is_bound(test_env, presented, code):
    """A binding signed for ?to=alice&tier=basic is rejected for any other query or a fragment."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    intent = make_intent(label="charge", target_url=CHARGE_URL)
    binding = gateway.create_siwx_binding(intent, test_env["agent_key"])
    assert binding.target_query == "to=alice&tier=basic"
    assert gateway.verify_siwx_binding(binding, CHARGE_URL, "POST") is True
    with pytest.raises(ValueError, match=code):
        gateway.verify_siwx_binding(binding, presented, "POST")


@pytest.mark.parametrize(
    "url",
    [
        CHARGE_URL + "\n",
        "https://api.example.com/v1/charge?to=alice\r\nX-Evil: 1",
        "https://api.example.com/v1/charge?to=al ice",
        "https://api.example.com/v1/\tcharge",
        "https://api.example.com/v1/charge\x7f",
        "https://api.example.com/v1/charge#frag",
        None,
    ],
)
def test_wave4_control_chars_and_fragments_fail_closed(url):
    with pytest.raises(ValueError, match="ERR_URL_NOT_CANONICAL"):
        gw_mod.canonicalize_siwx_url(url)


def test_wave4_canonical_tuple_and_legacy_helper():
    assert gw_mod.canonicalize_siwx_url("HTTPS://API.Example.com/v1/charge?to=Alice&x=%2F") == (
        "https", "api.example.com", "/v1/charge", "to=Alice&x=%2F",
    )
    assert gw_mod.canonicalize_siwx_url("https://api.example.com") == ("https", "api.example.com", "/", "")
    # Legacy (host, path) helper still parses http:// for display/compat purposes
    assert CoinbaseX402AgentGateway.parse_url_host_and_path("http://h.example:8080/p?q=1") == ("h.example:8080", "/p")


def test_wave4_http_rejected_by_default(test_env):
    """http:// is refused with a typed reason code unless allow_insecure_http=True."""
    with pytest.raises(ValueError, match="ERR_URL_INSECURE_SCHEME"):
        gw_mod.canonicalize_siwx_url("http://api.example.com/v1/charge")
    assert gw_mod.canonicalize_siwx_url("http://api.example.com/p", allow_insecure_http=True)[0] == "http"

    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    assert gateway.allow_insecure_http is False
    intent = make_intent(label="plain_http", target_url="http://api.example.com/v1/charge")
    with pytest.raises(ValueError, match="ERR_URL_INSECURE_SCHEME"):
        gateway.create_siwx_binding(intent, test_env["agent_key"])

    https_intent = make_intent(label="https_ok", target_url=CHARGE_URL)
    binding = gateway.create_siwx_binding(https_intent, test_env["agent_key"])
    with pytest.raises(ValueError, match="ERR_URL_INSECURE_SCHEME"):
        gateway.verify_siwx_binding(binding, CHARGE_URL.replace("https://", "http://"), "POST")

    # Only the literal True enables http
    truthy = _gateway(test_env, "truthy.jsonl", allow_insecure_http="yes")
    assert truthy.allow_insecure_http is False


def test_wave4_cross_scheme_rejected_even_when_http_allowed(test_env):
    """With allow_insecure_http=True the scheme is still bound in both directions."""
    gateway = _gateway(test_env, "insecure_ok.jsonl", allow_insecure_http=True)
    agent_key = test_env["agent_key"]
    http_url = CHARGE_URL.replace("https://", "http://")

    http_binding = gateway.create_siwx_binding(make_intent(label="h1", target_url=http_url), agent_key)
    assert http_binding.target_scheme == "http"
    with pytest.raises(ValueError, match="scheme mismatch"):
        gateway.verify_siwx_binding(http_binding, CHARGE_URL, "POST")

    https_binding = gateway.create_siwx_binding(make_intent(label="h2", target_url=CHARGE_URL), agent_key)
    with pytest.raises(ValueError, match="scheme mismatch"):
        gateway.verify_siwx_binding(https_binding, http_url, "POST")

    http_intent = make_intent(label="h3", target_url=http_url)
    res = gateway.reserve_escrow(http_intent, gateway.create_siwx_binding(http_intent, agent_key))
    assert res["status"] == "RESERVED"


# --- multi-process journal race ---------------------------------------------

_RACE_WORKER = r'''
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from cryptography.hazmat.primitives.asymmetric import ed25519
from src.coinbase_x402_agent_gateway import CoinbaseX402AgentGateway, GatewayConfig, PaymentIntent

journal, mode, label, sync, now = Path(sys.argv[2]), sys.argv[3], sys.argv[4], Path(sys.argv[5]), int(sys.argv[6])
key = ed25519.Ed25519PrivateKey.generate()
gw = CoinbaseX402AgentGateway(
    GatewayConfig(journal_path=journal, initial_balance_micro_usdc=10_000_000,
                  single_tx_max_bps=10000, max_velocity_bps=2500),
    trusted_signer_pubkeys_hex=[key.public_key().public_bytes_raw().hex()],
    clock=lambda: now,
)
amount = {"nonce": 1000 + len(label), "velocity": 1_500_000, "caid": 1000}[mode]
nonce = {"nonce": "shared_nonce", "velocity": "nonce_" + label, "caid": "shared_nonce"}[mode]
agent = "agent-shared" if mode == "caid" else "agent-" + label
intent = PaymentIntent.build(agent_id=agent, payee_address="0xpayee", amount_micro_usdc=amount,
                             target_url="https://api.example.com/v1/charge?to=alice", target_method="POST",
                             chain_id=8453, nonce=nonce, timestamp_epoch=now)
binding = gw.create_siwx_binding(intent, key)
(sync / ("ready_" + label)).touch()
deadline = time.monotonic() + 30
while not (sync / "go").exists():
    if time.monotonic() > deadline:
        print(json.dumps({"ok": False, "err": "TIMEOUT_WAITING_FOR_GO"}))
        sys.exit(3)
    time.sleep(0.002)
try:
    gw.reserve_escrow(intent, binding)
    print(json.dumps({"ok": True, "err": ""}))
except Exception as exc:
    print(json.dumps({"ok": False, "err": str(exc)}))
'''


def _run_race(tmp_path: Path, mode: str) -> List[Dict[str, Any]]:
    """Two real OS processes load the same journal, then reserve after a shared barrier."""
    worker = tmp_path / "race_worker.py"
    worker.write_text(_RACE_WORKER, encoding="utf-8")
    sync = tmp_path / f"sync_{mode}"
    sync.mkdir()
    journal = tmp_path / f"race_{mode}.jsonl"
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
    labels = ("a", "bb")
    procs = [
        subprocess.Popen(
            [sys.executable, str(worker), str(REPO_ROOT), str(journal), mode, label, str(sync), str(CLOCK_START)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=str(tmp_path), text=True,
        )
        for label in labels
    ]
    try:
        deadline = time.monotonic() + 60
        while not all((sync / f"ready_{label}").exists() for label in labels):
            assert time.monotonic() < deadline, "workers did not reach the barrier"
            assert all(p.poll() is None for p in procs), [p.communicate()[1] for p in procs]
            time.sleep(0.005)
        (sync / "go").touch()
        outputs = [p.communicate(timeout=60) for p in procs]
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
    results = []
    for out, err in outputs:
        lines = out.strip().splitlines()
        assert lines, err
        results.append(json.loads(lines[-1]))
    return results


@pytest.mark.parametrize(
    "mode, expected_err",
    [
        ("nonce", "ERR_NONCE_REPLAY"),
        ("velocity", "ERR_VELOCITY_QUOTA_EXCEEDED"),
        ("caid", "ERR_DUPLICATE_CAID_IN_FLIGHT"),
    ],
)
def test_wave4_multiprocess_race_exactly_one_succeeds(tmp_path: Path, mode: str, expected_err: str):
    """Same nonce / 2 x 60% of the epoch cap / same CAID from two processes: exactly one wins."""
    results = _run_race(tmp_path, mode)
    winners = [r for r in results if r["ok"]]
    losers = [r for r in results if not r["ok"]]
    assert len(winners) == 1, results
    assert len(losers) == 1 and expected_err in losers[0]["err"], results

    reloaded = CoinbaseX402AgentGateway(
        config=GatewayConfig(journal_path=tmp_path / f"race_{mode}.jsonl", initial_balance_micro_usdc=10_000_000)
    )
    held = [e for e in reloaded._journal_entries.values() if e["disposition"] == DISPOSITION_TRY_RESERVED]
    assert len(held) == 1


def test_wave4_stale_instance_replays_journal_under_lock(test_env):
    """An instance created before another instance's writes still sees them (no stale state)."""
    agent_key = test_env["agent_key"]
    gw_a = _gateway(test_env, "shared.jsonl", private_key=test_env["gateway_key"])
    gw_b = _gateway(test_env, "shared.jsonl")
    first = make_intent(label="stale_a", amount_micro_usdc=1000, nonce="stale_shared")
    gw_a.reserve_escrow(first, gw_a.create_siwx_binding(first, agent_key))

    assert gw_b.get_balances()["reserved_micro_usdc"] == 1000
    replay = make_intent(label="stale_b", amount_micro_usdc=2000, nonce="stale_shared")
    with pytest.raises(RuntimeError, match="ERR_NONCE_REPLAY"):
        gw_b.reserve_escrow(replay, gw_b.create_siwx_binding(replay, agent_key))
    with pytest.raises(RuntimeError, match="ERR_DUPLICATE_CAID_IN_FLIGHT"):
        gw_b.reserve_escrow(first, gw_b.create_siwx_binding(first, agent_key))

    # A partially written trailing line is not consumed until it is complete
    journal = test_env["tmp_path"] / "shared.jsonl"
    size_before = journal.stat().st_size
    with open(journal, "ab") as fh:
        fh.write(b'{"partial":')
    assert gw_b.get_balances()["reserved_micro_usdc"] == 1000
    assert gw_b._journal_offset == size_before
    assert gw_b.lock_path == journal.with_name("shared.jsonl.lock") and gw_b.lock_path.exists()


def test_wave4_dispatch_claim_blocks_concurrent_dispatch_and_detects_state_change(test_env):
    """While one instance is inside the HTTP call, another cannot dispatch the same CAID."""
    agent_key = test_env["agent_key"]
    gw_a = _gateway(test_env, "dispatch.jsonl")
    gw_b = _gateway(test_env, "dispatch.jsonl")
    claim_amt = 6100
    intent = make_intent(label="dispatch_claim", amount_micro_usdc=claim_amt)
    binding = gw_a.create_siwx_binding(intent, agent_key)
    seen: List[str] = []

    def client_racing(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        assert url == intent.target_url
        try:
            gw_b.dispatch_payment(intent, binding)
        except RuntimeError as exc:
            seen.append(str(exc))
        assert gw_b.get_balances()["reserved_micro_usdc"] == claim_amt
        return {"status_code": 200, "tx_hash": "0xonce"}

    assert gw_a.dispatch_payment(intent, binding, http_client=client_racing)["status"] == DISPOSITION_CONFIRMED
    assert len(seen) == 1 and "ERR_DUPLICATE_CAID_DISPATCH_IN_FLIGHT" in seen[0]
    assert gw_b.get_balances()["settled_micro_usdc"] == claim_amt

    # Another process reconciles the in-flight claim during the call -> fail closed
    intent2 = make_intent(label="dispatch_recon", amount_micro_usdc=7000)
    binding2 = gw_a.create_siwx_binding(intent2, agent_key)

    def client_reconciled(method: str, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        gw_b.reconcile(intent2.caid, DISPOSITION_REFUTED)
        return {"status_code": 200, "tx_hash": "0xlate"}

    with pytest.raises(RuntimeError, match="ERR_CAID_STATE_CHANGED_CONCURRENTLY"):
        gw_a.dispatch_payment(intent2, binding2, http_client=client_reconciled)
    assert gw_a.get_balances()["settled_micro_usdc"] == claim_amt


def test_wave4_append_requires_lock(test_env):
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    with pytest.raises(RuntimeError, match="ERR_JOURNAL_LOCK_NOT_HELD"):
        gateway._append_journal_entry({"caid": "c", "nonce": "n", "amount_micro_usdc": 1})
    assert not test_env["journal_path"].exists()


def test_wave4_cli_reconcile_resolves_latched_caid(monkeypatch, test_env):
    """main --reconcile resolves an EFFECT_INDETERMINATE CAID from the journal and exits 0."""
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    intent = make_intent(label="cli_recon", amount_micro_usdc=4200)
    binding = gateway.create_siwx_binding(intent, test_env["agent_key"])
    gateway.dispatch_payment(intent, binding, http_client=_dispatch_504)
    monkeypatch.setattr(
        sys, "argv",
        ["gateway", "--reconcile", intent.caid, "--disposition", DISPOSITION_REFUTED,
         "--journal-path", str(test_env["journal_path"])],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    assert gateway.get_balances()["reserved_micro_usdc"] == 0
    assert gateway._journal_entries[intent.caid]["disposition"] == DISPOSITION_REFUTED


# =============================================================================
# Wave 5: payee-host policy (confusable labels, optional host allow-set)
# =============================================================================

MIXED_HOST_URL = "https://\u0430pi.example.com/v1/charge"  # Cyrillic a + Latin "pi"
PURE_CYRILLIC_URL = "https://\u043f\u0440\u0438\u043c\u0435\u0440.example.com/v1/charge"
PURE_GREEK_URL = "https://\u03b1\u03b2\u03b3.example.com/v1/charge"
JAPANESE_URL = "https://\u65e5\u672c\u3054\u30ab.example.com/v1/charge"  # Han + Hiragana + Katakana


@pytest.mark.parametrize(
    "url",
    [
        MIXED_HOST_URL,
        "https://xn--pi-6kc.example.com/v1/charge",  # same label already in A-label form
        "https://p\u0430ypal.example.com/v1/charge",
        "https://\u03b1pi.example.com/v1/charge",  # Greek alpha + Latin
        "https://ex\u0430mple.com:8443/v1/charge",
    ],
)
def test_wave5_mixed_script_host_rejected_by_default(test_env, url):
    """A label mixing Latin with Cyrillic/Greek fails closed, in Unicode or xn-- form."""
    with pytest.raises(ValueError, match="ERR_URL_CONFUSABLE_HOST"):
        gw_mod.canonicalize_siwx_url(url)
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    intent = make_intent(label="mixed_host", target_url=url)
    with pytest.raises(ValueError, match="ERR_URL_CONFUSABLE_HOST"):
        gateway.create_siwx_binding(intent, test_env["agent_key"])


def test_wave5_mixed_script_binding_cannot_be_reserved(test_env):
    """The red-team case: a binding signed for the mixed-script host is never reserved."""
    permissive = _gateway(test_env, "permissive.jsonl", allow_mixed_script_hosts=True)
    intent = make_intent(label="mixed_reserve", target_url=MIXED_HOST_URL)
    binding = permissive.create_siwx_binding(intent, test_env["agent_key"])
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    with pytest.raises(ValueError, match="ERR_URL_CONFUSABLE_HOST"):
        gateway.reserve_escrow(intent, binding)
    assert gateway.get_balances()["reserved_micro_usdc"] == 0
    assert not test_env["journal_path"].exists()
    # Explicit opt-in restores the previous acceptance
    assert permissive.reserve_escrow(intent, binding)["status"] == "RESERVED"
    assert permissive.allow_mixed_script_hosts is True and gateway.allow_mixed_script_hosts is False


@pytest.mark.parametrize("url", [PURE_CYRILLIC_URL, PURE_GREEK_URL, JAPANESE_URL, "https://api-2.example.com/v1/charge"])
def test_wave5_single_script_idn_accepted(test_env, url):
    gateway: CoinbaseX402AgentGateway = test_env["gateway"]
    intent = make_intent(label="pure_idn", target_url=url)
    assert gateway.reserve_escrow(intent, gateway.create_siwx_binding(intent, test_env["agent_key"]))["status"] == "RESERVED"


def test_wave5_idn_opt_out(test_env):
    """allow_idn_hosts=False rejects every IDN label; only the literal False opts out."""
    with pytest.raises(ValueError, match="ERR_URL_IDN_HOST_REJECTED"):
        gw_mod.canonicalize_siwx_url(PURE_CYRILLIC_URL, allow_idn_hosts=False)
    strict = _gateway(test_env, "no_idn.jsonl", allow_idn_hosts=False)
    with pytest.raises(ValueError, match="ERR_URL_IDN_HOST_REJECTED"):
        strict.create_siwx_binding(make_intent(label="no_idn", target_url=PURE_CYRILLIC_URL), test_env["agent_key"])
    assert strict.canonical_target("https://api.example.com/x")[1] == "api.example.com"
    assert _gateway(test_env, "idn_zero.jsonl", allow_idn_hosts=0).allow_idn_hosts is True
    with pytest.raises(ValueError, match="ERR_URL_NOT_CANONICAL: invalid A-label"):
        gw_mod.canonicalize_siwx_url("https://xn--zz-0000.example.com/p")


def test_wave5_allowed_target_hosts_accept_and_reject(test_env):
    """With an allow-set, only listed canonical hosts (IDNA + port aware) are reservable."""
    agent_key = test_env["agent_key"]
    gateway = _gateway(
        test_env, "hosts.jsonl",
        allowed_target_hosts=["API.Example.com", "pay.example.com:8443", "\u043f\u0440\u0438\u043c\u0435\u0440.example.com"],
    )
    assert "api.example.com" in gateway.allowed_target_hosts
    for label, url in (
        ("ok1", "https://api.example.com/v1/charge"),
        ("ok2", "https://pay.example.com:8443/v1/charge"),
        ("ok3", PURE_CYRILLIC_URL),
    ):
        intent = make_intent(label=label, target_url=url, amount_micro_usdc=1000)
        assert gateway.reserve_escrow(intent, gateway.create_siwx_binding(intent, agent_key))["status"] == "RESERVED"

    reserved_before = gateway.get_balances()
    journal = test_env["tmp_path"] / "hosts.jsonl"
    size_before = journal.stat().st_size
    for label, url in (
        ("no1", "https://evil.example.com/v1/charge"),
        ("no2", "https://pay.example.com/v1/charge"),  # port differs from allow-set entry
        ("no3", "https://api.example.com:8443/v1/charge"),
    ):
        intent = make_intent(label=label, target_url=url, amount_micro_usdc=1000)
        with pytest.raises(ValueError, match="ERR_TARGET_HOST_NOT_ALLOWED"):
            gateway.reserve_escrow(intent, gateway.create_siwx_binding(intent, agent_key))
        with pytest.raises(ValueError, match="ERR_TARGET_HOST_NOT_ALLOWED"):
            gateway.dispatch_payment(intent, gateway.create_siwx_binding(intent, agent_key))
        assert intent.nonce not in gateway._consumed_nonces
    assert gateway.get_balances() == reserved_before
    assert journal.stat().st_size == size_before


def test_wave5_allowed_target_hosts_none_empty_and_invalid(test_env):
    agent_key = test_env["agent_key"]
    default_gw: CoinbaseX402AgentGateway = test_env["gateway"]
    assert default_gw.allowed_target_hosts is None
    intent = make_intent(label="any_host", target_url="https://anything.example.org/x")
    assert default_gw.reserve_escrow(intent, default_gw.create_siwx_binding(intent, agent_key))["status"] == "RESERVED"

    empty = _gateway(test_env, "empty_hosts.jsonl", allowed_target_hosts=[])
    assert empty.allowed_target_hosts == frozenset()
    intent2 = make_intent(label="empty_set", target_url="https://api.example.com/x")
    with pytest.raises(ValueError, match="ERR_TARGET_HOST_NOT_ALLOWED"):
        empty.reserve_escrow(intent2, empty.create_siwx_binding(intent2, agent_key))

    for bad in ("", None, "api.example.com/path", "api.example.com.", "\u0430pi.example.com", "user@api.example.com"):
        with pytest.raises(ValueError, match="ERR_INVALID_ALLOWED_TARGET_HOST"):
            _gateway(test_env, "bad_hosts.jsonl", allowed_target_hosts=[bad])
