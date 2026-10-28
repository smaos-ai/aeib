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
truth_compass.py — "Where we stand" ledger with re-executed evidence (prototype).

Evaluated under the stated model. The one rule that separates this from a
status list: a claim's VERIFIED / REFUTED status is never typed in by a person
or an agent. It is computed, now, by re-running the claim's check against the
current tree:

  * FILE_SHA256  — the compass re-hashes a repo-relative file and compares.
  * PYTEST       — the compass runs the named test node ids out-of-process
                   (`sys.executable -I -m pytest`, minimal env, timeout;
                   process isolation, not a sandbox). exit 0 -> VERIFIED,
                   exit 1 (tests failed: the falsifier fired) -> REFUTED,
                   anything else (collection error, timeout) -> UNKNOWN.

A claim without a check can only be ASSUMED, HYPOTHESIS, UNKNOWN or DISPUTED.
Declaring VERIFIED/OBSERVED without a check is rejected (self-asserted status
is a trivial verifier). A checked claim must state its `entailment` (why this
check supports this statement), and may list `open_defeaters` (known reasons
the check might not support the statement); while any defeater is open, a
passing check yields UNKNOWN, not VERIFIED (defeaters as in Assurance 2.0,
arXiv:2405.15800).

Tier rule (a decision aid, never an approval):
  * T1_LOCAL_TEST — always allowed; if something is refuted, the next step is
    to investigate it locally.
  * T2_STAGING    — blocked by any REFUTED or DISPUTED claim.
  * T3_IRREVERSIBLE — additionally blocked unless every safety-critical claim
    is VERIFIED and every other unverified claim names a human who accepted
    the residual risk (`accepted_by`). Even then the outcome is
    NO_KNOWN_BLOCKER_HUMAN_APPROVAL_REQUIRED: the compass does not approve.

Limitations (stated honestly): a passing test shows the test passed, not that
the statement is true in the world; a weak test makes a weak claim. The report
is bound to the tree state it was computed on (HEAD + `git status` + SHA-256
content hashes of regular changed/untracked files up to `MAX_HASH_FILE_BYTES`,
with `(size, mtime_ns)` fallback for larger or non-regular entries);
`report_is_current` must be checked before relying on an old report. The
ledger file itself is trusted input; protect it like code (review + diff).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from src.jcs_canonicalizer import encode_jcs
from src.strict_json_ingress import loads_strict

VERIFIED = "VERIFIED"
REFUTED = "REFUTED"
ASSUMED = "ASSUMED"
HYPOTHESIS = "HYPOTHESIS"
UNKNOWN = "UNKNOWN"
DISPUTED = "DISPUTED"

DECLARABLE_WITHOUT_CHECK = frozenset({ASSUMED, HYPOTHESIS, UNKNOWN, DISPUTED})
KIND_FILE_SHA256 = "FILE_SHA256"
KIND_PYTEST = "PYTEST"

T1 = "T1_LOCAL_TEST"
T2 = "T2_STAGING"
T3 = "T3_IRREVERSIBLE"
TIERS = (T1, T2, T3)

ENVELOPE_SCHEMA = "aeib.truth_compass.envelope.v1"
GENESIS_PREV_REPORT_CAID = "sha256:" + "0" * 64
MAX_HASH_FILE_BYTES = 2_000_000

_CLAIM_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_CAID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_NODEID_RE = re.compile(r"^tests/[A-Za-z0-9_./-]+\.py(?:::[A-Za-z0-9_\[\]-]+)*$")


@dataclass(frozen=True)
class Evidence:
    kind: str
    targets: Tuple[str, ...]
    expected_sha256: Optional[str] = None


@dataclass(frozen=True)
class Claim:
    claim_id: str
    statement: str
    falsifier: str
    safety_critical: bool
    evidence: Optional[Evidence] = None
    declared_status: Optional[str] = None
    accepted_by: Optional[str] = None
    entailment: Optional[str] = None
    open_defeaters: Tuple[str, ...] = ()
    depends_on: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaimResult:
    claim_id: str
    status: str
    detail: str


