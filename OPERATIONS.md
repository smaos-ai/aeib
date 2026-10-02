# 🛠️ SovereignNexus / SMAOS Operations & Deployment Runbook
**Version:** `v0.2.4`  
**Classification:** Enterprise Infrastructure Runbook  
**Status:** Hardened Engineering Release  

---

## 1. Quickstart & Deployment Models

SMAOS supports three hardened deployment topologies:

### Option A: Bare-Metal Native Process (Sub-Millisecond Wire Trap)
Ideal for latency-critical deployments alongside agent runtimes on macOS (Apple Silicon) or Linux x86_64:

```bash
# Clone the core repository
git clone https://github.com/smaos-ai/smaos-ai-sandbox.git
cd smaos-ai-sandbox

# Initialize dedicated virtual environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the complete test and verification suite
pytest tests/ -v
```

### Option B: Air-Gapped Docker Container (`--network none`)
Mandatory for DORA / PCI-DSS compliance audits where zero network egress must be cryptographically attested:

```bash
# Build the hermetic container
docker build -t smaos/wire-truth:v0.2.4 -f Dockerfile .

# Execute with zero egress (physical networking severed)
docker run --rm --network none -v $(pwd)/audit_out:/app/audit_out smaos/wire-truth:v0.2.4 --all-scenarios
```

### Option C: Live Multi-Environment Database Cluster (Docker Compose)
Runs the live PostgreSQL 16 and PostgreSQL 15 probe testing matrix:

```bash
# Start PostgreSQL 16 on port 5432 and PostgreSQL 15 on port 55433
docker compose -f docker-compose.infra.yml up -d

# Verify both instances are healthy
docker ps --filter "name=aeib-"
```

---

## 2. Database Connection Pooling & Sizing Guide

When deploying `PostgresProbeAdapter` in production, configure connection pools according to these tested parameters:

| Parameter | Recommended Value | Rationale |
| :--- | :--- | :--- |
| `minconn` | `1` per worker | Prevents idle connection starvation on high worker counts |
| `maxconn` | `5`–`10` per worker | Bounded pool prevents PostgreSQL server socket exhaustion |
| `statement_timeout_ms` | `100` ms (default) | Strict bounded probe execution prevents hung reconciliation |
| `idle_timeout_sec` | `300` s | Recycles stale TCP connections through proxies / firewalls |
| `max_reconnect_retries`| `3` | Graceful retry on transient network blips before fail-closed |

### PostgreSQL Statement Timeout Sizing
- **Fast OLTP Targets (e.g. Ledger Transfer):** Set `statement_timeout_ms=50`. If the database index does not respond within 50ms, the probe aborts and yields `PROBE_TIMEOUT`, preventing the agent thread from hanging.
- **Complex Analytical Queries:** Set `statement_timeout_ms=250`.

```python
from aeib_postgresql_probe.adapter import PostgresProbeAdapter

adapter = PostgresProbeAdapter(
    dsn="postgresql://postgres:postgres@localhost:5432/aeib_ledger",
    minconn=2,
    maxconn=10
)

# Execute probe with custom statement timeout
result = adapter.execute_probe(
    idempotency_key="IDEM-CZ-2026-001",
    table_name="settlement_ledger",
    statement_timeout_ms=50
)
```

---

## 3. Health Checks & Continuous Monitoring

### In-Process Health Verification
SMAOS exposes deterministic health telemetry without requiring outbound telemetry egress:

```bash
# Check database probe health and pool status
python3 -c "
from aeib_postgresql_probe.adapter import PostgresProbeAdapter
adapter = PostgresProbeAdapter('postgresql://postgres:postgres@localhost:5432/aeib_ledger')
print('Pool Status:', adapter.health_check())
adapter.close()
"
```

### SQLite WAL Invariant Checks
When using local SQLite persistence for nonces:
```bash
# Verify WAL mode is active (enforces crash-resilient atomic commits)
sqlite3 /tmp/aeib_live_ledger.db "PRAGMA journal_mode;"
# Expected output: wal

# Check WAL integrity
sqlite3 /tmp/aeib_live_ledger.db "PRAGMA integrity_check;"
# Expected output: ok
```

---

## 4. Troubleshooting & Incident Playbook

### Problem 1: `HTTP 504 Gateway Timeout` Observed
- **Diagnosis:** The remote API or database took longer than the gateway timeout (e.g., 30s) to return.
- **Action:** DO NOT RETRY THE ORIGINAL ACTION. Check the SMAOS disposition receipt:
  - If disposition is `OUTCOME_VERIFIED`: The database already committed the transaction. Proceed safely.
  - If disposition is `DISPATCHED_UNCONFIRMED`: The action is quarantined. Trigger an out-of-band probe query or await operator reconciliation.
  - If disposition is `RECONCILIATION_NOT_FOUND`: The database never received the write. Re-dispatch is safe only with a new authority token.

### Problem 2: `connection to server at "localhost", port 5432 failed`
- **Diagnosis:** Docker container `aeib-live-db` is stopped or network sandbox is active without port binding.
- **Action:**
  ```bash
  # Check container status
  docker ps -a --filter "name=aeib"
  
  # Restart PostgreSQL 16 container
  docker restart aeib-live-db
  
  # Verify port listening on host
  nc -zv 127.0.0.1 5432
  ```

### Problem 3: `OperationalError: statement timeout`
- **Diagnosis:** Downstream database table lacks an index on `idempotency_key`, causing a full table scan that exceeds the probe timeout.
- **Remediation:** Add a unique index on the idempotency column:
  ```sql
  CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_idempotency_key ON settlement_ledger (idempotency_key);
  ```

---

## 5. Audit Evidence Generation & Verification

To generate full multi-environment evidence bundles for compliance audits:

```bash
# Run the complete multi-environment matrix & 10,000-op soak test
python3 benchmarks/multi_env_matrix/run_production_benchmarks.py

# Evidence output location:
# dist/production_evidence/PRODUCTION_LONG_HAUL_EVIDENCE.json

# Offline verification using standalone browser verifier:
open dist/verifier.html
# Drag-and-drop the generated .json receipt or audit bundle for zero-egress cryptographic verification.
```
