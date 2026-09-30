# Mechanism Note: The Double-Mutation Flaw under Post-Dispatch Ambiguity

**Status:** Empirical Benchmark Finding  
**Benchmark:** Sovereign Multi-Agent OS (SMAOS) / AEIB Fault-Injection Suite  
**Scenario:** `C_0_NAIVE_RETRY`, `C_1_GATEWAY_STABLE_KEY`, `C_2_GATEWAY_SEMANTIC_DRIFT`, `AEIB_PROTOCOL`  

---

## 1. Important Qualification: Boundary Conditions of Conventional Idempotency

> **Core Finding:**  
> **Conventional gateway idempotency prevents duplicates only when the retry preserves the exact deduplication identity and request semantics. Under agent-driven semantic drift, the gateway can treat a retry as a new operation while the agent has no authoritative knowledge of whether the original operation committed.**

The benchmark explicitly demonstrates **post-dispatch ambiguity plus retry-key/request drift**, rather than asserting that conventional idempotency universally fails:
* **$C_1$ establishes the boundary condition:** Stable, correctly preserved idempotency keys and byte-exact payloads prevent duplication across network drops (0% duplicate rate).
* **$C_2$ establishes the agentic failure mode:** Autonomous agent retry loops (e.g., ReAct prompts, tool-calling LLMs) cannot safely rely on this assumption once semantic drift changes the deduplication identity (100% duplicate rate).

---

## 2. The Anatomy of the Failure

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

## 3. Five Critical Observations

1. **The Backend Committed Before the Response Was Lost:**  
   The target SQLite database ledger successfully committed transaction `tx_id=1` (`debit_id=D-001`, amount: \$100.00) and deducted account balance from \$10,000 to \$9,900.
2. **The Client Observed Only a Transport Failure:**  
   Because the connection severed post-commit but pre-acknowledgment (simulating network partition, proxy drop, or TCP reset), the client HTTP stack caught `HTTP 504 Gateway Timeout` (`GATEWAY_TIMEOUT`).
3. **The Agent Treated Uncertainty as Non-Execution:**  
   Conventional LLM ReAct loops (LangChain, AutoGen, CrewAI, OpenAI Assistant SDKs) classify `504` or `ECONNRESET` as a transient network glitch, interpreting the outcome as *"action did not execute, safe to retry"*.
4. **The Retry Created a Second Committed Debit:**  
   Upon re-dispatching, the database ledger committed transaction `tx_id=2` (`debit_id=D-002`, amount: \$100.00), reducing the balance further to \$9,800. Total debits committed for logical intent `I-001`: **2**.
5. **Conventional Idempotency Failed Under Context Reconstruction:**  
   - Under $C_0$, client omitted or regenerated client identifiers.
   - Under $C_2$, semantic drift (LLM prompt re-serialization, whitespace variation, re-formatted JSON keys, or regenerated UUIDv4 keys) caused an **idempotency cache miss** at the API gateway, allowing the request through to the target service.

---

## 4. Ground Truth Ledger Output

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

## 5. The Architectural Implication

This empirical evidence proves that **"Retry or Else"** is a catastrophic failure mode in autonomous agent architectures.  
To preserve execution integrity without human deadlock, the agent runtime requires an **Agent Execution Integrity Boundary (AEIB)**:
- Pre-dispatch canonicalization (RFC 8785 JCS) binding a deterministic **UUIDv5** anchor to payload semantics before wire transmission.
- Transport-level interception freezing unhedged retries (`retry_permitted = False`).
- Mandatory **out-of-band ledger probes** (`GET /operations/{id}`) to resolve true system state before releasing control.
- Cryptographically signed execution receipts (`OUTCOME_VERIFIED`).
