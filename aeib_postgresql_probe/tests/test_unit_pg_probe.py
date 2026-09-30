import pytest
import datetime
from unittest.mock import patch, MagicMock
from aeib_postgresql_probe.pg_probe_adapter import PgProbeAdapter, canonical_evidence_digest

@pytest.mark.unit
@patch("aeib_postgresql_probe.pg_probe_adapter.psycopg")
def test_unit_probe_committed_row(mock_psycopg):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_psycopg.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    
    mock_cur.fetchone.return_value = (
        "op_123", "intent_abc", 100.0, "COMMITTED", datetime.datetime(2026, 9, 30, 12, 0, 0)
    )

    adapter = PgProbeAdapter(dsn="postgresql://user:secret@localhost:5432/ledger")
    assert adapter.redacted_dsn == "postgresql://user:***@localhost:5432/ledger"
    
    result = adapter.probe_intent("intent_abc")
    assert result["status"] == "COMMITTED"
    assert result["amount"] == 100.0
    assert "2026-09-30" in result["committed_at"]
    assert "evidence_digest" in result
    assert len(result["evidence_digest"]) == 64

@pytest.mark.unit
@patch("aeib_postgresql_probe.pg_probe_adapter.psycopg")
def test_unit_probe_absent_row(mock_psycopg):
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_psycopg.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = None

    adapter = PgProbeAdapter(dsn="postgresql://user:secret@localhost:5432/ledger")
    result = adapter.probe_intent("intent_xyz")
    assert result["status"] == "RECONCILIATION_NOT_FOUND"
    assert "evidence_digest" in result

@pytest.mark.unit
def test_unit_dsn_redaction():
    adapter = PgProbeAdapter(dsn="postgresql://admin:super_secret@pg.prod.internal:5432/banking_db")
    assert "super_secret" not in adapter.redacted_dsn
    assert adapter.redacted_dsn == "postgresql://admin:***@pg.prod.internal:5432/banking_db"

@pytest.mark.unit
def test_unit_canonical_evidence_digest():
    rec1 = {"status": "COMMITTED", "intent_id": "abc", "amount": 100.0}
    rec2 = {"amount": 100.0, "status": "COMMITTED", "intent_id": "abc"}
    # JCS canonicalization guarantees invariant hash regardless of dict key insertion order
    assert canonical_evidence_digest(rec1) == canonical_evidence_digest(rec2)
