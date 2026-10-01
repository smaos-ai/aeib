# AEI Core Middleware (`aei_core_middleware`)

> **Status:** Research Prototype  
> **Target Module:** `src/aei_core_middleware.py`  
> **Test Suite:** `tests/test_aei_core_middleware.py`  

---

## 1. Focused Control Objective

This module addresses a single, concrete engineering failure mode in autonomous agent systems:
**preventing duplicate execution state during ambiguous transport drops (e.g., HTTP 504 Gateway Timeout or TCP connection severance).**

When an agent dispatches a mutating tool call, the downstream server may commit the mutation, but the network connection can drop before the caller receives a confirmation response. Naive client loops and standard ReAct retry handlers treat this transport exception as an unexecuted failure and issue a speculative retry, resulting in duplicate execution (e.g., duplicate financial debits or double database writes).

---

## 2. Essential Path Mechanics

1. **Pre-Dispatch Defense:** Checks the local in-memory registry. If an `idempotency_key` has already been resolved with `retry_permitted = False`, duplicate dispatch is blocked immediately before touching the network.
2. **Transport Drop Interposition:** Catches `TransportDropException` (HTTP 504 / TCP drops) immediately following dispatch.
3. **Fail-Closed Loop Halting:** Freezes the agent loop at `disposition: UNKNOWN` (`retry_permitted: False`).
4. **Authoritative Out-of-Band Probe:** Queries the target datastore/ledger directly using the original `idempotency_key`.
5. **Disposition Upgrade & Duplicate Suppression:**
   - If probe confirms mutation committed: disposition upgraded to `OUTCOME_VERIFIED` (`retry_permitted: False`). Any subsequent retry attempt is halted.
   - If probe confirms uncommitted: disposition marked `RECONCILIATION_NOT_FOUND` (`retry_permitted: True`).
6. **Cryptographic Sealing:** Emits a `DispositionReceipt` containing the exact `action_id`, `idempotency_key`, `disposition`, and `retry_permitted` flags. The record is serialized using RFC 8785 JSON Canonicalization Scheme (JCS) and signed with Ed25519.

---

## 3. Explicit Scoping Boundaries

To avoid scope creep and preserve formal engineering clarity:
- **Deferred:** eBPF kernel hooks, Confidential VM (TEE) attestation, and pairing-based BBS+ zero-knowledge redaction are maintained in dedicated research extensions and are **not** mixed into this core middleware prototype.
- **Strictly Technical Language:** Documentation and comments focus exclusively on concrete software mechanics (transport codes, idempotency keys, hash digests, signature validation) rather than legal or regulatory assertions.

---

## 4. Empirical Test Results

Validated via `tests/test_aei_core_middleware.py`:

```bash
$ pytest tests/test_aei_core_middleware.py -v
============================= test session starts ==============================
platform darwin -- Python 3.14.3, pytest-9.1.1, pluggy-1.6.0
collected 2 items

tests/test_aei_core_middleware.py::test_1_duplicate_mutation_guard PASSED [ 50%]
tests/test_aei_core_middleware.py::test_2_signature_and_hash_tamper_detection PASSED [100%]

============================== 2 passed in 0.15s ===============================
```

### Verified Invariants:
1. **Duplicate Mutation Guard:** A simulated downstream commit followed by an HTTP 504 wire drop halts the loop. The OOB probe discovers the committed record, sets `retry_permitted = False`, and raises `DuplicateExecutionBlockedError`. The server mutation counter remains strictly `1` despite subsequent agent retry attempts.
2. **Signature & Hash Tamper Detection:** Any 1-byte alteration of the canonical payload string (e.g. flipping `retry_permitted` from `false` to `true`), modifying the declared SHA-256 digest, or tampering with the Ed25519 signature causes `verify_disposition_receipt()` to fail immediately with `ValueError` or `InvalidSignature`.
