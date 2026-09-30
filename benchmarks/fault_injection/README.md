# AEIB Deterministic Fault-Injection Testbed & Control Matrix

Hermetic, non-LLM reproducible test harness proving the double-mutation flaw in conventional agent architectures under transport-layer ambiguity and semantic drift.

---

## 1. Quickstart & Reproduction

Run the complete 50-trial benchmark across all four baselines:

```bash
PYTHONPATH=. .venv/bin/python benchmarks/fault_injection/client_matrix.py --runs 50
```

Run the automated test suite:

```bash
PYTHONPATH=. .venv/bin/pytest benchmarks/fault_injection/tests/test_control_matrix.py -v
```

Execute the canonical single-intent failure proof:

```bash
PYTHONPATH=. .venv/bin/python benchmarks/fault_injection/run_single_failure_proof.py
```

---

## 2. Empirical Results

| Baseline Configuration | Safety ($\text{Commits} \le 1$) | Duplicate Rate | Mean Overhead |
| :--- | :--- | :--- | :--- |
| **$C_0$ (Naive Client Retry)** | **FAILED** | **100.0%** (50/50 double-spends) | ~9.8 ms |
| **$C_1$ (Gateway + Stable Key)** | **HELD** | **0.0%** (0/50 double-spends) | ~1.2 ms |
| **$C_2$ (Gateway + Semantic Drift)** | **FAILED** | **100.0%** (50/50 double-spends) | ~8.9 ms |
| **AEIB Execution Boundary** | **HELD (100% INVARIANT)** | **0.0%** (0/50 double-spends) | ~10.8 ms |

---

## 3. Architecture

* **`store.py`**: SQLite database with strict ACID transactions, balance tracking, and immutable bitemporal debit ledger.
* **`middleware.py`**: Intercepts `POST /debit` post-commit, injecting a 5ms delay and returning `HTTP 504 Gateway Timeout` (simulating dropped socket).
* **`app.py`**: FastAPI target service implementing `POST /debit` and authoritative `GET /operations/{id}` reconciliation endpoint.
* **`gateway_simulator.py`**: Simulates Kong/Envoy API Gateway RFC-compliant idempotency caching.
* **`aeib_interceptor.py`**: Userspace sidecar implementing pre-dispatch RFC 8785 JCS + UUIDv5 injection, retry freezing, out-of-band probing, and Ed25519-signed receipt generation.
* **`MECHANISM_NOTE.md`**: Detailed architectural breakdown of why traditional idempotency fails under LLM ReAct semantic drift.
