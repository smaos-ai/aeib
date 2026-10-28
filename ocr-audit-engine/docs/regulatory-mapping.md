# Regulatory Mapping Reference: DORA, EU AI Act, SOC 2, and FedRAMP

| Regulation | Article / Control | Requirement | OCR Audit Engine Compliance Mechanism |
| :--- | :--- | :--- | :--- |
| **DORA (EU 2022/2554)** | Art. 17(1) | Incident detection & classification | Automated detection of transport drops & timeout discrepancies |
| **DORA (EU 2022/2554)** | Art. 17(3) | Complete audit log chain of custody | Deterministic Anchor with byte-exact line offsets & SHA-256 hashes |
| **DORA RTS 2024/1772** | Art. 2-7 | Materiality criteria classification | TRI score calculation mapping unconfirmed mutating actions to loss exposure |
| **EU AI Act (2024/1689)**| Art. 12 | Automatic recording of events | Immutable JCS-canonicalized receipt validation |
| **EU AI Act (2024/1689)**| Art. 14 | Human oversight & fail-safe | Remediation diffs (`fix.patch`) requiring manual approver sign-off |
| **SOC 2 Type II** | CC6.8 / CC7.2 | Monitoring unauthorized activities | Ground-truth verification across database transaction IDs (`xid`) |
| **FedRAMP High** | AU-3 / AU-12 | Content of audit records | Bit-exact reproducible audit findings without statistical model drift |
