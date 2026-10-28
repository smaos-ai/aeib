# 🏛️ Architecture Guide: Postgres-Native Durable Execution Integration
## Eliminating External Orchestrators via Database-Native Coordination & WAL Anchoring

**Status:** ARCHITECTURAL SPECIFICATION & RUNBOOK  
**Applicability:** SMAOS Sovereign Agent Iron Dome (Moat 12)  
**Target Systems:** PostgreSQL 14+, Citus, CockroachDB, CloudNativePG  

---

## 1. 🎯 Executive Context: The Death of External Orchestrators

In late 2026, enterprise engineering teams across European financial institutions (including tier-1 retail banks and fintech scale-ups) are increasingly dismantling complex, multi-component workflow orchestrators (such as Temporal clusters, AWS Step Functions, and Camunda engines). 

### The Operational Rationale:
1. **Infrastructure Sprawl & Multi-Tenant Overhead:** Running external orchestration clusters introduces separate Cassandra/Elasticsearch state stores, additional operational failure domains, and egress audit complications under DORA Article 28.
2. **Dual-Write Vulnerability:** External orchestrators maintain their own state machine distinct from the transactional database. If an agent executes a financial mutation in Postgres but the orchestrator crashes before logging the checkpoint, the system enters an irreconcilable split-brain state.
3. **Database-Native Durability:** Modern PostgreSQL provides all necessary coordination primitives directly inside the ACID engine:
   - Row-level non-blocking concurrency: `SELECT ... FOR UPDATE SKIP LOCKED`.
   - Causal state deduplication: `ON CONFLICT (action_id, sequence_num) DO NOTHING`.
   - Write-Ahead Log (WAL) causal ordering: Physical disk guarantees before acknowledgment.

---

## 2. 🔬 The Postgres Coordination Primitives

SMAOS integrates directly into PostgreSQL transaction boundaries using two core database patterns:

### Primitive A: Idempotent State Checkpointing
Every autonomous agent mutation must record its causal sequence checkpoint within the same transaction as the business mutation:

```sql
-- DDL for SMAOS Checkpoint Coordination
CREATE TABLE IF NOT EXISTS smaos_action_checkpoints (
    action_id        VARCHAR(64) NOT NULL,
    sequence_num     INTEGER NOT NULL,
    agent_did        VARCHAR(128) NOT NULL,
    tool_name        VARCHAR(64) NOT NULL,
    payload_digest   CHAR(64) NOT NULL,
    disposition      VARCHAR(16) NOT NULL,
    ratchet_level    VARCHAR(16) NOT NULL,
    created_at       TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (action_id, sequence_num)
);

-- Idempotent Checkpoint Insertion
INSERT INTO smaos_action_checkpoints (
    action_id, sequence_num, agent_did, tool_name, payload_digest, disposition, ratchet_level
) VALUES (
    'ACT-2026-9912', 1, 'did:key:z6Mku...', 'disburse_funds', 'e3b0c442...', 'CONFIRMED', 'UNRESTRICTED'
)
ON CONFLICT (action_id, sequence_num) DO NOTHING;
```

### Primitive B: Lock Contention via `SKIP LOCKED`
When multiple autonomous worker pods or background queues compete for execution traces, workers acquire work without distributed locking brokers (e.g. Redis Redlock):

```sql
-- Atomic, non-blocking queue acquisition
BEGIN;

SELECT action_id, sequence_num, tool_name, payload_digest
FROM smaos_action_checkpoints
WHERE disposition = 'PENDING'
ORDER BY sequence_num ASC
LIMIT 1
FOR UPDATE SKIP LOCKED;

-- [Execute Wire Action via SMAOS Guard]

UPDATE smaos_action_checkpoints
SET disposition = 'CONFIRMED',
    ratchet_level = 'UNRESTRICTED'
WHERE action_id = 'ACT-2026-9912' AND sequence_num = 1;

COMMIT;
```

---

## 3. 🛡️ The SMAOS WAL Anchoring Flow

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      POSTGRES-NATIVE DURABLE SETTLEMENT SEQUENCE                       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   Agent Worker                SMAOS Gate               PostgreSQL (WAL)                │
│        │                           │                          │                        │
│   1.   │─── Begin Transaction ────>│                          │                        │
│        │                           │─── BEGIN ───────────────>│                        │
│        │                           │                          │                        │
│   2.   │─── Execute Mutation ─────>│                          │                        │
│        │    (e.g., disburse €50k)  │─── Verify Wire Proof ───>│                        │
│        │                           │    (0ms in-line check)   │                        │
│        │                           │                          │                        │
│   3.   │                           │─── Checkpoint State ────>│                        │
│        │                           │    (ON CONFLICT NOOP)    │                        │
│        │                           │                          │                        │
│   4.   │<── Commit / UNKNOWN ──────│<── COMMIT (WAL Flushed)──│                        │
│        │                           │                          │                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Fault Handling & Rollback Guarantees:
- **Wire Drops (HTTP 504 / TCP RST):** If the external API drops, the SMAOS gate catches the transport failure, ratchets the capability level down (`proof_or_ratchet`), and rolls back the Postgres transaction or records an immutable `disposition = 'UNKNOWN'` checkpoint.
- **Worker Crash:** If the worker pod crashes mid-execution, PostgreSQL automatically releases the row lock (`FOR UPDATE`), allowing standby workers to inspect the WAL and safely resume.

---

## 4. ⚡ Air-Gapped Verification

This pattern requires **zero external cloud infrastructure**. Both the agent runtime and PostgreSQL execute within an air-gapped network namespace:

```bash
# Verify local execution with zero network egress:
docker run --network none -v $(pwd)/data:/var/lib/postgresql/data postgres:16-alpine
```
