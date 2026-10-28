#!/usr/bin/env python3
"""
tools/where_we_stand.py — one command, one card, plus optional signed chain log.

    python3 tools/where_we_stand.py                 # T1 view of docs/truth/ledger.json
    python3 tools/where_we_stand.py --tier T3_IRREVERSIBLE --json-out /tmp/wws.json
    python3 tools/where_we_stand.py --append-chain /tmp/chain.jsonl --signing-key-hex <64hex>
    python3 tools/where_we_stand.py --verify-chain /tmp/chain.jsonl --trusted-pubkey-hex <64hex>

Exit code: 0 if the requested tier/chain is valid, 1 if blocked/tampered, 2 on bad input/ledger.
The card is a decision aid computed from re-run checks; it is not an approval.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from typing import Any, Dict, List

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, REPO_ROOT)

from src.jcs_canonicalizer import encode_jcs  # noqa: E402
from src.strict_json_ingress import loads_strict  # noqa: E402
from src.truth_compass import (  # noqa: E402
    GENESIS_PREV_REPORT_CAID,
    TIERS,
    load_ledger,
    render_card,
    sign_report_envelope,
    verify_report_chain,
    where_we_stand,
)


def _read_jsonl_chain(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            item = loads_strict(s)
            if not isinstance(item, dict):
                raise ValueError("ERR_CHAIN_LINE_NOT_OBJECT")
            out.append(item)
    return out


def _append_signed_envelope(chain_path: str, key_hex: str, report) -> int:
    try:
        raw_key = bytes.fromhex(key_hex.strip())
        if len(raw_key) != 32:
            raise ValueError("ERR_SIGNING_KEY_LEN")
        key = Ed25519PrivateKey.from_private_bytes(raw_key)
    except ValueError as exc:
        print(f"CHAIN_ERROR: invalid signing key ({exc})", file=sys.stderr)
        return 2
    pub_hex = key.public_key().public_bytes_raw().hex()
    parent = os.path.dirname(os.path.abspath(chain_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(chain_path, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.seek(0)
            existing: List[Dict[str, Any]] = []
            for line in fh:
                s = line.strip()
                if s:
                    obj = loads_strict(s)
                    if not isinstance(obj, dict):
                        raise ValueError("ERR_CHAIN_LINE_NOT_OBJECT")
                    existing.append(obj)
            if existing:
                ok, reason = verify_report_chain(existing, pub_hex)
                if not ok:
                    print(f"CHAIN_ERROR: existing chain failed verification ({reason})", file=sys.stderr)
                    return 2
                prev_caid = existing[-1]["report_caid"]
            else:
                prev_caid = GENESIS_PREV_REPORT_CAID
            env = sign_report_envelope(report, key, sequence=len(existing) + 1, prev_report_caid=prev_caid)
            fh.seek(0, os.SEEK_END)
            fh.write(encode_jcs(env).decode("utf-8") + "\n")
            fh.flush()
            os.fsync(fh.fileno())
            # Record this head out of band (second host / commit message): only a
            # pinned head lets --verify-chain detect tail truncation.
            print(f"CHAIN_HEAD  sequence={env['sequence']}  envelope_caid={env['envelope_caid']}")
        except (OSError, ValueError) as exc:
            print(f"CHAIN_ERROR: {exc}", file=sys.stderr)
            return 2
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--ledger", default=os.path.join(REPO_ROOT, "docs", "truth", "ledger.json"))
    ap.add_argument("--tier", default=TIERS[0], choices=TIERS)
    ap.add_argument("--json-out", default=None)
    ap.add_argument("--append-chain", default=None, help="Append Ed25519-signed envelope to JSONL chain")
    ap.add_argument("--signing-key-hex", default=os.environ.get("AEIB_TRUTH_SIGNING_KEY_HEX"))
    ap.add_argument("--verify-chain", default=None, help="Verify an existing JSONL signed report chain and exit")
    ap.add_argument("--trusted-pubkey-hex", default=None, help="Pinned Ed25519 public key hex for --verify-chain")
    ap.add_argument("--expect-head", default=None, help="Out-of-band pinned newest envelope_caid (detects truncation)")
    ap.add_argument("--min-entries", type=int, default=1, help="Out-of-band pinned minimum chain length")
    args = ap.parse_args(argv)

    if args.verify_chain:
        if not args.trusted_pubkey_hex:
            print("CHAIN_ERROR: --trusted-pubkey-hex is required with --verify-chain", file=sys.stderr)
            return 2
        try:
            envelopes = _read_jsonl_chain(args.verify_chain)
        except (OSError, ValueError) as exc:
            print(f"CHAIN_ERROR: {exc}", file=sys.stderr)
            return 2
        ok, reason = verify_report_chain(envelopes, args.trusted_pubkey_hex,
                                         expected_head_envelope_caid=args.expect_head,
                                         min_entries=args.min_entries)
        pinned = "yes" if args.expect_head else "no (tail truncation not detectable)"
        print(f"CHAIN_VERIFY  ok={ok}  entries={len(envelopes)}  reason={reason}  head_pinned={pinned}")
        return 0 if ok else 1

    try:
        with open(args.ledger, "r", encoding="utf-8") as fh:
            claims = load_ledger(fh.read())
    except (OSError, ValueError) as exc:
        print(f"LEDGER_ERROR: {exc}", file=sys.stderr)
        return 2
    report = where_we_stand(claims, REPO_ROOT, args.tier)
    print(render_card(report, claims))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"allowed": report.allowed, "reason": report.reason, "report_caid": report.report_caid,
                       "results": [[r.claim_id, r.status, r.detail] for r in report.results],
                       "tier": report.tier, "tree_state": report.tree_state}, fh, indent=2, sort_keys=True)
    if args.append_chain:
        if not args.signing_key_hex:
            print("CHAIN_ERROR: --signing-key-hex is required with --append-chain", file=sys.stderr)
            return 2
        rc = _append_signed_envelope(args.append_chain, args.signing_key_hex, report)
        if rc != 0:
            return rc
    return 0 if report.allowed else 1


if __name__ == "__main__":
    sys.exit(main())
