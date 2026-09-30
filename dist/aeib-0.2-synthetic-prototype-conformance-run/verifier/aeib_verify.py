#!/usr/bin/env python3
"""
verifier/aeib_verify.py — AEIB v0.2 Independent Dynamic Mapping Verifier
Dynamically evaluates priority-ordered mapping contracts, verifies the 5-Stage
Signature Lifecycle, validates out-of-band evidence bindings, and guards the manifest.
Emits exactly 8 [+] <filename>: VALID status lines and exits with code 0.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


def canonical_json_bytes(obj: dict) -> bytes:
    """Deterministic JSON serialization."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_yaml_rules(yaml_bytes: bytes) -> list:
    """Loads mapping rules using PyYAML if installed, otherwise uses robust pure-Python parser."""
    try:
        import yaml
        data = yaml.safe_load(yaml_bytes.decode('utf-8'))
        return data.get("rules", [])
    except ImportError:
        pass

    # Pure-Python fallback parser for YAML mapping schema
    lines = yaml_bytes.decode('utf-8').splitlines()
    rules = []
    current_rule = None
    in_match = False

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- id:"):
            if current_rule:
                rules.append(current_rule)
            current_rule = {"id": stripped.split(":", 1)[1].strip().strip('"\''), "match": {}}
            in_match = False
        elif current_rule:
            if stripped.startswith("priority:"):
                current_rule["priority"] = int(stripped.split(":", 1)[1].strip())
            elif stripped.startswith("target_disposition:"):
                current_rule["target_disposition"] = stripped.split(":", 1)[1].strip().strip('"\'')
            elif stripped.startswith("retry_policy:"):
                current_rule["retry_policy"] = stripped.split(":", 1)[1].strip().strip('"\'')
            elif stripped.startswith("match:"):
                in_match = True
            elif in_match and (line.startswith("      ") or line.startswith("    ")):
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                if k == "transport_code":
                    current_rule["match"][k] = int(v)
                else:
                    current_rule["match"][k] = v
            elif not line.startswith(" "):
                in_match = False

    if current_rule:
        rules.append(current_rule)

    return rules


def evaluate_dynamic_rule(rules: list, transport_code: int, probe_status: str) -> dict:
    """
    Evaluates mapping rules strictly in priority order (lowest priority number = highest precedence).
    For example, RULE-05-CONFLICT (priority 10) supersedes RULE-02A-504-AMBIGUOUS (priority 30).
    """
    sorted_rules = sorted(rules, key=lambda r: r.get("priority", 999))
    for rule in sorted_rules:
        match = rule.get("match", {})
        rule_t_code = match.get("transport_code")
        rule_p_status = match.get("probe_status")

        if rule_t_code is not None and rule_t_code != transport_code:
            continue
        if rule_p_status is not None and rule_p_status != probe_status:
            continue

        return rule

    return {"id": "RULE-UNKNOWN", "target_disposition": "UNKNOWN"}


