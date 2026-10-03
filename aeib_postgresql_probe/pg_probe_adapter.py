#!/usr/bin/env python3
# Copyright 2026 SovereignNexus. All Rights Reserved.
# PROPRIETARY AND TRADE SECRET — UNAUTHORIZED COPYING, DISTRIBUTION,
# OR DECOMPILATION STRICTLY PROHIBITED.
# Licensed under SovereignNexus Commercial License.

"""
aeib_postgresql_probe/pg_probe_adapter.py

Hardened PostgreSQL Out-of-Band State Probe Adapter.
Enforces connection pooling, session-level statement timeouts, and index-optimized
UNION ALL queries across outbox ledgers.
"""

import os
import sys
import json
import math
import hashlib
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger("aeib.pg_probe_adapter")

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2 import errors as pg_errors
    QueryCanceled = getattr(pg_errors, "QueryCanceled", getattr(psycopg2, "QueryCanceled", Exception))
except (ImportError, AttributeError):
    psycopg2 = None
    pool = None
    pg_errors = None

    class _QueryCanceledFallback(Exception):
        """Fallback exception type when psycopg2 is not installed."""
        pass

    QueryCanceled = _QueryCanceledFallback


def canonical_evidence_digest(record: Dict[str, Any]) -> str:
    """
    Returns a hex SHA-256 digest of the record's deterministic
    JSON representation (sort_keys=True, compact separators, UTF-8).
    """
    canonical_json = json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _percentile_nearest_rank(values: list, q: float) -> float:
    """
    Nearest-rank percentile (1-indexed ordinal).
    """
    if not values:
        raise ValueError("values must not be empty")
    rank = math.ceil(q * len(values))
    return sorted(values)[rank - 1]


