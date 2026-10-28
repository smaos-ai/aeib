"""Verification & Falsification Suite for SQLite FTS5 Lexical Retrieval (`src/hypersu_fts.py`)."""

from __future__ import annotations

from pathlib import Path
import hashlib
import math
import pytest

from src.hypersu_fts import HyperSUFTSRetriever, escape_like_pattern, sanitize_fts5_query
from src.hypersu_store import (
    FactRecord,
    HyperedgeEvidenceSpan,
    HyperedgeMember,
    HyperSUStore,
)


def _make_fact(
    fact_id: str,
    label: str,
    text: str,
    file_path: str = "src/eo1_write_before_execute.py",
    start_char: int = 0,
) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        episode_id=f"ep:{file_path}",
        label=label,
        text=text,
        source_id=f"src:{file_path}",
        file_path=file_path,
        start_char=start_char,
        end_char=start_char + len(text),
        content_sha256="sha256:" + ("a" * 64),
    )


def test_fts5_explicit_sync_on_insert_update_and_delete() -> None:
    """Verifies that `fact_fts` stays 1-to-1 synchronized across insert, update, and delete."""
    store = HyperSUStore()
    retriever = HyperSUFTSRetriever(store)

    f1 = _make_fact(
        "fact-1",
        "EO1 fsync requirement",
        "PreDispatchIntentInterlock calls fcntl F_FULLFSYNC before network dispatch.",
    )
    store.add_fact(f1)
    assert store.check_fts_sync_integrity() is True

    # Re-inserting same fact_id with updated text must not leave duplicate or stale FTS rows
    f1_updated = _make_fact(
        "fact-1",
        "EO1 flock requirement",
        "PreDispatchIntentInterlock acquires fcntl.flock LOCK_EX across OS processes.",
    )
    store.add_fact(f1_updated)
    assert store.check_fts_sync_integrity() is True

    # Old token 'F_FULLFSYNC' must no longer match; new token 'LOCK_EX' must match once
    assert retriever.coarse_to_fine_retrieve("F_FULLFSYNC") == []
    hits = retriever.coarse_to_fine_retrieve("LOCK_EX")
    assert len(hits) == 1
    assert hits[0]["fact_id"] == "fact-1"

    # Deleting fact removes it from both `facts` and `fact_fts`
    store.delete_fact("fact-1")
    assert store.check_fts_sync_integrity() is True
    assert retriever.coarse_to_fine_retrieve("LOCK_EX") == []
    store.close()


def test_fts5_single_term_multi_term_and_phrase_ranking() -> None:
    """Verifies BM25 ranking across single-term, multi-term OR/AND, and phrase queries."""
    store = HyperSUStore()
    retriever = HyperSUFTSRetriever(store)

    store.add_facts_batch(
        [
            _make_fact(
                "fact-fsync",
                "Durable fsync append",
                "Calls F_FULLFSYNC on Darwin and os.fsync on Linux before dispatch.",
            ),
            _make_fact(
                "fact-flock",
                "Cross-process flock",
                "Acquires fcntl.flock LOCK_EX on sibling lock file before F_FULLFSYNC.",
            ),
            _make_fact(
                "fact-reconcile",
                "Out-of-band reconcile",
                "Reconciles EFFECT_INDETERMINATE latches after transport timeout.",
            ),
        ]
    )
    assert store.check_fts_sync_integrity() is True

    # 1. Single term
    res_single = retriever.coarse_to_fine_retrieve("EFFECT_INDETERMINATE")
    assert [r["fact_id"] for r in res_single] == ["fact-reconcile"]

    # 2. Multi-term OR query: fact-flock matches both tokens so it ranks first (most negative bm25)
    res_or = retriever.coarse_to_fine_retrieve("flock F_FULLFSYNC", mode="or")
    assert len(res_or) == 2
    assert res_or[0]["fact_id"] == "fact-flock"

    # 3. Multi-term AND query: only fact-flock contains both 'flock' and 'F_FULLFSYNC'
    res_and = retriever.coarse_to_fine_retrieve("flock F_FULLFSYNC", mode="and")
    assert [r["fact_id"] for r in res_and] == ["fact-flock"]

    # 4. Phrase query
    res_phrase = retriever.coarse_to_fine_retrieve(
        "sibling lock file", mode="phrase"
    )
    assert [r["fact_id"] for r in res_phrase] == ["fact-flock"]
    store.close()


