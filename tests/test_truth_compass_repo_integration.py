#!/usr/bin/env python3
"""
tests/test_truth_compass_repo_integration.py — checks that need repo files
outside src/ and tests/ (docs/truth/ledger.json, tools/where_we_stand.py,
TRUTH_MANIFESTO.md). Kept separate because tools/mutation_adequacy_gate.py
copies only src/ and tests/ into its shadow root.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from src.truth_compass import load_ledger

REPO = Path(__file__).resolve().parent.parent


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_repo_ledger_loads() -> None:
    claims = load_ledger((REPO / "docs" / "truth" / "ledger.json").read_text())
    assert len(claims) >= 5
    assert any(c.evidence is None for c in claims) and any(c.evidence is not None for c in claims)


def test_cli_exit_codes(tmp_path: Path) -> None:
    manifesto = REPO / "TRUTH_MANIFESTO.md"
    ledger = {"claims": [
        {"claim_id": "m", "statement": "manifesto pinned", "falsifier": "hash differs", "safety_critical": True,
         "entailment": "byte-identical file",
         "evidence": {"kind": "FILE_SHA256", "targets": ["TRUTH_MANIFESTO.md"], "expected_sha256": _sha(manifesto)}},
        {"claim_id": "a", "statement": "assumed thing", "falsifier": "x", "safety_critical": False,
         "declared_status": "ASSUMED"},
    ]}
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps(ledger))
    cli = [sys.executable, str(REPO / "tools" / "where_we_stand.py"), "--ledger", str(path)]
    out = tmp_path / "out.json"
    r1 = subprocess.run([*cli, "--json-out", str(out)], capture_output=True, text=True, timeout=60)
    assert r1.returncode == 0 and "WHERE WE STAND" in r1.stdout
    assert json.loads(out.read_text())["reason"] == "OK_T1"
    r3 = subprocess.run([*cli, "--tier", "T3_IRREVERSIBLE"], capture_output=True, text=True, timeout=60)
    assert r3.returncode == 1 and "HALT_UNACCEPTED_RESIDUAL_RISK:a" in r3.stdout
    path.write_text(json.dumps({"claims": [{"claim_id": "x", "statement": "s", "falsifier": "f",
                                            "safety_critical": True, "declared_status": "VERIFIED"}]}))
    rb = subprocess.run(cli, capture_output=True, text=True, timeout=60)
    assert rb.returncode == 2 and "ERR_STATUS_WITHOUT_CHECK" in rb.stderr


def test_cli_append_and_verify_chain(tmp_path: Path) -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    key = Ed25519PrivateKey.generate()
    priv_hex = key.private_bytes_raw().hex()
    pub_hex = key.public_key().public_bytes_raw().hex()
    manifesto = REPO / "TRUTH_MANIFESTO.md"
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json.dumps({"claims": [
        {"claim_id": "m", "statement": "manifesto pinned", "falsifier": "hash differs", "safety_critical": True,
         "entailment": "byte-identical file",
         "evidence": {"kind": "FILE_SHA256", "targets": ["TRUTH_MANIFESTO.md"], "expected_sha256": _sha(manifesto)}},
    ]}))
    chain_path = tmp_path / "chain.jsonl"
    cli = [sys.executable, str(REPO / "tools" / "where_we_stand.py"), "--ledger", str(ledger_path)]

    # Append entry 1 (T1) and entry 2 (T2)
    r1 = subprocess.run([*cli, "--append-chain", str(chain_path), "--signing-key-hex", priv_hex],
                        capture_output=True, text=True, timeout=60)
    assert r1.returncode == 0 and "CHAIN_HEAD  sequence=1  envelope_caid=sha256:" in r1.stdout
    head1 = r1.stdout.split("envelope_caid=")[-1].split()[0]
    r2 = subprocess.run([*cli, "--tier", "T2_STAGING", "--append-chain", str(chain_path), "--signing-key-hex", priv_hex],
                        capture_output=True, text=True, timeout=60)
    assert r2.returncode == 0
    head2 = r2.stdout.split("envelope_caid=")[-1].split()[0]
    assert head2 != head1

    # Verify chain of 2 entries (unpinned, then pinned to the real head)
    rv = subprocess.run([*cli, "--verify-chain", str(chain_path), "--trusted-pubkey-hex", pub_hex],
                        capture_output=True, text=True, timeout=60)
    assert rv.returncode == 0 and "ok=True  entries=2  reason=OK_REPORT_CHAIN_VERIFIED" in rv.stdout
    assert "head_pinned=no" in rv.stdout
    rvp = subprocess.run([*cli, "--verify-chain", str(chain_path), "--trusted-pubkey-hex", pub_hex,
                          "--expect-head", head2, "--min-entries", "2"],
                         capture_output=True, text=True, timeout=60)
    assert rvp.returncode == 0 and "head_pinned=yes" in rvp.stdout

    # Tail truncation (drop newest line) is caught only with the pinned head
    truncated = tmp_path / "truncated.jsonl"
    truncated.write_text(chain_path.read_text().splitlines()[0] + "\n")
    rt = subprocess.run([*cli, "--verify-chain", str(truncated), "--trusted-pubkey-hex", pub_hex,
                         "--expect-head", head2],
                        capture_output=True, text=True, timeout=60)
    assert rt.returncode == 1 and "HALT_CHAIN_HEAD_MISMATCH_TRUNCATED_OR_FORKED" in rt.stdout
    rm = subprocess.run([*cli, "--verify-chain", str(truncated), "--trusted-pubkey-hex", pub_hex,
                         "--min-entries", "2"],
                        capture_output=True, text=True, timeout=60)
    assert rm.returncode == 1 and "HALT_CHAIN_SHORTER_THAN_PINNED:1<2" in rm.stdout

    # Wrong key fails verification with exit code 1
    other_pub = Ed25519PrivateKey.generate().public_key().public_bytes_raw().hex()
    rv_bad = subprocess.run([*cli, "--verify-chain", str(chain_path), "--trusted-pubkey-hex", other_pub],
                            capture_output=True, text=True, timeout=60)
    assert rv_bad.returncode == 1 and "HALT_UNTRUSTED_ISSUER_KEY:1" in rv_bad.stdout

    # Attempting to append with a different key to an existing chain halts with exit code 2
    other_priv = Ed25519PrivateKey.generate().private_bytes_raw().hex()
    r_tamper = subprocess.run([*cli, "--append-chain", str(chain_path), "--signing-key-hex", other_priv],
                              capture_output=True, text=True, timeout=60)
    assert r_tamper.returncode == 2 and "CHAIN_ERROR: existing chain failed verification" in r_tamper.stderr
