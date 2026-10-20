# Effectuation-Boundary Verification (EBV)
## Architectural Reference Specification & Candidate Implementation Model

**Document Status:** Academic Preprint & Informational Candidate Specification  
**Reference Alignment:** Aligned with vocabulary proposed in IETF Internet-Draft `draft-das-agent-execution-finality-00` / `draft-das-agentic-execution-finality-02`  
**Affiliation:** SovereignNexus Autonomous Systems Research Group & Lviv Polytechnic National University Academic Collaboration  
**Date:** October 2026  
**Target Submission:** Zenodo Open-Access Archive / IETF Informational Candidate Track  

> **Epistemic Notice & Normative Scope Boundaries**  
> This specification documents an architecture prototype and candidate reference implementation evaluated under the stated local verification model, deterministic simulation testing (DST), and native cryptographic testbeds.  
> Internet-Drafts possess no formal IETF standing and are not endorsed by the IETF. This document does not claim IETF consensus or endorsement.  
> Digital signatures provide authenticity of authorship and historical integrity; they do not evaluate host runtime uncompromised status or ensure transport confidentiality.  
> Local write-ahead logging (WAL) commits establish local durable evidence, not external payment-rail finality.

---

### Abstract

Autonomous software agents acting on external APIs, payment rails, and enterprise backends face a fundamental distributed systems dilemma: the **in-flight ambiguity gap**. When a transport-layer connection fails mid-flight (e.g., HTTP 504 Gateway Timeout or TCP reset), the agent cannot discern whether the requested mutation succeeded, failed, or remains queued downstream. Naive retries risk catastrophic duplicate mutations, while silent abandonment creates state drift.

This paper specifies **Effectuation-Boundary Verification (EBV)**, an architecture that decouples agent reasoning from consequential wire execution through a host-side **Protected Enforcement Domain (PED)**. EBV enforces:
1. Deterministic Content-Addressed Action Identifiers (CAIDs) calculated via RFC 8785 JSON Canonicalization Scheme (JCS);
2. Pre-dispatch write-ahead logging (`DirectIoWal` / `O_DIRECT` / `F_FULLFSYNC`) establishing a Protected Evidence Store;
3. A formal 7-state latch automaton where transport ambiguity transitions strictly to `EFFECT_INDETERMINATE`, locking blind retries until resolved through bounded, authoritative probing;
4. Post-Quantum Evidence Envelopes (PQEE) binding receipts using hybrid Ed25519 and FIPS 204 ML-DSA-65 signatures;
5. Selective disclosure receipts resolving GDPR Article 17 right-to-erasure against DORA Article 17 audit retention via salted SHA-256 field-path commitments.

The reference implementation was evaluated across 10,000 seeded deterministic simulation testing (DST) schedules, observing zero duplicate mutations across 3,018 injected transport timeouts.

---

## 1. Introduction & The Problem of In-Flight Ambiguity

Modern agentic systems generate tool calls dynamically. When interacting with consequential sinks (e.g., banking gateways, cloud infrastructure, supply chain ERPs), execution safety cannot rely on model self-restraint or prompt guidelines.

```
+------------------+         +----------------------------+         +----------------------+
|  Autonomous      |  Act    |   Host-Side Boundary       |  Wire   |   External Rail      |
|  Agent Runtime   |-------->|   (Protected Enforcement   |-------->|   (Finality Sink)    |
|  (Untrusted)     | Intent  |    Domain - PED)           | Mutation|   (Bank / API / ERP) |
+------------------+         +----------------------------+         +----------------------+
                                           |
                                           v
                             +----------------------------+
                             |  Protected Evidence Store  |
                             |  (Durable WAL Ledger)      |
                             +----------------------------+
```

When an external invocation returns an ambiguous transport fault:
- **The Duplicate Hazard:** If the downstream target executed the mutation before the timeout, re-dispatching with a fresh request ID results in duplicate execution (e.g., double-charging a customer or duplicating a resource provisioning call).
- **The Abandonment Hazard:** If the agent assumes failure and aborts, downstream resources remain allocated or funds remain debited without causal traceability in the agent's context.

