# AEIB PostgreSQL Probe Adapter

This is the real PostgreSQL probe adapter for the Agent Execution Integrity Benchmark (AEIB).

## Purpose
It provides a concrete implementation of an out-of-band ground truth probe. When an AI agent hits an ambiguous gateway fault (e.g., HTTP 504), this adapter executes a parameterized query directly against the target PostgreSQL `operations` ledger to ascertain if the mutation committed.

## Requirements
* `psycopg` (version 3.x)
* Target schema requires an `operations` table with columns: `operation_id`, `intent_id`, `amount`, `status`, `committed_at`.
* An index on `intent_id` is highly recommended to avoid slow sequential scans during ambiguity reconciliation.
* The `PG_LEDGER_DSN` environment variable must be set (e.g., `postgresql://user:pass@host/db`).

## Security & DSN Redaction
The adapter automatically redacts the connection string before logging, using strict URI parsing to replace passwords with `***`. It never logs the raw DSN.

## Notice
This adapter is a constituent component of the broader AEIB evaluation harness. It handles the PostgreSQL out-of-band observation step. The full AEIB benchmark runner (which generates the synthetic faults and C2 drift measurements) resides in the primary repository workspace.
