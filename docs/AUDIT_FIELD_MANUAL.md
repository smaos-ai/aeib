# SovereignNexus: 5-Gate Technical Audit Field Manual

**Classification:** STRICTLY CONFIDENTIAL / CLIENT-FACING  
**Target Audience:** Enterprise CISOs, VP of Engineering, Big-4 IT Auditors  
**Objective:** Provide a 60-second, locally reproducible terminal script that mathematically proves the SovereignNexus enterprise substrate is 100% air-gapped, non-mocked, and computationally governed.

---

## 🏛️ Executive Abstract

In the AI governance market, "compliance" is traditionally demonstrated via slide decks and SaaS dashboards. SovereignNexus takes a fundamentally different approach: **Mathematical Verifiability at the Hardware Level.**

This manual contains the **5-Gate Audit Protocol**. It is designed to be executed live on the client's own hardware, shifting the burden of proof from marketing claims to cryptographic facts. If the substrate fails any of these 5 gates, the audit is failed. 

---

## 🛡️ The 5-Gate Execution Protocol

### GATE 1: The Network Isolation Proof (Zero Egress)
**The Claim:** SovereignNexus operates 100% offline with zero cloud API dependencies, ensuring no financial telemetry or PII ever leaves the client's premises.
**The Audit Test:** 
Deploy the runtime container strictly without network interfaces and attempt to monitor for egress traffic.
```bash
# 1. Start the container in absolute isolation
docker run --rm --network none sovereignnexus/provenance-auditor:v0.2.0

# 2. In a separate terminal, attempt to catch any egress traffic on the host
sudo tcpdump -i any host <container_ip>
```
**Expected Result:** `0 packets captured, 0 packets received by filter`. The substrate successfully processes millions of rows of telemetry entirely locally.

### GATE 2: Falsification & Signature Tamper Resistance
**The Claim:** The system cannot be fooled by spoofed logs or AI hallucinated timestamps. Every state transition is bound to an RFC 8785 JSON Canonicalization Scheme (JCS) digest and an Ed25519 signature.
**The Audit Test:** 
Intercept a valid trace file and mutate a single byte (e.g., change an amount from `100` to `101`).
```bash
# 1. Mutate the payload
sed 's/"amount": 100/"amount": 101/' expected.jsonl > tampered.jsonl

# 2. Feed the tampered payload to the verification engine
cat tampered.jsonl | ./smaos-verify
```
**Expected Result:** The engine instantly catches the mutated state, triggering a `HALT_DIGEST_MISMATCH`. The operation is frozen, and an alert is logged to the DORA incident journal.

### GATE 3: Bitemporal AST Drift & Determinism
**The Claim:** The system dynamically calculates state transitions based on exact byte-offsets and logical clocks, meaning it does not rely on fragile, hardcoded line numbers.
**The Audit Test:** 
Inject random spaces, empty lines, and timestamp jitter (+/- 3s) into the raw log files before processing.
```bash
# 1. Inject chaos into the raw Splunk logs
python3 scratch/inject_jitter.py input.log > jittered_input.log

# 2. Run the dynamic bundler
cat jittered_input.log | python3 ocr-audit-engine/src/ocr_audit/bundler.py
```
**Expected Result:** The bundler successfully groups the mutating events into isolated `ActionBundle` buckets using its dynamic cascade window, ignoring the formatting chaos and maintaining 100% determinism.

### GATE 4: Net Ledger Conservation Invariant (The Saga Reconciler)
**The Claim:** If a network drop or 504 timeout occurs mid-transfer, the system will never leave the ledger in a corrupted state (Delta != 0).
**The Audit Test:** 
Simulate a catastrophic HTTP 504 gateway timeout exactly as the AI approves a transfer.
```bash
# 1. Feed a 504 timeout trace to the Saga Reconciler
cat traces/simulated_504_drop.jsonl | python3 ocr-audit-engine/src/ocr_audit/saga_reconciler.py
```
**Expected Result:** The engine defaults to `verdict: UNKNOWN`. The bitemporal saga engine immediately issues an idempotent `COMPENSATED_ROLLBACK` query, enforcing the net ledger invariant (Sum Delta = 0.00).

### GATE 5: Zero External Dependency (The "No pip" Rule)
**The Claim:** The core telemetry extraction and proof engines do not require downloading third-party libraries (which introduce supply-chain vulnerabilities).
**The Audit Test:** 
Execute the core parsing engine on a completely bare Python 3.12 installation.
```bash
# 1. Verify no external packages exist
pip freeze > /dev/null

# 2. Execute the Splunk-to-SMAOS telemetry converter
cat raw_splunk.json | python3 scratch/splunk_to_smaos.py
```
**Expected Result:** Clean execution. The converter relies entirely on the Python Standard Library, securely parsing, transforming, and outputting SMAOS-compliant data without triggering security flags.

---

## 📈 Post-Audit Deliverables
Upon successful completion of the 5-Gate Audit on the client's local machine, the technical sales engineer will transition directly to the **SOW Staging Audit Proposal** (Deliverable D2), locking in the €1,500 5-day on-premise ingress diagnostic.