EBV formalizes the boundary required to eliminate blind retries, contain uncertainty, and reconcile execution states deterministically.

---

## 2. Terminology Mapping & System Boundary Crosswalk

EBV terminology aligns with `draft-das-agent-execution-finality-00`:

| Internet-Draft Term | AEIB Architecture Primitive | Operational Meaning | System Boundary Caveat |
|---|---|---|---|
| **Protected Enforcement Domain (PED)** | Host-Side AEIB Authorization & Escrow Service | Isolated boundary evaluating permissions, budgets, and epochs prior to dispatch. | Boundary enforcement is environment-specific (Unix Domain Socket, process jail, microVM). |
| **Candidate Act** | Signed Proposed Action / Pre-Dispatch Intent | The agent's proposed mutation before wire transmission. | Non-effective until validated, escrowed, and dispatched. |
| **Finality Sink** | External Target System / Settlement Rail | The remote system where real-world state mutation occurs. | Local WAL commits do not equal external-rail settlement. |
| **Protected Evidence Store** | Local Durable Ledger (`DirectIoWal`) | Append-only, durable evidence log recording intents, escrows, and receipts. | Stores local causal proof; does not force external side-effects. |
| **Non-Effective State** | `PROPOSED`, `STAGED_ESCROWED`, `DISPATCHED`, `EFFECT_INDETERMINATE`, `REFUTED` | States where external outcome is pending, unconfirmed, or denied. | An action in `DISPATCHED` may be in-flight or already effective downstream. |
| **Finality** | Authoritative External Confirmation / Refutation | Definitive settlement confirmed via downstream status probe or idempotency lookup. | AEIB cannot force external rail finality; it reconciles local uncertainty against target evidence. |

---

## 3. Formal State Machine Formulation

The EBV lifecycle is governed by a finite state automaton $\mathcal{M} = (\mathcal{S}, \Sigma, \delta, s_0, \mathcal{F})$:
- $\mathcal{S} = \{\text{PROPOSED}, \text{STAGED\_ESCROWED}, \text{DISPATCHED}, \text{EFFECT\_INDETERMINATE}, \text{CONFIRMED}, \text{REFUTED}, \text{HALTED}\}$
- Initial State: $s_0 = \text{PROPOSED}$
- Terminal Absorbing Sinks: $\mathcal{F} = \{\text{CONFIRMED}, \text{REFUTED}, \text{HALTED}\}$
- Uncertainty Latch State: $\text{EFFECT\_INDETERMINATE}$

### 3.1 State Transition Definitions

```
                     [PROPOSED]
                     /        \
          Admissible/          \Rejected / Expired
                   v            v
          [STAGED_ESCROWED]   [REFUTED] (Terminal)
                   |
        WAL Flushed|
                   v
              [DISPATCHED]
              /    |     \
     HTTP 200/     |      \HTTP 4xx
            v   HTTP 504   v
       [CONFIRMED] |      [REFUTED] (Terminal)
       (Terminal)  v
           [EFFECT_INDETERMINATE] (LATCHED)
              /            \
    Probe    /              \Probe
   Settled  v                v Unseen
       [CONFIRMED]        [REFUTED]
       (Terminal)         (Terminal)
```

Transitions are strictly constrained by conditions $\mathcal{C}$:
1. $\delta(\text{PROPOSED}, \text{evaluate\_and\_stage}) \to \text{STAGED\_ESCROWED}$ iff schema valid $\land$ budget available $\land$ epoch fresh.
2. $\delta(\text{PROPOSED}, \text{reject\_admission}) \to \text{REFUTED}$ iff invalid schema $\lor$ budget exceeded $\lor$ stale epoch.
3. $\delta(\text{STAGED\_ESCROWED}, \text{wire\_invoke}) \to \text{DISPATCHED}$ iff pre-dispatch WAL entry is flushed (`DirectIoWal` fsync complete).
4. $\delta(\text{DISPATCHED}, \text{wire\_success}) \to \text{CONFIRMED}$ iff HTTP 200 $\land$ valid target receipt.
5. $\delta(\text{DISPATCHED}, \text{transport\_failure}) \to \text{EFFECT\_INDETERMINATE}$ iff HTTP 504, timeout, or TCP reset observed.
6. $\delta(\text{DISPATCHED}, \text{downstream\_rejection}) \to \text{REFUTED}$ iff HTTP 4xx deterministic rejection.
7. $\delta(\text{EFFECT\_INDETERMINATE}, \text{probe\_settled}) \to \text{CONFIRMED}$ iff authoritative status lookup verifies execution.
8. $\delta(\text{EFFECT\_INDETERMINATE}, \text{probe\_unseen}) \to \text{REFUTED}$ iff authoritative status lookup confirms zero transaction recorded.
9. $\delta(s, \text{operator\_or\_safety\_halt}) \to \text{HALTED}$ for any non-terminal state $s \notin \mathcal{F}$.

