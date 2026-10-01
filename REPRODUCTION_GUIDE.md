# AEIB v0.2.4: External Review Package

Welcome reviewers. This package contains the instructions and metadata required to independently reproduce the Agent Execution Integrity Benchmark (AEIB) v0.2.4 evaluation and PostgreSQL integration.

## 1. Release Identity & Target
* **Tag:** `v0.2.4`
* **Commit:** `cfb9d8994894ca33c04e60c681894ac1c9ee38a5`
* **Repository:** Private repository. Archive available on request with accompanying commit bundle.
* **Signature Status:** The tag is annotated but unsigned. Reviewers should verify the resolved commit ID and the release manifest’s artifact digests.

## 2. Dependencies & Environment Setup
To run the verification suite, ensure you are running exactly **Python 3.14.3** (other versions are untested) and create a fresh virtual environment. 
Execute the following to prepare your environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install fastapi==0.141.1 starlette==1.6.0 pydantic==2.13.5 \
    cryptography==50.0.1 pytest==9.1.1 psycopg2-binary==2.9.9
```

## 3. SQLite Benchmark & Provenance Reproduction
The core AEIB benchmark simulates a fault-injection environment using a local SQLite instance to demonstrate boundary integrity under ambiguous `HTTP 504` timeout conditions.

**Command:**
```bash
git clone --branch v0.2.4 <repository> /tmp/aeib-v024-review
cd /tmp/aeib-v024-review
source .venv/bin/activate
PYTHONPATH=. python benchmarks/fault_injection/verify_reproduction.py --strict-versions
```

**Expected Output:**
The offline verifier will run the full C0/C1/C2 control matrix and the AEIB fault trials, outputting an 8-step verification report terminating with:
```text
========================================================================
  SUCCESS: ALL REPRODUCTION CHECKS AND INVARIANTS VERIFIED
  Release target   : v0.2.4  (Branch: release/v0.2.0)
  Safety invariant : 0 duplicate debits under AEIB boundary (50/50)
  Control matrix   : C0=100% dup | C1=0% | C2=100% dup
  Negative controls: 20/20 RECONCILIATION_NOT_FOUND (0% false positive)
  Cryptographic    : tamper-rejection checks passed
========================================================================
```

## 4. PostgreSQL Integration Reproduction
This suite evaluates the `ThreadedConnectionPool` PostgreSQL outcome probe against a live database, proving active `statement_timeout` cancellation, pool recovery, and correct `RECONCILIATION_CONFLICT` (fail-closed) behavior on duplicate rows.

**Setup Instructions:**
1. Start an isolated PostgreSQL 16 instance:
   ```bash
   docker run -d --rm --name aeib-test-postgres -e POSTGRES_PASSWORD=password -e POSTGRES_DB=aeib_ledger -p 5432:5432 postgres:16-alpine
   ```
2. The integration test module creates and tears down the required schema in a module-scoped fixture. No manual schema setup is required.
3. Execute the integration suite using the isolated database DSN:
   ```bash
   PG_LEDGER_DSN="postgresql://postgres:password@localhost:5432/aeib_ledger" \
   PYTHONPATH=. pytest aeib_postgresql_probe/tests/test_integration_pg_probe.py -v
   ```

**Expected Output:**
```text
aeib_postgresql_probe/tests/test_integration_pg_probe.py::test_1_verified_outcome PASSED
aeib_postgresql_probe/tests/test_integration_pg_probe.py::test_2_reconciliation_not_found PASSED
aeib_postgresql_probe/tests/test_integration_pg_probe.py::test_3_reconciliation_conflict_on_duplicate_rows PASSED
aeib_postgresql_probe/tests/test_integration_pg_probe.py::test_4_statement_timeout_active_cancellation_and_pool_recovery PASSED

============================== 4 passed in 0.44s ===============================
```

### Measured Empirical Latency Distributions (N=100 Trials)
| Substrate | min | p50 (median) | p95 | p99 | max | mean (± σ) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **SQLite In-Process Local Probe** | 0.048 ms | 0.057 ms | 0.079 ms | 0.156 ms | 0.193 ms | 0.060 ms (± 0.019) |
| **PostgreSQL Live OOB Probe (`ThreadedConnectionPool`)** | 0.191 ms | 0.228 ms | 0.257 ms | 0.317 ms | 1.110 ms | 0.236 ms (± 0.090) |

## 5. Scope, Constraints, and Limitations
Please evaluate this release strictly within its stated bounds:
* **Architecture Distinction**: `v0.2.4` is an annotated, locally reproducible release containing the SQLite AEIB benchmark and a locally integration-tested PostgreSQL outcome probe with pooled connections, active statement-timeout cancellation, and pool-recovery tests. It is **not** designated as "production-ready."
* **Statistical Bounds**: The reported zero-failure results are sample observations under a specific synthetic trial model. By the Rule of Three, 0/50 duplicate mutations gives an approximate 95% upper bound of 5.8% for the underlying failure probability under the same trial model. The 0/20 false verifications on negative controls gives an approximate 95% upper bound of 15.0% for the underlying failure probability under the same trial model.
* **Prior-Art Conformance**: The mapping schema sorts keys deterministically but does not claim full RFC 8785 (JCS) compliance. AEIB claims **no conformance** to IETF drafts like `draft-sahu-agent-action-receipts` or `draft-etcheverry-action-ref`. It consumes these identities strictly as interoperability targets.
* **Regulatory Exemption**: This benchmark does not establish legal, standards-conformant, or regulatory certification under DORA, the EU AI Act, or equivalent frameworks.

## 6. Reviewer Report Template
Please return your verification results using the following standardized template:

```markdown
### Reviewer Name / ID: [Insert]
### Reproduction Environment:
- OS: [e.g., macOS 14.2 / Ubuntu 22.04]
- Python Version: [e.g., 3.14.3]
- Docker Engine Version: [e.g., 24.0.7]

### Gate 1: Git and Environment Setup
- [ ] Fresh clone of tag `v0.2.4` successful.
- [ ] `git log -1` confirms commit `cfb9d8994894ca33c04e60c681894ac1c9ee38a5`.
- [ ] Virtual environment and dependencies installed successfully.
*Deviations/Notes:* None.

### Gate 2: SQLite Benchmark & Verifier
- [ ] Script ran without crashing.
- [ ] All 8 verification steps passed.
- [ ] 12/12 manifest artifact hashes verified exactly.
- [ ] Reported 0/50 duplicates on AEIB trials.
*Deviations/Notes:* None.

### Gate 3: Live PostgreSQL Integration
- [ ] PostgreSQL docker container started successfully.
- [ ] `pytest` execution returned exactly `4 passed, 0 skipped, 0 errors`.
*Deviations/Notes:* None.

### Overall Verdict:
- [ ] **Reproduced:** The artifact matches the claims exactly.
- [ ] **Failed to Reproduce:** (Detail blocking issues below).

### Additional Comments:
[Enter any feedback, observations, or encountered errors here]
```