@dataclass(frozen=True)
class WhereWeStand:
    tier: str
    allowed: bool
    reason: str
    verified: Tuple[str, ...]
    refuted: Tuple[str, ...]
    unverified: Tuple[str, ...]
    tree_state: str
    results: Tuple[ClaimResult, ...]
    report_caid: str


# --------------------------------------------------------------------- parsing
def _nonempty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"ERR_LEDGER_FIELD_REQUIRED:{field}")
    return value


def parse_claim(raw: Dict[str, Any]) -> Claim:
    if not isinstance(raw, dict):
        raise ValueError("ERR_LEDGER_CLAIM_NOT_OBJECT")
    allowed = {"claim_id", "statement", "falsifier", "safety_critical", "evidence",
               "declared_status", "accepted_by", "entailment", "open_defeaters", "depends_on"}
    extra = set(raw) - allowed
    if extra:
        raise ValueError(f"ERR_LEDGER_UNKNOWN_FIELD:{sorted(extra)[0]}")
    claim_id = _nonempty_str(raw.get("claim_id"), "claim_id")
    if not _CLAIM_ID_RE.match(claim_id):
        raise ValueError(f"ERR_LEDGER_BAD_CLAIM_ID:{claim_id}")
    statement = _nonempty_str(raw.get("statement"), "statement")
    falsifier = _nonempty_str(raw.get("falsifier"), "falsifier")
    critical = raw.get("safety_critical")
    if type(critical) is not bool:
        raise ValueError("ERR_LEDGER_FIELD_REQUIRED:safety_critical")
    accepted_by = raw.get("accepted_by")
    if accepted_by is not None:
        accepted_by = _nonempty_str(accepted_by, "accepted_by")
    defeaters_raw = raw.get("open_defeaters", [])
    if not isinstance(defeaters_raw, list) or not all(isinstance(d, str) and d.strip() for d in defeaters_raw):
        raise ValueError(f"ERR_LEDGER_BAD_DEFEATERS:{claim_id}")
    defeaters = tuple(defeaters_raw)
    deps_raw = raw.get("depends_on", [])
    if (
        not isinstance(deps_raw, list)
        or not all(isinstance(d, str) and _CLAIM_ID_RE.match(d) for d in deps_raw)
        or len(set(deps_raw)) != len(deps_raw)
        or claim_id in deps_raw
    ):
        raise ValueError(f"ERR_LEDGER_BAD_DEPENDS_ON:{claim_id}")
    deps = tuple(deps_raw)
    ev_raw = raw.get("evidence")
    declared = raw.get("declared_status")
    if ev_raw is None:
        if declared not in DECLARABLE_WITHOUT_CHECK:
            raise ValueError(f"ERR_STATUS_WITHOUT_CHECK:{claim_id}:{declared}")
        if raw.get("entailment") is not None:
            raise ValueError(f"ERR_ENTAILMENT_WITHOUT_CHECK:{claim_id}")
        return Claim(claim_id, statement, falsifier, critical, None, declared, accepted_by, None, defeaters, deps)
    if declared is not None:
        raise ValueError(f"ERR_STATUS_IS_COMPUTED_FOR_CHECKED_CLAIM:{claim_id}")
    evidence = _parse_evidence(ev_raw, claim_id)
    entailment = _nonempty_str(raw.get("entailment"), "entailment")
    return Claim(claim_id, statement, falsifier, critical, evidence, None,
                 accepted_by, entailment, defeaters, deps)


