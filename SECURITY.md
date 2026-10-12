# Security Policy & Coordinated Vulnerability Disclosure (`SECURITY.md`)

## 1. Supported Versions

| Version | Branch / Tag | Status |
| :--- | :--- | :--- |
| `1.0.0-rc.1` | `release/v1.0-review-candidate` / `v1.0.0-rc.1` | Supported (Active Release Candidate) |
| `1.1.x-prototype` | `v1.1-roadmap/` | Experimental Prototype / Research Scope |
| `< 1.0.0-rc.1` | Legacy `v0.x` | Unsupported |

---

## 2. Reporting a Vulnerability (RFC 9116 & EU CRA Alignment)

Do **not** open a public GitHub issue for suspected security vulnerabilities in the AEIB runtime, RFC 8785 JCS canonicalizer, Ed25519 receipt verifier, or supply-chain workflows.

* **Primary Reporting Channel:** GitHub Private Vulnerability Reporting (`https://github.com/smaos-ai/aeib/security/advisories/new`) or `security@smaos.ai`.
* **RFC 9116 Discovery File:** [`.well-known/security.txt`](file:///Users/andriileukhin/Documents/SovereignNexus/.well-known/security.txt)
* **Required Report Contents:**
  1. Affected component (`aeib-verifier`, `aeib-runtime`, `src/jcs_canonicalizer.py`, or CI workflow).
  2. Minimal deterministic reproduction input (e.g., JSON receipt vector, PEM public key, or HTTP wire trace).
  3. Observed vs. expected exit code or disposition (`AUTHORIZED`, `REJECTED`, `EFFECT_INDETERMINATE`, `CONFIRMED`, `REFUTED`, `CONFLICT`).

---

## 3. Response & Disclosure Timeline (EU Cyber Resilience Act Alignment)

In alignment with EU Cyber Resilience Act (CRA, Regulation (EU) 2024/2847) vulnerability-handling obligations (applicable from **11 September 2026** for ENISA Single Reporting Platform notifications):

| Milestone | Target SLA | Action |
| :--- | :--- | :--- |
| **Initial Acknowledgment** | **$\le 24\text{ hours}$** | Confirm receipt of report; if an actively exploited vulnerability is confirmed in a deployed product with digital elements, prepare 24-hour early warning. |
| **Technical Triage & VEX Update** | **$\le 72\text{ hours}$** | Reproduce against the deterministic vector suite; assign severity (CVSS v3.1/v4.0) and update CycloneDX 1.6 VEX assertions. |
| **Remediation & Coordinated Advisory** | **$\le 14\text{ days}$ after fix** | Publish signed patch release, regression test vector in `manifest.json`, GitHub Security Advisory (GHSA / CVE), and final report. |

---

## 4. Scope Boundaries & Epistemic Disclaimers

* **Independent Penetration Testing Status:** Not yet performed by an external third-party assessor on `v1.0.0-rc.1`. Current assurance is grounded in deterministic unit, integration, and adversarial negative-vector suites (`NEG-01`–`NEG-08` and `14/14` verifier vectors).
* **Architectural Scaffolding:** Files in `ebpf/` and `hardware_attestation/` are structural scaffolding and do not provide live Linux kernel or CVM silicon enforcement unless deployed and attested on a physical Intel TDX / AMD SEV-SNP Linux host.
* **Key Custody:** The offline verifier (`ReceiptVerifier`) verifies signatures against a caller-supplied public key (`--pubkey`). Key custody, HSM/KMS isolation, RFC 3161 trusted timestamping, and transparency log anchoring must be configured per the deployment architecture in [`THREAT_MODEL.md`](file:///Users/andriileukhin/Documents/SovereignNexus/THREAT_MODEL.md).
