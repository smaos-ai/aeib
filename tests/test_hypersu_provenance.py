"""Provenance Falsification, Crash-Recovery, & Read-Only EO1 Integration Tests (`src/hypersu_store.py`)."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import pytest

from src.eo1_write_before_execute import (
    CaidAlreadyCommittedError,
    LatchedCaidExecutionHaltedError,
    PreDispatchIntentInterlock,
    compute_caid,
)
from src.hypersu_fts import HyperSUFTSRetriever
from src.hypersu_store import (
    FactRecord,
    HyperedgeEvidenceSpan,
    HyperedgeMember,
    HyperSUStore,
)


def test_provenance_valid_and_detects_mutated_or_deleted_source_files(
    tmp_path: Path,
) -> None:
    """
    Falsification vectors from Section 6:
      - Valid source file slice verifies with `PROVENANCE_OK`.
      - Mutating 1 byte of the source file invalidates provenance (`SOURCE_DIGEST_MISMATCH`)
        and filters the fact out when `verify_provenance=True`.
      - Deleting the source file invalidates provenance (`SOURCE_FILE_MISSING`).
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    sample_file = src_dir / "sample_policy.py"
    content = (
        "def enforce_latch() -> bool:\n"
        "    # F_FULLFSYNC durability check before dispatch\n"
        "    return True\n"
    )
    sample_file.write_text(content, encoding="utf-8")

    store = HyperSUStore(tmp_path / "hypersu.sqlite")
    retriever = HyperSUFTSRetriever(store, workspace_root=tmp_path)

    start_c = content.index("# F_FULLFSYNC")
    end_c = content.index("return True") + len("return True")
    fact = store.ingest_file_span(
        workspace_root=tmp_path,
        rel_file_path="src/sample_policy.py",
        start_char=start_c,
        end_char=end_c,
        label="enforce_latch durability clause",
    )

    # 1. Unmodified source file passes provenance check
    prov_ok = store.verify_fact_provenance(fact.fact_id, tmp_path)
    assert prov_ok.valid is True
    assert prov_ok.status_code == "PROVENANCE_OK"
    hits_ok = retriever.coarse_to_fine_retrieve(
        "F_FULLFSYNC", verify_provenance=True
    )
    assert len(hits_ok) == 1
    assert hits_ok[0]["provenance_valid"] is True

    # 2. Falsification: Mutate source bytes on disk and query again
    sample_file.write_text(
        content.replace("return True", "return False"), encoding="utf-8"
    )
    prov_mutated = store.verify_fact_provenance(fact.fact_id, tmp_path)
    assert prov_mutated.valid is False
    assert prov_mutated.status_code == "SOURCE_DIGEST_MISMATCH"
    assert (
        retriever.coarse_to_fine_retrieve("F_FULLFSYNC", verify_provenance=True)
        == []
    )

    # 3. Falsification: Delete source file on disk and query again
    sample_file.unlink()
    prov_deleted = store.verify_fact_provenance(fact.fact_id, tmp_path)
    assert prov_deleted.valid is False
    assert prov_deleted.status_code == "SOURCE_FILE_MISSING"
    assert (
        retriever.coarse_to_fine_retrieve("F_FULLFSYNC", verify_provenance=True)
        == []
    )
    store.close()


