#!/usr/bin/env python3
"""
Unit and adversarial test suite for SovereignPhaseVKernel (src/sovereign_phase_v_kernel.py).
Evaluated under the stated model with real Ed25519 cryptography and zero mocks.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import re
from typing import Dict

from cryptography.hazmat.primitives.asymmetric import ed25519
import pytest

from src.sovereign_phase_v_kernel import SovereignPhaseVKernel
from src.temporal_authority_guard import (
    IntentScope,
    TemporalAuthorityGuard,
    TemporalIntentEnvelope,
)
from src.temporal_graph_router import TemporalGraphRouter


def _make_signed_intent(
    priv: ed25519.Ed25519PrivateKey,
    actor_id: str = "spiffe://sovereign.nexus/agent/exec-01",
    issued_at: int = 1000,
    not_before: int = 1000,
    expires_at: int = 1060,
) -> TemporalIntentEnvelope:
    unsigned = TemporalIntentEnvelope(
        actor_spiffe_id=actor_id,
        effect_class="FINANCIAL_TRANSFER",
        idempotency_key="idem_phase_v_01",
        policy_version="v5.0",
        session_id="session_live_01",
        issued_at_epoch_sec=issued_at,
        not_before_epoch_sec=not_before,
        expires_at_epoch_sec=expires_at,
        max_retries=1,
        delegation_chain=("GENESIS",),
        taint_level=0,
        scope=IntentScope(
            allowed_hosts=("api.stripe.com",),
            allowed_tools=("execute_payment",),
            max_amount_minor=50000,
            max_blast_radius_bps=2000,
        ),
        preconditions={"balance_sufficient": True},
        payload={"invoice_id": "inv_500"},
    )
    sig = priv.sign(unsigned.canonical_unsigned_bytes()).hex()
    return unsigned.with_signature(sig)


def _sample_tools() -> Dict[str, dict]:
    return {
        "execute_payment": {"description": "execute payment settlement"},
        "unused_analytics_tool_1": {"description": "heavy unused schema " * 20},
        "unused_analytics_tool_2": {"description": "another unused schema " * 20},
    }


def test_1_nominal_five_station_pipeline_commits() -> None:
    priv = ed25519.Ed25519PrivateKey.generate()
    actor_id = "spiffe://sovereign.nexus/agent/exec-01"
    guard = TemporalAuthorityGuard({actor_id: priv.public_key()})
    kernel = SovereignPhaseVKernel(guard)

    router = TemporalGraphRouter(":memory:")
    chunk = router.ingest_document_version(
        "docs/stripe_api.md", "Stripe API v2026 endpoint spec", valid_from_epoch_sec=1000
    )
    env = _make_signed_intent(priv, actor_id=actor_id)

    old_code = "def helper():\n    return 1\n\ndef settle(x):\n    return x\n"
    new_code = "def helper():\n    return 1\n\ndef settle(x):\n    return x + 1\n"

    receipt = kernel.execute_five_station_pipeline(
        task_id="task_nominal",
        static_system_prefix="You are SovereignNexus deterministic verifier.",
        task_description="execute payment settlement",
        all_tool_schemas=_sample_tools(),
        old_file_code=old_code,
        candidate_code=new_code,
        raw_test_log="test_1 PASSED\ntest_2 PASSED\n",
        memory_chunk=chunk,
        current_epoch_sec=1010,
        max_memory_ttl_sec=3600,
        intent_envelope=env,
        live_preconditions={"balance_sufficient": True},
        target_file_path="src/payment_worker.py",
        requested_tool="execute_payment",
        requested_amount_minor=10000,
    )
    assert receipt.permitted is True
    assert receipt.halted_at_station == 5
    assert receipt.status_code == "OK_ALL_5_STATIONS_VERIFIED_AND_COMMITTED"
    assert receipt.token_savings_bps > 0
    assert receipt.memory_confidence_bps > 8000
    assert receipt.to_dict()["permitted"] is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt.permitted = False  # type: ignore


def test_2_station_0_halts_on_stale_memory_and_prefix_contamination_and_error_loop() -> None:
    priv = ed25519.Ed25519PrivateKey.generate()
    actor_id = "spiffe://sovereign.nexus/agent/exec-01"
    guard = TemporalAuthorityGuard({actor_id: priv.public_key()})
    kernel = SovereignPhaseVKernel(guard)

    router = TemporalGraphRouter(":memory:")
    chunk = router.ingest_document_version(
        "docs/stripe_api.md", "Stripe v2024 deprecated spec", valid_from_epoch_sec=1000
    )
    env = _make_signed_intent(priv, actor_id=actor_id, issued_at=1000, not_before=1000, expires_at=999999)

    # 1. Dynamic timestamp in static prefix halts at Station 0
    r_prefix = kernel.execute_five_station_pipeline(
        task_id="task_prefix",
        static_system_prefix="Prefix contaminated with 2026-10-31T12:00:00Z",
        task_description="execute payment",
        all_tool_schemas=_sample_tools(),
        old_file_code="x = 1\n",
        candidate_code="x = 2\n",
        raw_test_log="PASSED",
        memory_chunk=chunk,
        current_epoch_sec=1010,
        max_memory_ttl_sec=3600,
        intent_envelope=env,
        live_preconditions={"balance_sufficient": True},
        target_file_path="src/a.py",
        requested_tool="execute_payment",
        requested_amount_minor=100,
    )
    assert r_prefix.permitted is False
    assert r_prefix.halted_at_station == 0
    assert r_prefix.status_code == "HALT_STATION_0_PREFIX_CACHE_CONTAMINATED"

    # 2. Stale memory exceeding API TTL halts at Station 0 with HALT_STALE_MEMORY_NEEDS_RESEARCH
    r_stale = kernel.execute_five_station_pipeline(
        task_id="task_stale_mem",
        static_system_prefix="Clean static prefix",
        task_description="execute payment",
        all_tool_schemas=_sample_tools(),
        old_file_code="x = 1\n",
        candidate_code="x = 2\n",
        raw_test_log="PASSED",
        memory_chunk=chunk,
        current_epoch_sec=5000,
        max_memory_ttl_sec=1000,  # age=4000 > ttl=1000
        intent_envelope=env,
        live_preconditions={"balance_sufficient": True},
        target_file_path="src/a.py",
        requested_tool="execute_payment",
        requested_amount_minor=100,
    )
    assert r_stale.permitted is False
    assert r_stale.halted_at_station == 0
    assert "HALT_STALE_MEMORY_NEEDS_RESEARCH" in r_stale.status_code

    # 3. Repetitive identical error log halts at Station 0 on 2nd repeat
    r_loop = kernel.execute_five_station_pipeline(
        task_id="task_stale_mem",  # same task_id with identical raw_test_log
        static_system_prefix="Clean static prefix",
        task_description="execute payment",
        all_tool_schemas=_sample_tools(),
        old_file_code="x = 1\n",
        candidate_code="x = 2\n",
        raw_test_log="PASSED",
        memory_chunk=chunk,
        current_epoch_sec=1010,
        max_memory_ttl_sec=3600,
        intent_envelope=env,
        live_preconditions={"balance_sufficient": True},
        target_file_path="src/a.py",
        requested_tool="execute_payment",
        requested_amount_minor=100,
    )
    assert r_loop.permitted is False
    assert r_loop.halted_at_station == 0
    assert r_loop.status_code == "HALT_STATION_0_REPETITIVE_ERROR_LOOP"


def test_3_stations_1_3_4_halt_time_bomb_persistence_dns_and_402_replay() -> None:
    priv = ed25519.Ed25519PrivateKey.generate()
    actor_id = "spiffe://sovereign.nexus/agent/exec-01"
    guard = TemporalAuthorityGuard({actor_id: priv.public_key()})
    kernel = SovereignPhaseVKernel(guard)

    router = TemporalGraphRouter(":memory:")
    chunk = router.ingest_document_version("docs/spec.md", "Spec v1", valid_from_epoch_sec=1000)
    env = _make_signed_intent(priv, actor_id=actor_id)

    # 1. Station 3 blocks deferred time.sleep() time bomb
    r_sleep = kernel.execute_five_station_pipeline(
        task_id="t_sleep",
        static_system_prefix="Static prefix",
        task_description="execute payment",
        all_tool_schemas=_sample_tools(),
        old_file_code="x = 1\n",
        candidate_code="import time\ntime.sleep(3600)\n",
        raw_test_log="ok 1",
        memory_chunk=chunk,
        current_epoch_sec=1010,
        max_memory_ttl_sec=3600,
        intent_envelope=env,
        live_preconditions={"balance_sufficient": True},
        target_file_path="src/worker.py",
        requested_tool="execute_payment",
        requested_amount_minor=100,
    )
    assert r_sleep.permitted is False
    assert r_sleep.halted_at_station == 3
    assert r_sleep.status_code == "HALT_DEFERRED_SLEEP_BLOCKED"

    # 2. Station 3 blocks cron persistence write
    r_cron = kernel.execute_five_station_pipeline(
        task_id="t_cron",
        static_system_prefix="Static prefix",
        task_description="execute payment",
        all_tool_schemas=_sample_tools(),
        old_file_code="x = 1\n",
        candidate_code="x = 2\n",
        raw_test_log="ok 2",
        memory_chunk=chunk,
        current_epoch_sec=1010,
        max_memory_ttl_sec=3600,
        intent_envelope=env,
        live_preconditions={"balance_sufficient": True},
        target_file_path="/etc/cron.d/backdoor",
        requested_tool="execute_payment",
        requested_amount_minor=100,
    )
    assert r_cron.permitted is False
    assert r_cron.halted_at_station == 3
    assert "HALT_PERSISTENCE_WRITE_DENIED" in r_cron.status_code

    # 3. Station 4 blocks DNS TXT exfiltration
    r_dns = kernel.execute_five_station_pipeline(
        task_id="t_dns",
        static_system_prefix="Static prefix",
        task_description="execute payment",
        all_tool_schemas=_sample_tools(),
        old_file_code="x = 1\n",
        candidate_code="x = 2\n",
        raw_test_log="ok 3",
        memory_chunk=chunk,
        current_epoch_sec=1010,
        max_memory_ttl_sec=3600,
        intent_envelope=env,
        live_preconditions={"balance_sufficient": True},
        target_file_path="src/worker.py",
        requested_tool="execute_payment",
        requested_amount_minor=100,
        network_protocol="DNS",
        destination_host="api.stripe.com",
        dns_record_type="TXT",
    )
    assert r_dns.permitted is False
    assert r_dns.halted_at_station == 4
    assert "HALT_DNS_RECORD_TYPE_DENIED" in r_dns.status_code

    # 4. Station 1 blocks 402 insufficient balance and latches DENIED_TERMINAL on replay
    r_402 = kernel.execute_five_station_pipeline(
        task_id="t_402_a",
        static_system_prefix="Static prefix",
        task_description="execute payment",
        all_tool_schemas=_sample_tools(),
        old_file_code="x = 1\n",
        candidate_code="x = 2\n",
        raw_test_log="ok 4",
        memory_chunk=chunk,
        current_epoch_sec=1010,
        max_memory_ttl_sec=3600,
        intent_envelope=env,
        live_preconditions={"balance_sufficient": False},
        target_file_path="src/worker.py",
        requested_tool="execute_payment",
        requested_amount_minor=100,
    )
    assert r_402.permitted is False
    assert r_402.halted_at_station == 1
    assert "HALT_PRECONDITION_DENIED_TERMINAL" in r_402.status_code

    # Replay after balance top-up still halts at Station 1 with HALT_PRIOR_DENIAL_IS_TERMINAL
    r_replay = kernel.execute_five_station_pipeline(
        task_id="t_402_b",
        static_system_prefix="Static prefix",
        task_description="execute payment",
        all_tool_schemas=_sample_tools(),
        old_file_code="x = 1\n",
        candidate_code="x = 2\n",
        raw_test_log="ok 5",
        memory_chunk=chunk,
        current_epoch_sec=1020,
        max_memory_ttl_sec=3600,
        intent_envelope=env,
        live_preconditions={"balance_sufficient": True},
        target_file_path="src/worker.py",
        requested_tool="execute_payment",
        requested_amount_minor=100,
    )
    assert r_replay.permitted is False
    assert r_replay.halted_at_station == 1
    assert "HALT_PRIOR_DENIAL_IS_TERMINAL" in r_replay.status_code

    # 5. Station 1 rejects forged signature on registration
    bad_env = env.with_signature("00" * 64)
    guard2 = TemporalAuthorityGuard({actor_id: priv.public_key()})
    kernel2 = SovereignPhaseVKernel(guard2)
    r_bad_sig = kernel2.execute_five_station_pipeline(
        task_id="t_badsig",
        static_system_prefix="Static prefix",
        task_description="execute payment",
        all_tool_schemas=_sample_tools(),
        old_file_code="x = 1\n",
        candidate_code="x = 2\n",
        raw_test_log="ok 6",
        memory_chunk=chunk,
        current_epoch_sec=1010,
        max_memory_ttl_sec=3600,
        intent_envelope=bad_env,
        live_preconditions={"balance_sufficient": True},
        target_file_path="src/worker.py",
        requested_tool="execute_payment",
        requested_amount_minor=100,
    )
    assert r_bad_sig.permitted is False
    assert r_bad_sig.halted_at_station == 1
    assert r_bad_sig.status_code == "HALT_INVALID_INTENT_SIGNATURE"


def test_4_epistemic_purity_no_banned_words() -> None:
    banned = [
        r"\bguarant[e]e\b",
        r"\bguarant[e]ed\b",
        r"\bbullet[p]roof\b",
        r"\benterprise-[g]rade\b",
        r"\bproduction-[s]afe\b",
        r"\b100% [s]ecure\b",
    ]
    for fpath in (
        Path("src/sovereign_phase_v_kernel.py"),
        Path("tests/test_sovereign_phase_v_kernel.py"),
    ):
        text = fpath.read_text(encoding="utf-8")
        for pat in banned:
            assert not re.findall(pat, text, re.IGNORECASE)
