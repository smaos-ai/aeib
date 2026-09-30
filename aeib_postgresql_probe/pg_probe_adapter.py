import os
import json
import hashlib
import urllib.parse

try:
    import psycopg
except ImportError:
    try:
        import psycopg2 as psycopg
    except ImportError:
        psycopg = None

def canonical_evidence_digest(record: dict) -> str:
    """Computes SHA-256 over JCS-compatible canonical representation."""
    canonical_json = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

class PgProbeAdapter:
    def __init__(self, dsn=None, connect_timeout_sec: int = 3, statement_timeout_ms: int = 5000):
        self.dsn = dsn or os.environ.get("PG_LEDGER_DSN", "")
        if not self.dsn:
            raise ValueError("PG_LEDGER_DSN is required.")
        
        self.connect_timeout_sec = connect_timeout_sec
        self.statement_timeout_ms = statement_timeout_ms

        # Redact the DSN for safe logging and reporting
        try:
            parsed = urllib.parse.urlparse(self.dsn)
            user_part = f"{parsed.username}:***@" if parsed.username else ""
            port_part = f":{parsed.port}" if parsed.port else ""
            self.redacted_dsn = f"{parsed.scheme}://{user_part}{parsed.hostname or 'localhost'}{port_part}{parsed.path}"
        except Exception:
            self.redacted_dsn = "postgresql://***:***@***:***/***"

    def probe_intent(self, intent_id: str) -> dict:
        if psycopg is None:
            raise RuntimeError("psycopg or psycopg2 driver is required but neither is installed.")
            
        # Parameterized query with defined statement_timeout and connect_timeout
        connect_kwargs = {}
        # psycopg2 / psycopg options
        options_str = f"-c statement_timeout={self.statement_timeout_ms}"
        
        with psycopg.connect(
            self.dsn,
            connect_timeout=self.connect_timeout_sec,
            options=options_str,
        ) as conn:
            # Enforce READ COMMITTED isolation level
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT operation_id, intent_id, amount, status, committed_at
                    FROM operations
                    WHERE intent_id = %s
                    ORDER BY committed_at DESC
                    LIMIT 1
                    """,
                    (intent_id,),
                )
                row = cur.fetchone()

        if row is None:
            res = {
                "intent_id": intent_id,
                "status": "RECONCILIATION_NOT_FOUND",
                "probe_source": "postgresql",
            }
            res["evidence_digest"] = canonical_evidence_digest(res)
            return res

        committed_at_str = row[4].isoformat() if hasattr(row[4], 'isoformat') else str(row[4])
        res = {
            "operation_id": str(row[0]),
            "intent_id": str(row[1]),
            "amount": float(row[2]),
            "status": str(row[3]),
            "committed_at": committed_at_str,
            "probe_source": "postgresql",
        }
        res["evidence_digest"] = canonical_evidence_digest(res)
        return res