def _parse_evidence(ev: Any, claim_id: str) -> Evidence:
    if not isinstance(ev, dict):
        raise ValueError(f"ERR_EVIDENCE_NOT_OBJECT:{claim_id}")
    kind = ev.get("kind")
    targets = ev.get("targets")
    if not isinstance(targets, list) or not targets or not all(isinstance(t, str) and t for t in targets):
        raise ValueError(f"ERR_EVIDENCE_TARGETS:{claim_id}")
    if kind == KIND_FILE_SHA256:
        expected = ev.get("expected_sha256")
        if len(targets) != 1 or not isinstance(expected, str) or not _SHA256_HEX_RE.match(expected):
            raise ValueError(f"ERR_EVIDENCE_FILE_SHA256:{claim_id}")
        return Evidence(kind, tuple(targets), expected)
    if kind == KIND_PYTEST:
        for t in targets:
            if not _NODEID_RE.match(t) or ".." in t.split("::")[0].split("/"):
                raise ValueError(f"ERR_EVIDENCE_PYTEST_NODEID:{claim_id}:{t}")
        return Evidence(kind, tuple(targets))
    raise ValueError(f"ERR_EVIDENCE_KIND:{claim_id}:{kind}")


def validate_dependency_dag(claims: Sequence[Claim]) -> Tuple[Claim, ...]:
    """Validate that all `depends_on` targets exist and form a DAG; return
    claims in topological order (parents before children)."""
    by_id = {c.claim_id: c for c in claims}
    if len(by_id) != len(claims):
        raise ValueError("ERR_LEDGER_DUPLICATE_CLAIM_ID")
    state: Dict[str, int] = {}
    ordered: List[Claim] = []

    def visit(cid: str) -> None:
        st = state.get(cid, 0)
        if st == 1:
            raise ValueError(f"ERR_LEDGER_DEPENDENCY_CYCLE:{cid}")
        if st == 2:
            return
        state[cid] = 1
        claim = by_id[cid]
        for dep in claim.depends_on:
            if dep not in by_id:
                raise ValueError(f"ERR_LEDGER_UNKNOWN_DEPENDENCY:{cid}:{dep}")
            visit(dep)
        state[cid] = 2
        ordered.append(claim)

    for c in claims:
        visit(c.claim_id)
    return tuple(ordered)


def load_ledger(text: str) -> Tuple[Claim, ...]:
    data = loads_strict(text)
    if not isinstance(data, dict) or set(data) != {"claims"} or not isinstance(data["claims"], list):
        raise ValueError("ERR_LEDGER_SHAPE")
    claims = tuple(parse_claim(c) for c in data["claims"])
    if not claims:
        raise ValueError("ERR_LEDGER_EMPTY")
    validate_dependency_dag(claims)
    return claims


# ------------------------------------------------------------------ checking
def _inside(repo_root: str, rel: str) -> Optional[str]:
    if os.path.isabs(rel) or "\x00" in rel:
        return None
    full = os.path.realpath(os.path.join(repo_root, rel))
    return full if os.path.commonpath([repo_root, full]) == repo_root else None


def check_claim(claim: Claim, repo_root: str, pytest_timeout_s: float = 300.0) -> ClaimResult:
    """Re-run the claim's check. A passing check with open defeaters is
    reported as UNKNOWN (Assurance 2.0: an unrefuted defeater blocks
    confidence, arXiv:2405.15800); a failing check is REFUTED regardless."""
    result = _run_check(claim, repo_root, pytest_timeout_s)
    if result.status == VERIFIED and claim.open_defeaters:
        return ClaimResult(claim.claim_id, UNKNOWN, f"CHECK_PASSED_BUT_OPEN_DEFEATERS:{len(claim.open_defeaters)}")
    return result


