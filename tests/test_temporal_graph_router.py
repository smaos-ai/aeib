#!/usr/bin/env python3
"""
Unit and regression suite for TemporalGraphRouter (src/temporal_graph_router.py)
and State Baton Exporter (tools/export_state_baton.py).
Evaluated under the stated model with SQLite FTS5 raw provenance and zero mocks.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
import re

import pytest

from src.temporal_graph_router import TemporalGraphRouter
from tools.export_state_baton import build_state_baton


def test_1_temporal_fts5_provenance_and_superseded_exclusion() -> None:
    router = TemporalGraphRouter(":memory:")

    # Monday T=1000: ingest initial config.json
    c_v1 = router.ingest_document_version(
        doc_path="config/gateway_limits.json",
        raw_text="max_transfer_usd = 100000\npolicy_epoch = v1",
        valid_from_epoch_sec=1000,
    )
    assert len(c_v1.chunk_id) == 20
    assert c_v1.to_dict()["doc_path"] == "config/gateway_limits.json"
    with pytest.raises(dataclasses.FrozenInstanceError):
        c_v1.valid_to_epoch_sec = 999  # type: ignore

    # Friday T=5000: update config.json (automatically closes v1 at exact T=4999)
    c_v2 = router.ingest_document_version(
        doc_path="config/gateway_limits.json",
        raw_text="max_transfer_usd = 25000\npolicy_epoch = v2",
        valid_from_epoch_sec=5000,
    )

    # Exact boundary query at T=4999 returns ONLY v1
    receipt_t4999 = router.query_temporal_truth("max_transfer_usd", query_epoch_sec=4999)
    assert len(receipt_t4999.matched_chunks) == 1
    assert receipt_t4999.matched_chunks[0].content_sha256 == c_v1.content_sha256
    assert receipt_t4999.matched_chunks[0].valid_to_epoch_sec == 4999

    # Exact boundary query at T=5000 returns ONLY v2 (if v1 had closed at 5000 or 5001, len would be 2!)
    receipt_t5000 = router.query_temporal_truth("max_transfer_usd", query_epoch_sec=5000)
    assert len(receipt_t5000.matched_chunks) == 1
    assert receipt_t5000.matched_chunks[0].content_sha256 == c_v2.content_sha256
    with pytest.raises(dataclasses.FrozenInstanceError):
        receipt_t5000.freshness_bps = 0  # type: ignore

    # Query at Sunday T=6000 for "max_transfer_usd"
    receipt_t6000 = router.query_temporal_truth("max_transfer_usd", query_epoch_sec=6000)
    assert len(receipt_t6000.matched_chunks) == 1
    assert receipt_t6000.matched_chunks[0].content_sha256 == c_v2.content_sha256
    assert "25000" in receipt_t6000.matched_chunks[0].raw_text
    assert receipt_t6000.stale_Superseded_excluded_count == 1
    assert receipt_t6000.freshness_bps == 5000
    assert receipt_t6000.to_dict()["stale_superseded_excluded_count"] == 1

    # Query for non-matching term returns 0 chunks and 10000 bps freshness
    receipt_empty = router.query_temporal_truth("nonexistent_term_xyz", query_epoch_sec=6000)
    assert len(receipt_empty.matched_chunks) == 0
    assert receipt_empty.freshness_bps == 10000

    # Query where all matches are superseded (valid_matches=0, superseded_count=1) -> freshness_bps MUST be 0 (kills total_candidates > 0 mutant)
    router_sup = TemporalGraphRouter(":memory:")
    c_old = router_sup.ingest_document_version("doc.txt", "target_term content", valid_from_epoch_sec=100)
    # close c_old by ingesting something without target_term or update c_old
    router_sup.ingest_document_version("doc.txt", "completely different", valid_from_epoch_sec=200)
    receipt_all_sup = router_sup.query_temporal_truth("target_term", query_epoch_sec=300)
    assert len(receipt_all_sup.matched_chunks) == 0
    assert receipt_all_sup.stale_Superseded_excluded_count == 1
    assert receipt_all_sup.freshness_bps == 0

    # Fractional freshness sensitivity (valid_matches=6, superseded=1 -> (6*10000)//7 = 8571 bps)
    router_sens = TemporalGraphRouter(":memory:")
    for i in range(6):
        router_sens.ingest_document_version(f"valid_{i}.txt", "sensitive_keyword", valid_from_epoch_sec=100)
    router_sens.ingest_document_version("stale.txt", "sensitive_keyword", valid_from_epoch_sec=100)
    router_sens.ingest_document_version("stale.txt", "superseded_text", valid_from_epoch_sec=200)
    receipt_sens = router_sens.query_temporal_truth("sensitive_keyword", query_epoch_sec=300)
    assert len(receipt_sens.matched_chunks) == 6
    assert receipt_sens.stale_Superseded_excluded_count == 1
    assert receipt_sens.freshness_bps == 8571


def test_2_stale_context_drift_interlock() -> None:
    router = TemporalGraphRouter(":memory:")
    c_v1 = router.ingest_document_version("src/policy.py", "ALLOW = True", valid_from_epoch_sec=100)
    c_v2 = router.ingest_document_version(
        "src/policy.py", "ALLOW = False", valid_from_epoch_sec=200
    )

    # Agent holding cached v1 digest at T=250 is halted with stale context drift
    fresh_old, reason_old = router.verify_agent_context_freshness(
        "src/policy.py", c_v1.content_sha256, current_epoch_sec=250
    )
    assert fresh_old is False
    assert "HALT_STALE_CONTEXT_DRIFT_REQUIRES_REREAD" in reason_old

    # Agent holding active v2 digest at exact boundary T=200 passes
    fresh_exact, _ = router.verify_agent_context_freshness(
        "src/policy.py", c_v2.content_sha256, current_epoch_sec=200
    )
    assert fresh_exact is True

    # Agent holding v1 digest at exact boundary T=199 passes
    fresh_199, _ = router.verify_agent_context_freshness(
        "src/policy.py", c_v1.content_sha256, current_epoch_sec=199
    )
    assert fresh_199 is True

    # Agent holding active v2 digest at T=250 passes
    fresh_new, reason_new = router.verify_agent_context_freshness(
        "src/policy.py", c_v2.content_sha256, current_epoch_sec=250
    )
    assert fresh_new is True
    assert reason_new == "OK_CONTEXT_FRESH"

    # Unknown document or epoch before valid_from fails closed
    ok_unk, r_unk = router.verify_agent_context_freshness(
        "missing.py", c_v2.content_sha256, current_epoch_sec=250
    )
    assert ok_unk is False and "HALT_UNKNOWN_DOCUMENT" in r_unk

    ok_early, r_early = router.verify_agent_context_freshness(
        "src/policy.py", c_v1.content_sha256, current_epoch_sec=50
    )
    assert ok_early is False and "HALT_NO_VALID_VERSION_AT_EPOCH" in r_early


def test_3_validation_errors_and_state_baton_export() -> None:
    router = TemporalGraphRouter(":memory:")
    with pytest.raises(ValueError, match="ERR_EMPTY_DOC_PATH"):
        router.ingest_document_version("", "text", 100)
    with pytest.raises(ValueError, match="ERR_INVALID_VALID_FROM"):
        router.ingest_document_version("a.py", "text", 0)
    with pytest.raises(ValueError, match="ERR_INVALID_VALIDITY_INTERVAL"):
        router.ingest_document_version("a.py", "text", 100, valid_to_epoch_sec=50)
    with pytest.raises(ValueError, match="ERR_EMPTY_FTS_QUERY"):
        router.query_temporal_truth("   ", 100)

    baton = build_state_baton("Temporal Authority & Delegation verified")
    assert baton["status_label"] == "INTERNAL_PREVIEW_COMMISSIONED"
    assert baton["baton_caid"].startswith("sha256:")
    assert baton["serialized_byte_length"] < 1200  # well under 300 tokens


def test_3b_truth_decay_engine_halts_stale_legitimate_memory() -> None:
    router = TemporalGraphRouter(":memory:")
    chunk = router.ingest_document_version(
        doc_path="docs/stripe_webhook_spec.md",
        raw_text="Stripe API v2026-01 webhook signature header format",
        valid_from_epoch_sec=1000,
    )

    # Fresh memory at T=1000 (age=0) with authority 9000 bps and 1 cross-ref -> 9000 bps
    ok_fresh, conf_fresh, code_fresh = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=chunk,
        current_epoch_sec=1000,
        max_api_ttl_sec=1000,
        source_authority_bps=9000,
        cross_ref_count=1,
        min_confidence_bps=6000,
    )
    assert ok_fresh is True
    assert conf_fresh == 9000
    assert code_fresh == "OK_MEMORY_CONFIDENCE_VERIFIED"

    # Corroboration bonus without hitting 10000 cap: 7000 + (2-1)*500 = 7500 bps
    ok_bonus, conf_bonus, _ = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=chunk,
        current_epoch_sec=1000,
        max_api_ttl_sec=1000,
        source_authority_bps=7000,
        cross_ref_count=2,
    )
    assert ok_bonus is True
    assert conf_bonus == 7500

    # Exact N=10000 denominator test (Lesson L23): age=1 out of 10000 with authority=10000 -> 9999 bps
    ok_exact_ratio, conf_exact_ratio, _ = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=chunk,
        current_epoch_sec=1001,
        max_api_ttl_sec=10000,
        source_authority_bps=10000,
        cross_ref_count=1,
    )
    assert ok_exact_ratio is True
    assert conf_exact_ratio == 9999

    # Fractional ratio sensitivity without clamping: age=1, ttl=7 -> ((7-1)*10000)//7 = 8571 bps
    ok_sens_ratio, conf_sens_ratio, _ = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=chunk,
        current_epoch_sec=1001,
        max_api_ttl_sec=7,
        source_authority_bps=10000,
        cross_ref_count=1,
    )
    assert ok_sens_ratio is True
    assert conf_sens_ratio == 8571

    # Default min_confidence_bps=6000 exact boundary: 6000 passes, 5999 halts
    ok_6000, conf_6000, _ = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=chunk,
        current_epoch_sec=1000,
        max_api_ttl_sec=10000,
        source_authority_bps=6000,
    )
    assert ok_6000 is True and conf_6000 == 6000

    ok_5999, conf_5999, code_5999 = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=chunk,
        current_epoch_sec=1000,
        max_api_ttl_sec=10000,
        source_authority_bps=5999,
    )
    assert ok_5999 is False and conf_5999 == 5999 and "min=6000" in code_5999

    # Confidence decayed below min_confidence_bps (at T=1500, age=500/1000 -> 50% of 9000 = 4500 bps < 6000)
    ok_low, conf_low, code_low = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=chunk,
        current_epoch_sec=1500,
        max_api_ttl_sec=1000,
        source_authority_bps=9000,
        cross_ref_count=1,
        min_confidence_bps=6000,
    )
    assert ok_low is False
    assert conf_low == 4500
    assert "HALT_STALE_MEMORY_NEEDS_RESEARCH" in code_low

    # Age exceeds max_api_ttl_sec (T=2001 > 1000 + 1000) -> halts with 0 bps
    ok_exp, conf_exp, code_exp = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=chunk,
        current_epoch_sec=2001,
        max_api_ttl_sec=1000,
    )
    assert ok_exp is False
    assert conf_exp == 0
    assert "HALT_STALE_MEMORY_NEEDS_RESEARCH:age=1001>ttl=1000" == code_exp

    # Superseded chunk halts immediately
    closed_chunk = dataclasses.replace(chunk, valid_to_epoch_sec=1200)
    ok_sup, conf_sup, code_sup = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=closed_chunk,
        current_epoch_sec=1201,
        max_api_ttl_sec=5000,
    )
    assert ok_sup is False and conf_sup == 0 and "CHUNK_SUPERSEDED" in code_sup

    # Premature epoch fails closed
    ok_prem, conf_prem, code_prem = TemporalGraphRouter.evaluate_memory_truth_decay(
        chunk=chunk,
        current_epoch_sec=999,
        max_api_ttl_sec=1000,
    )
    assert ok_prem is False and conf_prem == 0 and code_prem == "HALT_PREMATURE_MEMORY_CHUNK"

    with pytest.raises(ValueError, match="ERR_INVALID_MAX_API_TTL"):
        TemporalGraphRouter.evaluate_memory_truth_decay(chunk, 1000, max_api_ttl_sec=0)
    with pytest.raises(ValueError, match="ERR_INVALID_SOURCE_AUTHORITY_BPS"):
        TemporalGraphRouter.evaluate_memory_truth_decay(chunk, 1000, source_authority_bps=10001)



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
        Path("src/temporal_graph_router.py"),
        Path("tests/test_temporal_graph_router.py"),
        Path("tools/export_state_baton.py"),
    ):
        text = fpath.read_text(encoding="utf-8")
        for pat in banned:
            assert not re.findall(pat, text, re.IGNORECASE)
