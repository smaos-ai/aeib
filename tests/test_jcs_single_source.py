#!/usr/bin/env python3
"""
tests/test_jcs_single_source.py — RFC 8785 single-source differential test.

Every in-repo JSON canonicalizer listed in CANONICALIZERS is run against the
reference src.jcs_canonicalizer.encode_jcs on:
  * the cyberphone RFC 8785 vectors in tests/data/jcs/input, and
  * ~300 seeded random / edge payloads (non-BMP keys, exponents, -0.0, large
    integers, control characters, nested containers).

Policies (a wrapper may keep its own stricter ingress rule):
  exact     — must return the reference bytes and raise whenever the reference raises.
  no_float  — may raise on payloads containing a float; otherwise behaves as exact.
  shape     — integer/ASCII-only wrapper: may raise on anything else; when it
              returns, the bytes must equal the reference.
  digest    — returns sha256 hex of the canonical bytes.

Also covers src.strict_json_ingress.loads_strict (I-JSON / RFC 7493 ingress).
Maintain CANONICALIZERS when adding a canonicalizer; an import failure fails.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, List, Tuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs as reference  # noqa: E402
from src.strict_json_ingress import StrictJSONError, loads_strict  # noqa: E402

# (module, attribute path, policy)
CANONICALIZERS: List[Tuple[str, str, str]] = [
    # delegating wrappers (src)
    ("src.cose_signer", "jcs_canonicalize", "exact"),
    ("src.diagnostic_normalizer", "deterministic_json_bytes", "exact"),
    ("src.mcp_outcome_normalizer", "deterministic_json_bytes", "exact"),
    ("src.tinyfish_runner", "encode_rfc8785_jcs", "exact"),
    ("src.cose_verifier", "jcs_canonicalize", "exact"),
    ("src.repo_reverse_engineering_engine", "encode_jcs", "no_float"),
    ("src.protection_governor", "jcs_canonical_bytes", "exact"),
    ("src.camel_fides_ifc_and_acid_hardening", "canonical_jcs", "no_float"),
    ("src.transactional_storage_backend", "canonical_jcs", "no_float"),
    ("src.aeib_track1_and_calibrated_guards", "canonical_json_v1", "no_float"),
    ("src.stateful_hitl", "canonical_json_v1", "exact"),
    ("src.border_policy", "canonical_json_v1", "exact"),
    ("src.formal_mags_gate", "canonical_mags_json", "no_float"),
    ("src.sovereign_agent_blueprint", "canonical_jcs_bytes", "no_float"),
    ("src.universal_agent_adapter", "rfc8785_jcs_canonicalize", "exact"),
    ("src.external_policy_gate", "canonical_json_v1", "exact"),
    ("src.harness_router", "canonical_json_v1", "exact"),
    ("src.epistemic_core", "canonical_jcs", "no_float"),
    ("src.bio_variant_contract", "canonical_json_v1", "exact"),
    ("src.human_translation_compiler", "canonical_json_v1", "exact"),
    ("src.decide_autonomous_query_research_engine", "canonical_jcs", "exact"),
    ("src.inverse_lifecycle_referee", "canonical_json_v1", "exact"),
    ("src.cerno_scion_ta14_omnigent_fabric", "canonical_jcs", "no_float"),
    ("src.planetary_clearinghouse_and_tee_swarm", "canonical_jcs", "no_float"),
    ("src.research_mcp_adapter", "jcs_canonicalize", "exact"),
    ("src.decide_v5_recursive_evidence_engine", "encode_jcs", "no_float"),
    ("src.runtime_boundary.runtime_execution_boundary", "canonical_json_bytes", "no_float"),
    ("src.station1_state_engine", "canonical_json_v1", "exact"),
    ("src.epistemic_action_compiler", "canonical_jcs_bytes", "no_float"),
    ("src.decide_evaluation_rate_and_decay_solver", "canonical_jcs", "no_float"),
    ("src.decide_v51_meta_hardening_engine", "canonical_jcs_bytes", "no_float"),
    ("src.sovereign_independent_state_hub_and_chain_proxy", "canonical_jcs_bytes", "no_float"),
    ("src.aei_core_middleware", "jcs_canonicalize", "exact"),
    ("src.toyota_5why_semantic_rca_and_token_analytics", "canonical_jcs_bytes", "no_float"),
    ("src.china_and_global_leaders_hardening_suite", "canonical_jcs", "no_float"),
    ("src.ncm_parallel_burst_latch", "encode_jcs", "exact"),
    ("src.predictive_trajectory_drift_latch", "encode_jcs", "exact"),
    ("src.bpf_lsm_profile_compiler", "encode_jcs", "exact"),
    # delegating wrappers (tools / compliance / benchmarks / scripts / root)
    ("tools.zk_tlsnotary_integration", "encode_jcs", "no_float"),
    ("tools.subagent_coordinator", "encode_jcs", "exact"),
    ("tools.aeib_offline_verifier", "canonical_json_v1", "exact"),
    ("tools.parallel_open_frontier_and_urgent_solver", "canonical_jcs_bytes", "no_float"),
    ("tools.decide_v2_constant_time_snapshot", "canonical_jcs", "no_float"),
    ("tools.cross_hemisphere_council_decide", "canonical_jcs", "exact"),
    ("tools.hamt_cross_pollination_and_evidence_graph", "canonical_jcs", "no_float"),
    ("tools.builder_breaker_adversarial_engine", "canonical_jcs_bytes", "no_float"),
    ("tools.aeib_orca_caprock_enforcer", "canonical_jcs_bytes", "no_float"),
    ("tools.palantir_ontology_joint_witness_engine", "canonical_jcs", "no_float"),
    ("tools.ruletrek_cross_model_decide_engine", "canonical_jcs_bytes", "no_float"),
    ("tools.epistemic_intent_outcome_engine", "canonical_jcs_bytes", "exact"),
    ("tools.aeib_surviving_principles_engine", "canonical_json_bytes", "no_float"),
    ("tools.credential_starvation_gateway", "canonical_jcs_bytes", "no_float"),
    ("tools.phase0_integrity_reset_core", "canonical_json_v1", "no_float"),
    ("compliance.eac_typestate_conflict_engine", "canonical_jcs", "no_float"),
    ("compliance.defense_in_depth_policy_gate", "canonical_jcs_bytes", "exact"),
    ("benchmarks.third_party.agent_disrupt_adapter", "canonical_json_bytes", "exact"),
    ("benchmarks.third_party.aeib_refund_desk_adapter", "canonical_json_bytes", "exact"),
    ("benchmarks.third_party.tau2_banking_eval", "canonical_json_bytes", "exact"),
    ("benchmarks.third_party.aeib_session_integrity_adapter", "canonical_json_bytes", "exact"),
    ("scripts.live_ciso_demo", "jcs_canonicalize", "exact"),
    ("aeib_mcp_proxy", "canonical_json_bytes", "exact"),
    ("adapters.mcp.idempotent_mcp_proxy", "canonical_json_v1", "exact"),
    # stdlib-only / standalone copies (own implementation, must match exactly)
    ("tools.standalone_receipt_verifier", "encode_jcs", "exact"),
    ("tools.standalone_offline_verifier", "encode_jcs", "exact"),
    ("aeib_verify", "canonical_json_bytes", "exact"),
    ("src.ocr_audit.tools.jcs_digest", "jcs_canonicalize_strict", "exact"),
    ("src.ocr_audit.core_proof_engine", "rfc8785_canonicalize", "exact"),
    ("src.ocr_audit.scitt_verifier", "rfc8785_canonicalize", "exact"),
    ("ocr_audit.tools.jcs_digest", "jcs_canonicalize_strict", "exact"),
    ("ocr_audit.core_proof_engine", "rfc8785_canonicalize", "exact"),
    ("ocr_audit.scitt_verifier", "rfc8785_canonicalize", "exact"),
    ("tools.covering_design_verifier", "canonical_bytes", "shape"),
    # digest helpers (sha256 hex over canonical bytes)
    ("src.ocr_audit.tools.jcs_digest", "jcs_digest", "digest"),
    ("benchmarks.test_negative_vectors", "jcs_sha256", "digest"),
    ("benchmarks.fault_injection.test_negative_vectors", "jcs_sha256", "digest"),
]

SMILE = "\U0001F600"
KEY_POOL = ["a", "B", "z", "1", "\r", "\u00e9", "e\u0301", "\u20ac", "\u00f6", "\ufb33",
            "\uffff", "\ue000", SMILE, "\U00010000", "\x01", '"', "\\", "\u2028", "\x7f"]


def _rnd_str(r: random.Random) -> str:
    return "".join(r.choice(KEY_POOL) for _ in range(r.randint(0, 5)))


def _rnd_float(r: random.Random) -> float:
    choice = r.randint(0, 7)
    if choice == 0:
        return r.uniform(-1, 1) * 10 ** r.randint(-30, 30)
    if choice == 1:
        return float(r.randint(-(10**22), 10**22))
    if choice == 2:
        return r.choice([1e21, 1e-7, 1e20, 1e-6, 5e-324, 1.7976931348623157e308, -0.0, 0.0,
                         0.1 + 0.2, 333333333.33333329, 9007199254740993.0, 1e23, 123e-20])
    if choice == 3:
        return r.random()
    if choice == 4:
        return float(r.randint(-1000, 1000))
    if choice == 5:
        return r.uniform(-1, 1) * 1e-8
    if choice == 6:
        return -r.uniform(1e15, 1e25)
    return r.uniform(-1e30, 1e30)


def _rnd_val(r: random.Random, floats: bool, depth: int = 0) -> Any:
    top = 7 if depth < 3 else 4
    t = r.randint(0, top)
    if t == 0:
        return r.choice([r.randint(-(2**70), 2**70), r.randint(-(2**53), 2**53), r.randint(-9, 9)])
    if t == 1:
        return r.choice([True, False, None])
    if t == 2:
        return _rnd_str(r)
    if t == 3:
        return _rnd_float(r) if floats else r.randint(-(10**6), 10**6)
    if t == 4:
        return 0
    if t == 5:
        return [_rnd_val(r, floats, depth + 1) for _ in range(r.randint(0, 3))]
    return {_rnd_str(r): _rnd_val(r, floats, depth + 1) for _ in range(r.randint(0, 4))}


def _cyberphone_payloads() -> List[Any]:
    input_dir = REPO_ROOT / "tests" / "data" / "jcs" / "input"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(input_dir.glob("*.json"))]


def _build_payloads() -> List[Any]:
    r = random.Random(8785)
    edge: List[Any] = [
        {SMILE: 1, "\uffff": 2},
        {"\u20ac": 1, "\r": 2, SMILE: 3, "1": 4, "\u00f6": 5, "\ufb33": 6, "\ue000": 7},
        {"a": 1e21}, {"a": 1e-7}, {"a": 1e20}, {"a": 5e-324}, {"a": -0.0}, {"a": 1.0},
        {"a": 1.7976931348623157e308}, {"a": 0.1 + 0.2}, {"a": 9007199254740993},
        {"a": 2**64 + 1}, {"a": -(2**64)}, {"s": "\u2028\u2029\x7f\x1f\x00"},
        {"s": "e\u0301"}, [], {}, "", 0, None, True, [[[{"": [None]}]]],
        {1: "non-string key"}, {"n": float("nan")}, {"n": float("inf")}, (1, "t", (2,)),
    ]
    int_payloads: List[Any] = [{"k": _rnd_val(r, floats=False)} for _ in range(120)]
    # 50 objects mixing supplementary-plane and U+E000..U+FFFF keys, where UTF-16
    # code-unit order differs from code-point order (json.dumps sort_keys).
    int_payloads += [
        {SMILE + _rnd_str(r): _rnd_val(r, floats=False),
         "\uffff" + _rnd_str(r): _rnd_val(r, floats=False),
         "\ue000" + _rnd_str(r): r.randint(-(2**70), 2**70)}
        for _ in range(50)
    ]
    float_payloads = [{"f": _rnd_float(r), "g": _rnd_val(r, floats=True)} for _ in range(130)]
    return _cyberphone_payloads() + edge + int_payloads + float_payloads


PAYLOADS = _build_payloads()


def _contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_float(v) for v in value)
    return False


def _resolve(module: str, attr: str) -> Callable[[Any], Any]:
    if sys.path[0] != str(REPO_ROOT):
        sys.path.insert(0, str(REPO_ROOT))
    if module.startswith("adapters.") and "adapters" in sys.modules:
        mod_file = getattr(sys.modules["adapters"], "__file__", "") or ""
        if "/src/adapters/" in mod_file.replace("\\", "/"):
            del sys.modules["adapters"]
    obj: Any = importlib.import_module(module)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


def _ref(payload: Any) -> Tuple[bool, bytes]:
    try:
        return True, reference(payload)
    except (TypeError, ValueError, UnicodeEncodeError):
        return False, b""


def _divergences(fn: Callable[[Any], Any], policy: str) -> List[str]:
    found: List[str] = []
    for idx, payload in enumerate(PAYLOADS):
        ok, expected = _ref(payload)
        try:
            out = fn(payload)
        except Exception as exc:  # candidate rejected the payload
            if not ok:
                continue
            if policy == "shape":
                continue
            if policy == "no_float" and _contains_float(payload):
                continue
            found.append(f"#{idx} candidate raised {type(exc).__name__} where reference accepted")
            continue
        if not ok:
            found.append(f"#{idx} candidate accepted payload rejected by reference")
            continue
        if policy == "digest":
            expected_cmp: Any = hashlib.sha256(expected).hexdigest()
        else:
            expected_cmp = expected
            if isinstance(out, str):
                out = out.encode("utf-8")
        if out != expected_cmp:
            found.append(f"#{idx} {payload!r:.80} -> {out!r:.80} != {expected_cmp!r:.80}")
    return found


def test_payload_corpus_size_and_reference_vectors() -> None:
    assert len(PAYLOADS) >= 300
    out_dir = REPO_ROOT / "tests" / "data" / "jcs" / "output"
    in_dir = REPO_ROOT / "tests" / "data" / "jcs" / "input"
    names = sorted(p.name for p in in_dir.glob("*.json"))
    assert names, "cyberphone vectors missing"
    for name in names:
        payload = json.loads((in_dir / name).read_text(encoding="utf-8"))
        assert reference(payload) == (out_dir / name).read_bytes().rstrip(b"\n")


@pytest.mark.parametrize("module,attr,policy", CANONICALIZERS,
                         ids=[f"{m}.{a}" for m, a, _ in CANONICALIZERS])
def test_canonicalizer_matches_reference(module: str, attr: str, policy: str) -> None:
    fn = _resolve(module, attr)
    divergences = _divergences(fn, policy)
    assert divergences == [], f"{len(divergences)} divergences, first: {divergences[:3]}"


def test_no_float_policy_still_accepts_integer_payloads() -> None:
    """A wrapper that rejects everything would pass the differential loop; pin acceptance."""
    probe = {SMILE: [1, -(2**64)], "\uffff": {"b": None, "a": "x\u2028"}}
    for module, attr, policy in CANONICALIZERS:
        if policy in ("no_float", "exact"):
            out = _resolve(module, attr)(probe)
            out = out.encode("utf-8") if isinstance(out, str) else out
            assert out == reference(probe), f"{module}.{attr}"


def test_shape_policy_accepts_its_witness_shape() -> None:
    from tools.covering_design_verifier import canonical_bytes, canonical_witness

    witness = canonical_witness(7, 3, 2, [[1, 2, 3], [1, 4, 5]])
    assert canonical_bytes(witness) == reference(witness)
    with pytest.raises(ValueError):
        canonical_bytes({"v": 1.5})
    with pytest.raises(ValueError):
        canonical_bytes({SMILE: 1})


def _run_emitted_canonicalizer(script: str, fn_name: str, payloads: List[Any]) -> List[bytes]:
    """Run a generated standalone script's canonicalizer out-of-process
    (process isolation, not a sandbox: empty env, temp cwd, timeout)."""
    driver = (
        "import importlib.util, json, sys\n"
        "spec = importlib.util.spec_from_file_location('emitted', sys.argv[1])\n"
        "mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)\n"
        "payloads = json.loads(sys.stdin.read())\n"
        f"print(json.dumps([mod.{fn_name}(p).hex() for p in payloads]))\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "emitted.py"
        path.write_text(script, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-I", "-c", driver, str(path)],
            input=json.dumps(payloads), capture_output=True, text=True,
            timeout=60, cwd=tmp, env={"PATH": os.environ.get("PATH", "")},
        )
    assert proc.returncode == 0, proc.stderr[-500:]
    return [bytes.fromhex(h) for h in json.loads(proc.stdout.strip().splitlines()[-1])]


def _json_round_trippable(payloads: List[Any], floats: bool) -> List[Any]:
    keep = []
    for p in payloads:
        if not _ref(p)[0] or (not floats and _contains_float(p)):
            continue
        if json.loads(json.dumps(p)) == p and not isinstance(p, tuple):
            keep.append(p)
    return keep


def test_gemma_kaggle_template_canonicalizer_matches_reference() -> None:
    """The emitted stdlib-only Kaggle script carries its own float-free copy."""
    import src.gemma_developer_agent_engine as gem

    engine_cls = next(
        obj for obj in vars(gem).values()
        if isinstance(obj, type) and hasattr(obj, "generate_kaggle_submission_script")
    )
    script = engine_cls.generate_kaggle_submission_script(None)
    payloads = _json_round_trippable(PAYLOADS, floats=False)
    got = _run_emitted_canonicalizer(script, "canonical_json", payloads)
    assert len(got) == len(payloads) > 100
    assert [i for i, (g, p) in enumerate(zip(got, payloads)) if g != reference(p)] == []


def test_evidence_pack_standalone_verifier_template_matches_reference() -> None:
    """scripts/build_us_gtm_evidence_pack.py emits verify_pack.py with its own JCS copy."""
    from scripts.build_us_gtm_evidence_pack import STANDALONE_VERIFIER_PY

    payloads = _json_round_trippable(PAYLOADS, floats=True)
    got = _run_emitted_canonicalizer(STANDALONE_VERIFIER_PY, "encode_jcs", payloads)
    assert len(got) == len(payloads) > 200
    assert [i for i, (g, p) in enumerate(zip(got, payloads)) if g != reference(p)] == []


# ---------------------------------------------------------------------------
# strict JSON ingress (I-JSON, RFC 7493)
# ---------------------------------------------------------------------------

def test_loads_strict_rejects_duplicate_keys_at_any_depth() -> None:
    with pytest.raises(StrictJSONError) as exc:
        loads_strict('{"to":"alice","to":"mallory"}')
    assert exc.value.code == "ERR_DUPLICATE_KEY"
    with pytest.raises(StrictJSONError) as exc:
        loads_strict('{"a":[{"b":1,"b":1}]}')
    assert exc.value.code == "ERR_DUPLICATE_KEY"
    # json.loads silently keeps the last value: the gap this module closes.
    assert json.loads('{"to":"alice","to":"mallory"}') == {"to": "mallory"}


@pytest.mark.parametrize("text", ['{"a":NaN}', "[Infinity]", "-Infinity", '{"a":1e400}', "[-1e999]"])
def test_loads_strict_rejects_non_finite_numbers(text: str) -> None:
    with pytest.raises(StrictJSONError) as exc:
        loads_strict(text)
    assert exc.value.code == "ERR_NON_FINITE_NUMBER"


def test_loads_strict_integers_only_mode() -> None:
    assert loads_strict('{"bps":2500,"n":-3}', integers_only=True) == {"bps": 2500, "n": -3}
    for text in ('{"x":1.0}', '{"x":1e2}', "[0.5]"):
        with pytest.raises(StrictJSONError) as exc:
            loads_strict(text, integers_only=True)
        assert exc.value.code == "ERR_FLOAT_FORBIDDEN"
    with pytest.raises(StrictJSONError) as exc:
        loads_strict(str(2**53), integers_only=True)
    assert exc.value.code == "ERR_INTEGER_OUT_OF_RANGE"
    assert loads_strict(str(2**53 - 1), integers_only=True) == 2**53 - 1
    # floats remain allowed by default
    assert loads_strict('{"x":1.5}') == {"x": 1.5}
    assert loads_strict(str(2**60)) == 2**60


def test_loads_strict_rejects_lone_surrogates_and_bad_input() -> None:
    for text in ('"\\ud800"', '{"\\udc00":1}', '["ok","\\ud83d"]', '{"k":"\\udfff"}'):
        with pytest.raises(StrictJSONError) as exc:
            loads_strict(text)
        assert exc.value.code == "ERR_LONE_SURROGATE"
    assert loads_strict('"\\ud83d\\ude00"') == SMILE
    # Boundaries of the surrogate block U+D800..U+DFFF are accepted just outside it.
    assert loads_strict('["\\ud7ff","\\ue000"]') == ["\ud7ff", "\ue000"]
    with pytest.raises(StrictJSONError) as exc:
        loads_strict("{'a': 1}")
    assert exc.value.code == "ERR_INVALID_JSON"
    with pytest.raises(StrictJSONError) as exc:
        loads_strict(b"\xff\xfe")
    assert exc.value.code == "ERR_INVALID_JSON"
    with pytest.raises(StrictJSONError) as exc:
        loads_strict(123)  # type: ignore[arg-type]
    assert exc.value.code == "ERR_INPUT_TYPE"


def test_loads_strict_error_detail_is_bounded_to_60_chars() -> None:
    long_key = "k" * 500
    cases = [
        ('{"%s":1,"%s":2}' % (long_key, long_key), {}, "ERR_DUPLICATE_KEY"),
        ('"\\ud800%s"' % long_key, {}, "ERR_LONE_SURROGATE"),
        ("1" * 200 + ".5", {"integers_only": True}, "ERR_FLOAT_FORBIDDEN"),
        ("1" * 500 + "e400", {}, "ERR_NON_FINITE_NUMBER"),
        ("9" * 200, {"integers_only": True}, "ERR_INTEGER_OUT_OF_RANGE"),
    ]
    for text, kwargs, code in cases:
        with pytest.raises(StrictJSONError) as exc:
            loads_strict(text, **kwargs)
        assert exc.value.code == code
        assert len(exc.value.detail) == 60, (code, len(exc.value.detail))
        assert str(exc.value) == f"{code}: {exc.value.detail}"


def test_loads_strict_round_trips_cyberphone_vectors_through_reference() -> None:
    in_dir = REPO_ROOT / "tests" / "data" / "jcs" / "input"
    out_dir = REPO_ROOT / "tests" / "data" / "jcs" / "output"
    for path in sorted(in_dir.glob("*.json")):
        parsed = loads_strict(path.read_bytes())
        assert reference(parsed) == (out_dir / path.name).read_bytes().rstrip(b"\n")
