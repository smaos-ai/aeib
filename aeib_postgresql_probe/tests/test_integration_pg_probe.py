import os
import pytest
import psycopg2
from aeib_postgresql_probe.adapter import PostgresProbeAdapter, ProbeResult

DSN = os.getenv("PG_LEDGER_DSN", "postgresql://postgres:password@localhost:55432/aeib_ledger")

@pytest.fixture(scope="module")
def pg_adapter():
    adapter = PostgresProbeAdapter(DSN, minconn=1, maxconn=3)
    
    # Deterministic Schema Setup
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("""
        DROP TABLE IF EXISTS transactions CASCADE;
        CREATE TABLE transactions (
            tx_id VARCHAR(64) PRIMARY KEY,
            intent_id VARCHAR(64) NOT NULL,
            idempotency_key VARCHAR(128) UNIQUE NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            status VARCHAR(32) NOT NULL,
            commit_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Unconstrained fixture to test multiple row reconciliation conflict
        DROP TABLE IF EXISTS transactions_conflict_fixture CASCADE;
        CREATE TABLE transactions_conflict_fixture (
            tx_id VARCHAR(64),
            intent_id VARCHAR(64),
            idempotency_key VARCHAR(128),
            amount DECIMAL(10, 2),
            status VARCHAR(32),
            commit_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

    yield adapter
    adapter.close()

def test_1_verified_outcome(pg_adapter):
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO transactions (tx_id, intent_id, idempotency_key, amount, status) "
        "VALUES (%s, %s, %s, %s, %s);",
        ("tx_01", "intent_01", "key_exact_match", 1500.00, "COMMITTED"),
    )
    conn.commit()
    cur.close()
    conn.close()

    outcome = pg_adapter.execute_probe("key_exact_match", table_name="transactions")
    assert outcome.result == ProbeResult.OUTCOME_VERIFIED
    assert outcome.evidence["row"]["tx_id"] == "tx_01"
    assert outcome.evidence["row_hash"] is not None
    assert "query_metadata" in outcome.evidence

def test_2_reconciliation_not_found(pg_adapter):
    outcome = pg_adapter.execute_probe("non_existent_key", table_name="transactions")
    assert outcome.result == ProbeResult.RECONCILIATION_NOT_FOUND
    assert outcome.evidence is None

def test_3_reconciliation_conflict_on_duplicate_rows(pg_adapter):
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    # Insert duplicate idempotency keys into unconstrained fixture
    cur.execute(
        "INSERT INTO transactions_conflict_fixture (tx_id, intent_id, idempotency_key, amount, status) "
        "VALUES (%s, %s, %s, %s, %s), (%s, %s, %s, %s, %s);",
        ("tx_dup_1", "intent_02", "key_duplicate", 2000.00, "COMMITTED",
         "tx_dup_2", "intent_02", "key_duplicate", 2000.00, "COMMITTED"),
    )
    conn.commit()
    cur.close()
    conn.close()

    outcome = pg_adapter.execute_probe("key_duplicate", table_name="transactions_conflict_fixture")
    assert outcome.result == ProbeResult.RECONCILIATION_CONFLICT
    assert outcome.evidence["row_count"] == 2
    assert "conflict_hash" in outcome.evidence

def test_4_statement_timeout_active_cancellation_and_pool_recovery(pg_adapter):
    # Trigger statement timeout using raw sleep test helper
    outcome = pg_adapter.execute_raw_sleep_for_test(sleep_seconds=1.5, statement_timeout_ms=200)
    assert outcome.result == ProbeResult.PROBE_TIMEOUT
    assert "exceeded timeout" in outcome.error_message or "canceling statement" in outcome.error_message.lower()

    # Verify connection pool recovered cleanly by running a normal probe
    recovery_outcome = pg_adapter.execute_probe("key_exact_match", table_name="transactions")
    assert recovery_outcome.result == ProbeResult.OUTCOME_VERIFIED
    assert recovery_outcome.evidence["row"]["tx_id"] == "tx_01"
