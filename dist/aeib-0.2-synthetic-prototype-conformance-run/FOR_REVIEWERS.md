# FOR_REVIEWERS.md — AEIB v0.2.0 Synthetic Prototype Review Guide

**Project:** SovereignNexus (Independent Research Initiative • Czech Republic incorporation pending)  
**Lead Researcher:** Andrii Leukhin (`andrejlo123@gmail.com`)  
**Repository:** [https://github.com/sovreignnexus/smaos](https://github.com/sovreignnexus/smaos) (Tag: `v0.2.0`)  
**Package:** `aeib-0.2-synthetic-prototype-conformance-run.zip`  
**Format Designation:** `AEIB_JSON_ED25519_PROTOTYPE`  
**Operational Scope:** Synthetic staging traces & local simulation only. Not a production security control or certified compliance solution.

---

## ⚡ 1. How to Run the Verifier (30 Seconds)

The prototype runs on stock Python 3.8+ using standard library modules (zero pip dependencies required; a pure-Python fallback handles YAML parsing if PyYAML is absent).

```bash
# 1. Unzip the hermetic archive
unzip aeib-0.2-synthetic-prototype-conformance-run.zip
cd aeib-0.2-synthetic-prototype-conformance-run

# 2. Run the offline verifier
python3 verifier/aeib_verify.py
```

### Expected Output:
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

### What the Verifier Tests:
1. **Asymmetric Signatures**: Validates Ed25519 signatures against `public-keys/ed25519-public.pem`.
2. **Digest Linkage**: Asserts `unsigned_payload_hash` matches `signed_payload_hash` byte-for-byte.
3. **Evidence Hash Binding**: Links out-of-band SHA-256 digests in `evidence/transport.jsonl` and `evidence/probe.jsonl`.
4. **Dynamic Rule Precedence**: Evaluates normative disposition rules in priority order from `mapping/transport-to-disposition-mapping.yaml`.
5. **Tamper Guard**: Cross-references `manifest.json` against all artifacts; any tampered receipt or mapping causes immediate non-zero exit.

---

## 🔍 2. What to Look at First (The 5-Minute Tour)

If you only have 5 minutes, inspect these three files in order:

### 1. `receipts/02a-504-ambiguous.json` (The Ambiguity Trap)
This scenario simulates an HTTP 504 Gateway Timeout during an irreversible payment disbursement.
* Look at the `org.smaos.aeib` namespace inside the signed payload.
* Notice that the disposition is **`DISPATCHED_UNCONFIRMED`**.
* Notice that `retry_policy.retry_permitted` is **`false`**.
* *Why it matters*: Standard agent frameworks catch 504 errors and either assume failure or trigger blind retries. AEIB treats transport drops as fundamentally ambiguous, freezing execution until out-of-band verification occurs.

### 2. `receipts/02b-504-reconciled.json` (The Out-of-Band Probe)
This scenario records what happens after the out-of-band adapter probes the downstream ledger using the UUIDv5 idempotency handle.
* The downstream state was found committed.
* Disposition resolves safely to **`OUTCOME_VERIFIED`**.
* Automated retry remains locked (`false`) because the operation already settled.

### 3. `mapping/transport-to-disposition-mapping.yaml` (The Decision Contract)
Review the priority-ordered rule table:
* Downstream state conflicts (Rule 05, Priority 10) supersede raw transport timeouts (Rule 02a, Priority 30).
* Policy context violations (Rule 06) and stale authority tokens (Rule 07) fail-closed before wire dispatch.

---

## ❓ 3. Open Questions for Engineering Feedback

I am looking for blunt, pragmatic critique on these distributed systems questions:

1. **Idempotency Symmetry**: We derive a deterministic UUIDv5 key from a deterministic JSON serialization of the request payload and inject it before dispatch. Does this match how your gateways/services handle deduplication, or do your downstream backends expect arbitrary client tokens?
2. **Ambiguity Taxonomy**: Does our 7-state taxonomy (`OUTCOME_VERIFIED`, `ACK_UNVERIFIED`, `DISPATCHED_UNCONFIRMED`, `RECONCILIATION_NOT_FOUND`, `RECONCILIATION_FAILED`, `PROBE_EXCEPTION`, `REFUSED`) accurately capture the edge cases you see during upstream proxy dropouts?
3. **Probe Failures**: In Scenario 08 (`PROBE_EXCEPTION`), what should happen when the out-of-band reconciliation probe itself times out? How do your saga orchestrators distinguish an unreachable ledger from an absent transaction?
4. **Integration Shape**: Would your platform team prefer this boundary enforcement as a local sidecar proxy (intercepting tool calls over `localhost`), or as an in-process middleware / filter (e.g., `ProofOrStopFilter.java` in Spring WebClient)?

---

## 📬 4. Contact Info & Preferred Feedback Format

* **Researcher**: Andrii Leukhin (Independent Researcher & Founder, SovereignNexus project)
* **Email**: `andrejlo123@gmail.com`
* **Location**: Prague, Czech Republic
* **Repository**: [https://github.com/sovreignnexus/smaos](https://github.com/sovreignnexus/smaos)

### Preferred Feedback Format:
* **Casual 3–5 bullet points** via email or LinkedIn messaging.
* **15-minute video call** to walk through your toughest distributed transaction failure mode.
* **Direct GitHub issues or diff comments** on the open repository.

*Any feedback pointing out broken assumptions, unrealistic invariants, or overlooked race conditions is deeply appreciated.*
