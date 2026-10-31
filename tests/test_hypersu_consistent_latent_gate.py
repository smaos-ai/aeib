#!/usr/bin/env python3
"""
tests/test_hypersu_consistent_latent_gate.py — Falsification Suite for SovereignNexus Tri-Core Invariant Engine

Verifies:
1. HyperSU Raw-History Pointer Cache: >70% context compaction, FTS5 retrieval, tamper detection.
2. Latent State Interceptor: Blocks unverified or tampered KV-Cache telepathy transfers (Swarm Telepathy).
3. Griffiths Consistent History Ledger: Blocks split-spend budget decoherence and phase regressions.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.hypersu_consistent_latent_gate import (
    ConsistentHistoryLedger,
    LatentStateInterceptor,
    LatentStatePacket,
    RawHistoryPointerCache,
    sha256_jcs_caid,
)


def test_1_raw_history_pointer_cache_compaction_and_fts5_retrieval() -> None:
    """Verify Raw-History Pointer Cache achieves >70% context compaction + FTS5 retrieval."""
    cache = RawHistoryPointerCache(":memory:")
    raw_code_block = (
        "def settle_escrow_transaction(tenant_id: str, amount_minor: int) -> dict:\n"
        "    if amount_minor <= 0:\n"
        "        raise ValueError('ERR_NON_POSITIVE_ESCROW_AMOUNT')\n"
        "    # Critical idempotency effect-key check before socket dispatch\n"
        "    effect_key = f'{tenant_id}:{amount_minor}:settled'\n"
        "    return {'status': 'COMMITTED', 'effect_key': effect_key}\n"
    )
    ptr = cache.ingest_raw_span("src/escrow.py", 10, 17, raw_code_block)

    # Immutability (frozen=True) test
    with pytest.raises(FrozenInstanceError):
        ptr.ref_id = "illegal_mutation"  # type: ignore

    # Exact hash length check (10 chars)
    short_hash = ptr.content_caid.split(":")[1][:10]
    assert len(short_hash) == 10
    assert ptr.ref_id == f"ref_{short_hash}"

    # Verify >70% context byte reduction when injecting pointer instead of raw block
    compression_ratio = 1.0 - (len(ptr.pointer_token_str.encode("utf-8")) / ptr.raw_byte_len)
    assert compression_ratio > 0.70

    # Verify FTS5 raw search finds the exact span without vector summarization loss
    hits = cache.search_raw_fts5("idempotency effect_key")
    assert len(hits) == 1
    assert hits[0].ref_id == ptr.ref_id
    caid_in_token = hits[0].pointer_token_str.split("caid=")[1].rstrip("]")
    assert len(caid_in_token) == 10

    # Verify dereferencing returns 100% verbatim raw text with SHA-256 verification
    restored = cache.fetch_reference(ptr.ref_id)
    assert restored == raw_code_block

    # Boundary and error cases
    with pytest.raises(ValueError, match="ERR_EMPTY_RAW_SPAN"):
        cache.ingest_raw_span("", 1, 5, "code")
    with pytest.raises(ValueError, match="ERR_EMPTY_RAW_SPAN"):
        cache.ingest_raw_span("path.py", 1, 5, "")
    with pytest.raises(ValueError, match="ERR_INVALID_LINE_RANGE"):
        cache.ingest_raw_span("path.py", 0, 5, "code")
    with pytest.raises(ValueError, match="ERR_INVALID_LINE_RANGE"):
        cache.ingest_raw_span("path.py", 10, 5, "code")

    # Unknown ref
    with pytest.raises(KeyError, match="HALT_UNKNOWN_POINTER_REF"):
        cache.fetch_reference("ref_nonexistent")

    # Tamper detection
    with cache._conn:
        cache._conn.execute(
            "UPDATE raw_spans SET raw_text = 'tampered code' WHERE ref_id = ?",
            (ptr.ref_id,),
        )
    with pytest.raises(ValueError, match="HALT_RAW_SPAN_TAMPER_DETECTED"):
        cache.fetch_reference(ptr.ref_id)


def test_2_latent_state_interceptor_blocks_swarm_telepathy_bypasses() -> None:
    """Verify Latent State Interceptor blocks unverified, low-fidelity, or tampered KV-Cache transfers."""
    interceptor = LatentStateInterceptor(
        allowed_model_backbones=frozenset({"qwen3-8b-v1", "llama-3.3-70b"})
    )
    fake_kv_bytes = b"\x00\x01\x02\x03_KV_CACHE_LATENT_TENSOR_PAYLOAD"
    valid_tensor_caid = sha256_jcs_caid(fake_kv_bytes)

    # Empty backbone set validation
    with pytest.raises(ValueError, match="ERR_EMPTY_ALLOWED_BACKBONES"):
        LatentStateInterceptor(frozenset())

    # 2A: Empty KV-Cache bytes -> HALT!
    empty_pkt = LatentStatePacket(
        sender_agent_id="agent_alpha",
        receiver_agent_id="agent_beta",
        model_backbone_id="qwen3-8b-v1",
        kv_cache_raw_bytes=b"",
        semantic_projection={"action": "test", "risk_tier": "T0", "target_scope": "x"},
        projection_fidelity_bps=9500,
        bound_tensor_caid=valid_tensor_caid,
    )
    v_empty = interceptor.inspect_kv_cache_transfer(empty_pkt)
    assert v_empty.allowed is False
    assert v_empty.status_code == "HALT_EMPTY_KV_CACHE_PAYLOAD"

    # 2B: Raw KV-Cache transfer without semantic projection -> HALT!
    unprojected_pkt = LatentStatePacket(
        sender_agent_id="agent_alpha",
        receiver_agent_id="agent_beta",
        model_backbone_id="qwen3-8b-v1",
        kv_cache_raw_bytes=fake_kv_bytes,
        semantic_projection=None,
        projection_fidelity_bps=9500,
        bound_tensor_caid=valid_tensor_caid,
    )
    v_unproj = interceptor.inspect_kv_cache_transfer(unprojected_pkt)
    assert v_unproj.allowed is False
    assert v_unproj.status_code == "HALT_LATENT_TRANSFER_UNVERIFIABLE:MISSING_PROJECTION"

    # 2C: Spoofed tensor hash -> HALT!
    tampered_pkt = LatentStatePacket(
        sender_agent_id="agent_alpha",
        receiver_agent_id="agent_beta",
        model_backbone_id="qwen3-8b-v1",
        kv_cache_raw_bytes=fake_kv_bytes,
        semantic_projection={
            "action": "summarize_module",
            "risk_tier": "T0_READONLY",
            "target_scope": "src/escrow.py",
        },
        projection_fidelity_bps=9500,
        bound_tensor_caid="sha256:0000000000000000000000000000000000000000000000000000000000000000",
    )
    v_tamper = interceptor.inspect_kv_cache_transfer(tampered_pkt)
    assert v_tamper.allowed is False
    assert v_tamper.status_code == "HALT_LATENT_TENSOR_HASH_MISMATCH"

    # 2D: Untrusted model backbone -> HALT!
    untrusted_pkt = LatentStatePacket(
        sender_agent_id="agent_alpha",
        receiver_agent_id="agent_beta",
        model_backbone_id="rogue-model-backbone",
        kv_cache_raw_bytes=fake_kv_bytes,
        semantic_projection={
            "action": "summarize_module",
            "risk_tier": "T0_READONLY",
            "target_scope": "src/escrow.py",
        },
        projection_fidelity_bps=9500,
        bound_tensor_caid=valid_tensor_caid,
    )
    v_untrusted = interceptor.inspect_kv_cache_transfer(untrusted_pkt)
    assert v_untrusted.allowed is False
    assert "HALT_UNTRUSTED_LATENT_BACKBONE:rogue-model-backbone" in v_untrusted.status_code

    # 2E: Incomplete semantic projection schema -> HALT!
    incomplete_pkt = LatentStatePacket(
        sender_agent_id="agent_alpha",
        receiver_agent_id="agent_beta",
        model_backbone_id="qwen3-8b-v1",
        kv_cache_raw_bytes=fake_kv_bytes,
        semantic_projection={"action": "test"},  # Missing risk_tier and target_scope
        projection_fidelity_bps=9500,
        bound_tensor_caid=valid_tensor_caid,
    )
    v_incomplete = interceptor.inspect_kv_cache_transfer(incomplete_pkt)
    assert v_incomplete.allowed is False
    assert "HALT_INCOMPLETE_SEMANTIC_PROJECTION" in v_incomplete.status_code

    # 2F: Low decoding fidelity floor (< 9000 bps) -> HALT!
    low_fid_pkt = LatentStatePacket(
        sender_agent_id="agent_alpha",
        receiver_agent_id="agent_beta",
        model_backbone_id="qwen3-8b-v1",
        kv_cache_raw_bytes=fake_kv_bytes,
        semantic_projection={
            "action": "summarize_module",
            "risk_tier": "T0_READONLY",
            "target_scope": "src/escrow.py",
        },
        projection_fidelity_bps=8999,
        bound_tensor_caid=valid_tensor_caid,
    )
    v_low_fid = interceptor.inspect_kv_cache_transfer(low_fid_pkt)
    assert v_low_fid.allowed is False
    assert "HALT_LATENT_PROJECTION_LOW_FIDELITY:8999" in v_low_fid.status_code

    # Exact threshold point: 9000 bps is accepted!
    exact_threshold_pkt = LatentStatePacket(
        sender_agent_id="agent_alpha",
        receiver_agent_id="agent_beta",
        model_backbone_id="qwen3-8b-v1",
        kv_cache_raw_bytes=fake_kv_bytes,
        semantic_projection={
            "action": "summarize_module",
            "risk_tier": "T0_READONLY",
            "target_scope": "src/escrow.py",
        },
        projection_fidelity_bps=9000,
        bound_tensor_caid=valid_tensor_caid,
    )
    v_exact = interceptor.inspect_kv_cache_transfer(exact_threshold_pkt)
    assert v_exact.allowed is True
    assert v_exact.status_code == "OK_LATENT_TRANSFER_VERIFIED"

    # 2G: Forbidden latent action (bypass_eo1) -> HALT!
    forbidden_pkt = LatentStatePacket(
        sender_agent_id="agent_alpha",
        receiver_agent_id="agent_beta",
        model_backbone_id="qwen3-8b-v1",
        kv_cache_raw_bytes=fake_kv_bytes,
        semantic_projection={
            "action": "bypass_eo1",
            "risk_tier": "T3_CRITICAL",
            "target_scope": "src/escrow.py",
        },
        projection_fidelity_bps=9500,
        bound_tensor_caid=valid_tensor_caid,
    )
    v_forbid = interceptor.inspect_kv_cache_transfer(forbidden_pkt)
    assert v_forbid.allowed is False
    assert "HALT_FORBIDDEN_LATENT_INTENT:bypass_eo1" in v_forbid.status_code

    # 2H: Valid cryptographically bound & high-fidelity KV-Cache transfer passes
    valid_pkt = LatentStatePacket(
        sender_agent_id="agent_alpha",
        receiver_agent_id="agent_beta",
        model_backbone_id="qwen3-8b-v1",
        kv_cache_raw_bytes=fake_kv_bytes,
        semantic_projection={
            "action": "refactor_function",
            "risk_tier": "T1_LOCAL_EDIT",
            "target_scope": "src/escrow.py",
        },
        projection_fidelity_bps=9450,
        bound_tensor_caid=valid_tensor_caid,
    )
    v_ok = interceptor.inspect_kv_cache_transfer(valid_pkt)
    assert v_ok.allowed is True
    assert v_ok.status_code == "OK_LATENT_TRANSFER_VERIFIED"
    assert v_ok.projected_intent_caid.startswith("sha256:")
    assert v_ok.verdict_caid.startswith("sha256:")


def test_3_consistent_history_ledger_blocks_budget_decoherence_and_phase_skip() -> None:
    """Verify Consistent History Ledger blocks split-spend budget decoherence and phase skips."""
    # Boundary init
    with pytest.raises(ValueError, match="ERR_INVALID_HISTORY_CONSTRAINTS"):
        ConsistentHistoryLedger(-1, frozenset({"a.py"}))
    with pytest.raises(ValueError, match="ERR_INVALID_HISTORY_CONSTRAINTS"):
        ConsistentHistoryLedger(100, frozenset())

    ledger = ConsistentHistoryLedger(
        max_budget_minor=100,
        authorized_files=frozenset({"consensus.md", "src/escrow.py"}),
    )

    # Negative spend rejection
    r_neg = ledger.append_and_verify_consistency("s_neg", "CYCLE_1_BRAINSTORM", "consensus.md", -5)
    assert r_neg.consistent is False
    assert r_neg.status_code == "HALT_INCONSISTENT_HISTORY:NEGATIVE_SPEND"

    # Unknown phase rejection
    r_unk = ledger.append_and_verify_consistency("s_unk", "CYCLE_UNKNOWN", "consensus.md", 10)
    assert r_unk.consistent is False
    assert "HALT_INCONSISTENT_HISTORY:UNKNOWN_PHASE" in r_unk.status_code

    # Scope amplification rejection
    r_scope = ledger.append_and_verify_consistency(
        "s_scope", "CYCLE_1_BRAINSTORM", "unauthorized_secret.py", 10
    )
    assert r_scope.consistent is False
    assert "HALT_INCONSISTENT_HISTORY:SCOPE_AMPLIFICATION" in r_scope.status_code

    # Attempt to jump straight to CYCLE_3_EXECUTE without CYCLE_2_GO_NOGO -> HALT!
    r_skip = ledger.append_and_verify_consistency(
        step_id="step_0",
        cycle_phase="CYCLE_3_EXECUTE",
        target_file="src/escrow.py",
        spend_minor_units=10,
    )
    assert r_skip.consistent is False
    assert r_skip.status_code == "HALT_INCONSISTENT_HISTORY:MISSING_CYCLE_2_GO_NOGO_GATE"

    # Valid Cycle 1 (Brainstorm, spend 40) -> Valid Cycle 2 (GO/NO-GO, spend 40)
    r1 = ledger.append_and_verify_consistency(
        "step_1", "CYCLE_1_BRAINSTORM", "consensus.md", 40
    )
    assert r1.consistent is True
    assert r1.chain_length == 1
    assert r1.history_chain_caid.startswith("sha256:")

    r2 = ledger.append_and_verify_consistency(
        "step_2", "CYCLE_2_GO_NOGO", "consensus.md", 40
    )
    assert r2.consistent is True
    assert r2.chain_length == 2
    assert ledger.cumulative_spend_minor == 80

    # Phase regression attempt: cannot go from Cycle 2 back to Cycle 1
    r_regress = ledger.append_and_verify_consistency(
        "step_regress", "CYCLE_1_BRAINSTORM", "consensus.md", 5
    )
    assert r_regress.consistent is False
    assert "HALT_INCONSISTENT_HISTORY:PHASE_REGRESSION" in r_regress.status_code
    assert ledger.cumulative_spend_minor == 80  # State unchanged

    # Smurfing / Split-Spend Attack: 3rd step requests 40 minor units (80 + 40 = 120 > 100)
    r3_over = ledger.append_and_verify_consistency(
        "step_3_over", "CYCLE_3_EXECUTE", "src/escrow.py", 40
    )
    assert r3_over.consistent is False
    assert "HALT_INCONSISTENT_HISTORY:BUDGET_DECOHERENCE:120_exceeds_100" in r3_over.status_code
    assert ledger.cumulative_spend_minor == 80  # State remains uncorrupted

    # Valid Cycle 3 step within remaining budget (80 + 20 == 100) succeeds
    r3_ok = ledger.append_and_verify_consistency(
        "step_3_ok", "CYCLE_3_EXECUTE", "src/escrow.py", 20
    )
    assert r3_ok.consistent is True
    assert r3_ok.chain_length == 3
    assert ledger.cumulative_spend_minor == 100

    # Test isolated history with ONLY CYCLE_2_GO_NOGO then CYCLE_3_EXECUTE (kills CMP_FLIP on == vs !=)
    isolated_ledger = ConsistentHistoryLedger(50, frozenset({"task.py"}))
    r_iso_2 = isolated_ledger.append_and_verify_consistency("s2", "CYCLE_2_GO_NOGO", "task.py", 10)
    assert r_iso_2.consistent is True
    r_iso_3 = isolated_ledger.append_and_verify_consistency("s3", "CYCLE_3_EXECUTE", "task.py", 10)
    assert r_iso_3.consistent is True
