# ISO/IEC 42001:2023 & EU AI Act Auditor Briefing Pack
## Consequence-Integrity Telemetry, Seven-Layer Authorization Decoupling, and Objective Execution Proof

- **Document Version:** `1.0.0` (October 2026)
- **Target Audience:** Lead ISO/IEC 42001 Auditors, Notified Body Technical Assessors, Internal Compliance Officers, and Enterprise AI Governance Committees.
- **Classification:** Audit Evidence Specification & Technical Control Crosswalk
- **Governing Architecture:** AEIB v0.4.0 (Agentic Execution-Integrity & Governance Core)
- **Status:** Bounded synthetic benchmark and execution-evidence proposal, with reported passing tests and a prior-art-adjusted claim set, prepared for independent reproduction.
- **Reference Artifacts:**
  - Machine-Readable Track B Results: [`dist/track_b_reproduction_report.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/track_b_reproduction_report.json)
  - Forensics Demonstration Trace: [`dist/decisive_demonstration_trace.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/decisive_demonstration_trace.json)
  - Turnkey Reproduction Harness: [`scripts/verify_track_b_reproduction.py`](file:///Users/andriileukhin/Documents/SovereignNexus/scripts/verify_track_b_reproduction.py)
  - Offline Receipt Verifier: [`dist/smaos_verify.wasm`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/smaos_verify.wasm)

---

> [!IMPORTANT]
> **Regulatory Scope & Evaluative Boundaries:**  
> SMAOS and the AEIB benchmark suite are designed to generate verifiable telemetry and execution evidence that may support an organization’s internal control assessment. AEIB does not certify compliance with ISO/IEC 42001:2023, ISO/IEC 42006, EU DORA (Regulation (EU) 2022/2554), or the EU AI Act (Regulation (EU) 2024/1689). ISO/IEC 42006 governs conformity assessment bodies, not software products. All standards mappings in this briefing pack represent technical control crosswalks and illustrative audit evidence artifacts designed for evaluation by accredited third-party assessors.  
> Under the declared synthetic and local physical evaluation harnesses, the AEIB gateway matched dispositions to a target-side ledger, withheld retry authority in tested ambiguous cases, and rejected the tested unauthorized egress, audience, delegation, and credential-handling cases. The local runtime experiment included real socket and HTTP behavior. Real-world efficacy across uncoordinated distributed systems, third-party APIs, and authenticated TinyFish cloud sessions remains subject to independent reproduction and provider-side validation.

---

## 1. Executive Summary for Conformity Assessors

Third-party auditors evaluating autonomous agent deployments encounter a critical systemic flaw: **the Container Fallacy** (demonstrated in DEMM-Bench, arXiv:2606.20634). Traditional GRC dashboards and API gateways rely on *container presence*—verifying that an agent possesses an OAuth token at session initialization ($T_0$) or that a structured JSON receipt was written to an observability pipeline. However, in autonomous tool execution:

1. **Permissions are time-indexed claims:** An active OAuth token or IAM role grants *capability*, but does not evaluate whether current *standing* remains valid at the exact millisecond of dispatch ($T_{\text{dispatch}}$).
2. **Transport ambiguity disconnects intent from state:** When network drops occur (`HTTP 504`, `TCP RST`), standard agents speculatively retry unconfirmed requests, generating duplicate real-world effects.
3. **Implicit MCP trust creates cascading privilege escalation:** As revealed in CVE-2026-14540 (Google MCP Toolbox) and related Model Context Protocol disclosures, downstream tools implicitly trust parameters passed from upstream reasoning agents, enabling indirect prompt injection and Server-Side Request Forgery (SSRF).

AEIB operates as an inline **Execution-Integrity Decision Boundary** sitting directly at the wire level beneath agent planning engines and tool transports. It establishes the operational axiom:

$$\text{Capability} (T_0) \neq \text{Authority} \neq \text{Standing} (T_{\text{dispatch}}) \neq \text{Execution}$$

And enforces the **Seven-Layer Authorization Decoupling**:

$$\text{MCP Auth} \neq \text{Agent Identity} \neq \text{Delegation Auth} \neq \text{Tool Auth} \neq \text{Destination Auth} \neq \text{Credential Audience} \neq \text{Business Effect Auth}$$

---

## 2. Comprehensive Standards Crosswalk

### 2.1 ISO/IEC 42001:2023 (Artificial Intelligence Management System)

| ISO 42001 Clause / Control | Standard Requirement | AEIB Technical Mechanism | Auditor Evidence Artifact | Evaluated Test Reference |
|:---|:---|:---|:---|:---|
| **Clause 6.1.2**<br>AI Risk Assessment | Identify, analyze, and evaluate risks of unauthorized actions, prompt drift, and unintended mutations. | Pre-dispatch evaluation of current standing, policy epoch, and circuit breaker state fail-closed at $T_{\text{dispatch}}$. | Latch journal entries; policy epoch logs. | `test_aeib_bench_at15_at25.py::test_at23`<br>(TOCTOU standing race) |
| **Clause 8.2**<br>AI System Impact Assessment | Assess impacts of unintended downstream side-effects on business systems and infrastructure. | Egress and proxy parameter boundary checking intercepting unauthorized network hops and SSRF pivots. | Blocked connection audit receipts (`DISPATCH_REJECTED`). | `tests/test_aeib_mcp_egress_at30_at36.py::test_at31`<br>(Redirect pivot SSRF) |
| **Clause 9.1**<br>Monitoring & Measurement | Continual monitoring of AI decision execution against physical operational ground truth. | Target-side ledger oracle grading; single-flight status probe reconciliation query strictly by `business_key`. | Target-side ledger snapshots with `commit_count = 1`. | `tests/test_track_b_scenarios.py::test_b01_nominal_execution`<br>`test_b03_post_commit_504_timeout` |
| **Clause 9.2**<br>Internal Audit Evidence | Objective, tamper-evident proof that controls executed at the moment of transport failure. | Durable SQLite WAL latching; zero speculative retries emitted; process crash recovery. | Forensic trace proving durable state across process termination. | [`dist/decisive_demonstration_trace.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/decisive_demonstration_trace.json)<br>`test_bt16_process_restart_recovery` |
| **Clause 10.2**<br>Nonconformity & Corrective Action | Containment and correction of runaway autonomous execution loops. | ANSI 50BF breaker failure cascade; retry oscillation suppression; saga compensation to net-zero. | Automated circuit interlock logs; compensation dispatch receipts. | `tests/test_ansi_50bf_breaker_failure.py`<br>`tests/test_saga_compensation.py` |
| **Control A.6.2**<br>AI System Lifecycle Governance | Traceability of agent-initiated operations back to authorized human intent. | Cryptographic delegation chains (`user_principal` $\to$ `orchestrator` $\to$ `tool`). | Delegation grant verification receipts (`principal_id` bound). | `tests/test_aeib_bench_at15_at25.py::test_at16`<br>(Unauthorized delegation) |
| **Control A.8.2**<br>Data Quality & Payload Integrity | Assurance that tool parameters have not been tampered with or modified post-approval. | RFC 8785 JSON Canonicalization Scheme (JCS) payload hashing ($H(\text{JCS}(\text{Payload}))$). | Candidate Action ID (CAID) cryptographic binding. | `tests/test_aeib_bench_at15_at25.py::test_at24`<br>`tests/test_track_b_scenarios.py::test_bt18` |
| **Control A.8.4**<br>Third-Party & Multi-Agent Oversight | Prevention of implicit privilege inheritance across connected tools and MCP agents. | Audience binding; token passthrough isolation; Agent Card cryptographic registry validation. | Audience mismatch rejection receipts; Agent Card hash records. | `tests/test_aeib_mcp_egress_at30_at36.py::test_at30, test_at34, test_at35` |
| **Control A.9.2**<br>Operational Anomaly Intervention | Halting dispatch upon transport ambiguity rather than executing blind retries. | Uncertainty Latching: freezes state at `EFFECT_INDETERMINATE`, locks `retry_safe: false`. | Typed indeterminate receipts; probe reconciliation logs. | `tests/test_track_b_scenarios.py::test_bt12`<br>(Duplicate retry blocked) |

---

### 2.2 EU AI Act (Regulation (EU) 2024/1689 — High-Risk AI Requirements)

| AI Act Article | Legal Mandate | AEIB Technical Implementation | Auditor Evidence Artifact |
|:---|:---|:---|:---|
| **Article 9**<br>Risk Management System | Continuous, iterative risk management system identifying foreseeable risks across the lifecycle. | Inline Gateway Adapter enforcing pre-dispatch gates, parameter bounds, and rate-of-change spikes before wire transmission. | Telemetry disturbance records (`disturbance_telemetry_triad`); gate denial journals. |
| **Article 12**<br>Record-Keeping & Logging | Automatic recording of events (logs) throughout system lifecycle enabling traceability. | Ed25519-signed bitemporal execution receipts; RFC 8785 canonical hash chaining; immutable audit ledger. | Machine-readable receipt bundles verifiable offline via [`dist/smaos_verify.wasm`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/smaos_verify.wasm). |
| **Article 13**<br>Transparency & Instructions | Operation must be sufficiently transparent to enable deployers to interpret system output. | Explicit, typed wire dispositions (`OUTCOME_CONFIRMED`, `EFFECT_INDETERMINATE`, `DISPATCH_REJECTED`) replacing ungrounded agent self-reports. | Standalone disposition reports with zero synthetic mock inferences. |
| **Article 14**<br>Human Oversight | Architectural measures enabling individuals to oversee, intervene, or override AI operations. | Decoupled Raw-Evidence Human Review Gate: presents un-summarized canonical payload bytes to human overseer with zero AI-summarization. | Dual-control escalation records; manual operator reset logs (`test_02_manual_lockout_latch`). |
| **Article 15**<br>Accuracy, Robustness & Cybersecurity | Resilience against third-party exploitation, prompt injection, data poisoning, and transport faults. | Two-channel Agent Card sanitization (`instruction_authority: none`, AT38); DNS rebinding filter (AT32); per-hop redirect re-resolution (AT39); header override defense (AT40). | Quarantine alerts (`OUTPUT_QUARANTINED`); blocked redirect receipts (`REDIRECT_HOP_BLOCKED`). |
| **Article 50**<br>Transparency Obligations | Attribution and machine-readable provenance marking on synthetic and agent-generated actions. | Ed25519 cryptographic signatures; SCITT-aligned COSE_Sign1 receipts with signed timestamps. | Offline-verifiable cryptographic receipts with verified cryptographic signatures. |

---

### 2.3 EU DORA (Regulation (EU) 2022/2554 — Digital Operational Resilience)

| DORA Article & RTS | Statutory Requirement | AEIB Telemetry Projection | Non-Claim & Regulatory Boundary |
|:---|:---|:---|:---|
| **Article 17**<br>(RTS 2025/301) | Major ICT-related incident reporting:<br>• Initial notification: $\le$4h of classification / $\le$24h of awareness<br>• Intermediate report: $\le$72h<br>• Final report: $\le$1 month | Dual-clock telemetry journals capturing exact monotonic and UTC timestamps of transport faults (`HTTP 504`, `TCP RST`), recovery events, and operator escalations. | AEIB generates supporting wire telemetry and incident timeline records; it does not satisfy DORA compliance requirements independently. |
| **Article 28(3)**<br>(ITS 2024/2956) | Register of Information on all contractual arrangements on the use of ICT third-party services. | Automated pre-fill and export of RT.01.01 through RT.02.03 xBRL-CSV templates capturing third-party agent tool dependencies. | Transport receipts do not populate the entire Register of Information; compliance is determined solely by the regulated entity. |

---

## 3. The Seven-Layer Authorization Decoupling in Practice

When inspecting multi-agent deployments (e.g., LangChain, AutoGen, CrewAI, MCP), auditors must evaluate whether authorization boundaries collapse into a single identity token. AEIB decouples and evaluates each layer independently:

```text
Layer 1: MCP Transport Authentication (mTLS / OAuth Bearer)
   ≠
Layer 2: Agent Identity (Ed25519 Keypair / SPIFFE ID)
   ≠
Layer 3: Delegation Authorization (Root Human Grant / Lineage)
   ≠
Layer 4: Tool Capability Authorization (Registered Tool Function)
   ≠
Layer 5: Destination Authorization (Origin / IP / CIDR Allowlist)
   ≠
Layer 6: Credential Audience Binding (Target Service Aud Tag)
   ≠
Layer 7: Business Effect Authorization (Millisecond Standing at T_dispatch)
```

### Detailed Acceptance Test Inventory (AT30–AT41)

1. **AT30 (Audience Mismatch):** Credential issued for Service A cannot be forwarded to Service B $\to$ `DISPATCH_REJECTED (AUDIENCE_MISMATCH)`.
2. **AT31 (Redirect Pivot SSRF):** Target redirects to cloud metadata (`169.254.169.254`) $\to$ `DISPATCH_REJECTED (REDIRECT_PIVOT_DETECTED)` (CVE-2026-14540 defense).
3. **AT32 (DNS Rebinding):** Target hostname resolves to private IP range (`10.0.0.0/8`, `127.0.0.0/8`, `172.16.0.0/12`) $\to$ `DISPATCH_REJECTED (DNS_REBINDING_DETECTED)`.
4. **AT33 (Cross-Protocol Delegation):** Downward protocol downgrade without standing $\to$ `DISPATCH_REJECTED (UNAUTHORIZED_CROSS_PROTOCOL)`.
5. **AT34 (Token Passthrough Isolation):** Prohibits fallback to ambient host credentials when grant is missing $\to$ `DISPATCH_REJECTED (AMBIENT_AUTH_BLOCKED)`.
6. **AT35 (Agent Card Mutation Guard):** Remote agent card declaration differs from approved registry hash $\to$ `DISPATCH_REJECTED (AGENT_CARD_MUTATION)`.
7. **AT36 (Credential Leakage Guard):** Raw tokens, keys, or secrets in tool output quarantined from model context $\to$ `OUTPUT_QUARANTINED (CREDENTIAL_LEAKAGE)`.
8. **AT37 (Handshake Discovery SSRF):** Discovery URLs in `WWW-Authenticate` targeting restricted IPs $\to$ `HANDSHAKE_BLOCKED` (CVE-2026-51994 defense).
9. **AT38 (Agent Card Context Poisoning Guard):** Prompt injections inside skill descriptions stripped of execution authority $\to$ `AGENT_CARD_FACTS_STRUCTURED` with `instruction_authority: "none"` (Google A2A defense).
10. **AT39 (Per-Hop Redirect Validation & TOCTOU Pinning):** Multi-hop redirect hops re-resolved and logged $\to$ `DISPATCH_REJECTED (REDIRECT_HOP_BLOCKED)` with `redirect_chain` receipt (CVE-2026-64849 defense).
11. **AT40 (Header-Layer Destination Override):** Out-of-band routing headers (`Host`, `X-Forwarded-Host`, `X-Atlassian-Jira-Url`) mismatching target origin $\to$ `DISPATCH_REJECTED (HEADER_DESTINATION_OVERRIDE)` (CVE-2026-27826 defense).
12. **AT41 (URI Scheme & Address Normalization):** Non-HTTP schemes (`file://`, `gopher://`), IPv6 loopbacks (`[::1]`), and non-canonical octal/hex IPs rejected $\to$ `DISPATCH_REJECTED (PROHIBITED_URI_SCHEME)` (MarkItDown defense).

---

## 4. Auditor Evidence Verification Runbook

Auditors can execute independent verification of the entire claim set locally without external internet egress:

```bash
# Step 1: Zone Boundary & Architecture Purity
python3 compliance/check_zone_boundary.py

# Step 2: Zero-Mock AST Verification
# Asserts real Ed25519 cryptography, RFC 8785 JCS, and zero mock objects across all files
python3 compliance/ast_purity.py . && python3 compliance/no_mock_enforcer.py

# Step 3: Turnkey Track B Independent Reproduction (4 Gates)
python3 scripts/verify_track_b_reproduction.py

# Step 4: Core 69-Test Verification Matrix (Reported Passing in 0.68s)
pytest tests/test_industrial_protection_matrix.py \
       tests/test_ansi_50bf_breaker_failure.py \
       tests/test_saga_compensation.py \
       tests/test_falsifiability_matrix.py \
       tests/test_track_b_scenarios.py \
       tests/test_aeib_mcp_egress_at30_at36.py \
       tests/test_aeib_mcp_egress_at37_at41.py \
       tests/test_live_physical_execution.py -v

# Step 5: Deterministic 500-Episode Execution Integrity Benchmark
python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42
```

---

## 5. Auditor Checkpoints & Verification Questions

Lead auditors conducting an ISO 42001 Stage 2 or EU AI Act conformity assessment should review the following technical checkpoints:

1. **Check for Target-Side Oracle Independence:**
   - *Audit Question:* Does the benchmark evaluate against an isolated target ledger or against agent self-reports?
   - *Evidence Inspection:* Inspect [`src/track_b_harness.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/track_b_harness.py). Confirm `MockTargetLedger.probe_state` accepts only a plain business key string and has zero access to expected dispositions or test metadata.
2. **Check for Durable Crash Survival:**
   - *Audit Question:* When the gateway process terminates during an unconfirmed `HTTP 504` drop, does it issue a speculative retry upon reboot?
   - *Evidence Inspection:* Inspect [`dist/decisive_demonstration_trace.json`](file:///Users/andriileukhin/Documents/SovereignNexus/dist/decisive_demonstration_trace.json). Confirm the second attempt was rejected with `UNCERTAINTY_LATCHED_RETRY_BLOCKED` and `target_commit_count` remained 1.
3. **Check for Epistemic Claims Boundaries:**
   - *Audit Question:* Does the system vendor claim universal exactly-once execution or certified regulatory compliance?
   - *Evidence Inspection:* Confirm presence of the locked disclaimer in Section 1. AEIB reports empirical observations under declared synthetic and local physical evaluation models; it does not claim universal distributed consensus or statutory certification.