def main():
    base_dir = Path(__file__).resolve().parent.parent

    # 1. Manifest Guard Check
    manifest_path = base_dir / "manifest.json"
    if not manifest_path.exists():
        print("[-] FAIL: manifest.json not found", file=sys.stderr)
        sys.exit(1)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[-] FAIL: Corrupted manifest.json ({e})", file=sys.stderr)
        sys.exit(1)

    # 1.1 Verify Mapping Contract Integrity
    mapping_rel = manifest.get("mapping_contract", {}).get("path")
    expected_mapping_hash = manifest.get("mapping_contract", {}).get("hash")
    if not mapping_rel or not expected_mapping_hash:
        print("[-] FAIL: Missing mapping_contract in manifest", file=sys.stderr)
        sys.exit(1)

    mapping_file = base_dir / mapping_rel
    if not mapping_file.exists():
        print(f"[-] FAIL: Mapping contract not found at {mapping_rel}", file=sys.stderr)
        sys.exit(1)

    mapping_raw = mapping_file.read_bytes()
    actual_mapping_hash = sha256_hex(mapping_raw)
    if actual_mapping_hash != expected_mapping_hash:
        print(f"[-] FAIL: Manifest Guard Violation — mapping_contract hash mismatch! "
              f"Recorded '{expected_mapping_hash}' != actual '{actual_mapping_hash}'", file=sys.stderr)
        sys.exit(1)

    dynamic_rules = load_yaml_rules(mapping_raw)

    # 1.2 Verify Evidence Logs (transport.jsonl and probe.jsonl)
    ev_meta = manifest.get("evidence", {})
    t_log_meta = ev_meta.get("transport_log", {})
    p_log_meta = ev_meta.get("probe_log", {})

    t_log_file = base_dir / t_log_meta.get("path", "evidence/transport.jsonl")
    p_log_file = base_dir / p_log_meta.get("path", "evidence/probe.jsonl")

    if not t_log_file.exists() or not p_log_file.exists():
        print("[-] FAIL: Evidence transport.jsonl or probe.jsonl missing", file=sys.stderr)
        sys.exit(1)

    t_bytes = t_log_file.read_bytes()
    p_bytes = p_log_file.read_bytes()

    if sha256_hex(t_bytes) != t_log_meta.get("hash"):
        print("[-] FAIL: Evidence transport.jsonl hash mismatch", file=sys.stderr)
        sys.exit(1)

    if sha256_hex(p_bytes) != p_log_meta.get("hash"):
        print("[-] FAIL: Evidence probe.jsonl hash mismatch", file=sys.stderr)
        sys.exit(1)

    transport_lines = [l.strip() for l in t_bytes.decode('utf-8').splitlines() if l.strip()]
    probe_lines = [l.strip() for l in p_bytes.decode('utf-8').splitlines() if l.strip()]

    if len(transport_lines) != 8:
        print(f"[-] FAIL: Idempotency violation — expected exactly 8 transport lines, got {len(transport_lines)}", file=sys.stderr)
        sys.exit(1)

    if len(probe_lines) != 8:
        print(f"[-] FAIL: Idempotency violation — expected exactly 8 probe lines, got {len(probe_lines)}", file=sys.stderr)
        sys.exit(1)

    # Map out-of-band hashes for verifiable ID-hash linkage
    transport_hashes = {}
    for line in transport_lines:
        line_data = json.loads(line)
        transport_hashes[line_data["event_id"]] = sha256_hex(line.encode('utf-8'))

    probe_hashes = {}
    for line in probe_lines:
        line_data = json.loads(line)
        probe_hashes[line_data["event_id"]] = sha256_hex(line.encode('utf-8'))

    # 2. Load Public Key
    pub_key_path = base_dir / "public-keys" / "ed25519-public.pem"
    if not pub_key_path.exists():
        print("[-] FAIL: Public key ed25519-public.pem not found", file=sys.stderr)
        sys.exit(1)

    try:
        pub_key = serialization.load_pem_public_key(pub_key_path.read_bytes())
    except Exception as e:
        print(f"[-] FAIL: Could not load public key ({e})", file=sys.stderr)
        sys.exit(1)

    # 3. Verify Every Receipt Listed in Manifest
    receipt_entries = manifest.get("receipt_files") or manifest.get("receipts", [])
    if len(receipt_entries) != 8:
        print(f"[-] FAIL: Expected 8 receipts in manifest, got {len(receipt_entries)}", file=sys.stderr)
        sys.exit(1)

    valid_lines = []

    for entry in receipt_entries:
        r_rel = entry.get("file")
        r_path = base_dir / r_rel
        if not r_path.exists():
            print(f"[-] FAIL: Receipt file missing: {r_rel}", file=sys.stderr)
            sys.exit(1)

        try:
            r_doc = json.loads(r_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[-] FAIL: Could not parse {r_rel} ({e})", file=sys.stderr)
            sys.exit(1)

        # Check format designation
        if r_doc.get("format") != "AEIB_JSON_ED25519_PROTOTYPE":
            print(f"[-] FAIL: Unexpected format in {r_rel}: {r_doc.get('format')}", file=sys.stderr)
            sys.exit(1)

        # Stage 1 & 2: Check unsigned_payload_hash against canonical serialization
        unsigned_payload = r_doc.get("unsigned_payload")
        if not unsigned_payload:
            print(f"[-] FAIL: Missing unsigned_payload in {r_rel}", file=sys.stderr)
            sys.exit(1)

        computed_hash = sha256_hex(canonical_json_bytes(unsigned_payload))
        recorded_unsigned_hash = r_doc.get("unsigned_payload_hash")

        if computed_hash != recorded_unsigned_hash:
            print(f"[-] FAIL: Hash mismatch in {r_rel}: computed '{computed_hash}' != recorded '{recorded_unsigned_hash}'", file=sys.stderr)
            sys.exit(1)

        # Stage 3: Hash-Order Check (signed_payload_hash must match unsigned_payload_hash exactly)
        sig_meta = r_doc.get("signature_metadata", {})
        signed_hash = sig_meta.get("signed_payload_hash")
        if signed_hash != recorded_unsigned_hash:
            print(f"[-] FAIL: Hash-order violation in {r_rel}: signed_payload_hash '{signed_hash}' != unsigned_payload_hash '{recorded_unsigned_hash}'", file=sys.stderr)
            sys.exit(1)

        # Stage 4: Verify Ed25519 signature over signable view
        signable_view = {
            "unsigned_payload": unsigned_payload,
            "unsigned_payload_hash": recorded_unsigned_hash
        }
        signable_bytes = canonical_json_bytes(signable_view)

        sig_hex = sig_meta.get("signature")
        if not sig_hex:
            print(f"[-] FAIL: Missing signature in {r_rel}", file=sys.stderr)
            sys.exit(1)

        try:
            sig_bytes = bytes.fromhex(sig_hex)
            pub_key.verify(sig_bytes, signable_bytes)
        except Exception as e:
            print(f"[-] FAIL: Invalid cryptographic signature in {r_rel} ({e})", file=sys.stderr)
            sys.exit(1)

        # AEIB Extension Check: org.smaos.aeib must reside strictly inside unsigned_payload
        aeib_ext = unsigned_payload.get("org.smaos.aeib")
        if not aeib_ext:
            print(f"[-] FAIL: org.smaos.aeib namespace missing from signed payload in {r_rel}", file=sys.stderr)
            sys.exit(1)

        disp = aeib_ext.get("disposition")
        t_code = aeib_ext.get("transport_code")
        p_status = aeib_ext.get("probe_status")

        # Dynamic Mapping Check: Re-evaluate mapping contract based on priority ordering
        matched_rule = evaluate_dynamic_rule(dynamic_rules, t_code, p_status)
        expected_disp = matched_rule.get("target_disposition")
        if disp != expected_disp:
            print(f"[-] FAIL: Dynamic mapping failure in {r_rel}: evaluated '{expected_disp}' != recorded '{disp}'", file=sys.stderr)
            sys.exit(1)

        # Out-of-Band Evidence Linkage Check: Verify transport and probe hash references
        bindings = aeib_ext.get("evidence_bindings", {})
        t_id = bindings.get("transport_event_id")
        t_h = bindings.get("transport_event_hash")
        if t_id and transport_hashes.get(t_id) != t_h:
            print(f"[-] FAIL: Out-of-band transport evidence mismatch in {r_rel}", file=sys.stderr)
            sys.exit(1)

        p_id = bindings.get("probe_event_id")
        p_h = bindings.get("probe_event_hash")
        if p_id and probe_hashes.get(p_id) != p_h:
            print(f"[-] FAIL: Out-of-band probe evidence mismatch in {r_rel}", file=sys.stderr)
            sys.exit(1)

        filename = os.path.basename(r_rel)
        rule_id = matched_rule.get("id", "UNKNOWN")
        valid_lines.append(f"[+] {filename}: VALID (Signature, Evidence Bindings, and Rule {rule_id} verified — disposition: {disp})")

    # Output exactly the 8 [+] VALID lines
    for line in valid_lines:
        print(line)

    sys.exit(0)


if __name__ == "__main__":
    main()
