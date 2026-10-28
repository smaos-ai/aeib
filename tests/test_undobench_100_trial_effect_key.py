"""Tests for benchmarks/undobench_100_trial_effect_key.py (UndoBench-style lost-ack port).

UndoBench-style lost-ack port with synthetic payloads; not the official UndoBench harness;
in-memory target. The assertions check invariants measured from a small seeded run against
the real PreDispatchIntentInterlock; they do not restate numbers from the benchmark source.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from benchmarks.undobench_100_trial_effect_key import (
    ARM_EFFECT_KEY,
    ARM_EFFECT_KEY_RECONCILED,
    ARM_FULL_PAYLOAD,
    ARM_NAIVE,
    FAMILY_F8,
    InMemoryPaymentsTarget,
    TOOL_NAME,
    build_registry,
    build_schedule,
    dispatch_effect_keyed,
    load_trials_from_jsonl,
    main,
    run_benchmark,
    wilson_interval_bps,
)
from src.eo1_effect_key import UnknownToolSchemaError, compute_effect_caid
from src.eo1_write_before_execute import PreDispatchIntentInterlock, compute_caid
from src.jcs_canonicalizer import encode_jcs
from src.strict_json_ingress import loads_strict

SMALL_F8 = 6
SMALL_DISTINCT = 6


@pytest.fixture(scope="module")
def small_summary(tmp_path_factory: pytest.TempPathFactory) -> dict:
    return run_benchmark(seed=42, n_f8=SMALL_F8, n_distinct=SMALL_DISTINCT,
                         workdir=tmp_path_factory.mktemp("undobench_small"))


def test_schedule_construction_splits_full_payload_but_not_effect_key() -> None:
    registry = build_registry()
    trials = build_schedule(seed=42, n_f8=SMALL_F8, n_distinct=SMALL_DISTINCT)
    for t in trials:
        assert compute_caid(t.first) != compute_caid(t.second)
        same_effect = compute_effect_caid(TOOL_NAME, t.first, registry) == compute_effect_caid(
            TOOL_NAME, t.second, registry)
        assert same_effect is (t.family == FAMILY_F8)
        if t.family == FAMILY_F8:
            assert t.first["memo"] != t.second["memo"]
            assert t.first["client_request_id"] != t.second["client_request_id"]
            assert list(t.first) != list(t.second)


def test_measured_invariants_small_run(small_summary: dict) -> None:
    arms = small_summary["arms"]
    a0, a2, a4, a5 = arms[ARM_NAIVE], arms[ARM_FULL_PAYLOAD], arms[ARM_EFFECT_KEY], arms[ARM_EFFECT_KEY_RECONCILED]
    assert a0["f8_duplicate_effects"] >= 1
    assert a2["f8_duplicate_effects"] >= 1
    assert a4["f8_duplicate_effects"] == 0
    assert a4["false_merges"] == 0
    assert a4["distinct_completed"] == a4["distinct_trials"] == SMALL_DISTINCT
    assert a4["f8_second_attempt_refused"] == a4["f8_trials"] == SMALL_F8
    # A4 refuses but cannot tell whether attempt 1 landed: those latches stay INDETERMINATE.
    assert a4["residual_effect_indeterminate"] >= SMALL_F8
    # A5 settles every lost-ack latch via read-back and leaves none INDETERMINATE.
    assert a5["f8_duplicate_effects"] == 0
    assert a5["false_merges"] == 0
    assert a5["residual_effect_indeterminate"] == 0
    assert a5["reconciler_still_latched"] == 0
    assert a5["reconciler_settled_committed"] == a4["residual_effect_indeterminate"]


def test_no_floats_in_summary_and_digest_recomputes(small_summary: dict) -> None:
    def walk(node: object) -> None:
        assert not isinstance(node, float)
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(small_summary)
    body = {k: v for k, v in small_summary.items() if k != "run_digest_sha256"}
    assert hashlib.sha256(encode_jcs(body)).hexdigest() == small_summary["run_digest_sha256"]


def test_same_seed_is_deterministic(tmp_path: Path, small_summary: dict) -> None:
    second = run_benchmark(seed=42, n_f8=SMALL_F8, n_distinct=SMALL_DISTINCT, workdir=tmp_path / "rerun")
    assert encode_jcs(second) == encode_jcs(small_summary)
    assert second["run_digest_sha256"] == small_summary["run_digest_sha256"]
    other = build_schedule(seed=43, n_f8=SMALL_F8, n_distinct=SMALL_DISTINCT)
    assert encode_jcs([t.first for t in other]) != encode_jcs(
        [t.first for t in build_schedule(seed=42, n_f8=SMALL_F8, n_distinct=SMALL_DISTINCT)])


def test_unknown_tool_fails_closed_under_a4(tmp_path: Path) -> None:
    target = InMemoryPaymentsTarget({})
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "ledger.jsonl",
        output_state_dir=tmp_path / "state",
        boundary_private_key=Ed25519PrivateKey.generate(),
        authority_id="undobench-unknown-tool-test",
    )
    payload = build_schedule(seed=42, n_f8=1, n_distinct=0)[0].first
    with pytest.raises(UnknownToolSchemaError):
        dispatch_effect_keyed(interlock, target, build_registry(), "payments.unregistered_tool", payload)
    assert target.calls == 0
    assert target.effects_by_ref == {}
    ledger = tmp_path / "ledger.jsonl"
    assert not ledger.exists() or ledger.read_bytes().strip() == b""
    # The registered tool on the same interlock dispatches.
    dispatch_effect_keyed(interlock, target, build_registry(), TOOL_NAME, payload)
    assert target.calls == 1


def test_unknown_tool_probe_in_summary(small_summary: dict) -> None:
    probe = small_summary["unknown_tool_probe_A4"]
    assert probe["refused_unknown_tool"] is True
    assert probe["target_calls"] == 0
    assert probe["ledger_records"] == 0


@pytest.mark.parametrize("k,n", [(0, 50), (1, 50), (25, 50), (49, 50), (50, 50), (3, 7), (0, 1)])
def test_wilson_bps_matches_float_formula_within_one_bp(k: int, n: int) -> None:
    z = 1.96
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo_ref = max(0.0, center - half) * 10000
    hi_ref = min(1.0, center + half) * 10000
    lo, hi = wilson_interval_bps(k, n)
    assert isinstance(lo, int) and isinstance(hi, int)
    assert lo <= lo_ref + 1e-9 and lo_ref - lo <= 1
    assert hi >= hi_ref - 1e-9 and hi - hi_ref <= 1


def test_wilson_rejects_invalid_counts() -> None:
    for k, n in [(1, 0), (-1, 5), (6, 5)]:
        with pytest.raises(ValueError):
            wilson_interval_bps(k, n)


def test_jsonl_roundtrip_and_cli_execution(tmp_path: Path, small_summary: dict, capsys: pytest.CaptureFixture[str]) -> None:
    trials = build_schedule(seed=42, n_f8=SMALL_F8, n_distinct=SMALL_DISTINCT)
    jsonl_path = tmp_path / "schedule.jsonl"
    lines = [
        encode_jcs({
            "family": t.family,
            "first": t.first,
            "first_fault": t.first_fault,
            "second": t.second,
        }).decode("utf-8")
        for t in trials
    ]
    jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    loaded = load_trials_from_jsonl(jsonl_path)
    assert len(loaded) == SMALL_F8 + SMALL_DISTINCT
    rerun = run_benchmark(seed=42, trials=loaded, workdir=tmp_path / "from_jsonl")
    assert rerun["schedule_digest_sha256"] == small_summary["schedule_digest_sha256"]
    assert rerun["run_digest_sha256"] == small_summary["run_digest_sha256"]
    assert rerun["arms"][ARM_EFFECT_KEY]["f8_duplicate_effects"] == 0
    assert rerun["arms"][ARM_EFFECT_KEY]["false_merges"] == 0
    assert rerun["arms"][ARM_FULL_PAYLOAD]["f8_duplicate_effects"] > 0

    rc = main(["--jsonl-in", str(jsonl_path), "--json"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    parsed = loads_strict(out, integers_only=True)
    assert encode_jcs(parsed).decode("utf-8") == out
    assert parsed["schedule_digest_sha256"] == small_summary["schedule_digest_sha256"]


def test_malformed_jsonl_rejected(tmp_path: Path) -> None:
    valid_trial = build_schedule(seed=42, n_f8=1, n_distinct=0)[0]
    valid_row = {
        "family": valid_trial.family,
        "first": dict(valid_trial.first),
        "first_fault": valid_trial.first_fault,
        "second": dict(valid_trial.second),
    }

    # 1. Empty file
    empty_path = tmp_path / "empty.jsonl"
    empty_path.write_text("   \n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ERR_INVALID_UNDOBENCH_JSONL_ROW"):
        load_trials_from_jsonl(empty_path)

    # 2. Bad family
    bad_fam_path = tmp_path / "bad_fam.jsonl"
    row_bad_fam = dict(valid_row, family="UNKNOWN_FAMILY")
    bad_fam_path.write_text(encode_jcs(row_bad_fam).decode("utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ERR_INVALID_UNDOBENCH_JSONL_ROW"):
        load_trials_from_jsonl(bad_fam_path)

    # 3. Bool amount_minor
    bool_amt_path = tmp_path / "bool_amt.jsonl"
    bad_first = dict(valid_trial.first, amount_minor=True)
    row_bool_amt = dict(valid_row, first=bad_first)
    bool_amt_path.write_text(encode_jcs(row_bool_amt).decode("utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ERR_INVALID_UNDOBENCH_JSONL_ROW"):
        load_trials_from_jsonl(bool_amt_path)

    # 4. Duplicate JSON key
    dup_key_path = tmp_path / "dup_key.jsonl"
    valid_json = encode_jcs(valid_row).decode("utf-8")
    dup_json = '{"family":"F8_reworded_retry",' + valid_json[1:]
    dup_key_path.write_text(dup_json + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="ERR_INVALID_UNDOBENCH_JSONL_ROW"):
        load_trials_from_jsonl(dup_key_path)


def test_default_seed_42_run_digest_unchanged(tmp_path: Path) -> None:
    summary = run_benchmark(seed=42, n_f8=50, n_distinct=50, workdir=tmp_path / "full100")
    assert summary["run_digest_sha256"] == "14ad3b7f14b62bf2a8a6096203e67c747882dd2e31384e5af74ecf6352255adb"
