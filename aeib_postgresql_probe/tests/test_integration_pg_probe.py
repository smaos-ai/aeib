import os
import json
import time
import pytest
from aeib_postgresql_probe.pg_probe_adapter import PgProbeAdapter, canonical_evidence_digest, _psycopg

TEST_PG_DSN = os.environ.get("PG_LEDGER_DSN", "postgresql://postgres@localhost:55432/aeib_ledger")

def is_pg_available(dsn: str) -> bool:
    try:
        with _psycopg.connect(dsn, connect_timeout=1) as conn:
            return True
    except Exception:
        return False

@pytest.fixture(scope="module")
def pg_live_setup():
    if not is_pg_available(TEST_PG_DSN):
        pytest.skip(f"PostgreSQL server not reachable at {TEST_PG_DSN}. Skipping live integration suite.")

    with _psycopg.connect(TEST_PG_DSN) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    operation_id VARCHAR(64) PRIMARY KEY,
                    intent_id VARCHAR(64) NOT NULL,
                    amount NUMERIC(12, 2) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    committed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_operations_intent_id ON operations(intent_id);
                TRUNCATE TABLE operations;
            """)
            # Seed committed test record
            cur.execute("""
                INSERT INTO operations (operation_id, intent_id, amount, status, committed_at)
                VALUES ('op_live_committed_001', 'intent_live_test_001', 100.00, 'COMMITTED', '2026-09-30 20:00:00+00');
            """)
            conn.commit()

    yield TEST_PG_DSN

@pytest.mark.integration
def test_live_pg_probe_committed_row(pg_live_setup):
    adapter = PgProbeAdapter(dsn=pg_live_setup)
    res = adapter.probe_intent("intent_live_test_001")

    assert res["status"] == "COMMITTED"
    assert res["operation_id"] == "op_live_committed_001"
    assert res["amount"] == 100.0
    assert res["probe_source"] == "postgresql"
    assert "evidence_digest" in res
    assert len(res["evidence_digest"]) == 64

@pytest.mark.integration
def test_live_pg_probe_absent_row(pg_live_setup):
    adapter = PgProbeAdapter(dsn=pg_live_setup)
    res = adapter.probe_intent("intent_absent_99999")

    assert res["status"] == "RECONCILIATION_NOT_FOUND"
    assert res["probe_source"] == "postgresql"
    assert res["intent_id"] == "intent_absent_99999"
    assert "evidence_digest" in res

@pytest.mark.integration
def test_live_pg_sql_injection_defense(pg_live_setup):
    adapter = PgProbeAdapter(dsn=pg_live_setup)
    # Attempt SQL injection: should be treated as literal string and not match
    malicious_intent = "' OR 1=1; DROP TABLE operations; --"
    res = adapter.probe_intent(malicious_intent)

    assert res["status"] == "RECONCILIATION_NOT_FOUND"
    # Ensure table was not dropped
    with _psycopg.connect(pg_live_setup) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM operations;")
            count = cur.fetchone()[0]
            assert count >= 1

@pytest.mark.integration
def test_live_pg_evidence_capture(pg_live_setup):
    adapter = PgProbeAdapter(dsn=pg_live_setup)
    
    # Capture database version, query plan, and isolation level
    with _psycopg.connect(pg_live_setup) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            pg_version = cur.fetchone()[0]

            cur.execute("SHOW transaction_isolation;")
            isolation_level = cur.fetchone()[0]

            cur.execute("EXPLAIN ANALYZE SELECT operation_id, intent_id, amount, status, committed_at FROM operations WHERE intent_id = 'intent_live_test_001' ORDER BY committed_at DESC LIMIT 1;")
            query_plan = [line[0] for line in cur.fetchall()]

    # Measure warmup + timed samples
    latencies_ms = []
    # Warmup
    for _ in range(10):
        adapter.probe_intent("intent_live_test_001")

    # 50 measured trials
    for _ in range(50):
        t0 = time.perf_counter()
        adapter.probe_intent("intent_live_test_001")
        latencies_ms.append((time.perf_counter() - t0) * 1000.0)

    latencies_ms.sort()
    from aeib_postgresql_probe.pg_probe_adapter import _percentile_nearest_rank
    mean_latency = sum(latencies_ms) / len(latencies_ms)
    p50_latency = _percentile_nearest_rank(latencies_ms, 0.50)
    p95_latency = _percentile_nearest_rank(latencies_ms, 0.95)
    p99_latency = _percentile_nearest_rank(latencies_ms, 0.99)

    evidence = {
        "database_engine": "PostgreSQL",
        "database_version": pg_version,
        "isolation_level": isolation_level,
        "target_table": "operations",
        "index_name": "idx_operations_intent_id",
        "query_plan": query_plan,
        "dsn_redacted": adapter.redacted_dsn,
        "sample_size": len(latencies_ms),
        "timing_methodology": "time.perf_counter() on dedicated loopback connection",
        "percentile_method": "nearest_rank",
        "latency_metrics_ms": {
            "mean": round(mean_latency, 3),
            "p50": round(p50_latency, 3),
            "p95": round(p95_latency, 3),
            "p99": round(p99_latency, 3),
            "min": round(latencies_ms[0], 3),
            "max": round(latencies_ms[-1], 3)
        }
    }

    import pathlib
    out_dir = pathlib.Path(__file__).resolve().parent.parent / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "PG_INTEGRATION_EVIDENCE.json", "w") as f:
        json.dump(evidence, f, indent=2)

    assert "PostgreSQL 16" in pg_version
    assert evidence["latency_metrics_ms"]["p50"] > 0.0

@pytest.mark.integration
def test_live_pg_statement_timeout_cancellation(pg_live_setup):
    """
    Verifies that the statement_timeout mechanism correctly cancels queries.
    Tests the exact SET syntax used by the adapter against the live database.
    """
    adapter = PgProbeAdapter(dsn=pg_live_setup, statement_timeout_ms=50) # 50ms timeout
    
    try:
        from psycopg.errors import QueryCanceled
    except ImportError:
        from psycopg2.errors import QueryCanceled
        
    with pytest.raises(QueryCanceled):
        with _psycopg.connect(adapter.dsn, connect_timeout=adapter.connect_timeout_sec) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # Test the exact same query syntax used by the adapter
                cur.execute(f"SET statement_timeout = {int(adapter.statement_timeout_ms)}")
                cur.execute("SELECT pg_sleep(0.5)") # Will run pg_sleep(0.5) and timeout!
