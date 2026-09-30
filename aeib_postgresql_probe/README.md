# AEIB PostgreSQL Authoritative Probe Adapter

A reference adapter for out-of-band ground-truth verification against a PostgreSQL ledger.

## Scope & Operational Context

When an agent observes transport-layer ambiguity (such as an `HTTP 504 Gateway Timeout`), this adapter executes a parameterized, read-only query directly against the target PostgreSQL `operations` ledger to verify whether the mutation committed.

### Local Integration Test Results
* **Environment**: PostgreSQL 16.14 (Homebrew) on macOS (Darwin arm64).
* **Workload**: 50 warm loopback probe calls against an indexed table (`idx_operations_intent_id`).
* **Empirical Latency**:
  - Mean: `5.17 ms`
  - p50: `4.62 ms`
  - p95: `8.38 ms`
  - p99: `8.96 ms`
* **Qualification**: These figures characterize local loopback query execution on a dedicated test instance. They must **not** be generalized to multi-tenant production PostgreSQL deployments under concurrent write load, replication lag, or WAN latency.

### Connection Architecture
* **Unpooled Discrete Connections**: The adapter invokes `psycopg.connect()` on each probe call. Measured latency includes TCP/socket connection establishment, query execution, and disconnection overhead.
* **Driver Support**: Compatible with both `psycopg` (v3) and `psycopg2-binary`.

### Canonical Evidence Representation
* **Canonical JSON Digest**: The `evidence_digest` is computed via SHA-256 over the project's **documented canonical JSON representation** (`json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`), providing deterministic hashing for the exercised schema fields rather than claiming full external RFC 8785 certification.

### Security & DSN Redaction
* **Zero Secret Leakage**: The adapter uses `urllib.parse.urlparse` to sanitize the connection string before logging or reporting. Passwords and credentials are fully redacted (`***`).
* **Parameterized Queries**: All lookups use parameterized SQL (`WHERE intent_id = %s`), preventing SQL injection.

## Schema Requirements

```sql
CREATE TABLE operations (
    operation_id VARCHAR(64) PRIMARY KEY,
    intent_id VARCHAR(64) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    committed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_operations_intent_id ON operations(intent_id);
```