def _run_check(claim: Claim, repo_root: str, pytest_timeout_s: float) -> ClaimResult:
    ev = claim.evidence
    if ev is None:
        return ClaimResult(claim.claim_id, str(claim.declared_status), "NO_CHECK_DECLARED_STATUS")
    if ev.kind == KIND_FILE_SHA256:
        full = _inside(repo_root, ev.targets[0])
        if full is None:
            return ClaimResult(claim.claim_id, UNKNOWN, "PATH_OUTSIDE_REPO")
        try:
            with open(full, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            return ClaimResult(claim.claim_id, REFUTED, "FILE_MISSING_OR_UNREADABLE")
        if digest == ev.expected_sha256:
            return ClaimResult(claim.claim_id, VERIFIED, "SHA256_MATCH")
        return ClaimResult(claim.claim_id, REFUTED, f"SHA256_MISMATCH:{digest}")
    for t in ev.targets:
        if _inside(repo_root, t.split("::")[0]) is None:
            return ClaimResult(claim.claim_id, UNKNOWN, "PATH_OUTSIDE_REPO")
    with tempfile.TemporaryDirectory() as home:
        try:
            res = subprocess.run(
                [sys.executable, "-I", "-m", "pytest", "-q", "-p", "no:cacheprovider", *ev.targets],
                cwd=repo_root, capture_output=True, text=True, timeout=pytest_timeout_s, check=False,
                env={"PATH": "/usr/bin:/bin", "HOME": home, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except subprocess.TimeoutExpired:
            return ClaimResult(claim.claim_id, UNKNOWN, "PYTEST_TIMEOUT")
    if res.returncode == 0:
        return ClaimResult(claim.claim_id, VERIFIED, "PYTEST_EXIT_0")
    if res.returncode == 1:
        return ClaimResult(claim.claim_id, REFUTED, "PYTEST_EXIT_1_TESTS_FAILED")
    return ClaimResult(claim.claim_id, UNKNOWN, f"PYTEST_COULD_NOT_RUN:EXIT_{res.returncode}")


def tree_state(repo_root: str) -> str:
    """Staleness fingerprint: sha256 over HEAD, the `git status -z` bytes,
    and `(path, size, mtime_ns, content_tag)` of every changed/untracked entry.
    Regular changed/untracked files up to `MAX_HASH_FILE_BYTES` (2 MB) are
    content-hashed with SHA-256 (defending against same-size `utime` mtime
    reset); files larger than 2 MB or non-regular entries fall back to
    `(size, mtime_ns)` with `content_tag = "STAT_ONLY"`."""
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": repo_root,
           "GIT_CONFIG_NOSYSTEM": "1"}
    outputs = []
    for args in (["rev-parse", "HEAD"], ["status", "--porcelain=v1", "-z", "--untracked-files=all"]):
        res = subprocess.run(["git", "-C", repo_root, *args], capture_output=True, timeout=60,
                             env=env, check=False)
        if res.returncode != 0:
            return "UNKNOWN_NOT_A_GIT_TREE"
        outputs.append(res.stdout)
    stats = []
    for entry in outputs[1].split(b"\x00"):
        if len(entry) < 4:
            continue
        rel = os.fsdecode(entry[3:])
        path = os.path.join(repo_root, rel)
        try:
            st = os.lstat(path)
        except OSError:
            stats.append([rel, -1, -1, "MISSING"])
            continue
        if stat.S_ISREG(st.st_mode) and 0 <= st.st_size <= MAX_HASH_FILE_BYTES:
            try:
                with open(path, "rb") as fh:
                    content_tag = hashlib.sha256(fh.read()).hexdigest()
            except OSError:
                content_tag = "UNREADABLE"
        else:
            content_tag = "STAT_ONLY"
        stats.append([rel, st.st_size, st.st_mtime_ns, content_tag])
    parts = [hashlib.sha256(outputs[0]).hexdigest(), hashlib.sha256(outputs[1]).hexdigest(),
             hashlib.sha256(encode_jcs(stats)).hexdigest()]
    return "sha256:" + hashlib.sha256(encode_jcs(parts)).hexdigest()


# ------------------------------------------------------------------ deciding
def decide(claims: Sequence[Claim], results: Sequence[ClaimResult], tier: str) -> Tuple[bool, str]:
    if tier not in TIERS:
        raise ValueError(f"ERR_INVALID_TIER:{tier}")
    by_id = {c.claim_id: c for c in claims}
    blocking = [r for r in results if r.status in (REFUTED, DISPUTED)]
    if tier == T1:
        return True, "OK_T1_INVESTIGATE_REFUTED" if blocking else "OK_T1"
    if blocking:
        return False, f"HALT_REFUTED_OR_DISPUTED:{blocking[0].claim_id}"
    if tier == T2:
        return True, "OK_T2_STAGING"
    for r in results:
        if r.status == VERIFIED:
            continue
        c = by_id[r.claim_id]
        if c.safety_critical:
            return False, f"HALT_SAFETY_CRITICAL_NOT_VERIFIED:{c.claim_id}"
        if c.accepted_by is None:
            return False, f"HALT_UNACCEPTED_RESIDUAL_RISK:{c.claim_id}"
    return True, "NO_KNOWN_BLOCKER_HUMAN_APPROVAL_REQUIRED"


def propagate_contagion(
    claims: Sequence[Claim], raw_results: Sequence[ClaimResult]
) -> Tuple[ClaimResult, ...]:
    """Propagate epistemic status along `depends_on` edges in topological order:
      - If a premise is REFUTED or DISPUTED, any dependent claim that did not
        already fail its own check becomes REFUTED (`CONTAGION_REFUTED_FROM:<dep>`).
      - If a premise is not VERIFIED (e.g. UNKNOWN / ASSUMED / HYPOTHESIS), a
        dependent claim whose own check passed is downgraded from VERIFIED to
        UNKNOWN (`CONTAGION_UNVERIFIED_FROM:<dep>`).
    Exact DAG traversal: zero false positives, zero floats."""
    topo_claims = validate_dependency_dag(claims)
    effective: Dict[str, ClaimResult] = {r.claim_id: r for r in raw_results}
    for c in topo_claims:
        cur = effective[c.claim_id]
        refuted_dep = next(
            (d for d in c.depends_on if effective[d].status in (REFUTED, DISPUTED)),
            None,
        )
        if refuted_dep is not None:
            if cur.status not in (REFUTED, DISPUTED):
                effective[c.claim_id] = ClaimResult(
                    c.claim_id, REFUTED, f"CONTAGION_REFUTED_FROM:{refuted_dep}"
                )
            continue
        if cur.status == VERIFIED:
            unverified_dep = next(
                (d for d in c.depends_on if effective[d].status != VERIFIED),
                None,
            )
            if unverified_dep is not None:
                effective[c.claim_id] = ClaimResult(
                    c.claim_id, UNKNOWN, f"CONTAGION_UNVERIFIED_FROM:{unverified_dep}"
                )
    return tuple(effective[c.claim_id] for c in claims)


def where_we_stand(claims: Sequence[Claim], repo_root: str, tier: str,
                   pytest_timeout_s: float = 300.0) -> WhereWeStand:
    if tier not in TIERS:
        raise ValueError(f"ERR_INVALID_TIER:{tier}")
    if not claims:
        raise ValueError("ERR_LEDGER_EMPTY")
    validate_dependency_dag(claims)
    root = os.path.realpath(repo_root)
    raw_results = tuple(check_claim(c, root, pytest_timeout_s) for c in claims)
    results = propagate_contagion(claims, raw_results)
    allowed, reason = decide(claims, results, tier)
    state = tree_state(root)
    verified = tuple(sorted(r.claim_id for r in results if r.status == VERIFIED))
    refuted = tuple(sorted(r.claim_id for r in results if r.status in (REFUTED, DISPUTED)))
    unverified = tuple(sorted(r.claim_id for r in results if r.status in (ASSUMED, HYPOTHESIS, UNKNOWN)))
    body = {
        "allowed": allowed,
        "claims": [_claim_json(c) for c in sorted(claims, key=lambda c: c.claim_id)],
        "reason": reason,
        "results": [[r.claim_id, r.status, r.detail] for r in sorted(results, key=lambda r: r.claim_id)],
        "tier": tier,
        "tree_state": state,
    }
    caid = "sha256:" + hashlib.sha256(encode_jcs(body)).hexdigest()
    return WhereWeStand(tier, allowed, reason, verified, refuted, unverified, state, results, caid)


def report_is_current(report: WhereWeStand, repo_root: str) -> bool:
    state = tree_state(os.path.realpath(repo_root))
    return state != "UNKNOWN_NOT_A_GIT_TREE" and state == report.tree_state


def _claim_json(c: Claim) -> Dict[str, Any]:
    out: Dict[str, Any] = {"claim_id": c.claim_id, "falsifier": c.falsifier,
                           "safety_critical": c.safety_critical, "statement": c.statement}
    if c.evidence is not None:
        ev: Dict[str, Any] = {"kind": c.evidence.kind, "targets": list(c.evidence.targets)}
        if c.evidence.expected_sha256 is not None:
            ev["expected_sha256"] = c.evidence.expected_sha256
        out["evidence"] = ev
    if c.declared_status is not None:
        out["declared_status"] = c.declared_status
    if c.accepted_by is not None:
        out["accepted_by"] = c.accepted_by
    if c.entailment is not None:
        out["entailment"] = c.entailment
    if c.open_defeaters:
        out["open_defeaters"] = list(c.open_defeaters)
    if c.depends_on:
        out["depends_on"] = list(c.depends_on)
    return out


_ENVELOPE_BODY_FIELDS = (
    "allowed",
    "issuer_public_key_hex",
    "prev_report_caid",
    "reason",
    "report_caid",
    "schema",
    "sequence",
    "tier",
    "tree_state",
)
_ENVELOPE_ALL_FIELDS = frozenset((*_ENVELOPE_BODY_FIELDS, "envelope_caid", "signature_hex"))


def sign_report_envelope(
    report: WhereWeStand,
    signing_key: Ed25519PrivateKey,
    sequence: int = 1,
    prev_report_caid: str = GENESIS_PREV_REPORT_CAID,
) -> Dict[str, Any]:
    """Sign a `WhereWeStand` summary as an append-only hash-chained envelope."""
    if not isinstance(signing_key, Ed25519PrivateKey):
        raise ValueError("ERR_INVALID_SIGNING_KEY")
    if type(sequence) is not int or sequence < 1:
        raise ValueError("ERR_INVALID_ENVELOPE_SEQUENCE")
    if not isinstance(prev_report_caid, str) or not _CAID_RE.match(prev_report_caid):
        raise ValueError("ERR_INVALID_PREV_REPORT_CAID")
    if not isinstance(report.report_caid, str) or not _CAID_RE.match(report.report_caid):
        raise ValueError("ERR_INVALID_REPORT_CAID")
    pub_hex = signing_key.public_key().public_bytes_raw().hex()
    body: Dict[str, Any] = {
        "allowed": report.allowed,
        "issuer_public_key_hex": pub_hex,
        "prev_report_caid": prev_report_caid,
        "reason": report.reason,
        "report_caid": report.report_caid,
        "schema": ENVELOPE_SCHEMA,
        "sequence": sequence,
        "tier": report.tier,
        "tree_state": report.tree_state,
    }
    raw_bytes = encode_jcs(body)
    envelope_caid = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    sig_hex = signing_key.sign(raw_bytes).hex()
    return {**body, "envelope_caid": envelope_caid, "signature_hex": sig_hex}


def verify_report_chain(
    envelopes: Sequence[Dict[str, Any]],
    trusted_public_key_hex: str,
    expected_head_envelope_caid: Optional[str] = None,
    min_entries: int = 1,
) -> Tuple[bool, str]:
    """Verify an ordered sequence of signed report envelopes against a pinned
    Ed25519 public key, checking sequence monotonicity and `prev_report_caid`
    hash-chaining from `GENESIS_PREV_REPORT_CAID`.

    Tail truncation (dropping the newest entries, e.g. to hide a later
    REFUTED report) leaves a valid prefix and cannot be detected from the
    chain alone. It is detected only when the verifier holds an out-of-band
    pin: `expected_head_envelope_caid` (the newest envelope_caid recorded
    elsewhere, e.g. a second host or a commit message) and/or `min_entries`."""
    if type(min_entries) is not int or min_entries < 1:
        return False, "HALT_INVALID_MIN_ENTRIES"
    if expected_head_envelope_caid is not None and (
        not isinstance(expected_head_envelope_caid, str) or not _CAID_RE.match(expected_head_envelope_caid)
    ):
        return False, "HALT_INVALID_EXPECTED_HEAD"
    if not envelopes:
        return False, "HALT_EMPTY_REPORT_CHAIN"
    if len(envelopes) < min_entries:
        return False, f"HALT_CHAIN_SHORTER_THAN_PINNED:{len(envelopes)}<{min_entries}"
    if not isinstance(trusted_public_key_hex, str) or not _SHA256_HEX_RE.match(trusted_public_key_hex.lower()):
        return False, "HALT_INVALID_TRUSTED_PUBLIC_KEY"
    expected_pub_hex = trusted_public_key_hex.lower()
    pub_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(expected_pub_hex))
    expected_prev = GENESIS_PREV_REPORT_CAID
    for idx, env in enumerate(envelopes, start=1):
        if not isinstance(env, dict) or set(env) != _ENVELOPE_ALL_FIELDS:
            return False, f"HALT_ENVELOPE_SCHEMA_MISMATCH:{idx}"
        if env.get("schema") != ENVELOPE_SCHEMA or type(env.get("allowed")) is not bool:
            return False, f"HALT_ENVELOPE_SCHEMA_MISMATCH:{idx}"
        if type(env.get("sequence")) is not int or env["sequence"] != idx:
            return False, f"HALT_CHAIN_SEQUENCE_GAP:{idx}"
        if not isinstance(env.get("prev_report_caid"), str) or not hmac.compare_digest(
            env["prev_report_caid"], expected_prev
        ):
            return False, f"HALT_CHAIN_BROKEN_PREV_CAID:{idx}"
        if not isinstance(env.get("issuer_public_key_hex"), str) or not hmac.compare_digest(
            env["issuer_public_key_hex"].lower(), expected_pub_hex
        ):
            return False, f"HALT_UNTRUSTED_ISSUER_KEY:{idx}"
        body = {k: env[k] for k in _ENVELOPE_BODY_FIELDS}
        raw_bytes = encode_jcs(body)
        computed_caid = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
        if not isinstance(env.get("envelope_caid"), str) or not hmac.compare_digest(
            env["envelope_caid"], computed_caid
        ):
            return False, f"HALT_ENVELOPE_CAID_MISMATCH:{idx}"
        sig_hex = env.get("signature_hex")
        if not isinstance(sig_hex, str) or len(sig_hex) != 128:
            return False, f"HALT_INVALID_SIGNATURE:{idx}"
        try:
            pub_key.verify(bytes.fromhex(sig_hex), raw_bytes)
        except (ValueError, InvalidSignature):
            return False, f"HALT_INVALID_SIGNATURE:{idx}"
        expected_prev = env["report_caid"]
    if expected_head_envelope_caid is not None and not hmac.compare_digest(
        envelopes[-1]["envelope_caid"], expected_head_envelope_caid
    ):
        return False, "HALT_CHAIN_HEAD_MISMATCH_TRUNCATED_OR_FORKED"
    return True, "OK_REPORT_CHAIN_VERIFIED"


def render_card(report: WhereWeStand, claims: Sequence[Claim]) -> str:
    by_id = {c.claim_id: c for c in claims}
    status = {r.claim_id: r for r in report.results}
    lines: List[str] = [f"WHERE WE STAND  tier={report.tier}  allowed={report.allowed}", f"reason: {report.reason}"]
    for title, ids in (("CHECKED NOW (verified)", report.verified), ("REFUTED / DISPUTED", report.refuted),
                       ("NOT VERIFIED (assumed / hypothesis / unknown)", report.unverified)):
        lines.append(f"{title}: {len(ids)}")
        for cid in ids:
            r = status[cid]
            lines.append(f"  - [{r.status}] {by_id[cid].statement}  ({r.detail})")
    lines.append(f"tree_state: {report.tree_state}")
    lines.append(f"report_caid: {report.report_caid}")
    lines.append("This is a decision aid computed from re-run checks; it is not an approval.")
    return "\n".join(lines)
