import json
import hashlib
from enum import Enum
from typing import Optional, Dict, Any, List
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.errors import QueryCanceled

class ProbeResult(Enum):
    OUTCOME_VERIFIED = "OUTCOME_VERIFIED"
    RECONCILIATION_NOT_FOUND = "RECONCILIATION_NOT_FOUND"
    RECONCILIATION_CONFLICT = "RECONCILIATION_CONFLICT"
    PROBE_TIMEOUT = "PROBE_TIMEOUT"

class ProbeOutcome:
    def __init__(self, result: ProbeResult, evidence: Optional[Dict[str, Any]] = None, error_message: str = ""):
        self.result = result
        self.evidence = evidence
        self.error_message = error_message

def project_canonical_json(data: Any) -> str:
    """
    Calibrated Canonical Serialization helper.
    Sorts keys and uses compact delimiters for exercised fields without claiming full RFC 8785 JCS edge-case coverage.
    """
    return json.dumps(data, separators=(',', ':'), sort_keys=True, default=str)

class PostgresProbeAdapter:
    def __init__(self, dsn: str, minconn: int = 1, maxconn: int = 3):
        self.dsn = dsn
        self.pool = ThreadedConnectionPool(minconn, maxconn, dsn)

    def close(self):
        self.pool.closeall()

    def _safe_rollback(self, conn):
        try:
            conn.rollback()
        except Exception:
            pass

    def execute_probe(self, idempotency_key: str, table_name: str = "transactions", statement_timeout_ms: int = 5000) -> ProbeOutcome:
        if not isinstance(statement_timeout_ms, int) or statement_timeout_ms <= 0:
            raise ValueError("statement_timeout_ms must be a positive integer")

        conn = None
        try:
            conn = self.pool.getconn()
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {statement_timeout_ms}")
                
                # We interpolate table_name for flexibility, ensuring it's alphanumeric/underscores to prevent injection
                if not table_name.replace("_", "").isalnum():
                    raise ValueError("Invalid table name")

                cur.execute(f"""
                    SELECT tx_id, intent_id, idempotency_key, amount, status, commit_timestamp 
                    FROM {table_name} 
                    WHERE idempotency_key = %s
                """, (idempotency_key,))
                
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                
                if len(rows) == 0:
                    return ProbeOutcome(ProbeResult.RECONCILIATION_NOT_FOUND, None)
                
                if len(rows) > 1:
                    conflict_data = []
                    for row in rows:
                        conflict_data.append(dict(zip(cols, row)))
                    
                    conflict_json = project_canonical_json(conflict_data)
                    conflict_hash = hashlib.sha256(conflict_json.encode('utf-8')).hexdigest()
                    
                    return ProbeOutcome(ProbeResult.RECONCILIATION_CONFLICT, {
                        "row_count": len(rows),
                        "conflict_hash": conflict_hash,
                        "conflict_data_preview": conflict_data[:2]
                    })
                
                # len(rows) == 1
                row_dict = dict(zip(cols, rows[0]))
                row_json = project_canonical_json(row_dict)
                row_hash = hashlib.sha256(row_json.encode('utf-8')).hexdigest()
                
                return ProbeOutcome(ProbeResult.OUTCOME_VERIFIED, {
                    "row": row_dict,
                    "row_hash": row_hash,
                    "query_metadata": {
                        "table": table_name,
                        "key": idempotency_key
                    }
                })
                
        except QueryCanceled as e:
            if conn:
                self._safe_rollback(conn)
                self.pool.putconn(conn, close=True)
                conn = None
            return ProbeOutcome(ProbeResult.PROBE_TIMEOUT, None, str(e))
        except Exception as e:
            if conn:
                self._safe_rollback(conn)
                self.pool.putconn(conn, close=True)
                conn = None
            raise e
        finally:
            if conn:
                self.pool.putconn(conn)

    def execute_raw_sleep_for_test(self, sleep_seconds: float, statement_timeout_ms: int) -> ProbeOutcome:
        if not isinstance(statement_timeout_ms, int) or statement_timeout_ms <= 0:
            raise ValueError("statement_timeout_ms must be a positive integer")

        conn = None
        try:
            conn = self.pool.getconn()
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {statement_timeout_ms}")
                cur.execute(f"SELECT pg_sleep({sleep_seconds})")
                return ProbeOutcome(ProbeResult.OUTCOME_VERIFIED, {})
        except QueryCanceled as e:
            if conn:
                self._safe_rollback(conn)
                self.pool.putconn(conn, close=True)
                conn = None
            return ProbeOutcome(ProbeResult.PROBE_TIMEOUT, None, str(e))
        except Exception as e:
            if conn:
                self._safe_rollback(conn)
                self.pool.putconn(conn, close=True)
                conn = None
            raise e
        finally:
            if conn:
                self.pool.putconn(conn)
