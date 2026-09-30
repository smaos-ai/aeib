# Mechanism Note: The Double-Mutation Flaw under Post-Dispatch Ambiguity

**Status:** Empirical Benchmark Finding  
**Benchmark:** Sovereign Multi-Agent OS (SMAOS) / AEIB Fault-Injection Suite  
**Scenario:** `C_0_NAIVE_RETRY` & `C_2_GATEWAY_SEMANTIC_DRIFT`  

---

## 1. The Anatomy of the Failure

The benchmark empirically demonstrates that conventional API gateway idempotency (e.g. Kong, Envoy, AWS API Gateway) and standard client retry loops fail to uphold the **Safety Invariant** ($\text{LedgerCommits}(O) \le 1$) when an autonomous agent encounters a post-dispatch response loss.

```text
Logical Intent: I-001 (Debit $100)

[ Agent Orchestrator ]                [ API Gateway ]                [ Target Ledger (SQLite) ]
         │                                   │                                    │
         ├─── (1) POST /debit ───────────────┼───────────────────────────────────►│ [BEGIN TX]
         │        key=K-001                  │                                    │ Balance: $10,000 -> $9,900
         │                                   │                                    │ Debit D-001 COMMITTED
         │                                   │                                    │ [COMMIT TX OK]
         │                                   │◄─── (2) Socket Severed (5ms) ──────┤
         │◄─── (3) HTTP 504 Timeout ─────────┤                                    │
         │     (Wire dropped post-commit)    │                                    │
         │                                   │                                    │
    [ Uncertainty ]                          │                                    │
    Agent assumes:                           │                                    │
    "Debit not executed"                     │                                    │
         │                                   │                                    │
    [ ReAct Loop Drift ]                     │                                    │
    Mutates whitespace / key                 │                                    │
         │                                   │                                    │
         ├─── (4) RETRY POST /debit ─────────┼───────────────────────────────────►│ [BEGIN TX]
         │        key=K-001-retry            │ (Cache Miss: drifted key/payload)  │ Balance: $9,900 -> $9,800
         │                                   │                                    │ Debit D-002 COMMITTED!
         │◄─── (5) HTTP 200 OK ──────────────┴────────────────────────────────────┤ [COMMIT TX OK]
         ▼
[ Double-Spend Realized: $200 debited for a single $100 intent ]
```

---

## 2. Five Critical Observations

1. **The Backend Committed Before the Response Was Lost:**  
   The target SQLite database ledger successfully committed transaction `tx_id=1` (`debit_id=D-001`, amount: \$100.00) and deducted account balance from \$10,000 to \$9,900.
2. **The Client Observed Only a Transport Failure:**  
   Because the connection severed post-commit but pre-acknowledgment (simulating network partition, proxy drop, or TCP reset), the client HTTP stack caught `HTTP 504 Gateway Timeout` (`GATEWAY_TIMEOUT`).
3. **The Agent Treated Uncertainty as Non-Execution:**  
   Conventional LLM ReAct loops (LangChain, AutoGen, CrewAI, OpenAI Assistant SDKs) classify `504` or `ECONNRESET` as a transient network glitch, interpreting the outcome as *"action did not execute, safe to retry"*.
4. **The Retry Created a Second Committed Debit:**  
   Upon re-dispatching, the database ledger committed transaction `tx_id=2` (`debit_id=D-002`, amount: \$100.00), reducing the balance further to \$9,800. Total debits committed for logical intent `I-001`: **2**.
5. **Conventional Idempotency Did Not Protect the Business Operation:**  
   - Under $C_0$, client omitted or regenerated client identifiers.
   - Under $C_2$, semantic drift (LLM prompt re-serialization, whitespace variation, re-formatted JSON keys, or regenerated UUIDv4 keys) caused an **idempotency cache miss** at the API gateway, allowing the request through to the target service.

---

## 3. Ground Truth Ledger Output

```text
intent_id=I-001
attempt=1
debit_id=D-001
amount=100.0
status=COMMITTED
timestamp=2026-09-30T16:52:38.739729+00:00

intent_id=I-001
attempt=2
debit_id=D-002
amount=100.0
status=COMMITTED
timestamp=2026-09-30T16:52:38.757745+00:00

total_debits=2
safety_invariant=FAILED (DOUBLE_MUTATION_DETECTED)
```

---

## 4. The Architectural Implication

This empirical evidence proves that **"Retry or Else"** is a catastrophic failure mode in autonomous agent architectures.  
To preserve execution integrity without human deadlock, the agent runtime requires an **Agent Execution Integrity Boundary (AEIB)**:
- Pre-dispatch canonicalization (RFC 8785 JCS) binding a deterministic **UUIDv5** anchor to payload semantics before wire transmission.
- Transport-level interception freezing unhedged retries (`retry_permitted = False`).
- Mandatory **out-of-band ledger probes** (`GET /operations/{id}`) to resolve true system state before releasing control.
- Cryptographically signed execution receipts (`OUTCOME_VERIFIED`).
