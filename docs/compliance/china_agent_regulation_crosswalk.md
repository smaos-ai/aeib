# China AI Agent Regulatory Compliance Crosswalk & Technical Alignment Matrix

**Document Version:** `v1.0.0-rc.5-preprod`  
**Status:** Pre-Production Regulatory Scaffold (Pending Statutory Legal Counsel Review)  
**Primary Regulatory Bases:**
1. CAC / NDRC / MIIT 《智能体规范应用与创新发展实施意见》 (Issued May 8, 2026; Enforced July 15, 2026)
2. SAMR / SAC `GB/Z 185-2026` 《人工智能 智能体互联》系列国家标准 (Parts 1–7)
3. CAC 《互联网信息服务算法推荐管理规定》 (Algorithm Registry Filing)
4. Beijing Municipal Bureau of Economy and Information Technology 《北京市关于加快推动人工智能智能体产业创新发展的十条措施》

---

## 1. Executive Summary & Epistemic Status

This document establishes a technical crosswalk between the declared architectural controls of the **Agent Execution Integrity Boundary (AEIB)** / **Software Manufacturing Fabric (SMF)** and the statutory intelligent agent governance requirements promulgated by the People's Republic of China (PRC).

Under the stated model, AEIB operates as an in-band request-path execution gate and out-of-band audit evidence registry. It maps deterministic state machines and cryptographic identity proofs to the requirements of Chinese statutory bodies. This mapping is evaluated and tested against local test harnesses and simulation environments; full statutory conformity requires operational filing with the Cyberspace Administration of China (CAC) and third-party testing by accredited inspection bodies (e.g., CESI / 中国电子技术标准化研究院).

---

## 2. Regulatory Control Crosswalk Matrix

