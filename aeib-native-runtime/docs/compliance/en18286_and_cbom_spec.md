# AEIB System-Level QMS (`EN 18286`), Incident Separation, IETF SCITT (RFC 9942/9943), and Crypto Bill of Materials (`ECMA-424` CBoM)

> **Scope Notice & Epistemic Boundary:**
> **AEIB is a governed execution boundary for consequential AI actions: it binds exact action and authority before dispatch, preserves uncertainty (`EFFECT_INDETERMINATE`) after transport ambiguity, reconciles through bounded authoritative evidence, and produces operation-bound verifiable receipts.**
> All properties described in this specification are **observed**, **tested**, **evaluated**, and **configured** **under the stated model** of our **prototype** and **scaffold** verification harnesses.

---

## 1. EU AI Act Article 17 & `EN 18286` System-Level Lifecycle Mapping
Per **European Commission Implementing Decision (EU) 2026/2274 (14 October 2026)**, `EN 18286` is cited in the Official Journal of the European Union and provides a legal presumption of conformity under **Article 40** for **Article 17 Quality Management Systems** at the individual high-risk AI system level (distinct from `ISO/IEC 42001`, which governs organizational AI management as a whole). AEIB generates system-level technical evidence across the four mandatory `EN 18286` lifecycle pillars:

1. **Testing and Validation:** Deterministic zero-mock fault-injection and red-team suites (`AT30`–`AT64`).
2. **Data Management (Context & Tool Provenance):** Provenance-tiered context taint tracking (`TIER_0`–`TIER_2`) and cryptographic MCP `tools/list` schema + source manifest pinning (`AT57a/b`, `AT60`, `AT63`, `AT63b`, `AT64`).
3. **Monitoring After Release:** Out-of-process append-only JCS ledger (`ledger.jsonl`) with boot-time per-entry signature verification (`AT59`) and OpenTelemetry GenAI `v1.43` span emission.
4. **Reporting of Serious Incidents:** Automated DORA Art. 17/19 and EU AI Act incident evidence bundles separating model behavior, execution authorization, and observed consequences.

---

## 2. Three-Question Incident Evidence Separation (`ELIAS` / Runtime AI Governance Alignment)
Every AEIB `COSE_Sign1` receipt explicitly partitions incident evidence into three distinct, independently verifiable fields:
- `attempted_model_proposal`: Canonical hash (`CAID`) of what the model/agent attempted to execute (recognizing that model capability is not execution authority).
- `boundary_authorization_state`: The governing sponsor key, delegation certificate, policy epoch at $T_n$, and boundary verdict (`ALLOW | HOLD | DENY | ESCALATE`).
- `observed_target_consequence`: Transport outcome (`CONFIRMED | REFUTED | EFFECT_INDETERMINATE`) and target-attested reconciliation status.

---

## 3. IETF SCITT Transparent Statement Architecture (RFC 9943 & RFC 9942)
To satisfy external auditors (e.g., `iFixAi` trajectory checks and EU Notified Bodies) without granting read access to the host's local `ledger.jsonl`, AEIB Station 3 packages every consequential decision as an **RFC 9943 Transparent Statement**:
1. **Signed Statement (`RFC 9052 COSE_Sign1`):** Protected header carries `alg` (`-8` for Ed25519 or `-49` for `ML-DSA-65`), `kid`, and `cty: "application/aeib.statement+json"`.
2. **SCITT Receipt (`RFC 9942`):** Attached in the unprotected header (`receipts: [...]` / IANA COSE Header `394`), containing the RFC 9162 / RFC 9942 Merkle inclusion proof (`tree_size`, `leaf_index`, `inclusion_path`) signed by the transparency log service (`vds = 1` in Header `395`, `vdp` proof map in Header `396`).
3. **OpenTelemetry GenAI `v1.43` Privacy Split:**
   - **Indexed Span Attributes (`execute_tool`):** Carries `gen_ai.operation.name: "execute_tool"`, `gen_ai.provider.name`, `gen_ai.tool.name`, `gen_ai.tool.type: "function"`, `gen_ai.agent.name`, `aeib.operation_id`, `aeib.action.caid`, `aeib.receipt.sha256`, and `aeib.boundary.verdict`, with zero raw PII or financial account numbers in span attributes.
   - **Isolated Operation Detail Event:** Raw sensitive arguments are isolated into `gen_ai.client.inference.operation.details` with `gen_ai.tool.call.arguments_redacted_digest` for vault-scoped inspection.

---

## 4. Standard ECMA-424 CycloneDX Cryptography Bill of Materials (`cbom.json`) & 2027 PQC Agility
Per NSA PQC 2027 transition guidance, **NIST FIPS 204 (`ML-DSA`)**, **RFC 9881 / RFC 9882 / RFC 9964**, and **NIST SP 1800-38**, AEIB supports banking and critical infrastructure PQC migration paths (2027–2030):
- **Canonicalization Digest:** `SHA-256` (RFC 8785 JCS) $\rightarrow$ Agile prefix `sha256:` (upgradable to `sha384:` / `sha3-256:`).
- **Receipt Envelope:** RFC 9052 `COSE_Sign1` with explicit `alg` parameter:
  - Current Baseline: `alg: -8` (`EdDSA` / `Ed25519`)
  - PQC / Hybrid Migration Slot: `alg: -48` / `-49` / `-50` (`ML-DSA-44` / `ML-DSA-65` / `ML-DSA-87` or Composite `Ed25519 + ML-DSA-65`).

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.6",
  "version": 1,
  "metadata": {
    "component": {
      "type": "application",
      "name": "aeib-execution-boundary",
      "version": "1.0.0-rc.3"
    }
  },
  "components": [
    {
      "type": "cryptographic-asset",
      "bom-ref": "crypto-ed25519-station1",
      "name": "Ed25519",
      "cryptoProperties": {
        "assetType": "algorithm",
        "algorithmProperties": {
          "primitive": "signature",
          "parameterSetIdentifier": "255",
          "curve": "Ed25519",
          "executionEnvironment": "software-plain-ram",
          "classicalSecurityLevel": 128,
          "nistQuantumSecurityLevel": 0
        },
        "oid": "1.3.101.112"
      }
    },
    {
      "type": "cryptographic-asset",
      "bom-ref": "crypto-mldsa65-pqc-slot",
      "name": "ML-DSA-65",
      "cryptoProperties": {
        "assetType": "algorithm",
        "algorithmProperties": {
          "primitive": "signature",
          "parameterSetIdentifier": "65",
          "mode": "pure",
          "classicalSecurityLevel": 192,
          "nistQuantumSecurityLevel": 3
        },
        "oid": "2.16.840.1.101.3.4.3.18"
      }
    }
  ]
}
```
