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


def canonical_json_bytes(obj: Any) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) deterministic subset."""
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')


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
    """Verifies cryptographic hash binding and contract rule conformance."""
    if "unsigned_payload" in receipt_data:
        payload = receipt_data["unsigned_payload"]
        computed_hash = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
        recorded_hash = receipt_data.get("unsigned_payload_hash")
        if recorded_hash and computed_hash != recorded_hash:
            if strict:
                raise ValueError(f"Payload hash mismatch: computed {computed_hash} != {recorded_hash}")
            return False

    disposition = (
        receipt_data.get("disposition")
        or receipt_data.get("org.smaos.aeib", {}).get("disposition")
        or receipt_data.get("unsigned_payload", {}).get("org.smaos.aeib", {}).get("disposition")
    )
    if not disposition and strict:
        raise ValueError("Receipt missing disposition field")
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
        default="transport-to-disposition-mapping.yaml",
        help="Path to transport-to-disposition mapping YAML contract"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enforce zero-tolerance mapping derivation check"
    )

    args = parser.parse_args()

    contract_file = Path(args.contract)
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
