# Regulatory Research Dossier: Q4 2026 Global AI & Operational Resilience Frameworks

**Scope**: DORA (Articles 17 & 28), EU AI Act (Article 50, Annex III & Digital Omnibus), and China Autonomous AI Agent Directives (CAC/NDRC/MIIT & GB/Z 185-2026)  
**Verification Date**: October 2026  
**Epistemic Standard**: Strict Zero-Mock & Empirical Boundary Validation under SMAOS / AEIB v1.1.0-rc.1  
**Operating Baseline**: Observed, tested, and evaluated under the stated model. Hardware/kernel modules (eBPF/TDX/SEV) remain structural scaffolding.  

---

## 1. Executive Summary & Verification Matrix

| Area | Regulatory Finding | Exact Legal / Technical Citation | Source URL | Concrete AEIB Verification Evidence Mapping |
| :--- | :--- | :--- | :--- | :--- |
| **1. DORA Incident Reporting Timelines** | Initial notification window is evaluated under $\min(T_{\text{class}} + 4\text{h}, T_{\text{aware}} + 24\text{h})$. Intermediate report within 72h; Final report within 1 month. | ESAs Joint Committee Final Report **JC 2024 33**; **Commission Delegated Regulation (EU) 2025/301** (Arts. 4, 6–8) supplementing Regulation (EU) 2022/2554 Art. 19. | [EBA / ESAs JC 2024 33 Press Release](https://www.eba.europa.eu/publications-and-media/press-releases/esas-publish-second-batch-policy-materials-under-dora) | `src/dora_annex_ii_prefill.py` (`StatutoryDeadlineEngine.calculate_deadlines`); evaluated in `tests/test_dora_annex_ii_prefill.py` (`test_03_statutory_deadlines_dual_threshold`, `test_04_statutory_deadlines_awareness_threshold_binds`). |
| **1. DORA Major Incident Criteria** | Requires critical/important function gate plus either Path A (malicious data access) or Path B (≥2 thresholds: >10% or >100k clients; >EUR 100k economic impact; AIC+C data loss). | **Commission Delegated Regulation (EU) 2024/1772** (Arts. 1, 5–9) supplementing Regulation (EU) 2022/2554 Art. 18. | [EUR-Lex Delegated Regulation (EU) 2024/1772](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1772) | `compliance/dora_art17_exporter.py` & `compliance/dora_art17_gap_exporter.py` trapping transport faults (HTTP 504 / TCP RST) and latching `EFFECT_INDETERMINATE`. |
| **2. DORA Register of Information Specifications** | Citation `JC 2024 03` is **UNVERIFIED / MISCITED** in ESA registries. The verified ITS is **JC 2023 85**, enacted as **Commission Implementing Regulation (EU) 2024/2956** (15 interconnected `RT` relational tables). | **Commission Implementing Regulation (EU) 2024/2956**; ESAs Joint Committee Final Report **JC 2023 85**; ESA Opinion **JC 2024 75**. | [EUR-Lex Implementing Regulation (EU) 2024/2956](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:L_202402956) | `compliance/dora_art28_roi_exporter.py` and `compliance/dora_art28_register_exporter.py` exporting `RT.01.01.csv` and `RT.02.01.csv`. |
| **2. DORA Technical Format & Taxonomy** | Mandatory submission in **xBRL-CSV** (XBRL OIM CSV package: `report.json` + `parameters.csv` + `FilingIndicator.csv` + `{table}.csv`). Governed by EBA Reporting Framework 4.0 / DPM 2.0. | **EBA Reporting Framework 4.0** Technical Package (incorporating DORA RoI taxonomy & DPM 2.0 semantic glossary). | [EBA Reporting Framework 4.0](https://www.eba.europa.eu/risk-and-data-analysis/reporting-frameworks/reporting-framework-40) | `tests/test_unified_governance_stack.py` (`test_dora_xbrl_csv_package_and_manifest_signature`) verifying xBRL-CSV packaging and Ed25519 signature sealing. |
| **3. EU AI Act Article 50 Implementation** | Applied and enforceable on **August 2, 2026** across 4 categories: human-AI interaction, synthetic content marking, emotion recognition, and deepfakes (grace period to Dec 2, 2026 for pre-existing models). | **Regulation (EU) 2024/1689** Article 50 & Article 113. | [EUR-Lex AI Act Regulation (EU) 2024/1689](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689) | `compliance/iso_42001_soa.py` and `tests/test_regulatory_evidence_exporters.py` generating machine-readable transparency tags and JCS-canonicalized receipts. |
| **3. EU AI Act Annex III Compliance Clocks** | Standalone Annex III high-risk compliance was deferred from August 2, 2026 to **December 2, 2027** by the Digital Omnibus on AI. Annex I embedded systems deferred to August 2, 2028. | **Regulation (EU) 2026/1744** (Digital Omnibus on AI) amending Regulation (EU) 2024/1689 Arts. 111 & 113(c). | [EUR-Lex Digital Omnibus Regulation (EU) 2026/1744](https://eur-lex.europa.eu) / [EU AI Act Legal Directory](https://artificialintelligenceact.eu) | `compliance/claims.json` and `benchmarks/aeib_execution_integrity/run_episodes.py` maintaining high-risk audit logging scaffolds without premature certification assertions. |
| **4. China AI Agent Application Scenarios** | Jointly published on **May 8, 2026**: China's first national policy specifically for AI agents, outlining **19 typical application scenarios** across 5 core domains with a 70% adoption target by 2027. | CAC / NDRC / MIIT **"Implementation Opinions on the Standardized Application and Innovative Development of Intelligent Agents"** (《智能体规范应用与创新发展实施意见》). | [CAC Official Portal Notice (May 8, 2026)](http://www.cac.gov.cn) / [NDRC News Release](https://www.ndrc.gov.cn) / [State Council Gov.cn](https://www.gov.cn) | `tests/test_subagent_coordinator.py` & `src/dora_annex_ii_prefill.py` evaluating autonomous task delegation boundaries across multi-agent workflows. |
| **4. China AI Agent Interoperability & Security** | National standard **GB/Z 185-2026** (7 parts covering architecture, identity code, identity management, description, discovery, interaction, tool calling); CAICT **ASL (Agent Security Link)** protocol and `YD/T 7360-2026`. | **GB/Z 185.1~185.7-2026**; CAICT / IIFAA **Agent Security Link Protocol**; MIIT Industry Standard **YD/T 7360-2026**. | [CESI National Standards Portal](http://www.cesi.cn) / [CAICT Terminal Labs ASL Specification](http://www.caict.ac.cn) | `compliance/claims.json` (Claims C1, C3, C4) & `tests/test_ansi_50bf_breaker_failure.py` enforcing Ed25519 identity verification and tool-invocation sandboxing. |

---

## 2. DORA Article 17 — Major ICT Incident Reporting Framework

### 2.1 Statutory Reporting Timeline (JC 2024 33 / Delegated Regulation (EU) 2025/301)
The Joint Committee of the European Supervisory Authorities (EBA, EIOPA, ESMA) finalized the draft Regulatory Technical Standards (RTS) on incident reporting under DORA Article 20 in report **JC 2024 33**, subsequently adopted by the European Commission as **Commission Delegated Regulation (EU) 2025/301**.

The mandatory lifecycle follows a strict tripartite sequence:
1. **Initial Notification (Article 6 of Delegated Regulation (EU) 2025/301):**
   * **The 4-Hour Window**: Must be transmitted as early as possible, and **no later than 4 hours** from the exact timestamp the ICT-related incident is formally *classified* as a major incident.
   * **The 24-Hour Backstop**: Must be submitted **no later than 24 hours** from the moment the financial entity first *became aware* of the incident, irrespective of classification delays.
   * **Binding Deadline Equation**:
     $$T_{\text{initial\_deadline}} = \min(T_{\text{class}} + 4\,\text{hours},\; T_{\text{aware}} + 24\,\text{hours})$$
   * **Non-Adjustment Exemption (Article 4(2))**: For Credit Institutions, Investment Firms, and Critical ICT Third-Party Service Providers (CTPPs), deadlines are calculated continuously in UTC with **no weekend or public holiday extension**.
2. **Intermediate Report (Article 7 of Delegated Regulation (EU) 2025/301):**
   * Due within **72 hours** from the submission of the initial notification, or immediately once regular activities have been restored or significant operational updates occur.
3. **Final Report (Article 8 of Delegated Regulation (EU) 2025/301):**
   * Due within **1 month** from the date of submission of the latest intermediate report (or upon formal resolution and root-cause analysis closure).

### 2.2 Major Incident Classification Criteria (Delegated Regulation (EU) 2024/1772)
Classification is evaluated under Commission Delegated Regulation (EU) 2024/1772 supplementing DORA Article 18:
* **The Critical Services Gate (Article 6)**: The incident *must* impact network and information systems that support **critical or important functions** of the financial entity. If critical functions are unaffected, the incident cannot be classified as major under DORA.
* **Dual Materiality Pathways (Article 8)**:
  * **Path A (Malicious Access)**: Successful, malicious, and unauthorized access to network and information systems that may result in data losses.
  * **Path B (Multi-Criteria Rule)**: The incident hits **at least two** materiality thresholds across:
    1. **Clients, Counterparts & Transactions (Articles 1 & 9)**:
       * Affects $> 10\%$ of all clients using the service, OR $> 100,000$ clients;
       * Affects $> 30\%$ of financial counterparts;
       * Disrupts transaction values $> \text{EUR } 100,000,000$ OR $> 10\%$ of average daily transaction volume.
    2. **Economic Impact (Articles 7 & 9)**:
       * Direct and indirect costs and losses (asset replacement, customer compensation, forgone revenues, incident response advisory) exceeding or likely to exceed **EUR 100,000**.
    3. **Data Losses (Articles 5 & 9)**:
       * Impairment across Availability, Authenticity, Integrity, or Confidentiality (AIC+C) that has or is likely to have an adverse impact on critical or important functions.
    4. **Service Downtime (Articles 2 & 9)**: Service disruption $> 2\text{ hours}$ for systems supporting critical functions.
    5. **Geographical Spread (Articles 3 & 9)**: Impact spanning across $\ge 2$ EU Member States.

---

## 3. DORA Article 28(3) — Register of Information (RoI)

### 3.1 Technical Specifications & Resolution of Citation `JC 2024 03`
* **Status of `JC 2024 03`**: Web verification confirms that `"JC 2024 03"` does **NOT** exist as an official publication in the European Supervisory Authorities' document registers. It is identified as an unverified citation.
* **Official Regulatory Instruments**:
  * **JC 2023 85**: Joint Committee Final Report on Draft Implementing Technical Standards (ITS) on the Register of Information under DORA Article 28(9).
  * **JC 2024 75**: Joint Opinion following Commission amendments.
  * **Commission Implementing Regulation (EU) 2024/2956**: The technical standard establishing the 15 standardized relational templates (`RT.01.01` through `RT.99.01`).

### 3.2 Technical Format (xBRL-CSV) & EBA Reporting Framework 4.0
* **xBRL-CSV Architecture**: Unstructured spreadsheets are rejected by regulatory gateways. Entities must submit an **xBRL-CSV** package (XBRL Open Information Model / OIM) formatted as a `.zip` archive containing:
  1. `report.json`: Machine-readable metadata referencing the EBA taxonomy entry point, submitter Legal Entity Identifier (ISO 17442 LEI), and reporting parameters.
  2. `FilingIndicator.csv`: Explicit boolean flags declaring which templates are populated.
  3. `parameters.csv`: Global context parameters.
  4. Tabular CSV files for each populated template (e.g., `RT.01.01.csv` for general contract terms, `RT.02.01.csv` for critical function mapping).
* **EBA DPM 4.0 / Reporting Framework 4.0**:
  * The European Banking Authority (jointly with ESMA and EIOPA) operationalized DORA reporting within **EBA Reporting Framework 4.0**.
  * Framework 4.0 finalized the migration to the **DPM 2.0** (Data Point Model) methodology and Taxonomy Architecture v2.0, establishing binary schema validation rules, extensible enumerations, and cross-table referential integrity rules for operational reporting.

---

## 4. EU AI Act — Implementation Clocks & Timelines (2026)

### 4.1 Article 50 Enforcement (August 2, 2026)
* **Application Date**: Under Regulation (EU) 2024/1689 Article 113, Article 50 transparency requirements took full legal effect across the EU on **August 2, 2026**.
* **Substantive Scope**:
  1. *Article 50(1)*: AI systems configured to interact directly with natural persons (autonomous agents, conversational bots) must inform users they are interacting with AI, unless self-evident from context.
  2. *Article 50(2)*: Providers of generative AI systems generating synthetic audio, image, video, or text must mark outputs in a machine-readable format and ensure detectability as artificially generated (transitional grace period until **December 2, 2026** for pre-existing models).
  3. *Article 50(3)*: Deployers of emotion recognition or biometric categorization systems must explicitly notify exposed natural persons.
  4. *Article 50(4)*: Deployers generating or manipulating deepfakes must prominently disclose that content is synthetic.

### 4.2 Annex III High-Risk Compliance Timeline & The Digital Omnibus Deferral
* **Legislative Amendment**: Standalone Annex III high-risk AI requirements were originally slated for August 2, 2026 under Regulation (EU) 2024/1689 Article 113. However, due to bottlenecks in CEN/CENELEC harmonized standard development and national notified body readiness, the European Union adopted **Regulation (EU) 2026/1744 (Digital Omnibus on AI)** in July 2026.
* **Updated Compliance Deadlines**:
  * **December 2, 2027**: Standalone high-risk AI systems categorized under **Annex III** (biometrics, critical infrastructure, education, employment/HR, essential public/private services, law enforcement, migration, administration of justice).
  * **August 2, 2028**: High-risk AI systems embedded as safety components in products covered by **Annex I** (machinery, medical devices, toys, civil aviation, lifts).
* **Article 111 Transitional Rules**:
  * Systems placed on the market prior to the applicable compliance dates are grandfathered, unless they undergo significant design modifications after that date.
  * General-Purpose AI (GPAI) models placed on the market prior to August 2, 2025 must achieve full compliance by **August 2, 2027**.
  * Large-scale IT systems in the area of freedom, security, and justice (Annex X) are granted transitional timelines extending to **December 31, 2030**.

---

## 5. China AI Agent Regulatory Landscape (2026)

### 5.1 CAC / NDRC / MIIT Joint Guidelines (May 8, 2026)
On **May 8, 2026**, the Cyberspace Administration of China (CAC), National Development and Reform Commission (NDRC), and Ministry of Industry and Information Technology (MIIT) jointly issued the **"Implementation Opinions on the Standardized Application and Innovative Development of Intelligent Agents"** (《智能体规范应用与创新发展实施意见》).
* **Significance**: Marks China's first national policy instrument dedicated specifically to autonomous AI agents (defined as systems equipped with perception, memory, decision-making, interaction, and execution capabilities). Sets a strategic target of **70% adoption** of intelligent agents across smart terminals and industrial workflows by 2027.
* **19 Typical Application Scenarios across 5 Domains**:
  1. **Scientific Research (2 Scenarios)**:
     - Theoretical deduction and simulation modeling agents.
     - Full-lifecycle software development agents (requirements, architecture, code generation, and testing).
  2. **Industrial Development (5 Scenarios)**:
     - Intelligent manufacturing (integration with CNC machines, industrial robotics, automation lines).
     - Energy and mineral resources (smart power grid dispatch).
     - Transportation and logistics (traffic safety supervision and automated routing).
     - Agricultural production (farming advisory and crop health monitoring).
     - Financial services (risk management, transaction screening, and fraud control).
  3. **Boosting Consumption (3 Scenarios)**:
     - Smart terminal collaboration (smartphones, PCs, intelligent vehicles, smart homes, wearable devices, consumer robotics).
     - Digital content creation (literature, music, visual arts, audiovisual media, performing arts).
     - Smart commerce and consumer service agents.
  4. **People's Livelihood / Public Well-being (4 Scenarios)**:
     - Education and teaching (courseware generation, homework grading, student learning analytics).
     - Medical and healthcare (medical imaging analysis, diagnostic reasoning, customized clinical treatment planning).
     - Human resources (talent acquisition, skill matching, and career coaching).
     - Information accessibility and public service assistance.
  5. **Social Governance (5 Scenarios)**:
     - Government affairs and citizen services.
     - Judicial assistance and legal documentation.
     - Public safety and emergency management (hazard monitoring, disaster early warning, rescue dispatch).
     - Collaborative urban governance and municipal infrastructure operations.
     - Public bidding and government procurement full-chain intelligent supervision.

### 5.2 Standard GB/Z 185-2026 & CAICT Technical Specifications
* **National Standard GB/Z 185-2026 (《人工智能 智能体互联》)**:
  Guided by MIIT and led by the China Electronics Standardization Institute (CESI) and CAICT with industrial participants, this 7-part guiding technical document establishes China's national interoperability framework:
  * `GB/Z 185.1-2026`: Part 1: Overall Architecture (总体架构) — conceptual and functional reference models.
  * `GB/Z 185.2-2026`: Part 2: Identity Code (身份码) — standardized digital identity coding rules for AI agents.
  * `GB/Z 185.3-2026`: Part 3: Identity Management (身份管理) — registration, authentication, revocation, and lifecycle governance.
  * `GB/Z 185.4-2026`: Part 4: Agent Description (智能体描述) — capability profiling, functional declarations, and permission bounds.
  * `GB/Z 185.5-2026`: Part 5: Agent Discovery (智能体发现) — cross-domain registry search, matchmaking, and address resolution.
  * `GB/Z 185.6-2026`: Part 6: Agent Interaction (智能体交互) — inter-agent communication, session negotiation, and state exchange.
  * `GB/Z 185.7-2026`: Part 7: Tool Calling (智能体工具调用) — external tool/API execution boundaries, runtime constraints, and audit logging.
* **CAICT Specifications & Standards**:
  * **Agent Security Link (ASL) Protocol** (《智能体安全可信互连协议》): Published by CAICT CTTL Terminal Labs and IIFAA. Addresses three vulnerabilities in multi-agent networks: untrusted protocol links, intent distortion/tampering, and privilege escalation. Formulates four pillars: Trusted Identity, Trusted Connection, Trusted Intent, and Trusted Authorization.
  * **Industry Standards**:
    - `YD/T 7360-2026`: Technical Requirements for Multi-Agent Collaboration (communication negotiation, task delegation, and security boundaries).
    - `YD/T 7364-2026`: Technical Requirements for Agent AI Systems.

---

## 6. Concrete AEIB Verification Evidence Mapping in SovereignNexus

The regulatory requirements detailed above map directly into the empirical harnesses and verification gates of SovereignNexus:

1. **DORA Article 17 Initial Notification Engine**:
   - `src/dora_annex_ii_prefill.py` & `tests/test_dora_annex_ii_prefill.py`:
     - Evaluated under `TestDORAAnnexIIPreFill.test_03_statutory_deadlines_dual_threshold` to enforce $\min(T_{\text{class}} + 4\text{h}, T_{\text{aware}} + 24\text{h})$.
     - Evaluated under `test_04_statutory_deadlines_awareness_threshold_binds` where awareness + 24h binds when classification is delayed.
     - Implements ISO 17442 LEI MOD-97 checksum validation (`validate_lei_mod97`).
     - Enforces the mandatory `PENDING_HUMAN_REVIEW` invariant prohibiting autonomous AI agents from self-classifying or downgrading severity.
   - `compliance/dora_art17_exporter.py` & `compliance/dora_art17_gap_exporter.py`:
     - Traps transport severances (HTTP 504 Gateway Timeout, TCP RST), latches `EFFECT_INDETERMINATE`, halts naive retries, and generates compliant telemetry records within the 4-hour window.

2. **DORA Article 28(3) Register of Information (xBRL-CSV)**:
   - `compliance/dora_art28_roi_exporter.py` & `compliance/dora_art28_register_exporter.py`:
     - Generates relational tables `RT.01.01.csv` and `RT.02.01.csv` compliant with EBA Reporting Framework 4.0 / Commission Implementing Regulation (EU) 2024/2956.
   - `tests/test_unified_governance_stack.py`:
     - Evaluates automated generation of the `.zip` archive holding xBRL-CSV templates, schema-compliant `report.json`, and Ed25519 cryptographic tamper sealing.

3. **EU AI Act Transparency & Risk Clocks (Article 50 & Annex III Deferral)**:
   - `compliance/iso_42001_soa.py` and `tests/test_regulatory_evidence_exporters.py`:
     - Formats machine-readable transparency disclosures, cryptographic content provenance seals (Ed25519 + JCS RFC 8785 canonicalization), and synthetic content tagging supporting Article 50.
   - `compliance/claims.json` (Claim C5):
     - Accommodates the Annex III deferral to December 2, 2027 by maintaining structured audit logging and deterministic boundary verification without prematurely asserting universal standalone Annex III conformity.

4. **China AI Agent Standards (GB/Z 185-2026 & CAICT ASL)**:
   - `compliance/claims.json` (Claims C1, C3, C4):
     - Evaluates offline JCS canonicalization and Ed25519 signing across all receipts, establishing verifiable agent identities matching GB/Z 185.2/185.3 and ASL Trusted Identity.
   - `tests/test_ansi_50bf_breaker_failure.py` & `tests/test_saga_compensation.py`:
     - Evaluates deterministic breaker isolation, bounded tool execution, and compensating transactions matching GB/Z 185.7 (Tool Calling) and YD/T 7360-2026 security specifications.
