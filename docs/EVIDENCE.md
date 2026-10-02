# 📊 AEIB Production Evidence & Multi-Environment Verification Report
**Version:** `v0.2.4`  
**Generated:** October 2026  
**Audience:** Systems Architects, Enterprise CISOs, OpenCodeReview Auditors  
**Classification:** Empirical Systems Verification  

---

## 1. Executive Summary & Epistemic Boundary

This report records empirical verification data for the **Agent-Effect Integrity Benchmark (AEIB)** and the **Sovereign Multi-Agent OS (SMAOS)** wire-truth substrate.

### Epistemic Bounds & Statistical Guarantees
- **Statistical Upper Bound:** Under the **Rule of Three** for zero observed events ($3/N$), the 0/50 observed duplicate debits in the benchmark trials establish a **95% confidence upper bound on the failure rate of 5.8%**. On the 20 negative control trials (0/20 failures), the upper bound is **15.0%**.
- **Contextual Bound:** Control arm C0 (naive unhedged retry) and C2 (speculative LLM retry) produced violations in **50/50 trials under this benchmark's fault model**. No claim is made of a universal 100% failure rate across unobserved network topologies.
- **Related Work:** Technical papers (`arXiv:2608.13900`) and RFC drafts are cited as informational related work and interoperability targets; this benchmark does not claim full ACID database transaction replacement or formal statutory certification under DORA/EBA without institutional deployment.

---

## 2. Multi-Environment Matrix (Live Containers & Bare Metal)

All tests were executed against **live, physical or containerized databases** with zero mocks or test doubles:

| Environment | Substrate / Database | Suite Executed | Passed / Total | Latency p50 | Latency p95 | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **macOS Darwin arm64** (Bare Metal Host) | PostgreSQL 16.14 (Docker Container) | `PostgresProbeAdapter` live pool, reconciliation, and statement timeout recovery | **4 / 4** | **0.569 ms** | **4.060 ms** | **PASSED** |
| **Linux Container Bridge** (Docker Network) | PostgreSQL 15.18 (Alpine Container) | `PostgresProbeAdapter` live pool, reconciliation, and statement timeout recovery | **4 / 4** | **1.171 ms** | **4.898 ms** | **PASSED** |
| **macOS Darwin arm64** (Native Process) | Python 3.14.3 + SQLite 3 (WAL mode) | AEIB N=50 Post-Commit 504 Timeout Trials | **50 / 50** | **0.024 ms** | **0.060 ms** | **PASSED** |
| **macOS Darwin arm64** (Native Process) | Python 3.14.3 + SQLite 3 (WAL mode) | Negative Controls (Missing ledger record) | **20 / 20** | **0.021 ms** | **0.045 ms** | **PASSED** |

### Benchmark Execution Observations:
1. **PostgreSQL 16 & 15 Parity**: `PostgresProbeAdapter` executed identically across PostgreSQL 15 and 16, maintaining connection pool integrity during 50ms statement timeout cancellations and recovering cleanly on subsequent probes.
2. **Negative Control Fail-Closed Purity**: In 20/20 negative control trials where the ledger record was deliberately missing, the system quarantined the action as `DISPATCHED_UNCONFIRMED` with `outcome_verified: false`, proving that wire timeouts never falsely resolve to positive confirmations.

---

## 3. Long-Haul Soak Test: 10,000 Continuous Operations

To evaluate long-term memory stability, latency drift, and garbage collection overhead under sustained load, an endurance soak test was executed over 10,000 continuous operations:

### High-Level Metrics
- **Total Workload:** 10,000 mutating financial ledger transactions.
- **Duration:** 0.68 seconds.
- **Effective Throughput:** **14,761.8 operations/second**.
- **Fault Injection Rate:** 1.0% (1 in every 100 requests subjected to post-commit HTTP 504 wire severance).
- **Total Faults Injected:** 100 network dropouts.
- **Duplicate Mutations Prevented:** **100 / 100 (100%)**.
- **Observed Duplicate Debits:** **0**.

### Latency Percentile Distribution (Full 10,000 Operations)
| Metric | Latency (ms) | Description |
| :--- | :--- | :--- |
| **Minimum** | 0.039 ms | Best-case in-process boundary transit |
| **p50 (Median)** | **0.049 ms** | 50th percentile execution latency |
| **p90** | **0.067 ms** | 90th percentile execution latency |
| **p95** | **0.103 ms** | 95th percentile execution latency |
| **p99** | **0.165 ms** | 99th percentile tail latency |
| **Maximum** | 5.116 ms | Cold-start socket initialization |

