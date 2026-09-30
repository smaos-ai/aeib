# AEIB v0.2 Synthetic Prototype Conformance Run
**Agent-Effect Integrity Benchmark (AEIB) — Hermetically Sealed Conformance Package**  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  

---

## 🏛️ Architectural Stance & Overview

This prototype does not claim to replace NVIDIA OpenShell, Archipelo, or established policy engines. 

Instead, it demonstrates the **missing post-dispatch reconciliation layer**:
- Integrates with existing transport proxies (such as `mcp-shield`) and receipt envelopes (such as IETF SCITT drafts).
- Extends standard logging with a **deterministic 7-state ambiguity taxonomy** that prevents catastrophic phantom retries upon encountering network timeouts (`HTTP 504`, `TCP RST`).
- Enforces the **5-Stage Signature Lifecycle** with the `org.smaos.aeib` governance namespace placed strictly inside the signed payload view.

---

## 🛠️ Quickstart (Independent Verification)

```bash
# 1. Install minimal dependencies
pip install -r requirements.txt

# 2. Run the prototype benchmark (executes 8 synthetic wire scenarios)
python3 run_prototype_benchmark.py

# 3. Verify all receipts, priority mappings, and manifest integrity
python3 verifier/aeib_verify.py
```

Expected output:
```text
[+] 01-confirmed.json: VALID (Signature, Evidence Bindings, and Rule RULE-01-CONFIRMED verified — disposition: OUTCOME_VERIFIED)
[+] 02a-504-ambiguous.json: VALID (Signature, Evidence Bindings, and Rule RULE-02A-504-AMBIGUOUS verified — disposition: DISPATCHED_UNCONFIRMED)
[+] 02b-504-reconciled.json: VALID (Signature, Evidence Bindings, and Rule RULE-02B-504-RECONCILED verified — disposition: OUTCOME_VERIFIED)
[+] 03-reset-not-found.json: VALID (Signature, Evidence Bindings, and Rule RULE-03-RESET-NOT-FOUND verified — disposition: RECONCILIATION_NOT_FOUND)
[+] 04-payload-mismatch.json: VALID (Signature, Evidence Bindings, and Rule RULE-04-PAYLOAD-MISMATCH verified — disposition: RECONCILIATION_FAILED)
[+] 05-conflict.json: VALID (Signature, Evidence Bindings, and Rule RULE-05-CONFLICT verified — disposition: RECONCILIATION_CONFLICT)
[+] 06-context-refused.json: VALID (Signature, Evidence Bindings, and Rule RULE-06-CONTEXT-REFUSED verified — disposition: CONTEXT_POLICY_VIOLATION)
[+] 07-authority-expired.json: VALID (Signature, Evidence Bindings, and Rule RULE-07-AUTHORITY-EXPIRED verified — disposition: AUTHORITY_NOT_BOUND)
```

---

## 🔒 The 5-Stage Signature Lifecycle

Every receipt in `receipts/*.json` is minted through five immutable phases:
1. **Stage 1 (Unsigned Payload Assembly)**: Construct `unsigned_payload` containing action identity, actor, transport status, out-of-band evidence bindings, and the `org.smaos.aeib` namespace.
2. **Stage 2 (Payload Digest Computation)**: Compute the canonical SHA-256 hash `unsigned_payload_hash`.
3. **Stage 3 (Signable View Construction)**: Build `signable_view` binding the payload and its hash.
4. **Stage 4 (Asymmetric Ed25519 Signing)**: Sign the signable view using the private key (`ED25519-KEY-AEIB-V02`).
5. **Stage 5 (Receipt Assembly)**: Wrap into `AEIB_JSON_ED25519_PROTOTYPE` with signature metadata and public key reference.

---

## 📁 Package Contents

- `run_prototype_benchmark.py`: Benchmark runner; ensures clean directory resets and runs 8 synthetic scenarios.
- `verifier/aeib_verify.py`: Independent offline verifier evaluating dynamic priority-ordered rules and signature integrity.
- `mapping/transport-to-disposition-mapping.yaml`: Priority-ordered mapping contract (e.g. `RECONCILIATION_CONFLICT` supersedes `DISPATCHED_UNCONFIRMED`).
- `manifest.json`: Cryptographic manifest binding mapping contracts, receipts, and raw evidence.
- `receipts/`: 8 Ed25519-signed JSON execution receipts.
- `evidence/`: 
  - `transport.jsonl`: 8 raw transport-layer dispatch events (idempotently reset).
  - `probe.jsonl`: Out-of-band probe verification records.
- `public-keys/`: Ed25519 public key in PEM format.
- `LIMITATIONS.md`: Formal boundaries, disclaimer statements, and engineering scope.

---

## ⚠️ Mandatory Disclaimer

This is a synthetic prototype for engineering review, not a production security control. It is **not RFC 8785 compliant**, **not COSE_Sign1 compliant**, and **uses synthetic data for engineering review only**.