### 3.2 Model-Checker Verification

The reference state machine was formally analyzed using `tools/ebv_state_machine_checker.py`:
- **Theorem 1 (Absence of Blind Retries):** There exists no directed path from $\text{EFFECT\_INDETERMINATE}$ to $\text{DISPATCHED}$ without passing through an authoritative terminal state ($\text{CONFIRMED}$ or $\text{REFUTED}$).
  $$\forall p \in \text{Paths}(\text{EFFECT\_INDETERMINATE} \rightsquigarrow \text{DISPATCHED}), \quad p \cap \{\text{CONFIRMED}, \text{REFUTED}\} \neq \emptyset$$
- **Theorem 2 (Deadlock-Freedom & Terminal Reachability):** From every non-terminal state $s \in \mathcal{S} \setminus \mathcal{F}$, there exists at least one reachable terminal state $t \in \mathcal{F}$.
- **Theorem 3 (Absorbing Sinks):** Terminal states have an out-degree of zero ($\text{OutDeg}(t) = 0, \forall t \in \mathcal{F}$). Once confirmed, refuted, or halted, the candidate act cannot transition further.

---

## 4. Post-Quantum Evidence Envelope (PQEE)

Long-term evidentiary records (such as those mandated by DORA Article 17 and EU AI Act Article 12) require protection against future quantum cryptanalytic compromise. The Post-Quantum Evidence Envelope (PQEE) provides a non-separable dual-signature format.

### 4.1 Hybrid Scheme Formulation

$$\text{Valid}(\text{envelope}) \iff \text{Verify}_{\text{Ed25519}}(pk_{\text{ed}}, m, \sigma_{\text{ed}}) \land \text{Verify}_{\text{ML-DSA-65}}(pk_{\text{ml}}, m, \sigma_{\text{ml}})$$

Where:
- $m = \text{SHA-256}(\text{JCS}(S_{\text{payload}}))$ represents the RFC 8785 canonical digest.
- Classical component: Ed25519 (RFC 8032) providing low-latency verification and legacy tooling interoperability.
- Post-quantum component: ML-DSA-65 (FIPS 204) lattice-based digital signature algorithm executed via native compiled Rust (`RustCrypto/ml-dsa`).
- Policy: `require_both_valid`. If either signature fails or is omitted, verification fails closed.

### 4.2 Machine-Readable Cryptographic Bill of Materials (CBOM)

Each envelope references an explicit CycloneDX 1.6 Cryptographic Asset entry:
```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.6",
  "component": {
    "type": "cryptographic-asset",
    "name": "hybrid-ed25519-mldsa65-v1",
    "cryptoProperties": {
      "assetType": "algorithm",
      "algorithmProperties": {
        "primitive": "signature",
        "parameterSetIdentifier": "ML-DSA-65",
        "nistQuantumSecurityCategory": 3,
        "implementationLevel": "native_rust",
        "executionEnvironment": "host_user_space"
      }
    }
  }
}
```

---

## 5. Selective Disclosure & Privacy-Preserving Receipts