| Control ID | PRC Regulatory Source | Statutory Obligation | AEIB / SMF Boundary Mechanism | Evidence Artifact | Status & Boundary |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CHN-REG-01** | CAC/NDRC/MIIT §III(1)<br>“明确决策权限” | Strict classification of decision authority into 3 tiers: Human-Only, User-Authorized, and Autonomous-Bounded. | [`tools/regulatory_three_tier_and_matrix.py`](file:///Users/andriileukhin/Documents/SovereignNexus/tools/regulatory_three_tier_and_matrix.py): `ThreeTierDecisionAuthorityGate` strictly halts agent execution on human-only actions and requires explicit Ed25519 user warrant for user-authorized actions. | `evidence/three_tier_decision_receipt.json` | **Implemented & Tested** locally. |
| **CHN-REG-02** | CAC/NDRC/MIIT §III(2)<br>“行为可验证、可追溯” | Comprehensive, tamper-evident audit trails capturing every agent action proposal, authorization, and execution outcome. | [`src/scitt_bitemporal_audit_engine.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/scitt_bitemporal_audit_engine.py): Append-only SQLite WAL with RFC 9162 Merkle tree, COSE_Sign1 receipts, and AT70b anti-reset anchor. | `evidence/scitt_audit_receipts.jsonl` | **Implemented & Tested** locally. |
| **CHN-REG-03** | `GB/Z 185.2-2026`<br>“智能体身份码编码” | Standardized, globally unique Agent Identity Code (AIC) registration, allocation, and lifecycle management. | `src/agent_identity_registry.py`: Content-addressed identity binding derived from public key thumbprint and sponsor authority (`did:aeib:agent:<pubkey_fingerprint>`). | `schemas/agent_identity_card.json` | **Implemented** under prototype schema. |
| **CHN-REG-04** | `GB/Z 185.3-2026`<br>“身份注册、凭证与鉴别” | Mutual cryptographic authentication and credential lifecycle management between communicating agent endpoints. | [`src/secure_mcp_uds_boundary.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/secure_mcp_uds_boundary.py): Local Unix Domain Socket (`0o600`) with kernel peer credentials (`SO_PEERCRED` / `LOCAL_PEERCRED`) and Ed25519 capability tokens. | `tests/test_secure_mcp_uds_boundary.py` | **Implemented & Tested** locally. |
| **CHN-REG-05** | `GB/Z 185.4-2026`<br>“智能体能力描述” | Explicit registration, declaration, and monotonic attenuation of agent tool-use capabilities. | [`compliance/dynamic_code_policy_gate.py`](file:///Users/andriileukhin/Documents/SovereignNexus/compliance/dynamic_code_policy_gate.py): Signed plugin manifest with pinned capability scopes and static AST validation. | `evidence/signed_plugin_manifest.json` | **Implemented & Tested** locally. |
| **CHN-REG-06** | `GB/Z 185.7-2026`<br>“外部工具调用数据格式” | Structured schema validation, parameter bounding, and fail-closed isolation for external tool invocation. | [`src/eo1_write_before_execute.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/eo1_write_before_execute.py) & `Station 1 Gate`: RFC 8785 canonical JSON serialization (CAID) and 30 MCP golden vector idempotency gating. | `conformance/vectors/mcp_golden_vectors_30.json` | **Implemented & Tested** locally. |
| **CHN-REG-07** | CAC 2026 Assistant Notice<br>“显著标识为人工智能” | Mandatory non-human disclosure in user-facing interactions and API interfaces. | `src/perception_fast_path_router.py`: Injects immutable `x-agent-origin: autonomous-assistant` header and identity metadata into all outbound HTTP responses. | `evidence/outbound_headers_audit.json` | **Configured** via proxy. |
| **CHN-REG-08** | CAC Algorithm Registry<br>“算法备案与安全评估” | Filing of algorithmic decision trees, risk assessment files, and continuous security self-evaluation reports. | `tools/cyclonedx_mlbom_generator.py`: CycloneDX 1.6 ML-BOM generating complete inventory of base models, weights hashes, training datasets, and gating policies. | `output/rc5_reproducible/cbom_aeib_v1.0.0_rc5.json` | **Implemented**; filing pending operator deployment. |

---

## 3. The Three-Tier Decision Authority Framework (CAC §III.1)

Section III(1) of the May 8, 2026 CAC/NDRC/MIIT Implementation Opinions explicitly delineates three decision boundaries. AEIB maps these directly into deterministic boundary code:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                          CAC/NDRC/MIIT THREE-TIER BOUNDARY                             │
├──────────────────────────────┬─────────────────────────────┬───────────────────────────┤
│ Tier A: 仅限用户本人决策       │ Tier B: 需由用户授权决策      │ Tier C: 智能体自主决策     │
│ (HUMAN-ONLY DECISION)        │ (USER-AUTHORIZED DECISION)  │ (AUTONOMOUS-BOUNDED)      │
├──────────────────────────────┼─────────────────────────────┼───────────────────────────┤
│ • Policy ceiling alteration  │ • Financial wire transfers  │ • Read-only catalog query │
│ • Root key rotation          │ • Customer refunds          │ • Local AST syntax checks │
│ • Audit log waiver           │ • Production deployments    │ • Internal cache lookups  │
│ • Statutory account closing  │ • Database schema changes   │ • Ephemeral draft writing │
├──────────────────────────────┼─────────────────────────────┼───────────────────────────┤
│ Dispatched by agent?         │ Dispatched by agent?        │ Dispatched by agent?      │
│ ❌ STRICTLY FORBIDDEN        │ ⚠️ REQUIRES Ed25519 USER    │ ✅ ALLOWED WITHIN         │
│ (Code: ERR_TIER_HUMAN_ONLY)  │    APPROVAL WARRANT         │    DELEGATED QUOTA        │
└──────────────────────────────┴─────────────────────────────┴───────────────────────────┘
```

---

## 4. Operational Operator Responsibilities & Gaps

To maintain strict regulatory clarity without overclaiming compliance, the following responsibilities are allocated between AEIB software scaffolding and the deploying enterprise operator:

1. **Algorithm Filing (算法备案):**  
   AEIB provides the technical evidence pack (`cbom_aeib_v1.0.0_rc5.json` and `coverage_ledger.json`). The enterprise deploying the system remains the statutory entity responsible for submitting the filing to the CAC portal (`beian.cac.gov.cn`).
2. **Ethics Review Committee (伦理审查委员会):**  
   The deploying enterprise must institute an internal AI Ethics Review Board to review high-consequence operational domains before deploying Tier B warrants into production.
3. **Data Localization & Cross-Border Transfer (数据出境安全评估):**  
   Under China's Data Security Law (DSL) and PIPL, AEIB enforces host-side credential isolation and zero outbound telemetry egress. Physical servers and cold backup vaults must reside within the domestic jurisdiction of the PRC unless an approved standard contract (个人信息出境标准合同) or security assessment is completed.