@pytest.mark.parametrize(
    "adversarial_query",
    [
        "",
        "   ",
        "%",
        "_",
        "%%__%%",
        '"',
        '""',
        'unclosed "quote F_FULLFSYNC',
        "AND",
        "OR",
        "NOT",
        "AND OR NOT NEAR",
        "F_FULLFSYNC AND OR NOT (",
        "label:secret_column ^ * : - +",
        "((( ))) [[[ ]]]",
        "'; DROP TABLE facts; --",
        "\x00\x01\x02",
        "NEAR(F_FULLFSYNC, flock, 2)",
    ],
)
def test_adversarial_fts5_syntax_and_wildcards_never_crash(
    adversarial_query: str,
) -> None:
    """Verifies that malformed FTS5 operators, quotes, wildcards, and SQL injection strings never crash."""
    store = HyperSUStore()
    retriever = HyperSUFTSRetriever(store)
    store.add_fact(
        _make_fact(
            "fact-1",
            "EO1 durability invariant",
            "Uses F_FULLFSYNC and fcntl.flock for durable intent latching.",
        )
    )

    # Must not raise sqlite3.OperationalError under any mode
    for mode in ("or", "and", "phrase"):
        results = retriever.coarse_to_fine_retrieve(adversarial_query, mode=mode)
        assert isinstance(results, list)

    # Also verify baseline LIKE scan handles wildcards safely without matching everything on '%'
    like_results = retriever.like_scan_retrieve(adversarial_query)
    if adversarial_query in ("%", "_"):
        assert like_results == []
    store.close()


def test_variable_cardinality_n_ary_hyperedge_attachment() -> None:
    """Verifies that a 4-member `JOINTLY_SUPPORTS` hyperedge is stored and returned with FTS hits."""
    store = HyperSUStore()
    retriever = HyperSUFTSRetriever(store)

    f1 = _make_fact("fact-eo1-fsync", "EO1 fsync", "Requires F_FULLFSYNC before dispatch.")
    f2 = _make_fact("fact-eo1-flock", "EO1 flock", "Requires fcntl.flock LOCK_EX.")
    f3 = _make_fact(
        "fact-eo1-sigkill",
        "EO1 SIGKILL test",
        "Verifies subprocess SIGKILL crash recovery.",
    )
    store.add_facts_batch([f1, f2, f3])

    edge = store.add_hyperedge(
        hyperedge_id="he-eo1-durability-triad",
        relation="JOINTLY_SUPPORTS",
        members=[
            HyperedgeMember("TOPIC", "topic:execution-integrity", role="pillar"),
            HyperedgeMember("FACT", f1.fact_id, role="premise"),
            HyperedgeMember("FACT", f2.fact_id, role="premise"),
            HyperedgeMember("FACT", f3.fact_id, role="verification_oracle"),
        ],
        evidence=[
            HyperedgeEvidenceSpan(
                f.fact_id,
                f.source_id,
                f.file_path,
                f.start_char,
                f.end_char,
                f.content_sha256,
            )
            for f in (f1, f2, f3)
        ],
    )
    assert edge.evidence_digest.startswith("sha256:")
    assert len(edge.members) == 4

    hits = retriever.coarse_to_fine_retrieve(
        "SIGKILL", include_hyperedges=True
    )
    assert len(hits) == 1
    assert len(hits[0]["hyperedges"]) == 1
    attached = hits[0]["hyperedges"][0]
    assert attached["hyperedge_id"] == "he-eo1-durability-triad"
    assert attached["relation"] == "JOINTLY_SUPPORTS"
    assert attached["arity"] == 4

    # Dual-Hypergraph 1-hop expansion (arXiv:2609.28108v2 & arXiv:2609.29282v2):
    # Querying "SIGKILL" with expand_hyperedge_hops=1 bridges across the hyperedge
    # to retrieve the co-supporting F_FULLFSYNC and flock facts (retrieval_hop == 1).
    expanded_hits = retriever.coarse_to_fine_retrieve(
        "SIGKILL",
        limit=10,
        include_hyperedges=True,
        expand_hyperedge_hops=1,
    )
    assert len(expanded_hits) == 3
    assert expanded_hits[0]["fact_id"] == "fact-eo1-sigkill"
    assert expanded_hits[0]["retrieval_hop"] == 0
    hop1_ids = {h["fact_id"] for h in expanded_hits[1:]}
    assert hop1_ids == {"fact-eo1-fsync", "fact-eo1-flock"}
    assert all(h["retrieval_hop"] == 1 for h in expanded_hits[1:])
    assert all(
        h["bridging_hyperedge_id"] == "he-eo1-durability-triad"
        for h in expanded_hits[1:]
    )

    # Falsification (Science Advances PMID:42566539): hyperedges exceeding max_hyperedge_degree
    # are suppressed from 1-hop expansion to prevent hub flooding.
    suppressed_hits = retriever.coarse_to_fine_retrieve(
        "SIGKILL",
        limit=10,
        expand_hyperedge_hops=1,
        max_hyperedge_degree=2,
    )
    assert len(suppressed_hits) == 1
    store.close()


