#!/usr/bin/env python3
# File: tests/test_notebooklm_bridge.py
"""
Test suite for SovereignNexus NotebookLM knowledge compiler and integration bridge.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from tools.compile_notebooklm_moats_pack import (
    MAX_WORDS_PER_SOURCE,
    compile_all_sources,
    count_words,
)
from tools.notebooklm_bridge import (
    DEFAULT_NOTEBOOK_ID,
    check_auth_status,
    export_to_drive_folder,
)


def test_1_pack_compilation_and_constraints() -> None:
    manifest = compile_all_sources()

    assert manifest["sources_count"] == 12
    assert manifest["target_notebook_id"] == DEFAULT_NOTEBOOK_ID
    assert DEFAULT_NOTEBOOK_ID in manifest["target_notebook_url"]
    assert manifest["total_word_count"] > 10_000

    for source in manifest["sources"]:
        assert source["words"] <= MAX_WORDS_PER_SOURCE
        assert source["words"] > 0
        assert source["sha256"].startswith("sha256:")
        p = Path(source["path"])
        assert p.exists()
        assert p.stat().st_size > 0


def test_2_bridge_status_and_cli() -> None:
    status = check_auth_status()
    assert "notebooklm_library_installed" in status
    assert "session_cookies_present" in status
    assert status["target_notebook_id"] == "e1b91409-02f9-4300-8bf7-5dfd4426dd16"
    assert status["pack_compiled"] is True


def test_3_drive_export() -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="test_drive_export_"))
    try:
        export_to_drive_folder(str(tmp_dir))
        copied_md = list(tmp_dir.glob("*.md"))
        assert len(copied_md) == 12
        manifest_copy = tmp_dir / "PACK_MANIFEST.json"
        assert manifest_copy.exists()
        data = json.loads(manifest_copy.read_text(encoding="utf-8"))
        assert data["sources_count"] == 12
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_4_epistemic_purity() -> None:
    forbidden_tokens = [
        "guaran" + "teed",
        "guaran" + "tee",
        "bullet" + "proof",
        "enterprise-" + "grade",
        "production-" + "safe",
        "100% " + "secure",
        "unassail" + "able",
        "immu" + "ne",
        "unhack" + "able",
    ]
    target_files = [
        Path("tools/compile_notebooklm_moats_pack.py"),
        Path("tools/notebooklm_bridge.py"),
        Path("tests/test_notebooklm_bridge.py"),
    ]
    for p in target_files:
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8").lower()
        for tok in forbidden_tokens:
            assert tok not in content, f"Forbidden promotional term '{tok}' found in {p}"
