#!/usr/bin/env python3
import sys
import argparse
import hashlib
from pathlib import Path

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="AEIB Manifest Verifier")
    parser.add_argument("--manifest", default="verification.txt", help="Path to verification manifest")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Error: Manifest '{manifest_path}' not found.", file=sys.stderr)
        sys.exit(1)

    lines = [line.strip() for line in manifest_path.read_text().splitlines() if line.strip() and not line.startswith("#")]
    total = len(lines)
    passed = 0

    print(f"Verifying {total} artifacts against {manifest_path}...")
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        expected_hash, rel_path = parts[0], parts[1].strip()
        target_path = Path(rel_path)
        if not target_path.exists():
            print(f"[FAIL] Missing file: {rel_path}", file=sys.stderr)
            continue
        actual_hash = compute_sha256(target_path)
        if actual_hash == expected_hash:
            passed += 1
            print(f"[OK] {rel_path}")
        else:
            print(f"[FAIL] Digest mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}", file=sys.stderr)

    if passed == total and total > 0:
        print(f"Manifest Gate Passed: {passed}/{total} files verified (100% OK).")
        sys.exit(0)
    else:
        print(f"Manifest Gate Failed: {passed}/{total} verified.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