def test_fts5_mutation_adequacy_boundary_and_provenance_oracles(tmp_path: Path) -> None:
    """Covers exact boundary, default-arg, degree-penalty, LIKE scan, and provenance invariants."""
    # 1. Direct sanitize_fts5_query, _fts_query, and escape_like_pattern contracts
    assert sanitize_fts5_query("") == ""
    assert sanitize_fts5_query(None) == ""  # type: ignore[arg-type]
    assert sanitize_fts5_query(12345) == ""  # type: ignore[arg-type]
    assert sanitize_fts5_query("%%%___!!!") == ""
    assert sanitize_fts5_query("alpha ALPHA beta", mode="or") == '"alpha" OR "beta"'
    assert HyperSUFTSRetriever._fts_query("EO1 latch", mode="and") == '"EO1" AND "latch"'
    assert escape_like_pattern(r"a\b%c_d") == r"a\\b\%c\_d"

    # 2. On-disk provenance verification on hop-0 and hop-1 + default limit=10 / include_hyperedges=False
    valid_file = tmp_path / "valid.py"
    valid_text = "alpha_seed_token beta_neighbor_token"
    valid_file.write_text(valid_text, encoding="utf-8")
    valid_sha = "sha256:" + hashlib.sha256(valid_text.encode("utf-8")).hexdigest()

    store = HyperSUStore()
    retriever = HyperSUFTSRetriever(store, workspace_root=tmp_path)

    f_seed = FactRecord(
        fact_id="f-seed",
        episode_id="ep:valid.py",
        label="Seed fact",
        text="alpha_seed_token",
        source_id="src:valid.py",
        file_path="valid.py",
        start_char=0,
        end_char=len("alpha_seed_token"),
        content_sha256=valid_sha,
    )
    f_neighbor_ok = FactRecord(
        fact_id="f-neighbor-ok",
        episode_id="ep:valid.py",
        label="Neighbor ok",
        text="beta_neighbor_token",
        source_id="src:valid.py",
        file_path="valid.py",
        start_char=len("alpha_seed_token "),
        end_char=len(valid_text),
        content_sha256=valid_sha,
    )
    f_bad_hop0 = _make_fact(
        "f-bad-hop0",
        "Bad hop0",
        "alpha_seed_token corrupted",
        file_path="missing.py",
    )
    f_bad_hop1 = _make_fact(
        "f-bad-hop1",
        "Bad hop1",
        "gamma_hop1_corrupted",
        file_path="missing.py",
    )
    store.add_facts_batch([f_seed, f_neighbor_ok, f_bad_hop0, f_bad_hop1])
    store.add_hyperedge(
        hyperedge_id="he-prov-bridge",
        relation="BRIDGES",
        members=[
            HyperedgeMember("FACT", "f-seed", role="premise"),
            HyperedgeMember("FACT", "f-neighbor-ok", role="conclusion"),
            HyperedgeMember("FACT", "f-bad-hop1", role="corrupted"),
        ],
        evidence=[
            HyperedgeEvidenceSpan(
                f_seed.fact_id,
                f_seed.source_id,
                f_seed.file_path,
                f_seed.start_char,
                f_seed.end_char,
                f_seed.content_sha256,
            )
        ],
    )

    # verify_provenance=False must NOT run provenance check even when workspace_root is set,
    # and include_hyperedges=False (default) with expand_hyperedge_hops=0 must NOT attach hyperedges
    raw_hits = retriever.coarse_to_fine_retrieve("alpha_seed_token", verify_provenance=False)
    assert len(raw_hits) == 2
    assert "provenance_valid" not in raw_hits[0]
    assert "hyperedges" not in raw_hits[0]

    # verify_provenance=True filters out f-bad-prov on hop 0 and hop 1, keeping f-seed and f-neighbor-ok
    prov_hits = retriever.coarse_to_fine_retrieve(
        "alpha_seed_token",
        limit=5,
        verify_provenance=True,
        include_hyperedges=False,
        expand_hyperedge_hops=1,
    )
    assert [h["fact_id"] for h in prov_hits] == ["f-seed", "f-neighbor-ok"]
    assert prov_hits[0]["provenance_valid"] is True
    assert prov_hits[1]["provenance_valid"] is True
    assert "hyperedges" not in prov_hits[1]
    expected_bridged_score = float(prov_hits[0]["score"]) / (1.0 + math.log(3))
    assert float(prov_hits[1]["score"]) == pytest.approx(expected_bridged_score)

    # Hop-1 expansion with verify_provenance=False must not attach provenance_valid on hop-1 item
    hop1_unverified = retriever.coarse_to_fine_retrieve(
        "alpha_seed_token",
        limit=5,
        verify_provenance=False,
        expand_hyperedge_hops=1,
    )
    hop1_only = [h for h in hop1_unverified if h["retrieval_hop"] == 1]
    assert len(hop1_only) == 2
    assert "provenance_valid" not in hop1_only[0]

    # 3. Default limit=10 & limit<=0 / limit==1 guards on coarse_to_fine_retrieve and like_scan_retrieve
    assert retriever.coarse_to_fine_retrieve("alpha_seed_token", limit=0) == []
    assert len(retriever.coarse_to_fine_retrieve("alpha_seed_token", limit=1)) == 1
    assert retriever.coarse_to_fine_retrieve("%%%") == []
    for idx in range(13):
        store.add_fact(_make_fact(f"f-bulk-{idx:02d}", f"Bulk {idx}", "bulk_shared_keyword"))
    default_limit_hits = retriever.coarse_to_fine_retrieve("bulk_shared_keyword")
    assert len(default_limit_hits) == 10

    # 2-member hyperedge expansion + remaining = limit - len(results) truncation + default max_hyperedge_degree=12
    f_pair_a = _make_fact("f-pair-a", "Pair A", "unique_pair_seed_kw")
    f_pair_b = _make_fact("f-pair-b", "Pair B", "unique_pair_neighbor_kw")
    f_pair_c = _make_fact("f-pair-c", "Pair C", "unique_pair_extra_kw")
    store.add_facts_batch([f_pair_a, f_pair_b, f_pair_c])
    store.add_hyperedge(
        hyperedge_id="he-binary-2",
        relation="LINKS",
        members=[
            HyperedgeMember("FACT", "f-pair-a", role="left"),
            HyperedgeMember("FACT", "f-pair-b", role="right"),
        ],
        evidence=[
            HyperedgeEvidenceSpan(
                f_pair_a.fact_id,
                f_pair_a.source_id,
                f_pair_a.file_path,
                f_pair_a.start_char,
                f_pair_a.end_char,
                f_pair_a.content_sha256,
            )
        ],
    )
    store.add_hyperedge(
        hyperedge_id="he-binary-extra",
        relation="LINKS",
        members=[
            HyperedgeMember("FACT", "f-pair-a", role="left"),
            HyperedgeMember("FACT", "f-pair-c", role="right"),
        ],
        evidence=[
            HyperedgeEvidenceSpan(
                f_pair_a.fact_id,
                f_pair_a.source_id,
                f_pair_a.file_path,
                f_pair_a.start_char,
                f_pair_a.end_char,
                f_pair_a.content_sha256,
            )
        ],
    )
    pair_hits_limit2 = retriever.coarse_to_fine_retrieve(
        "unique_pair_seed_kw", limit=2, expand_hyperedge_hops=1
    )
    assert len(pair_hits_limit2) == 2

    # 12-member vs 13-member hyperedge against default max_hyperedge_degree=12
    store.add_hyperedge(
        hyperedge_id="he-deg-12",
        relation="CLUSTER_12",
        members=[HyperedgeMember("FACT", "f-pair-a", role="hub")]
        + [HyperedgeMember("FACT", f"f-bulk-{i:02d}", role="leaf") for i in range(11)],
        evidence=[
            HyperedgeEvidenceSpan(
                f_pair_a.fact_id,
                f_pair_a.source_id,
                f_pair_a.file_path,
                f_pair_a.start_char,
                f_pair_a.end_char,
                f_pair_a.content_sha256,
            )
        ],
    )
    store.add_hyperedge(
        hyperedge_id="he-deg-13",
        relation="CLUSTER_13",
        members=[HyperedgeMember("FACT", "f-pair-b", role="hub")]
        + [HyperedgeMember("FACT", f"f-bulk-{i:02d}", role="leaf") for i in range(12)],
        evidence=[
            HyperedgeEvidenceSpan(
                f_pair_b.fact_id,
                f_pair_b.source_id,
                f_pair_b.file_path,
                f_pair_b.start_char,
                f_pair_b.end_char,
                f_pair_b.content_sha256,
            )
        ],
    )
    deg12_hits = retriever.coarse_to_fine_retrieve(
        "unique_pair_seed_kw", limit=20, expand_hyperedge_hops=1
    )
    assert len(deg12_hits) == 14
    deg13_hits = retriever.coarse_to_fine_retrieve(
        "unique_pair_neighbor_kw", limit=20, expand_hyperedge_hops=1
    )
    assert len(deg13_hits) == 2

    default_like_hits = retriever.like_scan_retrieve("bulk_shared_keyword")
    assert len(default_like_hits) == 10
    assert len(retriever.like_scan_retrieve("bulk_shared_keyword", limit=1)) == 1
    assert len(retriever.like_scan_retrieve("bulk_shared_keyword", limit=3)) == 3
    assert retriever.like_scan_retrieve("bulk_shared_keyword", limit=0) == []
    assert retriever.like_scan_retrieve("", limit=5) == []
    store.close()

