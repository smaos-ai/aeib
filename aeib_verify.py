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
aeib_verify.py
================================================================================
AEIB Offline Mapping Verifier & SCITT Receipt Conformity Tool
Validates cryptographic action receipts against transport-to-disposition contracts.
"""

import sys
import os
import json
import hashlib
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# RFC 8785 single source of truth: delegate to src/jcs_canonicalizer.encode_jcs
# (differential-tested in tests/test_jcs_single_source.py).
try:
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs
except ImportError:  # loaded without the repository root on sys.path
    import sys as _jcs_sys
    from pathlib import Path as _JcsPath

    _jcs_sys.path.insert(0, str(_JcsPath(__file__).resolve().parents[0]))
    from src.jcs_canonicalizer import encode_jcs as _reference_encode_jcs


def canonical_json_bytes(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) deterministic subset."""
    return _reference_encode_jcs(obj)


def load_yaml_contract(contract_path: Path) -> Dict[str, Any]:
    """Parse YAML contract safely with pyyaml or structured fallback."""
    try:
        import yaml
        with open(contract_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        # Structured fallback parser
        data: Dict[str, Any] = {"rules": []}
        current_rule: Dict[str, Any] = {}
        with open(contract_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("- id:"):
                    if current_rule:
                        data["rules"].append(current_rule)
                    current_rule = {"id": stripped.split(":", 1)[1].strip().strip('"\''), "match": {}}
                elif current_rule:
                    if stripped.startswith("priority:"):
                        current_rule["priority"] = int(stripped.split(":", 1)[1].strip())
                    elif stripped.startswith("target_disposition:"):
                        current_rule["target_disposition"] = stripped.split(":", 1)[1].strip().strip('"\'')
                    elif stripped.startswith("retry_policy:"):
                        current_rule["retry_policy"] = stripped.split(":", 1)[1].strip().strip('"\'')
                    elif stripped.startswith("transport_code:"):
                        current_rule["match"]["transport_code"] = int(stripped.split(":", 1)[1].strip())
                    elif stripped.startswith("probe_status:"):
                        current_rule["match"]["probe_status"] = stripped.split(":", 1)[1].strip().strip('"\'')
            if current_rule:
                data["rules"].append(current_rule)
        return data


def verify_receipt(receipt_data: Dict[str, Any], contract_data: Dict[str, Any], strict: bool = False) -> bool:
    """Verifies cryptographic hash binding, contract rule conformance, and signatures."""
    # 1. Payload hash verification
    if "unsigned_payload" in receipt_data:
        payload = receipt_data["unsigned_payload"]
        computed_hash = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        recorded_hash = receipt_data.get("unsigned_payload_hash")
        if recorded_hash and computed_hash != recorded_hash:
            if strict:
                raise ValueError(f"Payload hash mismatch: computed {computed_hash} != {recorded_hash}")
            return False

    # 2. Extract disposition and wire signals
    payload = receipt_data.get("unsigned_payload", {})
    aeib_data = (
        receipt_data.get("org.smaos.aeib")
        or payload.get("org.smaos.aeib")
        or receipt_data
    )
    disposition = (
        receipt_data.get("disposition")
        or aeib_data.get("disposition")
        or aeib_data.get("aeib.disposition")
    )
    if not disposition:
        if strict:
            raise ValueError("Receipt missing required disposition field")
        return False

    transport_code = (
        aeib_data.get("transport_code")
        or aeib_data.get("aeib.transport.status_code")
        or receipt_data.get("transport_code")
    )
    probe_status = (
        aeib_data.get("probe_status")
        or aeib_data.get("aeib.probe.query_status")
        or receipt_data.get("probe_status")
    )

    # 3. Contract rule matching: Match transport and probe signals to target disposition
    rules = contract_data.get("rules", [])
    if transport_code is not None and probe_status is not None and rules:
        sorted_rules = sorted(rules, key=lambda r: r.get("priority", 100))
        matched_rule = None
        for r in sorted_rules:
            m = r.get("match", {})
            if m.get("transport_code") == transport_code and m.get("probe_status") == probe_status:
                matched_rule = r
                break

        if matched_rule:
            expected_disp = matched_rule.get("target_disposition")
            if disposition != expected_disp:
                if strict:
                    raise ValueError(
                        f"Receipt disposition '{disposition}' violates contract rule {matched_rule.get('id')}: "
                        f"expected '{expected_disp}' for transport_code={transport_code}, probe_status={probe_status}"
                    )
                return False

    # 4. Cryptographic signature verification (if present)
    signatures = receipt_data.get("signatures", {})
    if "ed25519" in signatures:
        ed = signatures["ed25519"]
        pk_hex = ed.get("public_key")
        sig_hex = ed.get("signature")
        raw_payload = receipt_data.get("payload")
        if pk_hex and sig_hex and raw_payload:
            try:
                from cryptography.hazmat.primitives.asymmetric import ed25519
                pk_bytes = bytes.fromhex(pk_hex)
                sig_bytes = bytes.fromhex(sig_hex)
                vk = ed25519.Ed25519PublicKey.from_public_bytes(pk_bytes)
                msg_bytes = raw_payload.encode("utf-8") if isinstance(raw_payload, str) else raw_payload
                vk.verify(sig_bytes, msg_bytes)
            except Exception as e:
                if strict:
                    raise ValueError(f"Ed25519 signature verification failed: {e}")
                return False

    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AEIB Offline Mapping Verifier & SCITT Receipt Conformity Tool"
    )
    parser.add_argument(
        "--receipt",
        type=str,
        default=None,
        help="Path to signed JSON SCITT receipt envelope"
    )
    parser.add_argument(
        "--receipt-chain",
        type=str,
        default=None,
        help="Path to JSON receipt chain array"
    )
    parser.add_argument(
        "--contract",
        type=str,
        default=None,
        help="Path to transport-to-disposition mapping YAML contract (defaults to transport-to-disposition-mapping.yaml or docs/transport-to-disposition-mapping.yaml)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce zero-tolerance mapping derivation check"
    )

    args = parser.parse_args()

    if args.contract:
        contract_file = Path(args.contract)
    else:
        candidates = [
            Path("transport-to-disposition-mapping.yaml"),
            Path("docs/transport-to-disposition-mapping.yaml"),
            Path(__file__).resolve().parent / "docs/transport-to-disposition-mapping.yaml",
            Path(__file__).resolve().parent / "transport-to-disposition-mapping.yaml"
        ]
        contract_file = next((c for c in candidates if c.exists()), candidates[0])

    if not contract_file.exists():
        print(f"[-] Contract not found: {contract_file}", file=sys.stderr)
        sys.exit(1)

    contract = load_yaml_contract(contract_file)
    rules_count = len(contract.get("rules", contract.get("mappings", [])))

    if args.receipt_chain:
        chain_file = Path(args.receipt_chain)
        if not chain_file.exists():
            print(f"[-] Receipt chain not found: {chain_file}", file=sys.stderr)
            sys.exit(1)
        with open(chain_file, "r", encoding="utf-8") as f:
            chain = json.load(f)
        if not isinstance(chain, list):
            print(f"[-] Receipt chain must be a JSON array: {chain_file}", file=sys.stderr)
            sys.exit(1)
        
        passed = 0
        for idx, item in enumerate(chain):
            scenario = item.get("scenario_id", f"item_{idx}")
            if verify_receipt(item, contract, strict=args.strict):
                print(f"[+] Receipt [{idx+1}/{len(chain)}] ({scenario}): CONFORMANT")
                passed += 1
            else:
                print(f"[-] Receipt [{idx+1}/{len(chain)}] ({scenario}): NON-CONFORMANT", file=sys.stderr)
                sys.exit(1)
        print(f"\n[✔] Verified all {passed}/{len(chain)} receipts in chain under contract {contract_file.name}.")

    elif args.receipt:
        receipt_file = Path(args.receipt)
        if not receipt_file.exists():
            print(f"[-] Receipt not found: {receipt_file}", file=sys.stderr)
            sys.exit(1)
        with open(receipt_file, "r", encoding="utf-8") as f:
            receipt = json.load(f)
        try:
            valid = verify_receipt(receipt, contract, strict=args.strict)
            if valid:
                print(f"[+] Receipt {receipt_file.name}: CONFORMANT (Derived under contract: {contract_file.name})")
            else:
                print(f"[-] Receipt {receipt_file.name}: NON-CONFORMANT", file=sys.stderr)
                sys.exit(1)
        except Exception as e:
            print(f"[-] Verification error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"[+] Contract verified: {contract_file.name} ({rules_count} rules loaded).")
        print("[+] Offline verifier ready for receipt derivation verification.")

    sys.exit(0)


if __name__ == "__main__":
    main()
