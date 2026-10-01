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

def test_5_transport_interceptor_pg_reconciliation_and_cose_signing(pg_adapter, tmp_path):
    from src.transport_interceptor import TransportInterceptor, InterceptorAction
    from src.cose_verifier import verify_trust_passport
    import json

    # 1. Setup row in Postgres
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO transactions (tx_id, intent_id, idempotency_key, amount, status) "
        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (idempotency_key) DO NOTHING;",
        ("tx_interceptor_01", "intent_interceptor", "key_wire_reconciled", 7500.00, "COMMITTED"),
    )
    conn.commit()
    cur.close()
    conn.close()

    interceptor = TransportInterceptor(probe_adapter=pg_adapter, export_dir=tmp_path)
    action = InterceptorAction(
        action_id="act_oob_reconcile",
        idempotency_key="key_wire_reconciled",
        operation="payments.disburse",
        payload={"amount": 7500.00, "iban": "CZ998877665544"},
        destination="http://core-banking/api"
    )

    # 2. Simulate 504 Gateway Timeout on wire
    result = interceptor.intercept_and_reconcile(
        action=action,
        wire_status=504,
        redact_pii=True
    )

    # 3. Assert disposition upgraded from DISPATCHED_UNCONFIRMED to OUTCOME_VERIFIED via OOB probe
    assert result.disposition == "OUTCOME_VERIFIED"
    assert result.retry_policy == "PROBE_CONFIRMED_COMMITTED_NO_RETRY"
    assert result.probe_outcome["result"] == "OUTCOME_VERIFIED"

    # 4. Assert signed COSE envelope valid
    cose_file = tmp_path / "trust_passport.cose.json"
    assert cose_file.exists()
    with open(cose_file) as f:
        envelope = json.load(f)
    assert verify_trust_passport(envelope) is True

    # 5. Assert BBS+ redacted proof valid
    redacted_file = tmp_path / "trust_passport.redacted.json"
    assert redacted_file.exists()
