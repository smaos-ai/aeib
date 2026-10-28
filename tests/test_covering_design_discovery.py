"""Tests for the covering design discovery pipeline (verifier + comparator).

All designs below are real combinatorial objects checked by exhaustive coverage;
nothing is mocked. Negative controls confirm each check can fail.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from covering_design_record_comparator import (  # noqa: E402
    PinnedBaseline,
    compare,
    main as comparator_main,
)
from covering_design_verifier import (  # noqa: E402
    canonical_bytes,
    canonical_witness,
    main as verifier_main,
    schoenheim_bound,
    verify,
    verify_document,
)

FANO = [[0, 1, 3], [1, 2, 4], [2, 3, 5], [3, 4, 6], [4, 5, 0], [5, 6, 1], [6, 0, 2]]


def test_fano_plane_is_valid_and_optimal_cover():
    res = verify(7, 3, 2, FANO, claimed=7)
    assert res["valid"] is True
    assert res["status"] == "VALID"
    assert res["errors"] == []
    assert res["t_subsets_missing"] == 0
    assert res["t_subsets_covered"] == 7 * 3
    assert res["schoenheim_lower_bound"] == 7
    assert res["checks_failed"] == 0
    assert res["checks_passed"] == 5
    assert res["witness_digest"].startswith("sha256:")


def test_schoenheim_bound_known_values():
    assert schoenheim_bound(12, 4, 3) == 57
    assert schoenheim_bound(10, 4, 3) == 30
    assert schoenheim_bound(7, 3, 2) == 7


def test_removing_a_block_is_detected():
    res = verify(7, 3, 2, FANO[:-1])
    assert res["valid"] is False
    assert res["status"] == "INVALID"
    assert res["t_subsets_missing"] == 3
    assert res["t_subsets_covered"] == 18
    assert any("3 t-subsets uncovered" in e for e in res["errors"])


def test_single_point_mutation_is_detected():
    mutated = [b[:] for b in FANO]
    mutated[0] = [0, 1, 2]
    res = verify(7, 3, 2, mutated)
    assert res["valid"] is False
    assert not res["checks"]["every_t_subset_covered"]


@pytest.mark.parametrize("blocks,check", [
    ([[0, 1, 7]] + FANO[1:], "points_within_range"),
    ([[0, 1]] + FANO[1:], "block_size_equals_k"),
    ([[0, 0, 1]] + FANO[1:], "block_size_equals_k"),
    (FANO + [FANO[0]], "no_duplicate_block"),
])
def test_structural_violations_fail_closed(blocks, check):
    res = verify(7, 3, 2, blocks)
    assert res["valid"] is False
    assert res["checks"][check] is False
    assert len(res["errors"]) >= 1


def test_claim_mismatch_rejected():
    res = verify(7, 3, 2, FANO, claimed=6)
    assert res["valid"] is False
    assert res["checks"]["block_count_matches_claim"] is False
    assert any("claimed 6 blocks but found 7" in e for e in res["errors"])


def test_canonical_witness_is_order_independent_and_matches_jcs():
    sys.path.insert(0, str(ROOT))
    from src.jcs_canonicalizer import encode_jcs
    a = canonical_witness(7, 3, 2, FANO)
    b = canonical_witness(7, 3, 2, [list(reversed(x)) for x in reversed(FANO)])
    assert a["v"] == 7 and a["k"] == 3 and a["t"] == 2 and len(a["blocks"]) == 7
    assert canonical_bytes(a) == canonical_bytes(b)
    assert canonical_bytes(a) == encode_jcs(a)
    non_ascii = canonical_bytes({"z": "é", "a": 1})
    assert non_ascii == '{"a":1,"z":"é"}'.encode("utf-8")


def test_verify_document_parameters_and_cli_entry(tmp_path, monkeypatch, capsys):
    # t=1 valid design kills 0 < t -> 1 < t mutant
    res_t1 = verify(4, 2, 1, [[0, 1], [2, 3]])
    assert res_t1["valid"] is True
    assert res_t1["errors"] == []

    # Invalid parameters v < k kills line 63 valid=False -> True
    bad_param = verify(3, 5, 2, [])
    assert bad_param["valid"] is False
    assert "bad parameters" in bad_param["errors"][0]
    assert bad_param["checks"] == {}

    # verify_document with claimed_objective dict
    doc_ok = {
        "parameters": {"v": 7, "k": 3, "t": 2},
        "claimed_objective": {"value": 7},
        "blocks": FANO,
    }
    res_doc = verify_document(doc_ok)
    assert res_doc["valid"] is True

    doc_path = tmp_path / "witness_ok.json"
    doc_path.write_text(json.dumps(doc_ok), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["covering_design_verifier.py", "--input", str(doc_path)])
    assert verifier_main() == 0

    bad_doc_path = tmp_path / "witness_bad.json"
    bad_doc_path.write_text(json.dumps({"v": 7, "k": 3, "t": 2, "blocks": FANO[:-1]}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["covering_design_verifier.py", "--input", str(bad_doc_path)])
    assert verifier_main() == 1

    # Missing required --input argument
    monkeypatch.setattr(sys, "argv", ["covering_design_verifier.py"])
    with pytest.raises(SystemExit):
        verifier_main()

    # --help checks description line 0
    monkeypatch.setattr(sys, "argv", ["covering_design_verifier.py", "--help"])
    with pytest.raises(SystemExit):
        verifier_main()
    out = capsys.readouterr().out
    assert "Independent covering design verifier" in out

    # Line 103: VERIFIER_INCONSISTENCY alarm when count < schoenheim_bound
    import covering_design_verifier as _cdv

    monkeypatch.setattr(_cdv, "schoenheim_bound", lambda v, k, t: 99)
    inconsistent = verify(7, 3, 2, FANO)
    assert inconsistent["status"] == "VERIFIER_INCONSISTENCY"
    assert inconsistent["valid"] is False
    assert any("below Schoenheim bound" in e for e in inconsistent["errors"])


def test_capability_status_opt_in_contract(monkeypatch):
    sys.path.insert(0, str(ROOT))
    from src.capability_status import (
        CapabilityUnavailableError,
        SIMULATED_OPT_IN,
        SIMULATION_ENV,
        require_simulation_opt_in,
        simulation_allowed,
    )

    monkeypatch.delenv(SIMULATION_ENV, raising=False)
    assert simulation_allowed() is False
    assert simulation_allowed(True) is True
    assert simulation_allowed(False) is False

    monkeypatch.setenv(SIMULATION_ENV, "1")
    assert simulation_allowed() is True
    assert simulation_allowed(False) is False

    monkeypatch.delenv(SIMULATION_ENV, raising=False)
    assert require_simulation_opt_in("tpm_quote", explicit=True) == SIMULATED_OPT_IN
    with pytest.raises(CapabilityUnavailableError, match="extra_detail") as exc_info:
        require_simulation_opt_in("tpm_quote", explicit=False, detail="extra_detail")
    assert exc_info.value.capability == "tpm_quote"
    assert exc_info.value.detail == "extra_detail"


def test_pinned_baseline_digest_matches():
    base = PinnedBaseline()
    assert base.pinned is True
    assert base.entry(999, 99, 9) is None
    e12 = base.entry(12, 4, 3)
    assert e12["published_size"] == 57
    raw_imp = base.table["C(12,4,3)"]["imps"][0]
    assert e12["last_improvement"] == {
        "size": raw_imp[0],
        "method": raw_imp[1],
        "submitter": raw_imp[2],
        "timestamp": raw_imp[3],
    }
    assert e12["last_improvement"]["size"] != e12["last_improvement"]["method"]
    assert e12["last_improvement"]["method"] != e12["last_improvement"]["submitter"]
    assert base.entry(13, 6, 4)["published_size"] == 66


def test_comparator_labels_against_real_baseline(tmp_path, monkeypatch, capsys):
    base = PinnedBaseline()
    assert compare(verify(7, 3, 2, FANO), base)["label"] == "REPRODUCED_KNOWN_RESULT"
    padded = FANO + [[0, 1, 2]]
    assert compare(verify(7, 3, 2, padded), base)["label"] == "WORSE_THAN_RECORD"
    assert compare(verify(7, 3, 2, FANO[:-1]), base)["label"] == "INVALID_CANDIDATE"
    assert compare(verify(4, 2, 1, [[0, 1], [2, 3]]), base)["label"] == "ENTRY_NOT_IN_BASELINE"

    ver_ok_path = tmp_path / "ver_ok.json"
    ver_ok_path.write_text(json.dumps(verify(7, 3, 2, FANO)), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["covering_design_record_comparator.py", "--verification", str(ver_ok_path)])
    assert comparator_main() == 0
    out_ok = capsys.readouterr().out
    assert out_ok.startswith('{\n  "baseline": {')

    ver_bad_path = tmp_path / "ver_bad.json"
    ver_bad_path.write_text(json.dumps(verify(7, 3, 2, FANO[:-1])), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["covering_design_record_comparator.py", "--verification", str(ver_bad_path)])
    assert comparator_main() == 1
    capsys.readouterr()

    monkeypatch.setattr(sys, "argv", ["covering_design_record_comparator.py"])
    with pytest.raises(SystemExit):
        comparator_main()


def test_discovery_loop_pipeline_and_cli(tmp_path, monkeypatch):
    import argparse as _ap
    import builtins as _builtins
    import hashlib as _hl
    import time as _time
    import discovery_loop as dl

    # 1. sha256_file
    sample = tmp_path / "sample.txt"
    sample.write_bytes(b"abc")
    assert dl.sha256_file(sample) == "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    # 2. to_candidate (cyclic vs explicit)
    raw = {"v": 7, "k": 3, "t": 2, "blocks": FANO, "seed": 11, "moves": 5, "seconds": 0.1}
    cand_cyc = dl.to_candidate(raw, "cyclic")
    assert cand_cyc["construction_type"] == "CYCLIC_ORBITS_Z_V"
    assert cand_cyc["problem"] == "COVERING_DESIGN"
    assert cand_cyc["claimed_objective"] == {"metric": "block_count", "value": 7}
    assert cand_cyc["proposer"]["name"] == "CoveringDesignSearch.cyclic"
    assert cand_cyc["proposer"]["seed"] == 11
    cand_exp = dl.to_candidate(raw, "explicit")
    assert cand_exp["construction_type"] == "EXPLICIT_BLOCKS"

    # 3. parse_targets
    ns = _ap.Namespace(parameters='{"v":7,"k":3,"t":2}', targets=["10,4,3", "12,4,3"])
    assert dl.parse_targets(ns) == [(7, 3, 2), (10, 4, 3), (12, 4, 3)]
    assert dl.parse_targets(_ap.Namespace(parameters=None, targets=None)) == []

    # 4. process_candidate (reproduced, deduplicated, invalid, improvement, contradicts lower bound)
    out_dir = dl.ROOT / "reports" / "tmp_dl_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        base = PinnedBaseline()
        metrics = {
            k: 0
            for k in (
                "candidates_generated",
                "candidates_valid",
                "candidates_deduplicated",
                "known_records_reproduced",
                "strict_improvements_found",
                "false_improvement_claims_rejected",
                "verifier_rejections",
                "human_review_queue",
                "attempts",
                "attempts_without_candidate",
            )
        }
        seen: set[str] = set()
        r1 = dl.process_candidate(cand_exp, base, out_dir, seen, metrics)
        assert r1["label"] == "REPRODUCED_KNOWN_RESULT"
        assert r1["status"] == "REPRODUCED_KNOWN_RESULT"
        assert r1["block_count"] == 7
        assert r1["delta_vs_record"] == 0
        # Line 102: exact [7:19] slice check in witness_file
        assert r1["witness_file"] == f"reports/tmp_dl_test/witnesses/C7_3_2_b7_{r1['witness_digest'][7:19]}.json"
        assert metrics["candidates_generated"] == 1
        assert metrics["candidates_valid"] == 1
        assert metrics["known_records_reproduced"] == 1
        assert metrics["candidates_deduplicated"] == 0

        # Duplicate candidate increments candidates_deduplicated
        dl.process_candidate(cand_exp, base, out_dir, seen, metrics)
        assert metrics["candidates_deduplicated"] == 1

        # Invalid candidate increments verifier_rejections
        bad_cand = dict(cand_exp, blocks=FANO[:-1], claimed_objective={"metric": "block_count", "value": 6})
        r_bad = dl.process_candidate(bad_cand, base, out_dir, seen, metrics)
        assert r_bad["label"] == "INVALID_CANDIDATE"
        assert metrics["verifier_rejections"] == 1

        # Strict improvement increments strict_improvements_found and human_review_queue
        src_dir = ROOT / "experiments" / "covering_design" / "baseline"
        table = json.loads((src_dir / "coverdata.json").read_text(encoding="utf-8"))
        table["C(7,3,2)"]["size"] = 8
        raw_bytes = json.dumps(table).encode("utf-8")
        bdir = tmp_path / "base_imp"
        bdir.mkdir(parents=True, exist_ok=True)
        (bdir / "coverdata.json").write_bytes(raw_bytes)
        pin = json.loads((src_dir / "PIN.json").read_text(encoding="utf-8"))
        pin["sha256"] = _hl.sha256(raw_bytes).hexdigest()
        (bdir / "PIN.json").write_text(json.dumps(pin), encoding="utf-8")
        r_imp = dl.process_candidate(cand_exp, PinnedBaseline(bdir), out_dir, set(), metrics)
        assert r_imp["label"] == "CANDIDATE_IMPROVEMENT_PENDING_HUMAN_REVIEW"
        assert r_imp["status"] == "CANDIDATE_IMPROVEMENT_PENDING_HUMAN_REVIEW"
        assert metrics["strict_improvements_found"] == 1
        assert metrics["human_review_queue"] == 1

        # Contradicts published lower bound increments false_improvement_claims_rejected
        table["C(7,3,2)"]["low_bd"] = 9
        raw_lb = json.dumps(table).encode("utf-8")
        lbdir = tmp_path / "base_lb"
        lbdir.mkdir(parents=True, exist_ok=True)
        (lbdir / "coverdata.json").write_bytes(raw_lb)
        pin["sha256"] = _hl.sha256(raw_lb).hexdigest()
        (lbdir / "PIN.json").write_text(json.dumps(pin), encoding="utf-8")
        r_lb = dl.process_candidate(cand_exp, PinnedBaseline(lbdir), out_dir, set(), metrics)
        assert r_lb["label"] == "CONTRADICTS_PUBLISHED_LOWER_BOUND"
        assert metrics["false_improvement_claims_rejected"] == 1

        # 5. Line 56: run_engine failure truncates stderr to exactly [-2000:]
        orig_run = subprocess.run
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stdout="", stderr="HEAD" + ("E" * 2000)),
        )
        with pytest.raises(RuntimeError) as exc_info:
            dl.run_engine(sys.executable, "explicit", 7, 3, 2, 7, 1, 1.0, 42)
        err_tail = str(exc_info.value).split(": ", 1)[1]
        assert err_tail == "E" * 2000
        monkeypatch.setattr(subprocess, "run", orig_run)

        # 6. Line 153: unpinned baseline returns 2
        tampered_dir = tmp_path / "tampered_base"
        tampered_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(src_dir / "PIN.json", tampered_dir / "PIN.json")
        (tampered_dir / "coverdata.json").write_bytes(b"{}")
        monkeypatch.setattr(dl, "PinnedBaseline", lambda: PinnedBaseline(tampered_dir))
        monkeypatch.setattr(sys, "argv", ["discovery_loop.py", "--output", "reports/tmp_dl_test"])
        assert dl.main() == 2

        # 7. Lines 173, 174, 176, 183, 189, 194, 204, 213: full plan + rounding + flush + sort_keys
        custom_table = json.loads((src_dir / "coverdata.json").read_text(encoding="utf-8"))
        # C(10,4,3): rec=30, lb=20 -> (30-1)//10 = 2 (cyclic budget=2, max_blocks=20)
        custom_table["C(10,4,3)"]["size"] = 30
        custom_table["C(10,4,3)"]["low_bd"] = 20
        # C(7,3,2): rec=8, lb=7 -> rec-1 >= lb (7 >= 7 is True, 8-2 >= 7 is False)
        custom_table["C(7,3,2)"]["size"] = 8
        custom_table["C(7,3,2)"]["low_bd"] = 7
        # C(8,3,2): rec=11, lb=11 -> rec-1 >= lb (10 >= 11 is False, 11-0 >= 11 is True)
        custom_table["C(8,3,2)"]["size"] = 11
        custom_table["C(8,3,2)"]["low_bd"] = 11
        cbytes = json.dumps(custom_table).encode("utf-8")
        cdir = tmp_path / "custom_base"
        cdir.mkdir(parents=True, exist_ok=True)
        (cdir / "coverdata.json").write_bytes(cbytes)
        cpin = json.loads((src_dir / "PIN.json").read_text(encoding="utf-8"))
        cpin["sha256"] = _hl.sha256(cbytes).hexdigest()
        (cdir / "PIN.json").write_text(json.dumps(cpin), encoding="utf-8")
        monkeypatch.setattr(dl, "PinnedBaseline", lambda: PinnedBaseline(cdir))

        cand_file = tmp_path / "cand.json"
        cand_file.write_text(json.dumps(cand_exp), encoding="utf-8")
        monkeypatch.setattr(dl, "run_engine", lambda *a, **kw: ([raw], 0.126))
        clock_vals = iter([100.0, 100.126])
        monkeypatch.setattr(_time, "perf_counter", lambda: next(clock_vals, 100.126))
        flushes: list[object] = []
        orig_print = _builtins.print
        monkeypatch.setattr(
            _builtins,
            "print",
            lambda *a, **kw: (flushes.append(kw.get("flush")), orig_print(*a, **kw)),
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "discovery_loop.py",
                "--parameters",
                '{"v":10,"k":4,"t":3}',
                "--targets",
                "7,3,2",
                "8,3,2",
                "999,99,9",
                "--candidate-files",
                str(cand_file),
                "--output",
                "reports/tmp_dl_test",
            ],
        )
        assert dl.main() == 0
        assert True in flushes
        raw_summary_text = (out_dir / "run_summary.json").read_text(encoding="utf-8")
        assert raw_summary_text.startswith('{\n  "attempts": [')
        summary = json.loads(raw_summary_text)
        assert summary["run"]["wall_s"] == 0.13
        assert summary["metrics"]["attempts"] == 7
        assert summary["metrics"]["attempts_without_candidate"] == 0
        # Check C(10,4,3) explicit improvement (29) and cyclic (m=2, max_blocks=20)
        c10_attempts = [a for a in summary["attempts"] if a.get("target") == "C(10,4,3)"]
        assert [(a["mode"], a["budget_param"], a["max_blocks"], a["wall_s"]) for a in c10_attempts] == [
            ("explicit", 30, 30, 0.13),
            ("explicit", 29, 29, 0.13),
            ("cyclic", 2, 20, 0.13),
        ]
        # Check C(7,3,2) has 2 explicit attempts (8 and 7) + 1 cyclic attempt (1, 7), and C(8,3,2) has 1 explicit attempt (11)
        c7_attempts = [a for a in summary["attempts"] if a.get("target") == "C(7,3,2)" and a.get("mode") != "file"]
        assert [(a["mode"], a["budget_param"], a["max_blocks"]) for a in c7_attempts] == [
            ("explicit", 8, 8),
            ("explicit", 7, 7),
            ("cyclic", 1, 7),
        ]
        c8_attempts = [a for a in summary["attempts"] if a.get("target") == "C(8,3,2)"]
        assert [(a["mode"], a["budget_param"], a["max_blocks"]) for a in c8_attempts] == [
            ("explicit", 11, 11),
        ]
        assert any(a.get("label") == "ENTRY_NOT_IN_BASELINE" for a in summary["attempts"])
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def test_comparator_strict_improvement_path(tmp_path):
    # A copied baseline where C(7,3,2) is recorded as 8 blocks: the real Fano
    # plane then reads as a strict improvement and must enter human review.
    src_dir = ROOT / "experiments" / "covering_design" / "baseline"
    table = json.loads((src_dir / "coverdata.json").read_text(encoding="utf-8"))
    table["C(7,3,2)"]["size"] = 8
    raw = json.dumps(table).encode("utf-8")
    (tmp_path / "coverdata.json").write_bytes(raw)
    pin = json.loads((src_dir / "PIN.json").read_text(encoding="utf-8"))
    import hashlib
    pin["sha256"] = hashlib.sha256(raw).hexdigest()
    (tmp_path / "PIN.json").write_text(json.dumps(pin), encoding="utf-8")
    res = compare(verify(7, 3, 2, FANO), PinnedBaseline(tmp_path))
    assert res["label"] == "CANDIDATE_IMPROVEMENT_PENDING_HUMAN_REVIEW"
    assert res["delta_vs_record"] == -1


def test_tampered_baseline_fails_closed(tmp_path):
    src_dir = ROOT / "experiments" / "covering_design" / "baseline"
    shutil.copy(src_dir / "PIN.json", tmp_path / "PIN.json")
    raw = (src_dir / "coverdata.json").read_bytes().replace(b'"size": 66', b'"size": 99', 1)
    (tmp_path / "coverdata.json").write_bytes(raw)
    base = PinnedBaseline(tmp_path)
    assert base.pinned is False
    assert compare(verify(7, 3, 2, FANO), base)["label"] == "BASELINE_UNPINNED"


@pytest.mark.skipif(shutil.which("java") is None, reason="java not installed")
def test_java_engine_output_passes_independent_verifier():
    engine = ROOT / "experiments" / "covering_design" / "CoveringDesignSearch.java"
    proc = subprocess.run(["java", str(engine), "explicit", "10", "4", "3", "30", "4", "20", "7"],
                          capture_output=True, text=True, timeout=120, check=True)
    raw = json.loads(next(l for l in proc.stdout.splitlines() if l.startswith("{")))
    res = verify(10, 4, 3, raw["blocks"], claimed=30)
    assert res["valid"] is True
    assert compare(res, PinnedBaseline())["label"] == "REPRODUCED_KNOWN_RESULT"