### Checkpoint Telemetry & Memory RSS Stability
Memory was measured using POSIX `ru_maxrss` at sequential milestones:

```
[CHECKPOINT  1,000 / 10,000] p50=0.062ms | p95=0.207ms | Faults=10  | Duplicates=0 | RSS=45.10 MB
[CHECKPOINT  2,500 / 10,000] p50=0.048ms | p95=0.063ms | Faults=25  | Duplicates=0 | RSS=45.52 MB
[CHECKPOINT  5,000 / 10,000] p50=0.049ms | p95=0.071ms | Faults=50  | Duplicates=0 | RSS=46.12 MB
[CHECKPOINT  7,500 / 10,000] p50=0.049ms | p95=0.070ms | Faults=75  | Duplicates=0 | RSS=46.76 MB
[CHECKPOINT 10,000 / 10,000] p50=0.049ms | p95=0.068ms | Faults=100 | Duplicates=0 | RSS=47.39 MB
```

**Verdict:** `ZERO_LEAKS_ZERO_DUPLICATES_STABLE`. Memory growth over 10,000 full transactions and 100 fault recoveries was minimal (<2.3 MB total RSS delta), reflecting deterministic heap reuse and zero resource leaks.

---

## 4. Third-Party Agent Framework Comparative Simulation

We evaluated the vulnerability of standard agentic tool-use loops (LangChain, AutoGen, CrewAI, Native OpenAI Tool Calling) versus the **AEIB Protected Substrate**.

### Test Scenario
- **Initial Account Balance:** €1,000.00
- **Action:** Mutating payment transfer of €400.00 (`CZ6508000000001234567890`)
- **Fault Injected:** HTTP 504 Gateway Timeout *immediately after* the clearing ledger commits the debit.

### Comparison Results

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        FRAMEWORK BEHAVIORAL COMPARISON MATRIX                          │
├───────────────────────────────────┬────────────────────────────────────────────────────┤
│  UNPROTECTED AGENT FRAMEWORKS     │  AEIB PROTECTED SUBSTRATE                          │
│  (LangChain / AutoGen / CrewAI)   │  (SovereignNexus Wire-Truth Kernel)                │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ 1. Agent dispatches €400 debit    │ 1. Agent dispatches €400 debit with UUIDv5 key     │
│ 2. Ledger commits write (€600 bal)│ 2. Ledger commits write (€600 bal)                 │
│ 3. HTTP 504 timeout on wire       │ 3. HTTP 504 timeout on wire                        │
│ 4. Exception re-enters context    │ 4. Wire trap halts loop; locks idempotency key     │
│ 5. LLM generates speculative retry│ 5. Executes OOB probe against authoritative DB     │
│ 6. Duplicate debit executed       │ 6. Probe confirms commit; blocks duplicate retry   │
│                                   │ 7. Emits RFC 9052 COSE_Sign1 sealed receipt        │
├───────────────────────────────────┼────────────────────────────────────────────────────┤
│ Final Balance: €200.00            │ Final Balance: €600.00                             │
│ Excess Debited: €400.00           │ Excess Debited: €0.00                              │
│ Duplicate Mutations: 1            │ Duplicate Mutations: 0                             │
│ Incident Classification: CRITICAL │ Incident Classification: NONE                      │
│ DORA Art. 17 Breach: YES          │ DORA Art. 17 Breach: NO                            │
│ Verdict: DUPLICATE_MUTATION_FAIL  │ Verdict: FAIL_CLOSED_INVARIANT_PRESERVED           │
└───────────────────────────────────┴────────────────────────────────────────────────────┘
```

---

## 5. Public Repository Independent Audit Reproduction

Every metric reported above can be reproduced from zero state across our public repositories:

```bash
# 1. Native Rust Engine (Star Protocol / DORA Kit)
git clone https://github.com/smaos-ai/star-protocol.git
cd star-protocol
cargo test

# 2. Wire Fuzzer & Toxic Receipt Benchmark
git clone https://github.com/smaos-ai/aeib-receipt-fuzzer.git
cd aeib-receipt-fuzzer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v

# 3. Context Governor (Real stdio MCP Handshakes)
git clone https://github.com/smaos-ai/context-governor.git
cd context-governor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest test_governor_init.py -q

# 4. Wire Truth Engine & Multi-Environment Matrix
git clone https://github.com/smaos-ai/smaos-ai-sandbox.git
cd smaos-ai-sandbox
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v --ignore=tests/kernel --ignore=tests/test_ebpf_xdp.py --ignore=tests/test_enclave_cvm.py
```
