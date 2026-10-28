#!/usr/bin/env python3
"""Quarantine flattened files from a backup root (stdlib only; dry run by default).

Background: an `rsync src/ tests/ ... BACKUP/` (trailing slashes) copies the
CONTENTS of those directories into the backup root instead of the directories.
This script finds loose top-level files in the backup root and classifies each:

  LEGIT_ROOT        same name as a file in the live repo ROOT      -> never moved
  DIVERGENT_ROOT    same name as a live root file, content differs -> never moved
                    (an older mirror of a root file; a human decides)
  FLATTENED         name exists only below a live sub-directory    -> moved
  UNKNOWN           name not found in the live repo                -> never moved

Only FLATTENED files are moved, into `<backup>/_quarantine_flat_sync_<UTC stamp>/`.
Nothing is deleted. A manifest (name, sha256, matching live path, identical flag)
is written next to the moved files so the move can be reversed.

Usage:
    python3 scripts/quarantine_flat_backup.py --live REPO --backup BACKUP          # dry run
    python3 scripts/quarantine_flat_backup.py --live REPO --backup BACKUP --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

PRUNE = {".git", "node_modules", "target", "__pycache__", ".pytest_cache", "sdk", ".venv"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(live: Path, backup: Path) -> Dict[str, List[dict]]:
    by_name: Dict[str, List[Path]] = {}
    for root, dirs, files in os.walk(live):
        dirs[:] = [d for d in dirs if d not in PRUNE]
        for fn in files:
            by_name.setdefault(fn, []).append(Path(root) / fn)

    out: Dict[str, List[dict]] = {"LEGIT_ROOT": [], "DIVERGENT_ROOT": [], "FLATTENED": [], "UNKNOWN": []}
    for p in sorted(x for x in backup.iterdir() if x.is_file() and not x.is_symlink()):
        digest = _sha256(p)
        live_root_file = live / p.name
        if live_root_file.is_file():
            kind = "LEGIT_ROOT" if digest == _sha256(live_root_file) else "DIVERGENT_ROOT"
            out[kind].append({"name": p.name, "sha256": digest})
            continue
        matches = by_name.get(p.name, [])
        if matches:
            same = any(_sha256(m) == digest for m in matches)
            out["FLATTENED"].append({
                "name": p.name, "sha256": digest,
                "live_candidates": [str(m.relative_to(live)) for m in matches[:5]],
                "identical_to_a_live_file": same,
            })
        else:
            out["UNKNOWN"].append({"name": p.name, "sha256": digest})
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", required=True, type=Path)
    ap.add_argument("--backup", required=True, type=Path)
    ap.add_argument("--apply", action="store_true", help="move FLATTENED files (default: dry run)")
    args = ap.parse_args(argv)
    if not args.live.is_dir() or not args.backup.is_dir():
        print("ERR: --live and --backup must be existing directories", file=sys.stderr)
        return 2
    if args.live.resolve() == args.backup.resolve():
        print("ERR: live and backup are the same directory", file=sys.stderr)
        return 2

    result = classify(args.live, args.backup)
    for kind, rows in result.items():
        print(f"{kind:15s} {len(rows)}")
    flat = result["FLATTENED"]
    print(f"FLATTENED identical to a live file: {sum(1 for r in flat if r['identical_to_a_live_file'])}")
    if not args.apply:
        print("dry run: nothing moved (use --apply)")
        return 0

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    qdir = args.backup / f"_quarantine_flat_sync_{stamp}"
    qdir.mkdir(parents=False, exist_ok=False)
    for row in flat:
        src = args.backup / row["name"]
        dst = qdir / row["name"]
        if dst.exists():
            print(f"ERR: refusing to overwrite {dst}", file=sys.stderr)
            return 3
        os.rename(src, dst)  # same volume; no content is read or rewritten
    (qdir / "MANIFEST.json").write_text(json.dumps(
        {"moved": flat, "kept": {k: len(v) for k, v in result.items() if k != "FLATTENED"}}, indent=1))
    print(f"moved {len(flat)} files to {qdir} (nothing deleted; MANIFEST.json written)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
