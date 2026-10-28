# 🏛️ SMAOS - Final Scope Lock (v0.1.0)

This document defines the absolute, verified, and shippable scope for the v0.1.0 release. It establishes the technical boundaries, regulatory mappings, and commercial engagement tiers.

---

## 1. Product Line Architecture

* **`aeib-receipt-fuzzer` (v0.2.0):** The open-core local fault injection proxy and evaluator.
* **`smaos-audit` (v0.1.0):** The forensic engine generating DORA Article 17 and ISO 42001 compliance evidence.
* **`star-protocol` (v0.1.0 Roadmap):** JCS (RFC 8785) + Ed25519 / ML-DSA-65 (FIPS 204) cryptographic Merkle DAG receipts.

---

## 2. Container Spec & Zero-Egress Boundary

* **Image Name:** `sovereignnexus/aeib-receipt-fuzzer:v0.1.0`
* **Single Launch Command:** `docker compose up`
* **Network Isolation:** `--network none` (or `internal: true` bridge for localhost loopback UI). Absolutely zero external API calls, cloud telemetry, or external DNS resolution.
* **Volume Mounts:**
  * `./audit_out:/app/audit_out:rw` (Generated reports, Java filters, Mermaid traces)
  * `./fixtures:/app/fixtures:ro` (Test vectors, local PII test payloads, staging traces)
* **Target Runtimes Supported:**
  * **Enterprise JVM:** Java 21+ (Spring Boot `WebClient`, Spring AI, LangChain4j)
  * **Python Ecosystem:** Python 3.10+ (FastAPI, LangChain, CrewAI, AutoGen)

---

## 3. In-Scope Fault Modes

1. **HTTP 504 Gateway Timeout:** Transport drops post-dispatch before settlement acknowledgement.
2. **TCP RST (Socket Reset):** Connection severed abruptly during payment payload execution.
3. **Timeout Swallow:** Agent harness catches transport exception but falsely logs `CONFIRMED`.
4. **Idempotency Break:** Agent retries an unacknowledged mutating tool call, creating a double-spend hazard.

---

## 4. In-Scope Guards (The Engine)

* **Local PII/PCI-DSS Scrubber:** In-memory redaction of IBAN, PAN, JWT, and Bearer tokens *before* any disk write.
* **Proof-or-Stop Invariant:** Hard enforcement of `Evidence Absent => UNKNOWN`.
* **Visual Evidence:** Auto-generation of `audit_trace.mermaid` sequence diagrams.
* **Compliance Mappers:**
  * **EU DORA** (RTS 2024/1772 - Art. 17 Incident Classification & RT.01.03 register)
  * **ISO/IEC 42001** (Clause 9 Runtime Audit Evidence)
  * **CAICT ATH 1.0** (9-Step Decentralized Trusted Handshake Mapping)

---

## 5. Out-of-Scope (Summer 2026)

* No production eBPF sidecar or live traffic interception (Moved to Fall roadmap).
* No hosted SaaS / cloud dashboard (Violates zero-egress premise).
* No automatic refactoring of client business logic (Provides `ProofOrStopFilter.java` snippet only).
* No access required to client production databases.

---

## 6. Commercial Engagement Tiers

* **Tier 0: Open-Source Local Container (€0):** Self-hosted Docker evaluation running on client loopback.
* **Tier 1: 48-Hour Staging Diagnostic (€1,500 / ~38,000 CZK):** Ingestion of 250+ staging traces, Toxic Receipt Index (TRI %) calculation, and wire overclaim risk report.
* **Tier 2: 5-Day Forensic Reconciliation (€2,500 / ~63,000 CZK):** Full wire fault-injection pass, DORA Article 17 gap report, and delivery of custom `ProofOrStopFilter.java` integrations.
* **Tier 3: Continuous Production License (€4,500/month):** Air-gapped sidecar monitoring live payment wires and enforcing deterministic `UNKNOWN` circuit breakers.

---

## 7. Acceptance Criteria (v0.1.0 Release)

* [x] Container builds and runs via `docker compose up` with zero configuration.
* [x] Generates board-ready Mermaid trace + regulator JSON in <60 seconds.
* [x] Zero bytes of external egress verified via packet capture / `docker inspect`.
* [x] All 334+ automated tests green across modules.
