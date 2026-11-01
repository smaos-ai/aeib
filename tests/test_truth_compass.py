#!/usr/bin/env python3
"""
tests/test_truth_compass.py — real git repos, real pytest subprocesses, no mocks.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.truth_compass import (
    ASSUMED, DISPUTED, GENESIS_PREV_REPORT_CAID, HYPOTHESIS, MAX_HASH_FILE_BYTES, REFUTED, T1, T2, T3, UNKNOWN, VERIFIED,
    Claim, ClaimResult, Evidence, _claim_json, check_claim, decide, load_ledger, parse_claim,
    propagate_contagion, render_card, report_is_current, sign_report_envelope,
    tree_state, validate_dependency_dag, verify_report_chain, where_we_stand,
)

REPO = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", *args], check=True, capture_output=True, timeout=30)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "r"
    (r / "tests").mkdir(parents=True)
    (r / "tests" / "test_ok.py").write_text("def test_ok():\n    assert 2 + 2 == 4\n")
    (r / "tests" / "test_fail.py").write_text("def test_fail():\n    assert 2 + 2 == 5\n")
    (r / "tests" / "test_broken.py").write_text("def test_broken(:\n")
    (r / "tests" / "test_slow.py").write_text("import time\ndef test_slow():\n    time.sleep(30)\n")
    (r / "data.txt").write_text("hello\n")
    _git(r, "init", "-q")
    _git(r, "add", ".")
    _git(r, "commit", "-q", "-m", "base")
    return r


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _raw(**kw):
    base = {"claim_id": "c1", "statement": "s", "falsifier": "f", "safety_critical": False}
    base.update(kw)
    return base


# ------------------------------------------------------------------ parsing
def test_parse_rejects_self_asserted_status() -> None:
    for status in (VERIFIED, "OBSERVED", None, "verified"):
        with pytest.raises(ValueError, match="ERR_STATUS_WITHOUT_CHECK"):
            parse_claim(_raw(declared_status=status))
    for status in (ASSUMED, HYPOTHESIS, UNKNOWN, DISPUTED):
        assert parse_claim(_raw(declared_status=status)).declared_status == status
    with pytest.raises(ValueError, match="ERR_STATUS_IS_COMPUTED_FOR_CHECKED_CLAIM"):
        parse_claim(_raw(declared_status=ASSUMED, entailment="e",
                         evidence={"kind": "PYTEST", "targets": ["tests/test_ok.py"]}))
    with pytest.raises(ValueError, match="ERR_LEDGER_FIELD_REQUIRED:entailment"):
        parse_claim(_raw(evidence={"kind": "PYTEST", "targets": ["tests/test_ok.py"]}))
    with pytest.raises(ValueError, match="ERR_ENTAILMENT_WITHOUT_CHECK"):
        parse_claim(_raw(declared_status=ASSUMED, entailment="e"))
    for bad in ("x", [""], [1], ["ok", " "]):
        with pytest.raises(ValueError, match="ERR_LEDGER_BAD_DEFEATERS"):
            parse_claim(_raw(declared_status=ASSUMED, open_defeaters=bad))


@pytest.mark.parametrize("raw,err", [
    ("notadict", "ERR_LEDGER_CLAIM_NOT_OBJECT"),
    (_raw(extra=1, declared_status=ASSUMED), "ERR_LEDGER_UNKNOWN_FIELD:extra"),
    (_raw(claim_id="", declared_status=ASSUMED), "ERR_LEDGER_FIELD_REQUIRED:claim_id"),
    (_raw(claim_id="Bad ID", declared_status=ASSUMED), "ERR_LEDGER_BAD_CLAIM_ID"),
    (_raw(statement=" ", declared_status=ASSUMED), "ERR_LEDGER_FIELD_REQUIRED:statement"),
    (_raw(falsifier="", declared_status=ASSUMED), "ERR_LEDGER_FIELD_REQUIRED:falsifier"),
    (_raw(safety_critical=1, declared_status=ASSUMED), "ERR_LEDGER_FIELD_REQUIRED:safety_critical"),
    (_raw(accepted_by="", declared_status=ASSUMED), "ERR_LEDGER_FIELD_REQUIRED:accepted_by"),
    (_raw(evidence="x"), "ERR_EVIDENCE_NOT_OBJECT"),
    (_raw(evidence={"kind": "PYTEST", "targets": []}), "ERR_EVIDENCE_TARGETS"),
    (_raw(evidence={"kind": "PYTEST", "targets": [""]}), "ERR_EVIDENCE_TARGETS"),
    (_raw(evidence={"kind": "PYTEST", "targets": "tests/test_ok.py"}), "ERR_EVIDENCE_TARGETS"),
    (_raw(evidence={"kind": "PYTEST", "targets": ["tests/../x.py"]}), "ERR_EVIDENCE_PYTEST_NODEID"),
    (_raw(evidence={"kind": "PYTEST", "targets": ["-p", "evil"]}), "ERR_EVIDENCE_PYTEST_NODEID"),
    (_raw(evidence={"kind": "PYTEST", "targets": ["/etc/test.py"]}), "ERR_EVIDENCE_PYTEST_NODEID"),
    (_raw(evidence={"kind": "PYTEST", "targets": ["tests/t.py;rm"]}), "ERR_EVIDENCE_PYTEST_NODEID"),
    (_raw(evidence={"kind": "FILE_SHA256", "targets": ["a"], "expected_sha256": "zz"}), "ERR_EVIDENCE_FILE_SHA256"),
    (_raw(evidence={"kind": "FILE_SHA256", "targets": ["a", "b"], "expected_sha256": "0" * 64}), "ERR_EVIDENCE_FILE_SHA256"),
    (_raw(evidence={"kind": "FILE_SHA256", "targets": ["a"]}), "ERR_EVIDENCE_FILE_SHA256"),
    (_raw(evidence={"kind": "SHELL", "targets": ["rm -rf /"]}), "ERR_EVIDENCE_KIND"),
])
def test_parse_rejects_bad_claims(raw, err: str) -> None:
    with pytest.raises(ValueError, match=err):
        parse_claim(raw)


def test_parse_accepts_valid_forms() -> None:
    c = parse_claim(_raw(evidence={"kind": "PYTEST", "targets": ["tests/a_b.py::test_x[1-2]"]}, accepted_by="Andrii",
                         entailment="why", open_defeaters=["d1"]))
    assert c.entailment == "why" and c.open_defeaters == ("d1",)
    assert c.evidence == Evidence("PYTEST", ("tests/a_b.py::test_x[1-2]",)) and c.accepted_by == "Andrii"
    assert c.declared_status is None and c.safety_critical is False
    f = parse_claim(_raw(evidence={"kind": "FILE_SHA256", "targets": ["a"], "expected_sha256": "a" * 64},
                         entailment="e"))
    assert f.evidence.expected_sha256 == "a" * 64 and f.open_defeaters == ()
    with pytest.raises(FrozenInstanceError):
        c.statement = "x"  # type: ignore[misc]


def test_load_ledger_shape_and_strict_json() -> None:
    ok = {"claims": [_raw(declared_status=ASSUMED), _raw(claim_id="c2", declared_status=UNKNOWN)]}
    assert [c.claim_id for c in load_ledger(json.dumps(ok))] == ["c1", "c2"]
    for bad, err in ((json.dumps({"claims": []}), "ERR_LEDGER_EMPTY"),
                     (json.dumps({"claims": [_raw(declared_status=ASSUMED)] * 2}), "ERR_LEDGER_DUPLICATE_CLAIM_ID"),
                     (json.dumps({"claims": {}}), "ERR_LEDGER_SHAPE"),
                     (json.dumps({"claims": [], "x": 1}), "ERR_LEDGER_SHAPE"),
                     (json.dumps([1]), "ERR_LEDGER_SHAPE")):
        with pytest.raises(ValueError, match=err):
            load_ledger(bad)
    with pytest.raises(ValueError):  # duplicate key rejected by strict ingress
        load_ledger('{"claims": [], "claims": []}')



# ----------------------------------------------------------------- checking
def _chk(cid, kind, targets, sha=None, critical=False, defeaters=()):
    return Claim(cid, f"stmt {cid}", "f", critical, Evidence(kind, tuple(targets), sha), None, None, "e",
                 tuple(defeaters))


def test_check_file_sha256(repo: Path, tmp_path: Path) -> None:
    good = check_claim(_chk("a", "FILE_SHA256", ["data.txt"], _sha(repo / "data.txt")), str(repo))
    assert good == ClaimResult("a", VERIFIED, "SHA256_MATCH")
    bad = check_claim(_chk("b", "FILE_SHA256", ["data.txt"], "0" * 64), str(repo))
    assert bad.status == REFUTED and bad.detail == f"SHA256_MISMATCH:{_sha(repo / 'data.txt')}"
    missing = check_claim(_chk("c", "FILE_SHA256", ["nope.txt"], "0" * 64), str(repo))
    assert missing == ClaimResult("c", REFUTED, "FILE_MISSING_OR_UNREADABLE")
    (tmp_path / "secret").write_text("x")
    (repo / "link").symlink_to(tmp_path / "secret")
    for target in ("link", "../secret", "/etc/hosts", "a\x00b"):
        r = check_claim(_chk("d", "FILE_SHA256", [target], "0" * 64), str(repo))
        assert r == ClaimResult("d", UNKNOWN, "PATH_OUTSIDE_REPO"), target


def test_check_pytest_outcomes(repo: Path) -> None:
    root = str(repo)
    assert check_claim(_chk("ok", "PYTEST", ["tests/test_ok.py"]), root) == ClaimResult("ok", VERIFIED, "PYTEST_EXIT_0")
    assert check_claim(_chk("f", "PYTEST", ["tests/test_ok.py", "tests/test_fail.py"]), root) == \
        ClaimResult("f", REFUTED, "PYTEST_EXIT_1_TESTS_FAILED")
    r = check_claim(_chk("b", "PYTEST", ["tests/test_broken.py"]), root)
    assert r.status == UNKNOWN and r.detail.startswith("PYTEST_COULD_NOT_RUN:EXIT_")
    r = check_claim(_chk("m", "PYTEST", ["tests/test_missing.py"]), root)
    assert r.status == UNKNOWN
    assert check_claim(_chk("s", "PYTEST", ["tests/test_slow.py"]), root, pytest_timeout_s=3) == \
        ClaimResult("s", UNKNOWN, "PYTEST_TIMEOUT")
    os.symlink("/etc", str(repo / "tests" / "outside"))
    assert check_claim(_chk("o", "PYTEST", ["tests/outside/x.py"]), root) == ClaimResult("o", UNKNOWN, "PATH_OUTSIDE_REPO")
    declared = Claim("d", "s", "f", False, None, HYPOTHESIS)
    assert check_claim(declared, root) == ClaimResult("d", HYPOTHESIS, "NO_CHECK_DECLARED_STATUS")


def test_pytest_check_does_not_inherit_host_secrets(repo: Path) -> None:
    (repo / "tests" / "test_env.py").write_text(
        "import os\ndef test_env():\n    assert 'AWS_SECRET_ACCESS_KEY' not in os.environ\n")
    os.environ["AWS_SECRET_ACCESS_KEY"] = "truth-compass-canary"
    try:
        r = check_claim(_chk("e", "PYTEST", ["tests/test_env.py"]), str(repo))
    finally:
        del os.environ["AWS_SECRET_ACCESS_KEY"]
    assert r.status == VERIFIED


# ----------------------------------------------------------------- deciding
def _c(cid, critical=False, accepted=None):
    return Claim(cid, "s", "f", critical, None, ASSUMED, accepted)


def test_decide_tiers() -> None:
    claims = [_c("v", critical=True), _c("a"), _c("acc", accepted="Andrii")]
    ok = [ClaimResult("v", VERIFIED, ""), ClaimResult("acc", ASSUMED, "")]
    assert decide(claims, ok, T1) == (True, "OK_T1")
    assert decide(claims, ok, T2) == (True, "OK_T2_STAGING")
    assert decide(claims, ok, T3) == (True, "NO_KNOWN_BLOCKER_HUMAN_APPROVAL_REQUIRED")
    unaccepted = ok + [ClaimResult("a", HYPOTHESIS, "")]
    assert decide(claims, unaccepted, T2) == (True, "OK_T2_STAGING")
    assert decide(claims, unaccepted, T3) == (False, "HALT_UNACCEPTED_RESIDUAL_RISK:a")
    crit_unknown = [ClaimResult("v", UNKNOWN, "")]
    assert decide(claims, crit_unknown, T3) == (False, "HALT_SAFETY_CRITICAL_NOT_VERIFIED:v")
    crit_assumed_but_accepted = [Claim("x", "s", "f", True, None, ASSUMED, "Andrii")]
    assert decide(crit_assumed_but_accepted, [ClaimResult("x", ASSUMED, "")], T3) == (
        False, "HALT_SAFETY_CRITICAL_NOT_VERIFIED:x")
    for bad in (REFUTED, DISPUTED):
        res = ok + [ClaimResult("a", bad, "")]
        assert decide(claims, res, T1) == (True, "OK_T1_INVESTIGATE_REFUTED")
        assert decide(claims, res, T2) == (False, "HALT_REFUTED_OR_DISPUTED:a")
        assert decide(claims, res, T3) == (False, "HALT_REFUTED_OR_DISPUTED:a")
    with pytest.raises(ValueError, match="ERR_INVALID_TIER"):
        decide(claims, ok, "T9")


# ---------------------------------------------------------- end to end + state
def test_where_we_stand_end_to_end_and_staleness(repo: Path) -> None:
    claims = (
        _chk("file", "FILE_SHA256", ["data.txt"], _sha(repo / "data.txt"), critical=True),
        _chk("tests", "PYTEST", ["tests/test_ok.py"], critical=True),
        Claim("hyp", "a hypothesis", "f", False, None, HYPOTHESIS, "Andrii"),
        Claim("unk", "an unknown", "f", False, None, UNKNOWN),
    )
    r = where_we_stand(claims, str(repo), T3)
    assert (r.allowed, r.reason) == (False, "HALT_UNACCEPTED_RESIDUAL_RISK:unk")
    assert r.verified == ("file", "tests") and r.unverified == ("hyp", "unk") and r.refuted == ()
    assert r.report_caid.startswith("sha256:") and len(r.report_caid) == 71
    r2 = where_we_stand(claims, str(repo), T3)
    assert r2.report_caid == r.report_caid  # deterministic on the same tree
    assert where_we_stand(claims, str(repo), T2).report_caid != r.report_caid
    assert report_is_current(r, str(repo)) is True
    # editing the evidenced file refutes the claim and makes the old report stale
    (repo / "data.txt").write_text("changed\n")
    assert report_is_current(r, str(repo)) is False
    r_mod = where_we_stand(claims, str(repo), T2)
    # a second edit of an already-modified file (same status line) is still detected
    os.utime(repo / "data.txt", ns=(1, 1))
    assert report_is_current(r_mod, str(repo)) is False
    r3 = where_we_stand(claims, str(repo), T2)
    assert (r3.allowed, r3.reason, r3.refuted) == (False, "HALT_REFUTED_OR_DISPUTED:file", ("file",))
    assert r3.report_caid != r.report_caid
    card = render_card(r3, claims)
    assert "allowed=False" in card and "[REFUTED] stmt file" in card and "not an approval" in card
    assert "CHECKED NOW (verified): 1" in card and f"report_caid: {r3.report_caid}" in card
    with pytest.raises(ValueError, match="ERR_INVALID_TIER"):
        where_we_stand(claims, str(repo), "T0")
    with pytest.raises(ValueError, match="ERR_LEDGER_EMPTY"):
        where_we_stand((), str(repo), T1)
    with pytest.raises(FrozenInstanceError):
        r.allowed = True  # type: ignore[misc]


def test_tree_state_tracks_untracked_files_and_non_git(repo: Path, tmp_path: Path) -> None:
    s1 = tree_state(str(repo))
    assert s1.startswith("sha256:")
    # a new commit with a clean worktree changes HEAD only: must still change the state
    _git(repo, "commit", "-q", "--allow-empty", "-m", "empty")
    s_commit = tree_state(str(repo))
    assert s_commit != s1
    s1 = s_commit
    (repo / "new_untracked.txt").write_text("x")
    assert tree_state(str(repo)) != s1
    plain = tmp_path / "plain"
    plain.mkdir()
    assert tree_state(str(plain)) == "UNKNOWN_NOT_A_GIT_TREE"
    r = where_we_stand((Claim("u", "s", "f", False, None, UNKNOWN),), str(plain), T1)
    assert r.tree_state == "UNKNOWN_NOT_A_GIT_TREE" and report_is_current(r, str(plain)) is False


def test_tree_state_detects_same_size_edit_with_forged_mtime(repo: Path) -> None:
    p = repo / "data.txt"
    p.write_text("alpha1\n")
    st = os.lstat(p)
    s1 = tree_state(str(repo))
    p.write_text("alpha2\n")
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert os.lstat(p).st_size == st.st_size
    assert os.lstat(p).st_mtime_ns == st.st_mtime_ns
    assert tree_state(str(repo)) != s1
    # Boundary at MAX_HASH_FILE_BYTES: <= is content-hashed; > falls back to STAT_ONLY
    big = repo / "big.bin"
    big.write_bytes(b"a" * MAX_HASH_FILE_BYTES)
    st_eq = os.lstat(big)
    s_eq1 = tree_state(str(repo))
    big.write_bytes(b"b" * MAX_HASH_FILE_BYTES)
    os.utime(big, ns=(st_eq.st_atime_ns, st_eq.st_mtime_ns))
    assert tree_state(str(repo)) != s_eq1
    big.write_bytes(b"a" * (MAX_HASH_FILE_BYTES + 1))
    st_over = os.lstat(big)
    s_over1 = tree_state(str(repo))
    big.write_bytes(b"b" * (MAX_HASH_FILE_BYTES + 1))
    os.utime(big, ns=(st_over.st_atime_ns, st_over.st_mtime_ns))
    assert tree_state(str(repo)) == s_over1
    # Symlink and deleted tracked file (MISSING)
    (repo / "sym").symlink_to("data.txt")
    s_sym = tree_state(str(repo))
    assert s_sym != s_over1
    p.unlink()
    assert tree_state(str(repo)) != s_sym



# ----------------------------------------------------------------------- CLI

def test_open_defeater_blocks_verified_but_not_refuted(repo: Path) -> None:
    root = str(repo)
    passing = _chk("p", "PYTEST", ["tests/test_ok.py"], critical=True, defeaters=["test may not entail claim"])
    assert check_claim(passing, root) == ClaimResult("p", UNKNOWN, "CHECK_PASSED_BUT_OPEN_DEFEATERS:1")
    failing = _chk("f", "PYTEST", ["tests/test_fail.py"], defeaters=["d"])
    assert check_claim(failing, root).status == REFUTED
    r = where_we_stand((passing,), root, T3)
    assert (r.allowed, r.reason) == (False, "HALT_SAFETY_CRITICAL_NOT_VERIFIED:p")
    closed = _chk("p", "PYTEST", ["tests/test_ok.py"], critical=True)
    assert where_we_stand((closed,), root, T3).reason == "NO_KNOWN_BLOCKER_HUMAN_APPROVAL_REQUIRED"
    assert where_we_stand((closed,), root, T3).report_caid != r.report_caid


# ----------------------------------------- dependency DAG & contagion + chain
def test_depends_on_parsing_and_dag_validation() -> None:
    c = parse_claim(_raw(claim_id="b", declared_status=ASSUMED, depends_on=["a", "a_2"]))
    assert c.depends_on == ("a", "a_2")
    for bad in ("a", ["Bad ID"], [""], ["a", "a"], ["c1"], [1]):
        with pytest.raises(ValueError, match="ERR_LEDGER_BAD_DEPENDS_ON"):
            parse_claim(_raw(declared_status=ASSUMED, depends_on=bad))
    # unknown dependency
    with pytest.raises(ValueError, match="ERR_LEDGER_UNKNOWN_DEPENDENCY:b:missing"):
        load_ledger(json.dumps({"claims": [_raw(claim_id="b", declared_status=ASSUMED, depends_on=["missing"])]}))
    # 2-node cycle and 3-node cycle
    cyc = {"claims": [
        _raw(claim_id="a", declared_status=ASSUMED, depends_on=["b"]),
        _raw(claim_id="b", declared_status=ASSUMED, depends_on=["a"]),
    ]}
    with pytest.raises(ValueError, match="ERR_LEDGER_DEPENDENCY_CYCLE"):
        load_ledger(json.dumps(cyc))
    with pytest.raises(ValueError, match="ERR_LEDGER_DUPLICATE_CLAIM_ID"):
        validate_dependency_dag((_c("dup"), _c("dup")))


def test_transitive_contagion_propagation(repo: Path) -> None:
    root = str(repo)
    sha_ok = _sha(repo / "data.txt")
    # Chain: c_root (REFUTED) -> c_mid (own check passes!) -> c_leaf (own check passes!)
    c_root = Claim("c_root", "root", "f", True, Evidence("FILE_SHA256", ("data.txt",), "0" * 64), None, None, "e")
    c_mid = Claim("c_mid", "mid", "f", True, Evidence("FILE_SHA256", ("data.txt",), sha_ok), None, None, "e", (), ("c_root",))
    c_leaf = Claim("c_leaf", "leaf", "f", True, Evidence("PYTEST", ("tests/test_ok.py",)), None, None, "e", (), ("c_mid",))
    # Declare child on reverse order in input tuple to prove topological ordering works regardless of declaration order
    r = where_we_stand((c_leaf, c_mid, c_root), root, T2)
    by_id = {res.claim_id: res for res in r.results}
    assert by_id["c_root"].status == REFUTED and by_id["c_root"].detail.startswith("SHA256_MISMATCH:")
    assert by_id["c_mid"] == ClaimResult("c_mid", REFUTED, "CONTAGION_REFUTED_FROM:c_root")
    assert by_id["c_leaf"] == ClaimResult("c_leaf", REFUTED, "CONTAGION_REFUTED_FROM:c_mid")
    assert r.refuted == ("c_leaf", "c_mid", "c_root") and r.verified == ()

    # If a child's own check already failed, keep its own failure detail rather than overwriting with contagion
    c_own_fail = Claim("c_own", "own", "f", True, Evidence("FILE_SHA256", ("data.txt",), "1" * 64), None, None, "e", (), ("c_root",))
    res_own = propagate_contagion((c_root, c_own_fail), (check_claim(c_root, root), check_claim(c_own_fail, root)))
    assert res_own[1].status == REFUTED and res_own[1].detail.startswith("SHA256_MISMATCH:")

    # Unverified premise (ASSUMED) downgrades a passing dependent check from VERIFIED to UNKNOWN
    c_assumed = Claim("c_assumed", "assumed root", "f", False, None, ASSUMED, "Andrii")
    c_dep_ok = Claim("c_dep_ok", "checked child", "f", True, Evidence("FILE_SHA256", ("data.txt",), sha_ok),
                     None, None, "e", (), ("c_assumed",))
    r_unv = where_we_stand((c_assumed, c_dep_ok), root, T3)
    by_id_unv = {res.claim_id: res for res in r_unv.results}
    assert by_id_unv["c_dep_ok"] == ClaimResult("c_dep_ok", UNKNOWN, "CONTAGION_UNVERIFIED_FROM:c_assumed")
    assert (r_unv.allowed, r_unv.reason) == (False, "HALT_SAFETY_CRITICAL_NOT_VERIFIED:c_dep_ok")


def test_signed_hash_chained_report_envelopes(repo: Path) -> None:
    key = Ed25519PrivateKey.generate()
    pub_hex = key.public_key().public_bytes_raw().hex()
    c1 = _chk("file", "FILE_SHA256", ["data.txt"], _sha(repo / "data.txt"), critical=True)
    r1 = where_we_stand((c1,), str(repo), T1)
    r2 = where_we_stand((c1,), str(repo), T2)
    e1 = sign_report_envelope(r1, key, sequence=1, prev_report_caid=GENESIS_PREV_REPORT_CAID)
    e2 = sign_report_envelope(r2, key, sequence=2, prev_report_caid=r1.report_caid)
    assert verify_report_chain([e1, e2], pub_hex) == (True, "OK_REPORT_CHAIN_VERIFIED")

    # Tamper & adversarial checks
    assert verify_report_chain([], pub_hex) == (False, "HALT_EMPTY_REPORT_CHAIN")
    assert verify_report_chain([e1], "bad-key") == (False, "HALT_INVALID_TRUSTED_PUBLIC_KEY")
    other_pub = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
    assert verify_report_chain([e1], other_pub) == (False, "HALT_UNTRUSTED_ISSUER_KEY:1")
    assert verify_report_chain([e2], pub_hex) == (False, "HALT_CHAIN_SEQUENCE_GAP:1")
    e2_bad_prev = sign_report_envelope(r2, key, sequence=2, prev_report_caid=GENESIS_PREV_REPORT_CAID)
    assert verify_report_chain([e1, e2_bad_prev], pub_hex) == (False, "HALT_CHAIN_BROKEN_PREV_CAID:2")
    assert verify_report_chain([{**e1, "reason": "TAMPERED"}], pub_hex) == (False, "HALT_ENVELOPE_CAID_MISMATCH:1")
    flipped_sig = e1["signature_hex"][:-1] + ("0" if e1["signature_hex"][-1] != "0" else "1")
    assert verify_report_chain([{**e1, "signature_hex": flipped_sig}], pub_hex) == (False, "HALT_INVALID_SIGNATURE:1")
    assert verify_report_chain([{**e1, "signature_hex": "zz"}], pub_hex) == (False, "HALT_INVALID_SIGNATURE:1")
    assert verify_report_chain([{**e1, "extra": 1}], pub_hex) == (False, "HALT_ENVELOPE_SCHEMA_MISMATCH:1")
    assert verify_report_chain([{**e1, "schema": "wrong"}], pub_hex) == (False, "HALT_ENVELOPE_SCHEMA_MISMATCH:1")
    assert verify_report_chain([{**e1, "allowed": 1}], pub_hex) == (False, "HALT_ENVELOPE_SCHEMA_MISMATCH:1")

    for bad_seq in (0, -1, True, "1"):
        with pytest.raises(ValueError, match="ERR_INVALID_ENVELOPE_SEQUENCE"):
            sign_report_envelope(r1, key, sequence=bad_seq)  # type: ignore[arg-type]

    # Tail truncation: a valid prefix verifies unless a head / length pin is held out of band
    assert verify_report_chain([e1], pub_hex) == (True, "OK_REPORT_CHAIN_VERIFIED")
    assert verify_report_chain([e1], pub_hex, expected_head_envelope_caid=e2["envelope_caid"]) == (
        False, "HALT_CHAIN_HEAD_MISMATCH_TRUNCATED_OR_FORKED")
    assert verify_report_chain([e1, e2], pub_hex, expected_head_envelope_caid=e2["envelope_caid"]) == (
        True, "OK_REPORT_CHAIN_VERIFIED")
    assert verify_report_chain([e1], pub_hex, min_entries=2) == (False, "HALT_CHAIN_SHORTER_THAN_PINNED:1<2")
    assert verify_report_chain([e1, e2], pub_hex, min_entries=2) == (True, "OK_REPORT_CHAIN_VERIFIED")
    for bad_min in (0, -1, True, "2"):
        assert verify_report_chain([e1, e2], pub_hex, min_entries=bad_min) == (  # type: ignore[arg-type]
            False, "HALT_INVALID_MIN_ENTRIES")
    for bad_head in ("bad", 7, "sha256:" + "G" * 64):
        assert verify_report_chain([e1, e2], pub_hex, expected_head_envelope_caid=bad_head) == (  # type: ignore[arg-type]
            False, "HALT_INVALID_EXPECTED_HEAD")
    # empty chain still reported as empty even with a pin
    assert verify_report_chain([], pub_hex, expected_head_envelope_caid=e2["envelope_caid"]) == (
        False, "HALT_EMPTY_REPORT_CHAIN")
    # a forged fork with a different head is rejected by the head pin even when signed by the same key
    e2_fork = sign_report_envelope(where_we_stand((c1,), str(repo), T3), key, sequence=2,
                                   prev_report_caid=r1.report_caid)
    assert verify_report_chain([e1, e2_fork], pub_hex) == (True, "OK_REPORT_CHAIN_VERIFIED")
    assert verify_report_chain([e1, e2_fork], pub_hex, expected_head_envelope_caid=e2["envelope_caid"]) == (
        False, "HALT_CHAIN_HEAD_MISMATCH_TRUNCATED_OR_FORKED")
    with pytest.raises(ValueError, match="ERR_INVALID_SIGNING_KEY"):
        sign_report_envelope(r1, "not-a-key")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="ERR_INVALID_PREV_REPORT_CAID"):
        sign_report_envelope(r1, key, prev_report_caid="bad")
    from src.truth_compass import WhereWeStand
    bad_rep = WhereWeStand(r1.tier, r1.allowed, r1.reason, r1.verified, r1.refuted, r1.unverified,
                           r1.tree_state, r1.results, "bad-caid")
    with pytest.raises(ValueError, match="ERR_INVALID_REPORT_CAID"):
        sign_report_envelope(bad_rep, key)


def test_claim_result_frozen_immutability() -> None:
    res = ClaimResult("C1", "VERIFIED", "detail")
    with pytest.raises(FrozenInstanceError):
        res.status = "MUTATED"  # type: ignore[misc]


def test_claim_json_serialization_exact() -> None:
    c = Claim("C1", "statement", "falsifier", False, open_defeaters=("D1",), depends_on=("C0",))
    d = _claim_json(c)
    assert isinstance(d, dict)
    assert d["claim_id"] == "C1"
    assert d["open_defeaters"] == ["D1"]
    assert d["depends_on"] == ["C0"]

