#!/usr/bin/env python3
"""Tests for tools/wire_healthcheck.py: the four probes hold on the real components, and the
healthcheck FAILS when the gate is broken (negative control), so a green result means something."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Tuple

REPO = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location("wire_healthcheck", REPO / "tools" / "wire_healthcheck.py")
wh = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(wh)  # the repo's own tool module


def test_all_probes_hold_on_real_components(tmp_path: Path) -> None:
    report = wh.run_healthcheck(workdir=tmp_path)
    by = {p["probe"]: p for p in report["probes"]}
    assert report["all_probes_hold"] is True
    assert by["liveness"]["rows_after"] == by["liveness"]["rows_before"] + 1
    assert [r["verdict"] for r in by["sensitivity"]["rows"]] == ["DEFENDED"] * 4
    assert by["sensitivity"]["rows"][0]["reason"] == "HALT_HACK_FORBIDDEN_CALL:eval"
    assert by["sensitivity"]["rows"][3]["reason"] == "HALT_SCAFFOLD:SCAFFOLD_PASS_BODY"
    assert by["specificity"]["reason"] == "OK_ALLOW"
    assert by["replay"]["effects_at_target"] == 1
    assert by["replay"]["second_attempt"] == "CaidAlreadyCommittedError"
    # 1 liveness + 4x(control + gate) + 1 specificity
    assert report["probe_log_rows"] == 10
    assert report["tokens"].startswith("UNAVAILABLE")
    assert report["agent_llm_traffic"] == "NOT_OBSERVABLE_FROM_REPO"
    assert len(report["report_sha256"]) == 64


def test_broken_gate_fails_the_healthcheck(tmp_path: Path) -> None:
    report = wh.run_healthcheck(gate=wh.allow_all_gate, workdir=tmp_path)
    by = {p["probe"]: p for p in report["probes"]}
    assert report["all_probes_hold"] is False
    assert [r["verdict"] for r in by["sensitivity"]["rows"]] == ["BROKEN"] * 4


def test_reject_everything_gate_fails_specificity(tmp_path: Path) -> None:
    def deny_all(source: str) -> Tuple[bool, str]:
        return False, "HALT_EVERYTHING"
    report = wh.run_healthcheck(gate=deny_all, workdir=tmp_path)
    by = {p["probe"]: p for p in report["probes"]}
    assert by["specificity"]["holds"] is False and report["all_probes_hold"] is False


def test_inconclusive_when_control_cannot_accept(tmp_path: Path) -> None:
    log = wh.ProbeLog(tmp_path / "log.jsonl")
    original = wh.allow_all_gate
    try:
        wh.allow_all_gate = lambda s: (False, "CONTROL_BROKEN")  # control arm itself disabled
        res = wh.probe_sensitivity(log, wh.default_gate)
    finally:
        wh.allow_all_gate = original
    assert {r["verdict"] for r in res["rows"]} == {"INCONCLUSIVE"} and res["holds"] is False


def test_scaling_reports_sizes_without_complexity_verdict() -> None:
    s = wh.measure_scaling(wh.default_gate, sizes=(5, 50), reps=3)
    assert [r["functions"] for r in s["sizes"]] == [5, 50]
    assert s["sizes"][1]["bytes"] > s["sizes"][0]["bytes"]
    assert "no complexity verdict" in s["note"]
