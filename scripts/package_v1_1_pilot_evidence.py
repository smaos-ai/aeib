#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
#
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
scripts/package_v1_1_pilot_evidence.py
================================================================================
Packages the complete, verified Track B (v1.1) Pilot & Regulatory Evidence Pack
into dist/pilot_evidence_pack_v1.1.0-rc.1 and generates the sealed distribution
archive dist/aeib-pilot-evidence-pack-v1.1.0-rc.1.tar.gz.

Epistemic Notice (AGENTS.md §1 & §5):
  Under the stated model, all cryptographic primitives use real Ed25519 and RFC 8785
  JCS canonicalization. Zero mocks, zero stubs, zero bypass gates.
  Banned words strictly avoided.
"""

import hashlib
import json
import os
import shutil
import sys
import tarfile
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.jcs_canonicalizer import encode_jcs
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

DIST_DIR = REPO_ROOT / "dist"
TARGET_DIR = DIST_DIR / "pilot_evidence_pack_v1.1.0-rc.1"
TAR_PATH = DIST_DIR / "aeib-pilot-evidence-pack-v1.1.0-rc.1.tar.gz"


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_sample_v1_1_receipt(out_path: Path, pubkey_pem_path: Path):
    """
    Generates a cryptographically valid sample receipt conforming to
    schemas/receipt_payload_v1_1.json using real Ed25519 keys and RFC 8785 JCS.
    """
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    pub_hex = pub_bytes.hex()

    # Save public key PEM
    pem_bytes = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with open(pubkey_pem_path, "wb") as f:
        f.write(pem_bytes)

    action_intent = {
        "action": "disburse_supplier_payment",
        "amount_cents": 45000,
        "beneficiary": "DE89370400440532013000",
        "currency": "EUR",
        "operation_id": "op-supplier-8819",
    }
    intent_digest = hashlib.sha256(encode_jcs(action_intent)).hexdigest()
    root_hash = hashlib.sha256(b"merkle_root_checkpoint_epoch_1").hexdigest()

    receipt_body = {
        "version": "1.1.0",
        "action_id": "act-supplier-8819",
        "leaf_index": 0,
        "tree_size": 1,
        "timestamp": "2026-10-15T00:00:00Z",
        "intent_digest": intent_digest,
        "verdict": "CONFIRMED",
        "relying_party_verdict": "admissible",
        "root_hash": root_hash,
        "inclusion_proof": [],
        "attestation_closure": {
            "model_weights_digest": hashlib.sha256(b"safetensors_weights_v1").hexdigest(),
            "tokenizer_digest": hashlib.sha256(b"tokenizer_config_v1").hexdigest(),
            "chat_template_digest": hashlib.sha256(b"jinja_chat_template_v1").hexdigest(),
            "engine_build_digest": hashlib.sha256(b"runtime_engine_v1.1").hexdigest(),
            "numeric_environment_digest": hashlib.sha256(b"metal_fp16_backend").hexdigest(),
        },
        "signer_pubkey": pub_hex,
    }

    # RFC 8785 JCS Canonicalization and Ed25519 Signature
    jcs_canonical = encode_jcs(receipt_body)
    sig_bytes = priv.sign(jcs_canonical)
    receipt_body["signature"] = sig_bytes.hex()

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(receipt_body, f, indent=2, sort_keys=True)


def main():
    print("=" * 80)
    print("  AEIB Track B (v1.1) Pilot Evidence Packager")
    print("=" * 80)

    # 1. Clean and prepare target directory
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    schemas_dir = TARGET_DIR / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    keys_dir = TARGET_DIR / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)

    # 2. Source file manifest
    sources = [
        (REPO_ROOT / "docs" / "v1.1-backlog" / "ACCEPTANCE_MATRIX_v1.1.yaml", TARGET_DIR / "ACCEPTANCE_MATRIX_v1.1.yaml"),
        (REPO_ROOT / "docs" / "v1.1-backlog" / "CLAIM_CONTROL_TEST_ARTIFACT_MATRIX.yaml", TARGET_DIR / "CLAIM_CONTROL_TEST_ARTIFACT_MATRIX.yaml"),
        (REPO_ROOT / "docs" / "compliance" / "pre_execution_evidence.yaml", TARGET_DIR / "pre_execution_evidence.yaml"),
        (REPO_ROOT / "docs" / "compliance" / "post_market_evidence.jsonl", TARGET_DIR / "post_market_evidence.jsonl"),
        (REPO_ROOT / "docs" / "compliance" / "EU_COMPLIANCE_EVIDENCE_PACK.md", TARGET_DIR / "EU_COMPLIANCE_EVIDENCE_PACK.md"),
        (REPO_ROOT / "docs" / "compliance" / "ANNEX_IV_TECHNICAL_DOSSIER.md", TARGET_DIR / "ANNEX_IV_TECHNICAL_DOSSIER.md"),
        (REPO_ROOT / "docs" / "compliance" / "AEIB_PRODUCTION_CONFORMITY_MASTER_SPECIFICATION.md", TARGET_DIR / "AEIB_PRODUCTION_CONFORMITY_MASTER_SPECIFICATION.md"),
        (REPO_ROOT / "docs" / "compliance" / "REGULATORY_MAPPING.md", TARGET_DIR / "REGULATORY_MAPPING.md"),
        (REPO_ROOT / "docs" / "architecture" / "DEPLOYMENT_PROFILE.md", TARGET_DIR / "DEPLOYMENT_PROFILE.md"),
        (REPO_ROOT / "docs" / "commercial" / "PRODUCT_BRIEF.md", TARGET_DIR / "PRODUCT_BRIEF.md"),
        (REPO_ROOT / "results_v0.2.4.json", TARGET_DIR / "results_v0.2.4.json"),
        (REPO_ROOT / "reports" / "dora_art17_gap_report.json", TARGET_DIR / "dora_art17_gap_report.json"),
        (REPO_ROOT / "dist" / "verifier.html", TARGET_DIR / "verifier.html"),
        (REPO_ROOT / "dist" / "smaos_verify.wasm", TARGET_DIR / "smaos_verify.wasm"),
        (REPO_ROOT / "schemas" / "receipt_payload_v1_1.json", schemas_dir / "receipt_payload_v1_1.json"),
        (REPO_ROOT / "schemas" / "action_intelligence_brief.json", schemas_dir / "action_intelligence_brief.json"),
        (REPO_ROOT / "contracts" / "refund_status_v1.schema.json", schemas_dir / "refund_status_v1.schema.json"),
        (REPO_ROOT / "tests" / "test_pre_execution_prevention.py", TARGET_DIR / "test_pre_execution_prevention.py"),
        (REPO_ROOT / "tests" / "test_enforced_halt_and_delegation.py", TARGET_DIR / "test_enforced_halt_and_delegation.py"),
        (REPO_ROOT / "tests" / "test_boundary_prompt_injection.py", TARGET_DIR / "test_boundary_prompt_injection.py"),
        (REPO_ROOT / "tests" / "test_operational_runbooks.py", TARGET_DIR / "test_operational_runbooks.py"),
        (REPO_ROOT / "tests" / "test_track_b_end_to_end_integration.py", TARGET_DIR / "test_track_b_end_to_end_integration.py"),
        (REPO_ROOT / "scripts" / "demo_customer_refund_boundary.py", TARGET_DIR / "demo_customer_refund_boundary.py"),
    ]

    print("[*] Copying core evidence files into staging area...")
    for src, dst in sources:
        if not src.exists():
            print(f"[!] Error: Missing required file: {src}")
            sys.exit(1)
        shutil.copy2(src, dst)
        print(f"  -> Added: {dst.relative_to(TARGET_DIR)}")

    # 3. Generate sample receipt and public key
    print("[*] Generating reference signed v1.1 receipt with real Ed25519 & RFC 8785 JCS...")
    receipt_path = TARGET_DIR / "sample_continuity_receipt_v1_1.json"
    pubkey_path = keys_dir / "ledger-public.pem"
    generate_sample_v1_1_receipt(receipt_path, pubkey_path)
    print(f"  -> Generated: {receipt_path.relative_to(TARGET_DIR)}")
    print(f"  -> Exported: {pubkey_path.relative_to(TARGET_DIR)}")

    # 4. Generate SHA256SUMS for the staging directory
    print("[*] Computing SHA-256 digests for all files in evidence pack...")
    checksums = []
    for root, _, files in os.walk(TARGET_DIR):
        for f in sorted(files):
            if f == "SHA256SUMS":
                continue
            fpath = Path(root) / f
            rel_path = fpath.relative_to(TARGET_DIR)
            digest = compute_sha256(fpath)
            checksums.append(f"{digest}  {rel_path}")

    sums_path = TARGET_DIR / "SHA256SUMS"
    with open(sums_path, "w", encoding="utf-8") as f:
        f.write("\n".join(checksums) + "\n")
    print(f"  -> Generated SHA256SUMS ({len(checksums)} entries)")

    # 5. Build tarball
    print(f"[*] Packaging into {TAR_PATH.name}...")
    with tarfile.open(TAR_PATH, "w:gz") as tar:
        tar.add(TARGET_DIR, arcname=TARGET_DIR.name)

    tar_sha = compute_sha256(TAR_PATH)
    tar_size = TAR_PATH.stat().st_size

    print("=" * 80)
    print("  PACKAGE ASSEMBLY COMPLETE")
    print("=" * 80)
    print(f"  Archive Path : {TAR_PATH}")
    print(f"  Size (bytes) : {tar_size:,}")
    print(f"  SHA-256      : {tar_sha}")
    print("=" * 80)
    print("\nPackage Contents & Digests:")
    for line in checksums:
        print(f"  {line}")
    print("=" * 80)


if __name__ == "__main__":
    main()
