#!/usr/bin/env python3
# File: tools/notebooklm_bridge.py
"""
Bi-directional integration bridge between SovereignNexus / Antigravity
and Google NotebookLM (notebook e1b91409-02f9-4300-8bf7-5dfd4426dd16).

Acts as a "Second AI Brain" interface:
1. Compiles, packages, and synchronizes all architectural moats, proofs,
   evidence manifests, diagrams, and benchmarks into the target notebook.
2. Supports querying / asking grounded questions to NotebookLM with citations.
3. Automatically adapts between:
   - Live API Mode (via `notebooklm-py` when installed and authenticated).
   - Staged Mode (deterministic local 8-source pack ready for web upload or Drive sync).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist" / "notebooklm_pack"
DEFAULT_NOTEBOOK_ID = "e1b91409-02f9-4300-8bf7-5dfd4426dd16"
NOTEBOOKLM_STORAGE_PATH = Path.home() / ".notebooklm" / "storage_state.json"


def check_auth_status() -> Dict[str, Any]:
    """Inspects whether notebooklm-py is installed and session cookies are present."""
    has_lib = False
    try:
        import notebooklm  # type: ignore

        has_lib = True
    except ImportError:
        pass

    has_cookies = NOTEBOOKLM_STORAGE_PATH.exists() and NOTEBOOKLM_STORAGE_PATH.stat().st_size > 10

    has_pack = DIST_DIR.exists() and (DIST_DIR / "PACK_MANIFEST.json").exists()

    return {
        "notebooklm_library_installed": has_lib,
        "session_cookies_present": has_cookies,
        "storage_state_path": str(NOTEBOOKLM_STORAGE_PATH),
        "pack_compiled": has_pack,
        "pack_directory": str(DIST_DIR),
        "target_notebook_id": DEFAULT_NOTEBOOK_ID,
        "target_notebook_url": f"https://notebook.google.com/notebook/{DEFAULT_NOTEBOOK_ID}",
    }


def compile_pack() -> Dict[str, Any]:
    """Invokes the compiler to refresh the 8-source knowledge pack."""
    compiler_script = REPO_ROOT / "tools" / "compile_notebooklm_moats_pack.py"
    subprocess.run([sys.executable, str(compiler_script)], check=True)
    manifest_path = DIST_DIR / "PACK_MANIFEST.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


async def query_notebooklm_async(
    question: str, notebook_id: str = DEFAULT_NOTEBOOK_ID
) -> Dict[str, Any]:
    """Queries NotebookLM using notebooklm-py if installed and authenticated."""
    try:
        from notebooklm import NotebookLMClient  # type: ignore
    except ImportError:
        return {
            "status": "ERROR_LIBRARY_NOT_INSTALLED",
            "message": (
                "The `notebooklm-py` package is not installed. To enable direct CLI queries from this terminal:\n"
                "  1. Run: pip install notebooklm-py\n"
                "  2. Run: notebooklm login\n"
                "Alternatively, open the notebook directly in your browser: "
                f"https://notebook.google.com/notebook/{notebook_id}"
            ),
        }

    if not NOTEBOOKLM_STORAGE_PATH.exists():
        return {
            "status": "ERROR_AUTH_REQUIRED",
            "message": (
                "Session cookies not found at ~/.notebooklm/storage_state.json.\n"
                "Please authenticate once by running:\n"
                "  notebooklm login\n"
            ),
        }

    try:
        async with NotebookLMClient.from_storage() as client:
            answer = await client.ask_question(notebook_id, question)
            return {
                "status": "SUCCESS",
                "notebook_id": notebook_id,
                "question": question,
                "answer": answer.get("answer", str(answer)),
                "citations": answer.get("citations", []),
            }
    except Exception as exc:
        return {
            "status": "ERROR_QUERY_FAILED",
            "error": str(exc),
            "hint": "Session cookies may have expired. Try running `notebooklm login` to refresh.",
        }


async def upload_pack_to_notebooklm_async(
    notebook_id: str = DEFAULT_NOTEBOOK_ID,
) -> Dict[str, Any]:
    """Uploads the compiled 8-source pack into the target notebook via notebooklm-py."""
    try:
        from notebooklm import NotebookLMClient  # type: ignore
    except ImportError:
        return {
            "status": "ERROR_LIBRARY_NOT_INSTALLED",
            "message": (
                "`notebooklm-py` is not installed. You can upload the 8 files in `dist/notebooklm_pack/` "
                f"directly by dragging them into https://notebook.google.com/notebook/{notebook_id} in your browser."
            ),
        }

    if not DIST_DIR.exists():
        compile_pack()

    manifest_path = DIST_DIR / "PACK_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    results = []
    async with NotebookLMClient.from_storage() as client:
        for source_info in manifest["sources"]:
            fpath = Path(source_info["path"])
            fname = source_info["file_name"]
            print(f"Uploading {fname} to NotebookLM {notebook_id}...")
            try:
                upload_res = await client.add_source_file(notebook_id, str(fpath))
                results.append({"file": fname, "status": "UPLOADED", "response": upload_res})
            except Exception as exc:
                results.append({"file": fname, "status": "FAILED", "error": str(exc)})

    return {"status": "COMPLETE", "notebook_id": notebook_id, "results": results}


def export_to_drive_folder(target_folder: str) -> None:
    """Copies the 8 compiled files into a specified local Google Drive sync folder."""
    dest = Path(target_folder).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if not DIST_DIR.exists():
        compile_pack()

    for item in DIST_DIR.glob("*.md"):
        shutil.copy2(item, dest / item.name)
    shutil.copy2(DIST_DIR / "PACK_MANIFEST.json", dest / "PACK_MANIFEST.json")
    print(f"✓ Exported 8 sources + manifest to: {dest}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SovereignNexus NotebookLM Integration Bridge")
    subparsers = parser.add_subparsers(dest="command")

    # Command: status
    subparsers.add_parser("status", help="Check NotebookLM auth and pack status")

    # Command: compile
    subparsers.add_parser("compile", help="Compile and refresh the 8-source knowledge pack")

    # Command: ask
    ask_parser = subparsers.add_parser("ask", help="Ask a question to NotebookLM")
    ask_parser.add_argument("question", type=str, help="Question to query the notebook")
    ask_parser.add_argument("--notebook-id", type=str, default=DEFAULT_NOTEBOOK_ID, help="Target notebook ID")

    # Command: sync
    sync_parser = subparsers.add_parser("sync", help="Upload compiled pack to NotebookLM")
    sync_parser.add_argument("--notebook-id", type=str, default=DEFAULT_NOTEBOOK_ID, help="Target notebook ID")

    # Command: export-drive
    export_parser = subparsers.add_parser("export-drive", help="Export pack to local Google Drive folder")
    export_parser.add_argument("drive_path", type=str, help="Destination directory path")

    args = parser.parse_args()

    if args.command == "status" or args.command is None:
        status = check_auth_status()
        print(json.dumps(status, indent=2))

    elif args.command == "compile":
        res = compile_pack()
        print(f"Compiled {res['sources_count']} sources ({res['total_word_count']:,} total words).")

    elif args.command == "ask":
        res = asyncio.run(query_notebooklm_async(args.question, args.notebook_id))
        print(json.dumps(res, indent=2))

    elif args.command == "sync":
        res = asyncio.run(upload_pack_to_notebooklm_async(args.notebook_id))
        print(json.dumps(res, indent=2))

    elif args.command == "export-drive":
        export_to_drive_folder(args.drive_path)


if __name__ == "__main__":
    main()
