#!/usr/bin/env python3
"""
tools/commit_lessons_l22_l25.py — Idempotently Commit Lessons L22–L25 to AGENTS.md

Enforces constitutional governance:
- Lesson L22: Epistemic Status Grounding Invariant (§1)
- Lesson L23: Surviving Mutant Disclosure & Exact Boundary Tests (§6)
- Lesson L24: Statistical Interval Reporting (§6)
- Lesson L25: Execution Plane Competitor Differentiation (§6)

Generates cryptographically signed receipt with RFC 8785 single-source JCS canonicalization
and Ed25519 verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
if str(DEFAULT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_ROOT))

from src.jcs_canonicalizer import encode_jcs
from src.wilson_bps_interval import verify_l22_status_grounding

L22_TEXT = """- **STATUS LABEL GROUNDING (LESSON L22):** Never declare a system "DELIVERED & COMMISSIONED" or "CERTIFIED REGULATORY COMPLIANT" based solely on internal test suites. Use strictly grounded engineering statuses: "INTERNAL PREVIEW COMMISSIONED" (prototype evaluated on local host), "COMPLIANCE EVIDENCE EXPORTER PROTOTYPE" (automated statutory evidence pack generator; not external accredited legal certification), and "READY FOR INTERNAL PREVIEW / PILOT"."""

L23_TEXT = """- **SURVIVING MUTANT DISCLOSURE & EXACT BOUNDARY TESTS (LESSON L23):** If any mutant survives an AST mutation gate, it must be explicitly cited in the run summary with file, line number, operator type, and mathematical reason for survival. When testing rate or basis-point calculations, test exact extreme points (N=1) and non-trivial fractions (e.g. 5/7) rather than loose inequalities (> 0) to prevent integer-division truncations from masking arithmetic mutants."""

L24_TEXT = """- **STATISTICAL INTERVAL REPORTING (LESSON L24):** For any benchmark evaluated on discrete task sets, report conservative Wilson 95% confidence intervals in integer basis points ([low_bps..high_bps]) alongside point estimates. Distinguish task-level from trial-level distributions across multi-repetition runs."""

L25_TEXT = """- **EXECUTION PLANE COMPETITOR DIFFERENTIATION (LESSON L25):** Articulate architectural distinction across execution planes: L7 HTTP proxies (OpenAI, Anthropic, LangChain gateways) inspect textual payloads post-generation but fail to intercept counterfeit in-kernel mutations. AEIB/EO1 operates at the kernel/AST execution boundary intercepting unauthorized file, process, and socket intents before dispatch."""


def commit_lessons_to_agents_md(repo_root: Path = DEFAULT_ROOT) -> Tuple[bool, str]:
    """Idempotently commit Lessons L22-L25 to AGENTS.md."""
    agents_path = repo_root / "AGENTS.md"
    if not agents_path.is_file():
        return (False, f"AGENTS.md not found at {agents_path}")

    content = agents_path.read_text(encoding="utf-8")
    modified = False

    # Check §1 addition (L22)
    if "STATUS LABEL GROUNDING (LESSON L22)" not in content:
        # Insert after THREE-TIER CLAIM CLASSIFICATION bullet in section 1
        sec1_target = "Never claim biometric non-repudiation proves human understanding; state: \"The Secure Enclave signature binds the canonical proposal to a device-unlock event and signing key.\""
        if sec1_target in content:
            replacement = sec1_target + "\n" + L22_TEXT
            content = content.replace(sec1_target, replacement, 1)
            modified = True
        else:
            # Fallback insertion before Section 2
            sec2_header = "## 2. ZERO-MOCK & CRYPTOGRAPHIC PURITY"
            if sec2_header in content:
                content = content.replace(sec2_header, L22_TEXT + "\n\n" + sec2_header, 1)
                modified = True

    # Check §6 additions (L23, L24, L25)
    sec6_additions = []
    if "SURVIVING MUTANT DISCLOSURE & EXACT BOUNDARY TESTS (LESSON L23)" not in content:
        sec6_additions.append(L23_TEXT)
    if "STATISTICAL INTERVAL REPORTING (LESSON L24)" not in content:
        sec6_additions.append(L24_TEXT)
    if "EXECUTION PLANE COMPETITOR DIFFERENTIATION (LESSON L25)" not in content:
        sec6_additions.append(L25_TEXT)

    if sec6_additions:
        block_to_add = "\n".join(sec6_additions)
        # Append before Section 7 or end of file
        sec7_header = "## 7. PARALLEL AGENT ORCHESTRATION"
        if sec7_header in content:
            content = content.replace(sec7_header, block_to_add + "\n\n" + sec7_header, 1)
            modified = True
        else:
            content = content + "\n\n" + block_to_add
            modified = True

    if modified:
        agents_path.write_text(content, encoding="utf-8")
        return (True, "Committed Lessons L22-L25 to AGENTS.md successfully.")
    else:
        return (False, "AGENTS.md already contains Lessons L22-L25 (idempotent no-op).")


def generate_and_sign_receipt(repo_root: Path = DEFAULT_ROOT) -> Dict[str, Any]:
    """Generate and cryptographically sign the lessons commit receipt."""
    agents_path = repo_root / "AGENTS.md"
    agents_bytes = agents_path.read_bytes()
    agents_sha256 = hashlib.sha256(agents_bytes).hexdigest()

    status_label = "INTERNAL PREVIEW COMMISSIONED"
    is_grounded, ground_msg = verify_l22_status_grounding(status_label)
    if not is_grounded:
        raise ValueError(f"Status label failed epistemic grounding: {ground_msg}")

    signing_key = ed25519.Ed25519PrivateKey.generate()
    pubkey_bytes = signing_key.public_key().public_bytes_raw()
    pubkey_hex = pubkey_bytes.hex()

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload: Dict[str, Any] = {
        "action": "COMMIT_CONSTITUTIONAL_LESSONS",
        "agents_md_sha256": agents_sha256,
        "epistemic_status": status_label,
        "grounding_check": ground_msg,
        "lessons": ["L22", "L23", "L24", "L25"],
        "timestamp_utc": now_iso,
    }

    canonical_bytes = encode_jcs(payload)
    caid = hashlib.sha256(canonical_bytes).hexdigest()
    signature_bytes = signing_key.sign(canonical_bytes)
    signature_hex = signature_bytes.hex()

    receipt: Dict[str, Any] = {
        "caid": caid,
        "canonical_payload_jcs": canonical_bytes.decode("utf-8"),
        "ed25519_public_key_hex": pubkey_hex,
        "payload": payload,
        "signature_hex": signature_hex,
    }

    out_dir = repo_root / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "lessons_l22_l25_receipt.json"
    out_file.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Commit Lessons L22-L25 to AGENTS.md with cryptographic receipt.")
    parser.add_argument("repo_root", nargs="?", default=".", help="Root directory of repository")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    modified, msg = commit_lessons_to_agents_md(root)
    print(f"[*] {msg}")

    receipt = generate_and_sign_receipt(root)
    print(f"[✓] Generated and signed receipt: CAID {receipt['caid'][:16]}... Public Key {receipt['ed25519_public_key_hex'][:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