def test_invalid_span_bounds_rejected_at_insertion(tmp_path: Path) -> None:
    """Verifies that mismatched text length vs (end_char - start_char) raises ValueError."""
    store = HyperSUStore()
    with pytest.raises(ValueError) as exc_info:
        store.add_fact(
            FactRecord(
                fact_id="bad-span",
                episode_id="ep-1",
                label="bad",
                text="short",
                source_id="src-1",
                file_path="src/eo1_write_before_execute.py",
                start_char=10,
                end_char=100,
                content_sha256="sha256:" + ("0" * 64),
            )
        )
    assert "(90) for bad-span" in str(exc_info.value)

    # Batch insertion boundary checks (start_char > 0 valid so end_char - start_char != end_char + start_char)
    valid_batch_fact = FactRecord(
        fact_id="batch-ok",
        episode_id="ep-1",
        label="ok",
        text="abc",
        source_id="src-1",
        file_path="src/eo1_write_before_execute.py",
        start_char=5,
        end_char=8,
        content_sha256="sha256:" + ("0" * 64),
    )
    store.add_facts_batch([valid_batch_fact])
    with pytest.raises(Exception):
        valid_batch_fact.label = "mutated"  # type: ignore[misc]

    with pytest.raises(ValueError):
        store.add_facts_batch(
            [
                FactRecord(
                    fact_id="batch-bad-len",
                    episode_id="ep-1",
                    label="bad",
                    text="abc",
                    source_id="src-1",
                    file_path="f.py",
                    start_char=2,
                    end_char=10,
                    content_sha256="sha256:" + ("0" * 64),
                )
            ]
        )

    # ingest_file_span directory (not is_file -> FileNotFoundError vs IsADirectoryError) & out-of-bounds span
    f_disk = tmp_path / "doc.txt"
    f_disk.write_text("hello world", encoding="utf-8")
    sub_dir = tmp_path / "a_directory"
    sub_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        store.ingest_file_span(tmp_path, "a_directory", 0, 5, "lbl")
    with pytest.raises(ValueError, match="out of bounds"):
        store.ingest_file_span(tmp_path, "doc.txt", 8, 3, "lbl")

    mem = HyperedgeMember("FACT", "batch-ok")
    with pytest.raises(Exception):
        mem.role = "mutated"  # type: ignore[misc]
    ev = HyperedgeEvidenceSpan("batch-ok", "s", "f", 0, 3, "sha256:" + ("0" * 64))
    with pytest.raises(ValueError):
        store.add_hyperedge("he-1-mem", "REL", [mem], [ev])

    # verify_fact_provenance: FACT_NOT_FOUND, SOURCE_DECODE_ERROR, and SPAN_SLICE_MISMATCH
    nf = store.verify_fact_provenance("nonexistent-fact-id", tmp_path)
    assert (nf.valid, nf.status_code, nf.start_char, nf.end_char) == (
        False,
        "FACT_NOT_FOUND",
        0,
        0,
    )
    with pytest.raises(Exception):
        nf.valid = True  # type: ignore[misc]

    bad_utf8_file = tmp_path / "binary.bin"
    bad_utf8_bytes = b"\xff\xfe\xfd"
    bad_utf8_file.write_bytes(bad_utf8_bytes)
    from src.hypersu_store import compute_sha256_hex

    store.add_fact(
        FactRecord(
            fact_id="f-bad-utf8",
            episode_id="ep",
            label="bin",
            text="abc",
            source_id="s",
            file_path="binary.bin",
            start_char=0,
            end_char=3,
            content_sha256=f"sha256:{compute_sha256_hex(bad_utf8_bytes)}",
        )
    )
    dec_err = store.verify_fact_provenance("f-bad-utf8", tmp_path)
    assert (dec_err.valid, dec_err.status_code) == (False, "SOURCE_DECODE_ERROR")

    store.add_fact(
        FactRecord(
            fact_id="f-slice-mismatch",
            episode_id="ep",
            label="slice",
            text="XXXXX",
            source_id="s",
            file_path="doc.txt",
            start_char=0,
            end_char=5,
            content_sha256=f"sha256:{compute_sha256_hex(b'hello world')}",
        )
    )
    slice_err = store.verify_fact_provenance("f-slice-mismatch", tmp_path)
    assert (slice_err.valid, slice_err.status_code) == (False, "SPAN_SLICE_MISMATCH")
    store.close()


