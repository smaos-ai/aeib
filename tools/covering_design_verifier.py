#!/usr/bin/env python3
"""Independent covering design verifier (stdlib only, prototype).

Checks a candidate C(v,k,t) covering design without trusting the proposer:

  1. points_within_range   every point is an integer in [0, v)
  2. block_size_equals_k   every block has exactly k distinct points
  3. no_duplicate_block    no block appears twice
  4. every_t_subset_covered  every t-subset of {0..v-1} lies in some block
  5. block_count_matches_claim  len(blocks) equals the claimed objective (if given)

It also reports the Schoenheim lower bound L(v,k,t). A design that passes all
checks while using fewer blocks than L(v,k,t) is mathematically impossible, so
that combination is reported as VERIFIER_INCONSISTENCY (a verifier bug alarm).

Coverage uses the combinatorial number system: rank(s) = sum C(s_i, i+1) for a
sorted t-subset s, indexing a bytearray of length C(v,t).

Usage:
  python3 tools/covering_design_verifier.py --input witness.json
Exit code 0 only when the design is valid.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
from typing import Any

VERIFIER_VERSION = "1.0.0"


def schoenheim_bound(v: int, k: int, t: int) -> int:
    """Schoenheim lower bound L(v,k,t) = ceil(v/k * L(v-1,k-1,t-1)), L(.,.,0)=1."""
    if t == 0:
        return 1
    inner = schoenheim_bound(v - 1, k - 1, t - 1)
    return -(-v * inner // k)


def subset_rank(sorted_subset: tuple[int, ...]) -> int:
    return sum(math.comb(p, i + 1) for i, p in enumerate(sorted_subset))


def canonical_witness(v: int, k: int, t: int, blocks: list[list[int]]) -> dict[str, Any]:
    norm = sorted(sorted(int(p) for p in b) for b in blocks)
    return {"blocks": norm, "k": k, "t": t, "v": v}


def _check_jcs_integer_shape(value: Any) -> None:
    """Fail closed outside the shape where sorted json.dumps equals RFC 8785."""
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, str)):
        return
    if isinstance(value, list):
        for item in value:
            _check_jcs_integer_shape(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key.isascii():
                raise ValueError("ERR_WITNESS_KEY_NOT_ASCII_STRING")
            _check_jcs_integer_shape(item)
        return
    raise ValueError(f"ERR_WITNESS_VALUE_TYPE_{type(value).__name__.upper()}")


def canonical_bytes(witness: dict[str, Any]) -> bytes:
    # Integer-only payload with ASCII keys: sorted keys + no whitespace is the
    # RFC 8785 JCS form for this shape (no floats, no non-ASCII strings). The
    # shape is enforced so the stdlib-only shortcut cannot silently diverge
    # (UTF-16 key order, ECMAScript number format); parity is tested in
    # tests/test_jcs_single_source.py.
    _check_jcs_integer_shape(witness)
    return json.dumps(witness, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify(v: int, k: int, t: int, blocks: list[list[int]], claimed: int | None = None) -> dict[str, Any]:
    checks: dict[str, bool] = {}
    errors: list[str] = []
    if not (isinstance(v, int) and isinstance(k, int) and isinstance(t, int) and 0 < t <= k <= v):
        return {"valid": False, "errors": [f"bad parameters v={v} k={k} t={t}"], "checks": {}}

    in_range = all(isinstance(p, int) and not isinstance(p, bool) and 0 <= p < v for b in blocks for p in b)
    checks["points_within_range"] = in_range
    if not in_range:
        errors.append("point outside [0, v) or non-integer")

    sized = all(len(b) == k and len(set(b)) == k for b in blocks)
    checks["block_size_equals_k"] = sized
    if not sized:
        errors.append("block with wrong size or repeated point")

    keys = [tuple(sorted(b)) for b in blocks]
    no_dup = len(set(keys)) == len(keys)
    checks["no_duplicate_block"] = no_dup
    if not no_dup:
        errors.append("duplicate block")

    n_t = math.comb(v, t)
    covered = bytearray(n_t)
    if in_range and sized:
        for key in set(keys):
            for sub in itertools.combinations(key, t):
                covered[subset_rank(sub)] = 1
    missing = n_t - sum(covered)
    checks["every_t_subset_covered"] = in_range and sized and missing == 0
    if missing:
        errors.append(f"{missing} t-subsets uncovered")

    count = len(blocks)
    if claimed is not None:
        checks["block_count_matches_claim"] = claimed == count
        if claimed != count:
            errors.append(f"claimed {claimed} blocks but found {count}")

    valid = all(checks.values())
    lower = schoenheim_bound(v, k, t)
    status = "VALID" if valid else "INVALID"
    if valid and count < lower:
        status = "VERIFIER_INCONSISTENCY"
        valid = not bool(status)
        errors.append(f"valid design below Schoenheim bound {lower}: verifier defect")

    result: dict[str, Any] = {
        "verifier_version": VERIFIER_VERSION,
        "status": status,
        "valid": valid,
        "parameters": {"v": v, "k": k, "t": t},
        "block_count": count,
        "t_subsets_total": n_t,
        "t_subsets_covered": n_t - missing,
        "t_subsets_missing": missing,
        "schoenheim_lower_bound": lower,
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_failed": sum(not c for c in checks.values()),
        "errors": errors,
    }
    if in_range and sized:
        cw = canonical_witness(v, k, t, blocks)
        result["witness_digest"] = "sha256:" + hashlib.sha256(canonical_bytes(cw)).hexdigest()
    return result


def verify_document(doc: dict[str, Any]) -> dict[str, Any]:
    params = doc.get("parameters", doc)
    claimed = None
    obj = doc.get("claimed_objective")
    if isinstance(obj, dict) and isinstance(obj.get("value"), int):
        claimed = obj["value"]
    return verify(int(params["v"]), int(params["k"]), int(params["t"]), doc["blocks"], claimed)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True, help="candidate or witness JSON file")
    args = ap.parse_args()
    with open(args.input, encoding="utf-8") as fh:
        doc = json.load(fh)
    res = verify_document(doc)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
