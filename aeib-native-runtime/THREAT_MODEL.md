# AEIB v1.0 Threat Model & Semantics

## 1. Absolute Reconciliation Deadline (Option A)
The `reconciliationDeadline` enforced in the `ProbeBudget` is a property of the **operation**, not the probe. 
- The deadline is set when `operationId` is first created.
- Once the absolute clock time surpasses this deadline, no further reconciliation probes are permitted.
- The operation becomes permanently terminal at `EFFECT_INDETERMINATE`.
- **Rationale:** Prevents a hostile or misconfigured caller from keeping an operation alive indefinitely by re-invoking the probe layer, nullifying the DoS protection.

## 2. Caller-Supplied Public Key
In v1.0, the `VerifierCli` requires the caller to supply the correct public key for the receipt's `keyId` and `epoch`.
- The verifier performs strict cryptographic mathematical validation.
- It is the responsibility of the auditing environment to map the `keyId` to the correct public key out-of-band.
- Automatic `LedgerKeyStore` lookup and key rotation anchoring is deferred to v1.1.

## 3. Cryptographic Bounds
- All receipts are canonicalized via RFC 8785 (JCS) prior to signing to prevent semantic tampering through whitespace or JSON key reordering.
- The JCS output must strictly conform to RFC 8785 Appendix I vectors.
- Signatures are strictly Ed25519. Post-Quantum (ML-DSA-65) signatures are typed in the schema but nullified in v1.0.