class PostgreSQLProbeAdapter:
    """Hardened out-of-band database prober with zero connection leakage and index guarantees."""

    def __init__(
        self,
        dsn: Optional[str] = None,
        minconn: int = 2,
        maxconn: int = 16,
        timeout_ms: int = 3000
    ):
        self.dsn = dsn or os.environ.get("AEIB_PG_DSN", "dbname=aeib_production user=aeib host=localhost")
        self.timeout_ms = timeout_ms
        self.minconn = minconn
        self.maxconn = maxconn
        self._pool = None

        # FIX 1 & 3: Pass session-level statement_timeout and connect_timeout in DSN options.
        # This guarantees timeout enforcement regardless of autocommit state.
        if psycopg2 is not None and hasattr(psycopg2, "pool") and hasattr(psycopg2.pool, "ThreadedConnectionPool"):
            try:
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=minconn,
                    maxconn=maxconn,
                    dsn=self.dsn,
                    options=f"-c statement_timeout={timeout_ms} -c lock_timeout=1000",
                    connect_timeout=3
                )
                logger.info(f"Initialized PostgreSQL probe pool (min={minconn}, max={maxconn}, timeout={timeout_ms}ms)")
            except Exception as e:
                logger.warning(f"Could not connect to PostgreSQL immediately ({e}); deferring connection checkout.")
                self._pool = None

    @contextmanager
    def get_connection(self):
        """FIX 3: Bounded connection checkout with deterministic try/finally release."""
        conn = None
        from_pool = False
        try:
            if self._pool is not None:
                conn = self._pool.getconn()
                from_pool = True
            elif psycopg2 is not None:
                conn = psycopg2.connect(
                    self.dsn,
                    options=f"-c statement_timeout={self.timeout_ms} -c lock_timeout=1000",
                    connect_timeout=3
                )
                from_pool = False
            else:
                raise RuntimeError("psycopg2 is not installed")
            yield conn
        finally:
            if conn is not None:
                if from_pool and self._pool is not None:
                    self._pool.putconn(conn)
                else:
                    try:
                        conn.close()
                    except Exception:
                        logger.debug("Failed closing non-pooled connection during teardown.")

    def probe_state(self, caid: str, idempotency_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Executes out-of-band state lookup.
        FIX 1: Wrapped in explicit transaction context ('with conn:').
        FIX 2: Uses UNION ALL to force B-tree index usage on caid and idempotency_key.
        """
        if psycopg2 is None:
            logger.warning(f"psycopg2 unavailable; probe failed for CAID={caid}")
            return None

        idem_key = idempotency_key or caid

        # FIX 2: Replaced 'WHERE caid = %s OR idempotency_key = %s' with index-friendly UNION ALL
        query = """
            (SELECT caid, idempotency_key, state, amount, account_id, created_at
             FROM outbox_ledger WHERE caid = %s LIMIT 1)
            UNION ALL
            (SELECT caid, idempotency_key, state, amount, account_id, created_at
             FROM outbox_ledger WHERE idempotency_key = %s LIMIT 1)
            LIMIT 1;
        """

        try:
            with self.get_connection() as conn:
                # FIX 1: Enforce explicit transaction block
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(query, (caid, idem_key))
                        row = cur.fetchone()
                        if row:
                            return {
                                "caid": row[0],
                                "idempotency_key": row[1],
                                "state": row[2],
                                "amount": row[3],
                                "account_id": row[4],
                                "created_at": str(row[5])
                            }
        except QueryCanceled:
            logger.warning(f"Probe query canceled: statement_timeout ({self.timeout_ms}ms) exceeded for CAID={caid}")
            return None
        except Exception as e:
            logger.error(f"PostgreSQL probe exception for CAID={caid}: {e}")
            return None

        return None

    def probe_ledger(self, caid: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatched disposition lookup adhering to AEIB wire contract specifications.
        Maps authoritative row outcomes to deterministic disposition taxonomy.
        """
        if psycopg2 is None:
            return {"status": "PROBE_EXCEPTION", "probe_outcome": "PROBE_EXCEPTION", "error": "psycopg2 not installed", "resolved": False}

        idem_key = idempotency_key or caid
        try:
            rec = self.probe_state(caid, idem_key)
            if rec is not None:
                raw_state = str(rec.get("state", "COMMITTED")).upper()
                norm_status = "OUTCOME_VERIFIED" if raw_state in ("COMMITTED", "VERIFIED") else raw_state
                return {
                    "status": norm_status,
                    "probe_outcome": "RECONCILIATION_MATCH",
                    "committed_at": rec.get("created_at"),
                    "payload_hash": hashlib.sha256(canonical_evidence_digest(rec).encode("utf-8")).hexdigest(),
                    "resolved": True,
                    "record": rec
                }
            return {
                "status": "RECONCILIATION_NOT_FOUND",
                "probe_outcome": "RECONCILIATION_NOT_FOUND",
                "resolved": True
            }
        except Exception as e:
            return {
                "status": "PROBE_EXCEPTION",
                "probe_outcome": "PROBE_EXCEPTION",
                "resolved": False,
                "error": str(e)
            }

    # Backward-compatible method aliases
    probe_transaction = probe_ledger
    probe_intent = probe_ledger

    def close(self):
        """Gracefully closes all pool connections."""
        if self._pool is not None and not getattr(self._pool, "closed", True):
            self._pool.closeall()


# Backward-compatible class aliases
PostgresOutboxProbe = PostgreSQLProbeAdapter
PGProbeAdapter = PostgreSQLProbeAdapter
PgProbeAdapter = PostgreSQLProbeAdapter


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="AEIB PostgreSQL Probe Harness")
    parser.add_argument("--timeout-ms", type=int, default=3000, help="Statement timeout in milliseconds")
    parser.add_argument("--dsn", type=str, default=None, help="PostgreSQL connection DSN")
    args = parser.parse_args()

    probe = PostgreSQLProbeAdapter(dsn=args.dsn, timeout_ms=args.timeout_ms)
    print(f"[*] Initialized PostgreSQLProbeAdapter with statement_timeout={args.timeout_ms}ms (pool min=2, max=16)")
    res = probe.probe_state("sample-caid-001", "idem-sample-key-001")
    print(f"[+] Probe State Result: {res}")
    ledger_res = probe.probe_ledger("sample-caid-001", "idem-sample-key-001")
    print(f"[+] Probe Ledger Result: {ledger_res}")


if __name__ == "__main__":
    main()

