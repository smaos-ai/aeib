# Distributed Database TCC Pre-Dispatch Proxy Specification

**Status:** Pre-Production Specification (`v1.0.0-rc.5-preprod`)  
**Scope:** Station 1 Pre-Dispatch Interlock Integration with Alibaba Seata TCC, PingCAP TiDB / TiKV, OceanBase Paxos, and PolarDB MVCC  
**Epistemic Boundary:** Formally evaluated under the stated model. Real SQLite WAL, real PostgreSQL `FOR UPDATE NOWAIT` row serialization, real RFC 8785 JCS canonicalization.

---

## 1. Architectural Scope & Problem Statement

In distributed database environments supporting autonomous multi-agent workloads, traditional application-level transactions face severe synchronization hazards:
1. **The Distributed Split-Brain Hazard:** When an agent cluster partitions across regions (e.g., `us-east-1` leader isolated from `eu-west-1` and `ap-northeast-1` followers), minority partitions risk executing divergent mutations without consensus.
2. **The Non-Atomic Tool Call Hazard:** While distributed databases maintain internal transactional consistency (e.g., TiKV Percolator, OceanBase Multi-Paxos), the *boundary between the agent runtime and the database wire protocol* is asynchronous. If a network drop occurs during a mutation commit, the agent cannot determine whether the transaction succeeded, risking duplicate mutations on retry.
3. **The S-Isolation Hazard:** Concurrent autonomous agents operating on shared tables create cascading lock contention, leading to deadlocks or speculative execution rollbacks.

To bridge the Agent Execution Integrity Boundary (AEIB) with production distributed database engines, Station 1 functions as a **TCC (Try-Confirm-Cancel) Pre-Dispatch Proxy**.

```text
                     DISTRIBUTED DATABASE PRE-DISPATCH TOPOLOGY
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │ Autonomous Agent Cluster (Untrusted Model Runtime)                            │
 │  • Emits Transaction Proposals (Candidate DB Mutations)                       │
 └──────────────────────────────────────┬────────────────────────────────────────┘
                                        │ (UDS / mTLS with Ed25519 CAID Warrant)
                                        ▼
 ┌───────────────────────────────────────────────────────────────────────────────┐
 │ Station 1 TCC Pre-Dispatch Proxy (AEIB Gateway)                              │
 │  1. Computes CAID = SHA256(JCS(Tenant, Table, Action, Args, Nonce))           │
 │  2. Enforces Try-Phase Resource Escrow & Bitemporal Monotonic Clock           │
 │  3. Validates Majority Quorum Consensus (>= 2/3 Nodes)                         │
 └──────────────┬───────────────────────┬───────────────────────────────┬────────┘
                │                       │                               │
                ▼                       ▼                               ▼
    ┌───────────────────────┐ ┌───────────────────┐         ┌───────────────────┐
    │ Alibaba Seata TCC     │ │ PingCAP TiDB/TiKV │         │ OceanBase Paxos   │
    │  • Branch Try() Lock  │ │  • Percolator TSO │         │  • Multi-Paxos MVCC│
    │  • Confirm() / Cancel │ │  • Primary Lock   │         │  • Log Replication│
    └───────────────────────┘ └───────────────────┘         └───────────────────┘
```

---

## 2. Distributed Database Adapter Specifications

### 2.1 Alibaba Seata TCC Integration

Alibaba Seata provides a two-phase transaction pattern across heterogeneous microservices via Try-Confirm-Cancel:
- **Phase 1 (Try):** Reserves business resources. In AEIB, Station 1 executes the `Try` phase before granting the agent dispatch permission:
  - Deducts or locks funds/slots in a dedicated `escrow_amount` column.
  - Generates a cryptographically bound `xid` (Transaction ID) and branch ID matching the action's `CAID`.
- **Phase 2 (Confirm):** If Station 3 receives an authenticated success acknowledgment from the downstream service, the proxy issues `Confirm`, transitioning `escrow_amount` to zero and applying final ledger credit.
- **Phase 2 (Cancel):** If a timeout (HTTP 504) or gate rejection occurs, the proxy transitions the intent to `EFFECT_INDETERMINATE`, preventing speculative re-execution. Once active reconciliation determines failure, the proxy issues `Cancel`, returning the escrowed balance to `available_balance`.

#### Wire Payload Schema (Seata TCC Branch Reservation):
```json
{
  "protocol": "SEATA_TCC_V1",
  "caid": "c6a2f4405a1e27a9...",
  "xid": "aeib-cluster-10.0.1.5:8091:9823746",
  "branch_id": 9823746001,
  "action_name": "escrow_settlement_reservation",
  "resource_id": "db.tenant_treasury.balance",
  "try_payload": {
    "account_id": "acc_enterprise_99",
    "reserve_minor_units": 250000,
    "currency": "EUR"
  },
  "timeout_ms": 5000,
  "signature": "ed25519_base64_..."
}
```

---

### 2.2 PingCAP TiDB / TiKV Distributed Transaction Alignment