Auditing autonomous actions presents a regulatory tension between **DORA Article 17** (mandatory 5-year retention of ICT audit logs) and **GDPR Article 17** (data subject's right to erasure).

EBV resolves this using RFC 8785 canonical field-path blind salt commitments:
1. When generating the execution receipt, sensitive leaf fields (e.g., `user_pii.iban`, `customer_ssn`) are hashed alongside a cryptographically secure 256-bit salt:
   $$C_i = \text{SHA-256}(\text{path}_i \parallel \text{salt}_i \parallel \text{JCS}(\text{value}_i))$$
2. The root Merkle receipt and PQEE envelope commit to the blind commitment map $\{ \text{path}_i \mapsto C_i \}$.
3. When erasure is executed, the raw value and salt are purged from the operational data store.
4. The remaining non-PII fields, Merkle inclusion path, and post-quantum receipt signatures remain mathematically verifiable without exposing redacted data.

---

## 6. Empirical Evaluation & Deterministic Simulation Testing

The reference implementation was evaluated under rigorous simulation and physical hardware testing.

### 6.1 10,000-Schedule Deterministic Simulation Testing (DST)

A seeded discrete-event simulation harness (`output/dst-report-20261020.json`) evaluated 10,000 execution schedules under adversarial fault injection:
- Pre-commit network drops (simulating network partition before reaching the target);
- Post-commit lost acknowledgments (simulating HTTP 504 timeouts where target executed mutation);
- Upstream client crashes and sudden restarts during in-flight dispatches.

**Observed Empirical Results:**
```text
Schedules Evaluated       : 10,000
Total Dispatch Requests   : 6,520
Injected Transport Drops  : 3,018
Blind Retries Blocked     : 3,018 (100.0%)
Reconciled Outcomes       : 6,520 (100.0%)
Observed Duplicate Acts   : 0 (0.000%)
Invariant Violations      : 0
```

### 6.2 DORA Article 17 Restorability Evaluation

Physical backup and clean-room recovery verification (`output/backup-restorability-receipt.json`) evaluated bit-for-bit restoration from external storage (`/Volumes/EXTssd/SovereignNexus_Backup`):
- Measured Recovery Time Objective (RTO): **1.4674 seconds** (Threshold: $< 60.0\text{ s}$).
- Git object integrity (`git fsck`): Clean (exit code 0).
- Hash verification across critical artifacts (`smaos_verify.wasm`, `evidence/cbom.json`, `Cargo.toml`): 6/6 verified bit-identical.

---

## 7. Descriptive Telemetry: Agent Execution Integrity Telemetry (AEIT)

Telemetry emitted by the boundary is governed by the principle of **Separation of Concerns**:
- Usage Policy: `input_only_not_decision`.
- Telemetry never acts as an authorization oracle or credit underwriter.
- Transport uncertainty latching (`EFFECT_INDETERMINATE`) is classified as a positive/neutral safety event when properly reconciled, ensuring that boundary latency does not penalize operational metrics.

---

## 8. Limitations & Future Work

1. **Host-Level TCB Dependency:** The Protected Enforcement Domain relies on the integrity of the host OS kernel. Scaffolding for hardware-rooted execution environments (Intel TDX, AMD SEV-SNP) is currently structural.
2. **External Settlement Asynchrony:** Downstream targets lacking idempotency keys or status lookup endpoints cannot support automated reconciliation, requiring operator intervention.
3. **PQC Performance Overhead:** Native ML-DSA-65 signature generation introduces higher CPU overhead compared to Ed25519; batched verification models are under active investigation.

---

## 9. References

1. Das, S. et al. *Protected Execution-Finality Architecture for AI and Autonomous Systems*. IETF Internet-Draft `draft-das-agent-execution-finality-00` / `-02`, 2026.
2. NIST. *Module-Lattice-Based Digital Signature Standard*. FIPS PUB 204, August 2024.
3. European Parliament & Council. *Digital Operational Resilience Act (DORA)*. Regulation (EU) 2022/2554, 2022.
4. European Parliament & Council. *Artificial Intelligence Act*. Regulation (EU) 2024/1689, 2024.
5. Rundgren, A. *JSON Canonicalization Scheme (JCS)*. RFC 8785, June 2020.
6. Josefsson, S. & Liusvaara, I. *Edwards-Curve Digital Signature Algorithm (EdDSA)*. RFC 8032, January 2017.
7. CycloneDX. *CycloneDX v1.6 Specification: Cryptographic Bill of Materials (CBOM)*. OWASP Foundation, 2024.
