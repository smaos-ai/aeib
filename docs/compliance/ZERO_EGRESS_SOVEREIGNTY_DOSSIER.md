# European Sovereignty & Zero-Egress Execution Dossier
## Technical Runbook, Architecture Comparison, and EU Regulatory Alignment Brief

**Classification:** Enterprise Confidential / Public Sector & Regulated Financial Institutions  
**Target:** CISOs, Data Protection Officers (DPOs), Supervisory Regulators (ČNB, BaFin, ECB)  
**System:** Sovereign Multi-Agent OS (SMAOS) / `smaos-audit`  
**Date:** Late 2026

---

## Executive Summary

As autonomous agents transition to executing financial disbursements, database mutations, and code generation, conventional observability and GRC platforms (Microsoft AGT, ServiceNow, Datadog) harvest customer agent execution traces and export telemetry to US-headquartered multi-tenant clouds. 

Under **GDPR Chapter V (Articles 44–49 / Schrems II)** and **DORA Articles 17 & 28(3)**, this creates unacceptable regulatory exposure:
1. **Data Exfiltration & Cross-Border Transfer:** Agent execution traces contain un-redacted PII, proprietary source code, and transactional payloads subject to US CLOUD Act subpoena.
2. **Critical Dependency Risks:** Cloud-first telemetry fails during wide-area network drops, obscuring the exact moment when transport drops trigger toxic agent hallucination.

`smaos-audit` is architected from Ring 0 up for **Air-Gapped, Zero-Egress Execution**. It operates strictly on local silicon with zero cloud calls, zero outbound sockets, and deterministic offline verification.

---

## Part 1: Zero-Egress Audit Runbook

This runbook guides bank security engineers through executing an enterprise audit trace verification on completely isolated hardware while mathematically verifying that 0 bytes leave the host.

### 1.1 Air-Gapped Environment Preparation

```bash
# 1. Verify container image signature and digest
docker load -i smaos-audit-v1.1.0-airgap.tar.gz

# 2. Inspect image digest against published SCITT Merkle root
docker inspect --format='{{index .RepoDigests 0}}' smaos-audit:v1.1.0
```

### 1.2 The Zero-Egress Execution Ritual

Run the container using explicit network isolation (`--network none`):

```bash
docker run --rm \
  --network none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid \
  -v /var/audit/staging_traces.jsonl:/data/traces.jsonl:ro \
  -v /var/audit/output:/output:rw \
  smaos-audit:v1.1.0 \
  cega-scan \
    --input /data/traces.jsonl \
    --format json \
    --out /output/dora_art17_gap_report.json \
    --export-xbrl /output/DORA_ROI_VENDOR_CONTRIBUTION.csv
```

### 1.3 Real-Time Network Egress Verification Protocol

To satisfy lead internal auditors and DPA inspectors, execute `tcpdump` on the host during the scan:

```bash
# Terminal 1: Attach packet capture to all network interfaces (excluding loopback)
sudo tcpdump -i any -nn 'not host 127.0.0.1 and not arp' -w /tmp/egress_audit.pcap

# Terminal 2: Run the 250-trace audit scan
docker run --rm --network none ... smaos-audit:v1.1.0 ...

# Terminal 3: Verify packet capture result
tcpdump -r /tmp/egress_audit.pcap
```

**Expected Host Verification Output:**
```text
reading from file /tmp/egress_audit.pcap, link-type LINUX_SLL2 (Linux cooked v2)
0 packets captured
0 packets received by filter
0 packets dropped by kernel
```

**Kernel Socket Audit:**
```bash
# Verify no active or listening foreign sockets from the audit PID
ss -tulpn | grep -E "cega|smaos"
# Expected output: (EMPTY - 0 listening or connected sockets)
```

---

## Part 2: Architecture Comparison Matrix

| Architectural Dimension | Cloud-First Platforms (Microsoft AGT, ServiceNow, Datadog) | Sovereign Local Fuzzer (`smaos-audit` / STAR) |
| :--- | :--- | :--- |
| **Execution Plane** | Multi-tenant US cloud (Azure / AWS / GCP) | Local hardware / Dedicated on-premise VPC |
| **Network Egress** | Continuous telemetry streams (HTTPS / gRPC) | **Zero Egress (`--network none`)** |
| **PII & Data Residency** | Customer traces harvested to vendor cloud | **Zero Data Transfer** (traces remain on-prem) |
| **US CLOUD Act Exposure** | **High** (subject to US extraterritorial warrants) | **Zero** (no US corporate entity holds data) |
| **Fault Mode Behavior** | Assumes SDK status is true; fails on network drop | **Active wire fuzzer** (injects 504 / TCP RST) |
| **Normative Precedence** | Undefined (harness context decides status) | Strict order (`UNKNOWN` overrides `CONFIRMED`) |
| **Offline Verification** | **Impossible** (requires cloud API keys & SaaS auth) | **Native** (Single-file `smaos_verify.html` in browser) |
| **DORA xBRL-CSV Output** | Manual export or proprietary JSON | Native schema-validated RTS 2024/1772 register |
| **Defense & Tier-1 Ready** | Requires cloud risk exception waiver | **Standard compliant** (air-gapped safe harbor) |

---

## Part 3: European Sovereignty Brief

### 3.1 GDPR Chapter V Compliance (Cross-Border Data Transfers)

1. **The Risk with Incumbents:**  
   Under the *Schrems II* (Case C-311/18) doctrine and the European Data Protection Board (EDPB) recommendations 01/2020, transmitting operational logs containing user identifiers, payment details, or corporate IP to US-based cloud infrastructure requires supplementary technical measures that guarantee US intelligence agencies cannot access the data in clear text. Passive observability tools that stream traces fail this threshold.
2. **The SovereignNexus Solution:**  
   Because `smaos-audit` executes entirely inside local Docker runtimes without network interfaces, **no international data transfer occurs under GDPR Article 44**. Data residency is absolute, eliminating the need for Standard Contractual Clauses (SCCs) or Transfer Impact Assessments (TIAs).

### 3.2 DORA Article 17 & Article 28(3) Alignment

1. **Local Operational Resilience (DORA Art. 17):**  
   Financial entities must detect, classify, and report major ICT-related incidents autonomously. Relying on an external cloud provider to audit agent transaction validity introduces a single point of failure: when the external network fails, the bank loses audit visibility. `smaos-audit` runs locally, maintaining continuous verification even during total telecom isolation.
2. **Critical Third-Party ICT Risk (DORA Art. 28(3)):**  
   DORA mandates that financial entities maintain a Register of Information covering all contractual arrangements on the use of ICT services. By deploying `smaos-audit` as an offline, air-gapped container rather than a SaaS subscription, the bank avoids categorizing the audit tool as a Critical ICT Third-Party Provider (CTPP) subject to direct Joint Oversight under Article 31, dramatically simplifying supervisory filings with the European Supervisory Authorities (EBA, EIOPA, ESMA).

### 3.3 National Competent Authority Readiness (ČNB & BaFin)

* **Czech National Bank (ČNB):** Aligns with Decree No. 367/2024 Coll. on ICT operational resilience and security controls for payment institutions.
* **German Federal Financial Supervisory Authority (BaFin):** Fully conforms to Supervisory Requirements for IT in Financial Institutions (BAIT) Chapter 8 (IT Operations) and Chapter 10 (Individual Data Processing).

---

## Conclusion

By formalizing Moat 4 into a tangible, air-gapped runbook and regulatory brief, SovereignNexus provides European CISOs with a mathematically verified safe harbor: **full multi-agent audit compliance with zero cloud egress and zero sovereignty compromise.**