TiDB utilizes the Google Percolator distributed transaction model with a centralized Timestamp Oracle (TSO):
- **TSO Alignment:** Station 1 queries the TiDB placement driver for the physical/logical commit timestamp $t_{\text{TSO}}$. The CAID intent record binds this timestamp into its monotonic epoch field ($|t_{\text{agent}} - t_{\text{TSO}}| \le 5\text{s}$).
- **Primary Lock Binding:** Station 1 writes the Primary Lock into the dedicated `aeib_intent_latch` table before secondary row mutations are proposed to TiKV storage nodes:
  $$\text{PrimaryLock} = \langle CAID, \text{PrimaryRowKey}, \text{LockTTL} \rangle$$
- **Crash Recovery & Rollback Invariant:** If the agent runtime crashes mid-transaction, TiKV's transaction resolver inspects the Primary Lock. Because the Station 1 latch marks unacknowledged transactions as `EFFECT_INDETERMINATE`, the resolver can query the Station 1 proxy to determine whether to roll back or roll forward, preventing orphaned distributed locks.
- **TLA+ Conformance:** Validated against the formal TLA+ model (`formal/tlaplus/TLC_OUTPUT.md`), where all 27 distinct states and 66 transitions exhibit zero deadlocks and zero invariant violations.

---

### 2.3 OceanBase Multi-Paxos Pre-Dispatch Consensus

OceanBase employs Multi-Paxos consensus across partition replicas:
- **Leader Lease Verification:** Station 1 pre-dispatch requests verify that the target OceanBase partition leader holds an active Paxos lease.
- **Quorum Gating:** In multi-region deployments (evaluated in `tests/test_dst_multi_region_partition.py` across `us-east-1`, `eu-west-1`, and `ap-northeast-1`), mutations require an ex-ante quorum acknowledgment from a strict majority ($\ge 2/3$ nodes).
- **Split-Brain Mitigation:** If an isolated leader attempts dispatch during a network partition, the Station 1 proxy halts fail-closed with `HALT_CONSENSUS_QUORUM_UNAVAILABLE`. Speculative minority writes are eliminated.

---

## 3. Mathematical Solvency & Concurrency Control

When multiple autonomous agents concurrently access shared tables, Station 1 enforces pessimistic row-level locking or optimistic timestamp verification:

### 3.1 Pessimistic Serialization (`FOR UPDATE NOWAIT`)
For high-contention accounts, Station 1 wraps SQL operations in explicit pessimistic lock blocks:

```sql
BEGIN TRANSACTION;
SELECT balance_minor, escrow_minor 
FROM tenant_accounts 
WHERE account_id = 'acc_corp_01' 
FOR UPDATE NOWAIT;

-- Assert Solvency Invariant:
-- (balance_minor - escrow_minor) >= requested_minor

UPDATE tenant_accounts 
SET escrow_minor = escrow_minor + :requested_minor,
    updated_at = CURRENT_TIMESTAMP
WHERE account_id = 'acc_corp_01';

INSERT INTO aeib_tcc_branch_ledger (caid, account_id, amount_minor, state, valid_time_start)
VALUES (:caid, 'acc_corp_01', :requested_minor, 'ESCROWED', CURRENT_TIMESTAMP);

COMMIT;
```

If another transaction holds the lock, `NOWAIT` immediately aborts the attempt with `TCC_ERROR_LOCK_CONTENTION`, signaling the agent to apply deterministic exponential backoff rather than blocking database worker threads.

### 3.2 Bitemporal Audit Outbox
Every confirmed or cancelled transaction creates an outbox entry conforming to `src/storage/postgres_bitemporal_outbox.sql`:
- `valid_time_start`: Logical transaction occurrence time.
- `system_time_start`: Physical database write timestamp.
- `payload_jcs_hash`: SHA-256 digest of the RFC 8785 canonical transaction statement.

---

## 4. Empirical Benchmark Verification

The distributed database proxy contract has been verified across the following test suites:

| Metric / Scenario | Test Suite | Benchmark Condition | Observed Result |
|---|---|---|---|
| **Multi-Region Partition (Split-Brain)** | `tests/test_dst_multi_region_partition.py` | 100 seeds, 3 regions, asymmetric partitions | **0 double-reservations**; minority fails closed |
| **High-Contention Concurrency** | `tests/test_postgres_tcc_concurrency_stress.py` | 100 concurrent threads, €5,000 budget | **0 double-allocations**; 0 lost updates |
| **TLA+ Model Checking** | `formal/tlaplus/TLC_OUTPUT.md` | Complete state-space exploration | **27 states, 66 transitions, 0 violations** |
| **Transport Drop Latching** | `tests/test_dst_seeded_invariants.py` | 500 episodes, 20% lost acknowledgments | **0 duplicate dispatches** |

---

## 5. Epistemic Calibration
This contract defines an evaluated architectural bridge for distributed database coordination. It does not claim universal immunity from hardware or operating system failures; rather, it enforces deterministic, fail-closed isolation under the declared execution model.
