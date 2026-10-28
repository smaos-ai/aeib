#!/usr/bin/env python3
"""
Regression tests: offline / deterministic fallbacks must be labelled as NOT retrieved.

Pre-market audit finding: offline fallbacks in ``src/sovereign_search.py`` and
``src/decide_autonomous_query_research_engine.py`` returned literal URL/title/content
dicts that were indistinguishable from live retrieval results, a synthesis
fallback that emitted ``[n]`` citation markers and the sentence
"All sources hashed and validated." without validating anything, and an AST
inspector that returned a hardcoded ``callers_count`` of 4.

Zero-egress: no test here performs outbound HTTP. Fallback paths are invoked
directly (``_offline_fallback``, ``_offline_fixture``) or forced by pointing
``OLLAMA_HOST`` at a closed loopback port (127.0.0.1:9).
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import sovereign_search as ss  # noqa: E402
from src.decide_autonomous_query_research_engine import (  # noqa: E402
    AutonomousQueryResearchDispatcher,
)

OFFLINE = "OFFLINE_FIXTURE_NOT_RETRIEVED"
CLOSED_PORT = "http://127.0.0.1:9"

_WEB_QUERIES = (
    "EU AI Act Annex III deferral",
    "DeepSeek context window scaling",
    "DORA Annex II RTS template",
    "an unrelated query with no keyword",
)


def _assert_offline_labelled(rows: list, origin: str) -> None:
    assert rows, "fallback must still return fixture rows (shape preserved)"
    for r in rows:
        assert r["retrieved"] is False
        assert r["provenance"] == OFFLINE
        assert r["engine"] == "offline_fixture"
        assert r["fixture_origin_engine"] == origin
        assert r["title"].startswith("OFFLINE_FIXTURE: ")
        # content_hash must still be the sha256 of the (unchanged) fixture content
        import hashlib

        assert r["content_hash"] == hashlib.sha256(r["content"].encode("utf-8")).hexdigest()


@pytest.mark.parametrize("query", _WEB_QUERIES)
def test_searxng_offline_fallback_is_labelled_not_retrieved(query: str) -> None:
    rows = ss.SearxNGClient(base_url=CLOSED_PORT)._offline_fallback(query)
    _assert_offline_labelled(rows, "searxng_fallback")


def test_searxng_offline_fallback_branch_selection_preserved() -> None:
    client = ss.SearxNGClient(base_url=CLOSED_PORT)
    assert len(client._offline_fallback("ai act deferral")) == 4
    assert len(client._offline_fallback("deepseek")) == 2
    assert len(client._offline_fallback("dora")) == 2
    assert len(client._offline_fallback("zzz")) == 1
    assert any("CELEX:32026R1744" in r["url"] for r in client._offline_fallback("annex iii"))


def test_academic_offline_fixture_is_labelled_not_retrieved() -> None:
    rows = ss.SovereignAcademicRetriever._offline_fixture("DORA operational resilience")
    _assert_offline_labelled(rows, "academic_fallback")
    assert "DORA operational resilience" in rows[0]["content"]


def test_live_label_helper_marks_rows_retrieved() -> None:
    row = ss._live_row("https://example.invalid/x", "T", "body", "searxng")
    assert row["retrieved"] is True
    assert row["provenance"] == "LIVE_RETRIEVAL"
    assert row["engine"] == "searxng"
    assert row["title"] == "T" and row["url"] == "https://example.invalid/x"
    assert row["content"] == "body"


_CITATION = re.compile(r"\[\d+\]")


@pytest.fixture
def offline_synth(monkeypatch: pytest.MonkeyPatch) -> "ss.SovereignSynthesisEngine":
    monkeypatch.setenv("OLLAMA_HOST", CLOSED_PORT)
    return ss.SovereignSynthesisEngine()


def test_synthesis_fallback_empty_sources_makes_no_validation_claim(offline_synth) -> None:
    out = offline_synth.synthesize("anything", [])
    assert out.startswith("OFFLINE_FIXTURE (not retrieved, not validated):")
    assert "validated." not in out.replace("not validated", "")
    assert "All sources hashed and validated" not in out
    assert not _CITATION.search(out)


def test_synthesis_fallback_regulatory_branch_has_no_citation_markers(offline_synth) -> None:
    q = "EU AI Act Annex III deferral and DORA Article 17 reporting thresholds"
    out = offline_synth.synthesize(q, [])
    assert out.startswith("OFFLINE_FIXTURE (not retrieved, not validated):")
    assert not _CITATION.search(out)
    # shape relied upon by tests/test_provenance.py::test_07 is preserved
    assert "AI Act Annex III Deferral" in out
    assert "December 2, 2027" in out
    assert "DORA Article 17 Reporting" in out


def test_synthesis_fallback_with_sources_reports_counts_without_citations(offline_synth) -> None:
    fixtures = ss.SearxNGClient(base_url=CLOSED_PORT)._offline_fallback("zzz")
    live = ss._live_row("https://example.invalid/a", "A", "live excerpt text", "arxiv")
    out = offline_synth.synthesize("zzz", [live] + fixtures)
    assert out.startswith("OFFLINE_FIXTURE (not retrieved, not validated):")
    assert not _CITATION.search(out)
    assert "2 source(s) supplied" in out
    assert "1 labelled live-retrieved" in out
    assert "live excerpt text" in out


def test_dispatcher_default_web_search_is_labelled_not_retrieved() -> None:
    d = AutonomousQueryResearchDispatcher()
    for q in ("deep research", "action space", "oracle gap", "clinical llms", "totally_unmatched_query"):
        rows = d._default_mockless_web_search(q)
        assert rows
        for r in rows:
            assert r["retrieved"] is False
            assert r["provenance"] == OFFLINE
            assert r["engine"] == "offline_fixture"
            assert r["title"].startswith("OFFLINE_FIXTURE: ")


def _independent_reference_count(symbol: str) -> tuple[int, list[str]]:
    total = 0
    mods: list[str] = []
    for path in sorted((_ROOT / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if symbol not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        n = sum(
            1
            for node in ast.walk(tree)
            if (isinstance(node, ast.Name) and node.id == symbol)
            or (isinstance(node, ast.Attribute) and node.attr == symbol)
        )
        if n:
            total += n
            mods.append(path.relative_to(_ROOT).as_posix())
    return total, mods


def test_ast_inspector_computes_real_reference_count() -> None:
    d = AutonomousQueryResearchDispatcher()
    sym = "canonical_jcs"
    info = d._default_ast_inspector(sym)
    expected_count, expected_mods = _independent_reference_count(sym)
    assert expected_count > 0
    assert info["symbol"] == sym
    assert info["callers_count"] == expected_count
    assert info["affected_modules"] == expected_mods
    assert info["provenance"] == "LOCAL_AST_REFERENCE_SCAN"
    assert info["retrieved"] is False
    assert info["scan_scope"] == "src/"


def test_ast_inspector_unknown_symbol_is_zero_not_hardcoded() -> None:
    d = AutonomousQueryResearchDispatcher()
    info = d._default_ast_inspector("zz_symbol_that_does_not_exist_q9x")
    assert info["callers_count"] == 0
    assert info["affected_modules"] == []
    assert info["is_pure_functional"] is None


def test_synthesis_fixture_forces_closed_port(offline_synth) -> None:
    """Guard: the synthesis fixture really targets the closed loopback port."""
    assert offline_synth.host == CLOSED_PORT
    assert os.environ["OLLAMA_HOST"] == CLOSED_PORT
