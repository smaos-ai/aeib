#!/usr/bin/env python3
"""Every repo path cited in docs/INHERITANCE_BLUEPRINT.md must exist (no dangling references).

The blueprint's catch #14/#7 rule ("never cite a file that is not present") is enforced here, so a
rename or deletion fails CI instead of leaving the guide pointing at nothing.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "INHERITANCE_BLUEPRINT.md"
_PATH_RE = re.compile(
    r"`((?:src|tests|tools|compliance|benchmarks|docs|scripts|adapters|formal)/[A-Za-z0-9_./-]+)`"
)


def cited_paths(text: str) -> list[str]:
    return sorted(set(_PATH_RE.findall(text)))


def test_blueprint_cites_paths_and_all_exist() -> None:
    text = DOC.read_text(encoding="utf-8")
    paths = cited_paths(text)
    assert len(paths) >= 20, f"expected the blueprint to cite repo files, found {len(paths)}"
    missing = [p for p in paths if not (REPO / p).exists()]
    assert missing == [], f"dangling references in blueprint: {missing}"


def test_path_extractor_detects_a_planted_missing_file() -> None:
    planted = "see `src/this_module_does_not_exist_xyz.py` and `src/truth_compass.py`"
    paths = cited_paths(planted)
    assert paths == ["src/this_module_does_not_exist_xyz.py", "src/truth_compass.py"]
    assert [p for p in paths if not (REPO / p).exists()] == ["src/this_module_does_not_exist_xyz.py"]