def test_sigkill_mid_ingestion_preserves_fts5_sync_integrity(
    tmp_path: Path,
) -> None:
    """
    Falsification vector: kill process (`SIGKILL`) during ingestion.
    Verifies that SQLite atomic transactions keep `facts` and `fact_fts` strictly
    synchronized (`check_fts_sync_integrity() == True`) after a hard kill.
    """
    db_file = tmp_path / "crash_test.sqlite"
    repo_root = Path(__file__).resolve().parent.parent

    child_code = f"""
import os, signal, sys
sys.path.insert(0, {str(repo_root)!r})
from src.hypersu_store import FactRecord, HyperSUStore

store = HyperSUStore({str(db_file)!r})
for i in range(25):
    txt = f"Committed durability fact number {{i}} with F_FULLFSYNC"
    store.add_fact(FactRecord(
        fact_id=f"committed-{{i}}",
        episode_id="ep-1",
        label=f"fact {{i}}",
        text=txt,
        source_id="src-1",
        file_path="src/eo1_write_before_execute.py",
        start_char=0,
        end_char=len(txt),
        content_sha256="sha256:" + ("b" * 64),
    ))

# Begin an uncommitted manual write and immediately SIGKILL the process
store.conn.execute("BEGIN IMMEDIATE")
store.conn.execute(
    "INSERT INTO facts VALUES ('torn-1','ep','lbl','torn','s','f',0,4,'sha','v1','now')"
)
os.kill(os.getpid(), signal.SIGKILL)
"""
    proc = subprocess.run(
        [sys.executable, "-c", child_code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0

    reopened = HyperSUStore(db_file)
    assert reopened.check_fts_sync_integrity() is True
    assert reopened.get_fact("torn-1") is None
    assert reopened.get_fact("committed-0") is not None
    assert reopened.get_fact("committed-24") is not None
    reopened.close()


def test_eo1_read_only_explanation_separation_of_authority(
    tmp_path: Path,
) -> None:
    """
    Section 7 Separation of Authority test:
    When EO1 latches an intent on transport drop (`EFFECT_INDETERMINATE`),
    `HyperSUStore.explain_eo1_block` returns the source-grounded policy facts,
    prior intent record, and hyperedge evidence WITHOUT mutating EO1 state.
    """
    repo_root = Path(__file__).resolve().parent.parent
    store = HyperSUStore(tmp_path / "eo1_explain.sqlite")

    eo1_rel = "src/eo1_write_before_execute.py"
    eo1_text = (repo_root / eo1_rel).read_text(encoding="utf-8")
    idx_fsync = eo1_text.index("def _fsync_fd")
    idx_reconcile = eo1_text.index("def reconcile_out_of_band")

    f_fsync = store.ingest_file_span(
        workspace_root=repo_root,
        rel_file_path=eo1_rel,
        start_char=idx_fsync,
        end_char=idx_fsync + 180,
        label="EO1 _fsync_fd durability helper",
    )
    f_reconcile = store.ingest_file_span(
        workspace_root=repo_root,
        rel_file_path=eo1_rel,
        start_char=idx_reconcile,
        end_char=idx_reconcile + 180,
        label="EO1 reconcile_out_of_band resolution gate",
    )
    store.add_hyperedge(
        hyperedge_id="he-eo1-indeterminate-recovery",
        relation="JOINTLY_SUPPORTS",
        members=[
            HyperedgeMember("FACT", f_fsync.fact_id, role="durability"),
            HyperedgeMember("FACT", f_reconcile.fact_id, role="reconciliation"),
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
            for f in (f_fsync, f_reconcile)
        ],
    )

    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "eo1_ledger.jsonl",
        output_state_dir=tmp_path / "latches",
    )
    payload = {"action": "wire_transfer", "amount_minor": 50000, "recipient": "acct-99"}
    caid = compute_caid(payload)

    def _timeout_transport() -> dict:
        raise TimeoutError("simulated 504 gateway timeout after wire send")

    with pytest.raises(RuntimeError, match="EFFECT_INDETERMINATE"):
        interlock.dispatch(
            target_uri="http://127.0.0.1:9/wire",
            tool_name="wire_transfer",
            payload=payload,
            dispatch_fn=_timeout_transport,
            intent_id="intent-timeout-01",
        )

    assert interlock.is_caid_latched(caid) is True

    explanation = store.explain_eo1_block(
        interlock,
        caid,
        repo_root,
        mcp_tool_annotations={"readOnlyHint": True, "idempotentHint": True},
        mcp_server_pinned=False,
    )
    assert explanation["authority"] == "EO1_SOLE_EXECUTION_AUTHORITY"
    assert explanation["hypersu_role"] == "READ_ONLY_PROVENANCE_EXPLANATION"
    assert explanation["block_reason"] == "EFFECT_INDETERMINATE_LATCHED"
    assert explanation["reconciliation_required"] is True
    assert explanation["diagnosis_status"] == "GROUNDED_DIAGNOSIS"
    assert explanation["abstention_reasons"] == []
    assert explanation["diagnosis_replay_sha256"].startswith("sha256:")
    assert (
        explanation["mcp_annotation_status"]
        == "UNTRUSTED_HINT_IGNORED_ENFORCE_EO1"
    )
    mutating_pinned = store.explain_eo1_block(
        interlock,
        caid,
        repo_root,
        mcp_tool_annotations={"readOnlyHint": False, "idempotentHint": False, "destructiveHint": True},
        mcp_server_pinned=True,
    )
    assert (
        mutating_pinned["mcp_annotation_status"]
        == "CONSERVATIVE_MUTATING_ENFORCE_EO1"
    )
    assert explanation["prior_intent_record"]["intent_id"] == "intent-timeout-01"
    assert len(explanation["policy_facts"]) == 2
    assert all(pf["provenance_valid"] is True for pf in explanation["policy_facts"])
    assert len(explanation["supporting_hyperedges"]) == 1

    # Verify HyperSU did NOT mutate EO1 latch state
    assert interlock.is_caid_latched(caid) is True

    # Falsification (AgentTriage arXiv:2610.30738v1): when mandatory evidence is missing
    # (e.g., manual latch without a canonical DISPATCH_INTENT record on disk),
    # explain_eo1_block must abstain with ABSTAIN_MISSING_MANDATORY_EVIDENCE.
    manual_caid = "caid-manual-without-ledger-intent"
    interlock.latch_intent(manual_caid, reason="OPERATOR_EMERGENCY_LATCH")
    abstained = store.explain_eo1_block(interlock, manual_caid, repo_root)
    assert abstained["diagnosis_status"] == "ABSTAIN_MISSING_MANDATORY_EVIDENCE"
    assert "MISSING_CANONICAL_DISPATCH_INTENT_RECORD" in abstained["abstention_reasons"]
    store.close()


def test_mhg_mem_provenance_preserving_state_evolution(tmp_path: Path) -> None:
    """
    Tests MHG-Mem (arXiv:2610.29995v1) provenance-preserving state evolution:
    When a source file changes on disk, `refresh_fact_evolution` ingests the new span,
    removes the superseded fact from active FTS5 search, links `new_fact -> old_fact`
    via an `EVOLVES_FROM` hyperedge, and preserves `check_fts_sync_integrity()`.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    policy_file = src_dir / "policy.py"
    v1_text = "MAX_RETRY_ATTEMPTS = 3  # v1 policy\n"
    policy_file.write_text(v1_text, encoding="utf-8")

    store = HyperSUStore(tmp_path / "evolution.sqlite")
    retriever = HyperSUFTSRetriever(store, workspace_root=tmp_path)

    f_v1 = store.ingest_file_span(
        workspace_root=tmp_path,
        rel_file_path="src/policy.py",
        start_char=0,
        end_char=len(v1_text.strip()),
        label="retry limit policy",
    )
    assert len(retriever.coarse_to_fine_retrieve("v1", verify_provenance=True)) == 1

    # Mutate file to v2 on disk
    v2_text = "MAX_RETRY_ATTEMPTS = 0  # v2 strict zero-retry policy\n"
    policy_file.write_text(v2_text, encoding="utf-8")
    assert retriever.coarse_to_fine_retrieve("v1", verify_provenance=True) == []

    # Evolve fact state
    f_v2, evo_he_id = store.refresh_fact_evolution(
        workspace_root=tmp_path,
        old_fact_id=f_v1.fact_id,
        new_start_char=0,
        new_end_char=len(v2_text.strip()),
        label="retry limit policy v2",
    )
    assert f_v2.fact_id != f_v1.fact_id
    assert store.check_fts_sync_integrity() is True

    # Old text is no longer in active FTS5; new text is retrievable and provenance-valid
    assert retriever.coarse_to_fine_retrieve("v1", verify_provenance=True) == []
    hits_v2 = retriever.coarse_to_fine_retrieve(
        "zero-retry", verify_provenance=True, include_hyperedges=True
    )
    assert len(hits_v2) == 1
    assert hits_v2[0]["fact_id"] == f_v2.fact_id
    assert hits_v2[0]["provenance_valid"] is True
    assert hits_v2[0]["hyperedges"][0]["hyperedge_id"] == evo_he_id
    assert hits_v2[0]["hyperedges"][0]["relation"] == "EVOLVES_FROM"
    store.close()


def test_ingest_file_span_with_eo1_latch_prevents_duplicate_memory_writes(
    tmp_path: Path,
) -> None:
    """
    Tests `HyperSUStore.ingest_file_span_with_eo1_latch()` (Vector 1: EO1-latched
    persistent memory ingestion):
      - Clean ingestion commits once and blocks duplicate re-ingestion (`CaidAlreadyCommittedError`).
      - Transport-dropped ingestion latches `EFFECT_INDETERMINATE` and blocks blind retry
        (`IndeterminateEffectLatchedError`) until out-of-band reconciliation.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    doc_file = src_dir / "memory_note.py"
    text = "DURABLE_WAL_REQUIRED = True\n"
    doc_file.write_text(text, encoding="utf-8")

    store = HyperSUStore(tmp_path / "eo1_memory.sqlite")
    interlock = PreDispatchIntentInterlock(
        ledger_path=tmp_path / "mem_ledger.jsonl",
        output_state_dir=tmp_path / "mem_latches",
    )

    fact, receipt = store.ingest_file_span_with_eo1_latch(
        interlock=interlock,
        workspace_root=tmp_path,
        rel_file_path="src/memory_note.py",
        start_char=0,
        end_char=12,
        label="part 1",
    )
    assert receipt.receipt.status == "RECONCILED"
    assert receipt.response["status"] == "INGESTED"
    assert store.get_fact(fact.fact_id) is not None

    with pytest.raises(CaidAlreadyCommittedError):
        store.ingest_file_span_with_eo1_latch(
            interlock=interlock,
            workspace_root=tmp_path,
            rel_file_path="src/memory_note.py",
            start_char=0,
            end_char=12,
            label="part 1 duplicate",
        )

    # Second distinct span with transport drop latches indeterminate
    with pytest.raises(RuntimeError, match="EFFECT_INDETERMINATE"):
        store.ingest_file_span_with_eo1_latch(
            interlock=interlock,
            workspace_root=tmp_path,
            rel_file_path="src/memory_note.py",
            start_char=12,
            end_char=len(text.strip()),
            label="part 2",
            simulate_transport_drop=True,
        )

    with pytest.raises(LatchedCaidExecutionHaltedError):
        store.ingest_file_span_with_eo1_latch(
            interlock=interlock,
            workspace_root=tmp_path,
            rel_file_path="src/memory_note.py",
            start_char=12,
            end_char=len(text.strip()),
            label="part 2 blind retry",
        )
    store.close()

