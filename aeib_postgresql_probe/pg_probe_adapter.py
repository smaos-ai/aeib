"""
pg_probe_adapter.py — PostgreSQL Authoritative Outcome-Probe Adapter
AEIB / Sovereign Multi-Agent OS (SMAOS)

Performs a parameterized, read-only SELECT against the operations table
to determine whether an intent has a committed ledger entry.

Driver compatibility
--------------------
Tries psycopg (v3) first; falls back to psycopg2 if absent.
If neither is installed, `PgProbeAdapter` raises ImportError on
instantiation so that SQLite-only benchmark code remains importable
without any PostgreSQL dependency.

Transaction semantics
---------------------
Each probe uses a fresh connection, autocommit mode, READ COMMITTED
isolation, and a per-statement timeout enforced via a post-connect
``SET statement_timeout`` command (compatible with both psycopg and
psycopg2).  The probe is strictly read-only; no writes are performed.

Evidence digest
---------------
``canonical_evidence_digest`` hashes the response dict *before*
the ``evidence_digest`` key is added.  Callers must observe this
ordering — build the full payload, call the function, then attach
the returned hex digest as ``res["evidence_digest"]``.
"""

import os
import json
import hashlib
import urllib.parse
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Driver detection — intentionally deferred to instantiation time so that
# importing this module does not fail in SQLite-only environments.
# ---------------------------------------------------------------------------
try:
    import psycopg as _psycopg          # psycopg v3
    _DRIVER = "psycopg"
except ImportError:
    try:
        import psycopg2 as _psycopg     # type: ignore[no-redef]
        _DRIVER = "psycopg2"
    except ImportError:
        _psycopg = None                 # type: ignore[assignment]
        _DRIVER = None


def _percentile_nearest_rank(values: list, q: float) -> float:
    """
    Nearest-rank percentile (1-indexed ordinal).

    For a sorted list of n values and quantile q in (0, 1]:
        rank = ceil(q * n)  → index rank - 1

    This matches the method reported in PG_INTEGRATION_EVIDENCE.json
    under ``percentile_method: nearest_rank``.
    """
    if not values:
        raise ValueError("values must not be empty")
    import math
    rank = math.ceil(q * len(values))
    return sorted(values)[rank - 1]


def canonical_evidence_digest(record: Dict[str, Any]) -> str:
    """
    Returns a hex SHA-256 digest of the record's documented deterministic
    JSON representation (sort_keys=True, compact separators, UTF-8).

    CONTRACT: the caller must NOT include the ``evidence_digest`` key in
    ``record`` before calling this function.  The key is appended after
    the digest is computed.
    """
    canonical_json = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class PgProbeAdapter:
    """
    Stateless, read-only probe against a PostgreSQL ``operations`` table.

    Parameters
    ----------
    dsn : str, optional
        PostgreSQL DSN (``postgresql://user:pass@host:port/dbname``).
        Falls back to the ``PG_LEDGER_DSN`` environment variable.
    connect_timeout_sec : int
        TCP connection timeout in seconds (default 3).
    statement_timeout_ms : int
        Per-statement server-side timeout in milliseconds (default 5000).
        Applied via ``SET statement_timeout = <n>`` after connecting, which
        is compatible with both psycopg v3 and psycopg2.
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        connect_timeout_sec: int = 3,
        statement_timeout_ms: int = 5000,
    ) -> None:
        if _psycopg is None:
            raise ImportError(
                "PostgreSQL probe requires psycopg (v3) or psycopg2. "
                "Install with: pip install psycopg2-binary"
            )

        self.dsn = dsn or os.environ.get("PG_LEDGER_DSN", "")
        if not self.dsn:
            raise ValueError("A PostgreSQL DSN is required (pass dsn= or set PG_LEDGER_DSN).")

        self.connect_timeout_sec = connect_timeout_sec
        self.statement_timeout_ms = statement_timeout_ms

        # Redact credentials for safe logging / evidence output.
        try:
            parsed = urllib.parse.urlparse(self.dsn)
            user_part = f"{parsed.username}:***@" if parsed.username else ""
            port_part = f":{parsed.port}" if parsed.port else ""
            self.redacted_dsn = (
                f"{parsed.scheme}://{user_part}"
                f"{parsed.hostname or 'localhost'}{port_part}{parsed.path}"
            )
        except Exception:
            self.redacted_dsn = "postgresql://***:***@***:***/***"

    def probe_intent(self, intent_id: str) -> Dict[str, Any]:
        """
        Query the ``operations`` table for the most-recent committed row
        matching ``intent_id``.

        Returns a dict with ``status`` == ``"COMMITTED"`` on success,
        or ``"RECONCILIATION_NOT_FOUND"`` when no row exists.
        An ``evidence_digest`` key is always present.

        Raises
        ------
        RuntimeError
            If the connection or query fails.
        """
        with _psycopg.connect(
            self.dsn,
            connect_timeout=self.connect_timeout_sec,
        ) as conn:
            # Autocommit — read-only probe, no transaction needed.
            conn.autocommit = True

            with conn.cursor() as cur:
                # SET does not uniformly support parameterization across drivers.
                # Validate as integer and format directly.
                timeout_val = int(self.statement_timeout_ms)
                if timeout_val < 0:
                    timeout_val = 0
                cur.execute(f"SET statement_timeout = {timeout_val}")

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
            res: Dict[str, Any] = {
                "intent_id": intent_id,
                "status": "RECONCILIATION_NOT_FOUND",
                "probe_source": "postgresql",
            }
            res["evidence_digest"] = canonical_evidence_digest(res)
            return res

        committed_at_str = (
            row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4])
        )
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
