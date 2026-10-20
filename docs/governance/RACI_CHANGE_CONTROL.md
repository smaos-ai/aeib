# DORA Article 17 Separation of Duties & Change Control RACI
## Institutional Governance, Role Segregation, and Operational Approval Protocol

> **Regulatory Reference:** Regulation (EU) 2022/2554 (DORA) Article 17(1)–(2); Commission Delegated Regulation (EU) 2025/301; EU AI Act Article 17  
> **Classification:** Pre-Production Operational Governance & Change Management Policy  
> **Epistemic Notice:** This specification establishes the separation of duties evaluated under the stated model of our execution boundary architecture.

---

### 1. Mandatory Segregation of Duties

To satisfy DORA Article 17 requirements for strict segregation between authors, reviewers, approvers, and operational deployers, the following role matrix governs all code modifications, policy changes, and release distributions:

```
Designated Roles:
• CODE-AUTH: Code Author (Developer / AI Agent)
• SEC-REV:   Independent Security Reviewer (Staff Engineer)
• REL-APP:   Release Approver (Risk Owner / CISO Delegate)
• PLAT-DEP:  Platform Deployer (Site Reliability Engineer)
• INC-CMD:   Incident Commander (Treasury / Risk Lead)
```

| Lifecycle Action | Code Author (Dev / AI Agent) | Security Reviewer | Release Approver (Risk Owner) | Platform Deployer (SRE) | Incident Commander |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Author Code / Policy PR** | **Responsible (R)** | Consulted (C) | Informed (I) | Informed (I) | Informed (I) |
| **Approve Policy / AST / Threat Diff** | **Forbidden** | **Responsible (R)** | **Accountable (A)** | Informed (I) | Informed (I) |
| **Sign Release Tag & Verify SBOM/WASM**| **Forbidden** | Consulted (C) | **Accountable (A)** | **Responsible (R)** | Informed (I) |
| **Issue SupervisorRecoveryWarrant (Un-Halt)** | **Forbidden** | Consulted (C) | **Accountable (A)** | Informed (I) | **Responsible (R)** |

*(Legend: **Responsible (R)** = executes the action; **Accountable (A)** = holds veto and legal authorization; **Consulted (C)** = provides technical review; **Informed (I)** = receives event telemetry; **Forbidden** = explicitly disallowed to prevent self-approval.)*

---

### 2. Operational Change Lifecycle

1. **Change Ingestion:** Feature branch created from main repository worktree.
2. **Automated Conformance Gate:** AST purity scanner (`compliance/ast_purity.py`), zero-mock enforcer, and zone boundary checks execute via CI.
3. **Independent Peer Review:** Security Reviewer conducts independent review of diff and static verification receipts without author participation.
4. **Pre-Deployment Authorization:** Risk Owner signs the change request manifest over canonical RFC 8785 JCS data.
5. **Deployment & Smoke Test:** SRE deploys signed release binary and executes live verification suite.
6. **Telemetry & Audit Registration:** Change event and new release digest are anchored to the local WAL and SCITT transparency service.
