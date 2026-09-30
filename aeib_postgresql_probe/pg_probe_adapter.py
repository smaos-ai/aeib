import os
import urllib.parse
try:
    import psycopg
except ImportError:
    psycopg = None

class PgProbeAdapter:
    def __init__(self, dsn=None):
        self.dsn = dsn or os.environ.get("PG_LEDGER_DSN", "")
        if not self.dsn:
            raise ValueError("PG_LEDGER_DSN is required.")
        
        # Redact the DSN for safe logging
        try:
            parsed = urllib.parse.urlparse(self.dsn)
            # Safely rebuild the string without the password
            if parsed.username:
                self.redacted_dsn = f"{parsed.scheme}://{parsed.username}:***@{parsed.hostname}:{parsed.port or 5432}{parsed.path}"
            else:
                self.redacted_dsn = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 5432}{parsed.path}"
        except Exception:
            self.redacted_dsn = "postgresql://***:***@***:***/***"

    def probe_intent(self, intent_id):
        if psycopg is None:
            raise RuntimeError("psycopg driver is required but not installed.")
            
        print(f"[PgProbeAdapter] Probing intent {intent_id} on {self.redacted_dsn}")
        with psycopg.connect(self.dsn) as conn:
            # Enforce read committed isolation (default in PG, but good practice to note)
            with conn.cursor() as cur:
                # Assuming index exists on intent_id
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
            return {
                "intent_id": intent_id,
                "status": "RECONCILIATION_NOT_FOUND",
                "probe_source": "postgresql",
            }

        return {
            "operation_id": row[0],
            "intent_id": row[1],
            "amount": row[2],
            "status": row[3],
            "committed_at": row[4].isoformat() if hasattr(row[4], 'isoformat') else str(row[4]),
            "probe_source": "postgresql",
        }
