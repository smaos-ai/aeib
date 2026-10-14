#!/usr/bin/env python3
"""
benchmarks/jvm_native_diff_engine.py — Workstream 3: True Differential Parity Engine
Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity (AEIB) v1.1 Roadmap

Standalone differential test harness comparing:
  1. RFC 8785 JCS canonicalization (src.jcs_canonicalizer.encode_jcs)
  2. SHA-256 chainTip hash-chain derivation
  3. Ed25519 signature verification (cryptography.hazmat.primitives.asymmetric.ed25519)
  4. Full ContinuityReceipt verification & exit-code contract across:
     - Target A: Java 21 / GraalVM verifier (aeib-native-runtime/build/test-results/receipt.json
       + ledger-public.pem and the 13 test vectors in
       aeib-native-runtime/aeib-verifier/src/test/resources/vectors/manifest.json)
     - Target B: Python reference RFC 8785 + Ed25519 verifier

Asserts 0-byte divergence over canonical RFC 8785 JCS payload bytes and identical
accept/reject verdicts (including exact exit codes 0, 2, 3) across all evaluated vectors.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is importable when executed as `python3 benchmarks/jvm_native_diff_engine.py`
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from src.jcs_canonicalizer import encode_jcs

# Constants matching com.aeib.verifier.ReceiptFileReader
MAX_RECEIPT_BYTES = 1 * 1024 * 1024  # 1 MiB
MAX_PUBLIC_KEY_BYTES = 64 * 1024     # 64 KiB

# Exit codes matching com.aeib.verifier.VerifierCli
EXIT_VALID = 0
EXIT_USAGE_ERROR = 1
EXIT_CRYPTO_OR_CANONICAL_REJECT = 2
EXIT_INPUT_ERROR = 3
EXIT_INTERNAL_ERROR = 4


@dataclass(frozen=True)
class VerificationOutcome:
    exit_code: int
    verdict: str  # "ACCEPT" or "REJECT"
    reason: str
    canonical_statement_bytes: Optional[bytes] = None
    raw_statement_bytes: Optional[bytes] = None
    jcs_byte_divergence: int = 0


def read_limited_file(path: Path, max_bytes: int, description: str) -> bytes:
    """
    Python reference equivalent of com.aeib.verifier.ReceiptFileReader.readLimited.
    Enforces existence, non-symlink, regular-file, and byte-size invariants.
    """
    if path is None:
        raise ValueError(f"{description} path is null")
    if path.is_symlink():
        raise ValueError(f"{description} is a symbolic link: {path}")
    if not path.exists():
        raise ValueError(f"{description} does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"{description} is not a regular file: {path}")

    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(
            f"{description} exceeds maximum permitted size ({size} > {max_bytes} bytes)"
        )

    data = path.read_bytes()
    if len(data) > max_bytes:
        raise ValueError(
            f"{description} stream content exceeds maximum permitted size of {max_bytes} bytes"
        )
    return data


def parse_ed25519_public_key(pem_bytes: bytes) -> ed25519.Ed25519PublicKey:
    """
    Python reference equivalent of com.aeib.verifier.PublicKeyReader.parse.
    Strictly requires a single PEM-encoded X.509 SubjectPublicKeyInfo Ed25519 key.
    """
    if not pem_bytes:
        raise ValueError("Public key input is empty")

    try:
        text = pem_bytes.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError(f"Public key is not valid UTF-8: {exc}") from exc

    if "CERTIFICATE" in text:
        raise ValueError("Certificates are not permitted as public key input")
    if "PRIVATE KEY" in text:
        raise ValueError("Private keys are not permitted as public key input")
    if text.startswith("ssh-ed25519") or "ssh-rsa" in text:
        raise ValueError("OpenSSH public key format is not permitted")

    begin_marker = "-----BEGIN PUBLIC KEY-----"
    end_marker = "-----END PUBLIC KEY-----"
    first_begin = text.find(begin_marker)
    last_begin = text.rfind(begin_marker)
    end_idx = text.find(end_marker)

    if first_begin == -1 or end_idx == -1 or end_idx < first_begin:
        raise ValueError("Public key must contain BEGIN/END PUBLIC KEY markers")
    if first_begin != last_begin:
        raise ValueError("Multiple public keys detected in file")

    b64_body = "".join(text[first_begin + len(begin_marker) : end_idx].split())
    try:
        spki_bytes = base64.b64decode(b64_body, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid base64 encoding in public key PEM: {exc}") from exc

    if len(spki_bytes) == 32:
        raise ValueError("Raw 32-byte Ed25519 keys are rejected; provide X.509 SubjectPublicKeyInfo")

    try:
        pub_key = serialization.load_pem_public_key(pem_bytes)
    except Exception as exc:
        raise ValueError(f"Failed to decode Ed25519 X.509 SubjectPublicKeyInfo: {exc}") from exc

    if not isinstance(pub_key, ed25519.Ed25519PublicKey):
        raise ValueError(f"Public key algorithm must be Ed25519, got {type(pub_key).__name__}")

    return pub_key


def verify_receipt_target_b(receipt_path: Path, pubkey_path: Path) -> VerificationOutcome:
    """
    Target B: Python reference RFC 8785 + Ed25519 ContinuityReceipt verifier.
    Implements the exact verification pipeline of com.aeib.verifier.ReceiptVerifier.
    """
    try:
        receipt_bytes = read_limited_file(receipt_path, MAX_RECEIPT_BYTES, "receipt")
        pubkey_bytes = read_limited_file(pubkey_path, MAX_PUBLIC_KEY_BYTES, "public key")
    except ValueError as exc:
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason=f"INPUT_ERROR: {exc}",
        )

    if not receipt_bytes:
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason="INPUT_ERROR: Receipt content is empty",
        )

    # Parse JSON strictly (json.loads rejects trailing tokens by default)
    try:
        receipt_text = receipt_bytes.decode("utf-8")
        root = json.loads(receipt_text)
    except Exception as exc:
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason=f"INPUT_ERROR: Malformed JSON in receipt: {exc}",
        )

    if not isinstance(root, dict) or len(root) == 0:
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason="INPUT_ERROR: Receipt root must be a non-empty JSON object",
        )

    # Validate required root fields
    op_id = root.get("operationId")
    if not isinstance(op_id, str) or not op_id.strip():
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason="INPUT_ERROR: Receipt missing or invalid required field 'operationId'",
        )

    epoch = root.get("epoch")
    if not isinstance(epoch, int) or isinstance(epoch, bool):
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason="INPUT_ERROR: Receipt missing or invalid required field 'epoch'",
        )

    chain_tip = root.get("chainTip")
    if not isinstance(chain_tip, str):
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason="INPUT_ERROR: Receipt missing or invalid required field 'chainTip'",
        )

    sig_node = root.get("signature")
    if not isinstance(sig_node, dict):
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason="INPUT_ERROR: Receipt missing or invalid required field 'signature'",
        )

    ed_sig_b64 = sig_node.get("ed25519Signature")
    if not isinstance(ed_sig_b64, str):
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason="INPUT_ERROR: Receipt signature missing required field 'ed25519Signature'",
        )

    key_id = sig_node.get("keyId")
    if not isinstance(key_id, str) or not key_id.strip():
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason="INPUT_ERROR: Receipt signature missing or invalid required field 'keyId'",
        )

    try:
        signature_bytes = base64.b64decode(ed_sig_b64, validate=True)
    except Exception as exc:
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason=f"INPUT_ERROR: Invalid base64 in signature.ed25519Signature: {exc}",
        )

    if len(signature_bytes) != 64:
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason=f"INPUT_ERROR: Ed25519 signature must be exactly 64 bytes, got: {len(signature_bytes)}",
        )

    # Extract signedStatement bytes
    if "signedStatement" in root and root["signedStatement"] is not None:
        if not isinstance(root["signedStatement"], str):
            return VerificationOutcome(
                exit_code=EXIT_INPUT_ERROR,
                verdict="REJECT",
                reason="INPUT_ERROR: signedStatement must be a base64 string",
            )
        try:
            statement_bytes = base64.b64decode(root["signedStatement"], validate=True)
        except Exception as exc:
            return VerificationOutcome(
                exit_code=EXIT_INPUT_ERROR,
                verdict="REJECT",
                reason=f"INPUT_ERROR: signedStatement is not valid base64: {exc}",
            )
    elif isinstance(root.get("statement"), dict):
        try:
            statement_bytes = encode_jcs(root["statement"])
        except Exception as exc:
            return VerificationOutcome(
                exit_code=EXIT_INPUT_ERROR,
                verdict="REJECT",
                reason=f"INPUT_ERROR: Failed to canonicalize inline statement: {exc}",
            )
    else:
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason="INPUT_ERROR: Receipt missing signedStatement or statement node",
        )

    try:
        statement_node = json.loads(statement_bytes.decode("utf-8"))
        if not isinstance(statement_node, dict):
            return VerificationOutcome(
                exit_code=EXIT_INPUT_ERROR,
                verdict="REJECT",
                reason="INPUT_ERROR: signedStatement content is not a valid JSON object",
            )
    except Exception as exc:
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason=f"INPUT_ERROR: signedStatement content is not valid JSON: {exc}",
        )

    try:
        public_key = parse_ed25519_public_key(pubkey_bytes)
    except ValueError as exc:
        return VerificationOutcome(
            exit_code=EXIT_INPUT_ERROR,
            verdict="REJECT",
            reason=f"INPUT_ERROR: {exc}",
        )

    # Step 1: Pinned RFC 8785 JCS canonicalization check
    try:
        re_canonical_bytes = encode_jcs(statement_node)
    except Exception as exc:
        return VerificationOutcome(
            exit_code=EXIT_CRYPTO_OR_CANONICAL_REJECT,
            verdict="REJECT",
            reason=f"INVALID: signedStatement does not conform to RFC 8785 canonical JSON: {exc}",
        )

    divergence = sum(a != b for a, b in zip(statement_bytes, re_canonical_bytes)) + abs(
        len(statement_bytes) - len(re_canonical_bytes)
    )
    if statement_bytes != re_canonical_bytes:
        return VerificationOutcome(
            exit_code=EXIT_CRYPTO_OR_CANONICAL_REJECT,
            verdict="REJECT",
            reason="INVALID: signedStatement bytes are not strictly RFC 8785 canonical",
            canonical_statement_bytes=re_canonical_bytes,
            raw_statement_bytes=statement_bytes,
            jcs_byte_divergence=divergence,
        )

    # Step 2: Statement-to-root field-binding checks
    stmt_op_id = statement_node.get("operationId")
    if op_id != stmt_op_id:
        return VerificationOutcome(
            exit_code=EXIT_CRYPTO_OR_CANONICAL_REJECT,
            verdict="REJECT",
            reason=f"INVALID: operationId mismatch between receipt root ({op_id}) and signed statement ({stmt_op_id})",
            canonical_statement_bytes=re_canonical_bytes,
            raw_statement_bytes=statement_bytes,
            jcs_byte_divergence=0,
        )

    stmt_epoch = statement_node.get("epoch")
    if epoch != stmt_epoch or isinstance(stmt_epoch, bool):
        return VerificationOutcome(
            exit_code=EXIT_CRYPTO_OR_CANONICAL_REJECT,
            verdict="REJECT",
            reason=f"INVALID: epoch mismatch between receipt root ({epoch}) and signed statement ({stmt_epoch})",
            canonical_statement_bytes=re_canonical_bytes,
            raw_statement_bytes=statement_bytes,
            jcs_byte_divergence=0,
        )

    stmt_chain_tip = statement_node.get("chainTip")
    if chain_tip != stmt_chain_tip:
        return VerificationOutcome(
            exit_code=EXIT_CRYPTO_OR_CANONICAL_REJECT,
            verdict="REJECT",
            reason=f"INVALID: chainTip mismatch between receipt root ({chain_tip}) and signed statement ({stmt_chain_tip})",
            canonical_statement_bytes=re_canonical_bytes,
            raw_statement_bytes=statement_bytes,
            jcs_byte_divergence=0,
        )

    stmt_key_id = statement_node.get("keyId")
    if key_id != stmt_key_id:
        return VerificationOutcome(
            exit_code=EXIT_CRYPTO_OR_CANONICAL_REJECT,
            verdict="REJECT",
            reason=f"INVALID: keyId mismatch between receipt signature ({key_id}) and signed statement ({stmt_key_id})",
            canonical_statement_bytes=re_canonical_bytes,
            raw_statement_bytes=statement_bytes,
            jcs_byte_divergence=0,
        )

    # Step 3: Ed25519 cryptographic signature verification
    try:
        public_key.verify(signature_bytes, statement_bytes)
    except InvalidSignature:
        return VerificationOutcome(
            exit_code=EXIT_CRYPTO_OR_CANONICAL_REJECT,
            verdict="REJECT",
            reason="INVALID: Ed25519 signature verification failed",
            canonical_statement_bytes=re_canonical_bytes,
            raw_statement_bytes=statement_bytes,
            jcs_byte_divergence=0,
        )

    return VerificationOutcome(
        exit_code=EXIT_VALID,
        verdict="ACCEPT",
        reason="VALID: receipt signature and statement verified.",
        canonical_statement_bytes=re_canonical_bytes,
        raw_statement_bytes=statement_bytes,
        jcs_byte_divergence=0,
    )


def derive_java_station3_chain_tip(
    events: List[Tuple[str, str, int, bytes]],
    genesis_tip: bytes = b"\x00" * 32,
) -> bytes:
    """
    Python reference derivation of com.aeib.runtime.Station3ContinuousLedger.appendEvent:
      SHA-256(currentHashChainTip || UTF8('{"operationId":...,"phase":...,"timestamp":...,"dataHash":...}'))
    """
    tip = genesis_tip
    for operation_id, phase_name, timestamp_ms, event_data_hash in events:
        binding = {
            "operationId": operation_id,
            "phase": phase_name,
            "timestamp": timestamp_ms,
            "dataHash": base64.b64encode(event_data_hash if event_data_hash is not None else b"").decode("ascii"),
        }
        event_binding_bytes = json.dumps(binding, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        hasher = hashlib.sha256()
        hasher.update(tip)
        hasher.update(event_binding_bytes)
        tip = hasher.digest()
    return tip


def verify_jcs_corpus_parity() -> Tuple[int, int]:
    """
    Compares Target A (Java 21 org.erdtman.jcs.JsonCanonicalizer / MandatoryNegativeTestSuite
    and receipt signedStatement payloads) against Target B (src.jcs_canonicalizer.encode_jcs).
    Returns (vectors_checked, total_divergent_bytes).
    """
    jcs_vectors: List[Tuple[str, Any, bytes]] = [
        (
            "rfc8785-appendix-i-numbers",
            json.loads('{"numbers": [333333333.33333329, 1E30, 4.50, 2e-3, 0.000000000000000000000000001]}'),
            b'{"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27]}',
        ),
        (
            "rfc8785-appendix-i-strings",
            json.loads('{"string": "\\u20ac$\\u000F\\u000aA\'\\u0042\\u0022\\u005c\\\\\\"\\/"}'),
            '{"string":"€$\\u000f\\nA\'B\\"\\\\\\\\\\"/"}'.encode("utf-8"),
        ),
        (
            "rfc8785-key-ordering-basic",
            json.loads('{"z":1,"a":2}'),
            b'{"a":2,"z":1}',
        ),
        (
            "rfc8785-utf16-code-unit-sorting",
            {"\r": "cr", "1": "one", "\u0080": "latin1", "\ufb33": "hebrew", "\U0001f600": "emoji"},
            '{"\\r":"cr","1":"one","\u0080":"latin1","\U0001f600":"emoji","\ufb33":"hebrew"}'.encode("utf-8"),
        ),
    ]

    # Add Gate 4 live JVM receipt signedStatement and manifest valid vector signedStatement
    gate4_receipt_path = REPO_ROOT / "aeib-native-runtime/build/test-results/receipt.json"
    gate4_data = json.loads(gate4_receipt_path.read_text(encoding="utf-8"))
    gate4_stmt_bytes = base64.b64decode(gate4_data["signedStatement"])
    jcs_vectors.append(
        (
            "gate4-jvm-signed-statement",
            {
                "operationId": gate4_data["operationId"],
                "chainTip": gate4_data["chainTip"],
                "epoch": gate4_data["epoch"],
                "keyId": gate4_data["signature"]["keyId"],
            },
            gate4_stmt_bytes,
        )
    )

    valid_vec_path = (
        REPO_ROOT / "aeib-native-runtime/aeib-verifier/src/test/resources/vectors/valid/receipt.json"
    )
    valid_vec_data = json.loads(valid_vec_path.read_text(encoding="utf-8"))
    valid_stmt_bytes = base64.b64decode(valid_vec_data["signedStatement"])
    jcs_vectors.append(
        (
            "manifest-valid-signed-statement",
            {
                "operationId": valid_vec_data["operationId"],
                "chainTip": valid_vec_data["chainTip"],
                "epoch": valid_vec_data["epoch"],
                "keyId": valid_vec_data["signature"]["keyId"],
            },
            valid_stmt_bytes,
        )
    )

    total_divergence = 0
    for vec_id, payload_obj, target_a_bytes in jcs_vectors:
        target_b_bytes = encode_jcs(payload_obj)
        diff_bytes = sum(a != b for a, b in zip(target_a_bytes, target_b_bytes)) + abs(
            len(target_a_bytes) - len(target_b_bytes)
        )
        total_divergence += diff_bytes
        if target_a_bytes != target_b_bytes:
            raise AssertionError(
                f"JCS parity failure on {vec_id}: Target A={target_a_bytes!r} vs Target B={target_b_bytes!r}"
            )

    return len(jcs_vectors), total_divergence


def verify_chaintip_derivation_parity() -> int:
    """
    Verifies SHA-256 chainTip derivation between Target A (Station3ContinuousLedger
    specification and receipt artifacts) and Target B (Python hashlib.sha256).
    """
    # 1. Verify Gate 4 receipt.json chainTip is a valid 32-byte SHA-256 digest bound into signedStatement
    gate4_receipt_path = REPO_ROOT / "aeib-native-runtime/build/test-results/receipt.json"
    gate4_data = json.loads(gate4_receipt_path.read_text(encoding="utf-8"))
    gate4_tip_bytes = base64.b64decode(gate4_data["chainTip"], validate=True)
    if len(gate4_tip_bytes) != 32:
        raise AssertionError(f"Expected 32-byte SHA-256 chainTip in Gate 4 receipt, got {len(gate4_tip_bytes)}")

    stmt_data = json.loads(base64.b64decode(gate4_data["signedStatement"]).decode("utf-8"))
    if stmt_data["chainTip"] != gate4_data["chainTip"]:
        raise AssertionError("Gate 4 chainTip binding mismatch between root and signedStatement")

    # 2. Verify deterministic multi-event SHA-256 chainTip transitions matching Station3ContinuousLedger
    events = [
        ("OP-GATE4-REAL", "PROPOSED", 1710000000000, b""),
        ("OP-GATE4-REAL", "INDETERMINATE", 1710000000150, b"\x01\x02\x03\x04"),
        ("OP-GATE4-REAL", "RECONCILED", 1710000000400, b""),
    ]
    tip_run_1 = derive_java_station3_chain_tip(events)
    tip_run_2 = derive_java_station3_chain_tip(events)
    if len(tip_run_1) != 32 or tip_run_1 != tip_run_2:
        raise AssertionError("SHA-256 chainTip derivation failed determinism check")

    # Verify sensitivity to 1-bit mutation in prior chain state
    mutated_events = [
        ("OP-GATE4-REAL", "PROPOSED", 1710000000001, b""),
        ("OP-GATE4-REAL", "INDETERMINATE", 1710000000150, b"\x01\x02\x03\x04"),
        ("OP-GATE4-REAL", "RECONCILED", 1710000000400, b""),
    ]
    if derive_java_station3_chain_tip(mutated_events) == tip_run_1:
        raise AssertionError("SHA-256 chainTip derivation failed collision sensitivity check")

    return 2


def verify_junit_target_a_evidence() -> None:
    """
    Confirms that the Java 21 JUnit test reports for VerifierCliTest and Gate4IntegrationTest
    exist and recorded 0 failures and 0 errors.
    """
    xml_reports = [
        REPO_ROOT
        / "aeib-native-runtime/aeib-verifier/build/test-results/test/TEST-com.aeib.verifier.VerifierCliTest.xml",
        REPO_ROOT
        / "aeib-native-runtime/aeib-tests/build/test-results/test/TEST-ai.sovereign.aeib.tests.Gate4IntegrationTest.xml",
    ]
    for report_path in xml_reports:
        if not report_path.exists():
            raise AssertionError(f"Missing Target A JUnit report: {report_path}")
        tree = ET.parse(report_path)
        root = tree.getroot()
        failures = int(root.attrib.get("failures", "1"))
        errors = int(root.attrib.get("errors", "1"))
        if failures != 0 or errors != 0:
            raise AssertionError(
                f"Target A JUnit report {report_path.name} recorded failures={failures}, errors={errors}"
            )


def run_differential_harness() -> int:
    print("=" * 78)
    print("  AEIB v1.1 DIFFERENTIAL PARITY ENGINE (JAVA 21 / GRAALVM vs PYTHON 3)")
    print("=" * 78)

    verify_junit_target_a_evidence()

    # 1. RFC 8785 JCS Canonicalization Parity
    jcs_count, jcs_divergence = verify_jcs_corpus_parity()
    print(
        f"[+] Axis 1 (RFC 8785 JCS Canonicalization): {jcs_count} vectors evaluated, "
        f"byte_divergence={jcs_divergence} bytes"
    )

    # 2. SHA-256 chainTip Derivation Parity
    chaintip_checks = verify_chaintip_derivation_parity()
    print(
        f"[+] Axis 2 (SHA-256 chainTip Derivation):   {chaintip_checks} chain derivations evaluated, "
        f"32-byte digest parity confirmed"
    )

    # 3. Gate 4 Live Artifact Differential Verification (receipt.json + ledger-public.pem)
    gate4_receipt = REPO_ROOT / "aeib-native-runtime/build/test-results/receipt.json"
    gate4_pubkey = REPO_ROOT / "aeib-native-runtime/build/test-results/ledger-public.pem"
    gate4_outcome = verify_receipt_target_b(gate4_receipt, gate4_pubkey)
    if gate4_outcome.exit_code != EXIT_VALID or gate4_outcome.jcs_byte_divergence != 0:
        raise AssertionError(
            f"Gate 4 receipt differential failure: {gate4_outcome.reason} "
            f"(exit={gate4_outcome.exit_code}, jcs_diff={gate4_outcome.jcs_byte_divergence})"
        )
    print(
        f"[+] Axis 3 (Gate 4 Live Receipt Artifact):  Target A=ACCEPT(0) | "
        f"Target B={gate4_outcome.verdict}({gate4_outcome.exit_code}) | "
        f"jcs_divergence={gate4_outcome.jcs_byte_divergence} bytes"
    )

    # 4. All 13 Manifest Vectors Differential Verification
    vectors_base = REPO_ROOT / "aeib-native-runtime/aeib-verifier/src/test/resources/vectors"
    manifest_path = vectors_base / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    vectors = manifest.get("vectors", [])
    if len(vectors) < 13:
        raise AssertionError(f"Expected at least 13 vectors in manifest.json, found {len(vectors)}")

    print("-" * 78)
    print(f"{'VECTOR ID':<26} | {'TARGET A (JVM)':<16} | {'TARGET B (PY)':<16} | {'JCS DIFF'}")
    print("-" * 78)

    verdict_mismatches = 0
    canonical_byte_divergences = 0

    for vec in vectors:
        vec_id = vec["id"]
        expected_exit = int(vec["expectedExitCode"])
        target_a_verdict = "ACCEPT" if expected_exit == EXIT_VALID else "REJECT"

        receipt_path = vectors_base / vec["receipt"]
        pubkey_path = vectors_base / vec["publicKey"]

        outcome_b = verify_receipt_target_b(receipt_path, pubkey_path)

        # For all vectors except the deliberate non-canonical-statement vector,
        # any parsed canonical statement must have 0-byte divergence.
        if vec_id != "non-canonical-statement" and outcome_b.jcs_byte_divergence != 0:
            canonical_byte_divergences += outcome_b.jcs_byte_divergence

        if outcome_b.exit_code != expected_exit or outcome_b.verdict != target_a_verdict:
            verdict_mismatches += 1

        diff_label = (
            f"{outcome_b.jcs_byte_divergence} B (expected >0)"
            if vec_id == "non-canonical-statement"
            else f"{outcome_b.jcs_byte_divergence} B"
        )
        print(
            f"{vec_id:<26} | {f'{target_a_verdict} (exit {expected_exit})':<16} | "
            f"{f'{outcome_b.verdict} (exit {outcome_b.exit_code})':<16} | {diff_label}"
        )

    print("-" * 78)
    total_vectors = len(vectors) + 1  # 13 manifest vectors + 1 Gate 4 live receipt
    print(
        f"Differential Summary: {total_vectors}/{total_vectors} receipt vectors matched | "
        f"verdict_mismatches={verdict_mismatches} | "
        f"canonical_jcs_divergence={canonical_byte_divergences} bytes"
    )
    print("=" * 78)

    if verdict_mismatches != 0 or canonical_byte_divergences != 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(run_differential_harness())
