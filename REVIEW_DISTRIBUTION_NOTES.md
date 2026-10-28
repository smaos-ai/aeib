# REVIEW_DISTRIBUTION_NOTES.md — Scope Classification & Canonical Release Lock

**Project:** SovereignNexus (Independent Research Initiative • Czech Republic)  
**Lead Researcher:** Andrii Leukhin (`andrejlo123@gmail.com`)  
**Repository:** [https://github.com/sovreignnexus/smaos](https://github.com/sovreignnexus/smaos) (Tag: `v1.0-review`)  
**Package:** `dist/aeib-enterprise-v1.0.tar.gz` (SHA-256: `cf3a319ee801784fae303b534178c5590020bc72990cd0119e7753a15abb6525`)  
**DOI:** [`10.5281/zenodo.22844531`](https://doi.org/10.5281/zenodo.22844531)  
**Release Designation:** `AEIB_ENTERPRISE_V1_0_REVIEW`  

---

## 🏛️ 1. Single Release Identity (Canonical Release Lock)

To eliminate competing or ambiguous release parameters across documents, the official release identity is established as follows:

```text
Version:                  v1.0-review (AEIB Core v0.2.4-final)
Git commit:               e8f510954d52573a1860bae03bf011398e77f1fe (40-char SHA-1 object ID, tag: v0.2.4 / v1.0-review)
Archive filename:         dist/aeib-enterprise-v1.0.tar.gz
Archive byte count:       298,188,215 bytes
Archive SHA-256:          cf3a319ee801784fae303b534178c5590020bc72990cd0119e7753a15abb6525
Manifest SHA-256:         7bb91c8c0a69eec17d931c4a9fa9153ee6a5e94a9d70299ca508788b3040a08f (compliance/aeib_manifest.json, 15/15 matched)
Test command:             pytest -v --ignore=scratch/
Test count:               353 total (343 passed, 10 skipped, 0 failed)
Skipped tests & reasons:  10 skipped total:
                          • 2 story integration tests (tests/stories/test_story_001_treasury_authorization.py:63, 231: requires live backend service)
                          • 7 eBPF LSM/XDP controller tests (tests/test_ebpf_controller.py:56, 61, 83, 100, 114, 123, 154: deferred to Linux kernel / WP3)
                          • 1 BBS+ Rust port test (tests/test_transport_interceptor.py:88: deferred to Phase 3 roadmap in WP2)
```

---

## 📊 2. Research Component Maturity & Labeling Matrix

To prevent evidence transfer from the verified core, every experimental extension and research component is strictly classified:

### A. Implemented and Tested
- **AEIB Core Harness**: 500-episode deterministic baseline under synthetic fault model (0/500 duplicate mutations, ~0.60% Rule-of-Three bound, ~0.86ms p50).
- **Local PostgreSQL OOB Probing**: Authoritative out-of-band state resolution on local PostgreSQL instances.
- **Local Qwen/Ollama Semantic-Drift Loop**: Tested against local Qwen 35B / Ollama prompt rephrasings with fallback.
- **Offline WASM Verification**: ReceiptPayload v1.0/v1.1 verified via standalone WASM engine in tested runtime.
- **Local Saga-Compensation Harness**: Preserves tested net-balance invariant (\(\sum \Delta_{net} = 0.00\)) locally as an eventual consistency strategy.
- **Ghost Audit Scanner (`ghost_audit_scanner.py`)**: Local AST, configuration, and environment crawler (596 lines).

### B. Implemented Prototype
- **Toxiproxy / Network-Chaos Harness**: Tested in local containerized socket proxy loops; not live-WAN results.
- **Rust BBS+ Selective Disclosure**: Tested in prototype crate under Cargo feature gate; pending full C-ABI integration.
- **MCP and Cross-Benchmark Adapters**: Local adapters around external suites (`duplicate-side-effect-desk`, `agent-runtime-integrity-bench`, `AgentDisruptBench`, \(\tau^2\)-bench 083–085); local adapter execution is not independent third-party validation.

### C. Scaffold or Deferred
- **JVM Virtual-Thread Implementation**: Structural Java 21+ Project Loom scaffold; pending physical multi-tenant integration.
- **eBPF LSM Enforcement**: Kernel-level LSM `bprm_check_security` hooks deferred to Phase 3 Linux kernel roadmap.
- **Physical PKCS#11 HSM**: Software PKCS#11 wrapper tested; physical HSM bus pending.
- **TDX / SEV-SNP Hardware Attestation**: Linux ioctl hooks structured; does not validate hardware-backed production enclaves.
- **Multi-Region Replication & WAN Failure**: Cross-datacenter consensus and live WAN network splits deferred.
- **Broad Framework Compatibility**: General-purpose agent framework interoperability beyond tested adapters deferred.

---

## ⚠️ 3. Important Qualifications & Epistemic Boundaries

1. **Eventual Consistency vs. Rollback**: The saga compensation harness demonstrates an **eventual consistency strategy**, not atomic distributed rollback.
2. **Hardware Boundaries**: A software PKCS#11 wrapper does not validate a physical HSM. An ioctl path does not validate real TDX or SEV-SNP attestation.
3. **Kernel Boundaries**: An eBPF source file with deferred or stubbed hooks is not kernel enforcement.
4. **Network Boundaries**: A local Toxiproxy loop is not a live-WAN result.
5. **Adapter vs. Third-Party**: A local adapter around an external benchmark is not independent third-party validation.
6. **Latency Profiling**: The 0.86 ms benchmark measurement is substrate-specific (pure-Python in-memory verification loop, macOS ARM64) and must not be generalized to distributed network boundaries.
7. **Strict Language Discipline**: Use **"observed," "tested,"** and **"under the stated model."** Do NOT use absolute claims of guarantee, universal proof, or operational safety.

---

## 📑 3. Paper Results Hierarchy (arXiv / Publication)

In the academic manuscript (`AEIB_arXiv_Paper_Draft.tex` / `AEIB_arXiv_Paper.tex`), all results are explicitly separated into four distinct categories:

1. **Primary Experiment**: The AEIB v0.2.4 synthetic 15-vector, 500-episode benchmark (**0/500 duplicate mutations**, p50 latency 0.86ms).
2. **Secondary Experiments**: PostgreSQL out-of-band state reconciliation and local cross-benchmark adapter runs (`duplicate-side-effect-desk`, `agent-runtime-integrity-bench`, `AgentDisruptBench`, \\(\\tau^2\\)-bench tasks 083–085).
3. **Prototype Demonstrations**: Local demonstrations of MCP proxy integration, JVM virtual thread unpinning, WASM offline verification, PKCS#11 zero-RAM enclave, and Toxiproxy fault injection.
4. **Future Work**: Independent third-party reproduction, physical eBPF LSM kernel enforcement, live TDX/SEV-SNP hardware quote verification, multi-region distributed DB replication testing, and formal ISO 42001 certification.

---

## 🛡️ 4. Risk Mitigation & Epistemic Boundaries

* **Independent Benchmark Wording**: All references to third-party benchmarks are strictly phrased as *"evaluated through local adapters against externally originated benchmark scenarios"* rather than claiming independent third-party validation.
* **Zero-Mock Claims**: AST scans verify the absence of `unittest.mock` and hardcoded stub patterns in active Python/Rust production paths, while recognizing conceptual test doubles in local simulation environments.
* **RFC 8785 JCS Conformance**: `canonical_json_bytes()` explicitly enforces byte-level RFC 8785 JSON Canonicalization Scheme rules (strict UTF-8, no whitespace, lexicographically sorted keys, IEEE 754 number formatting), rather than unconstrained `json.dumps()`.
* **Compensation Semantics**: Saga compensation provides eventual consistency rather than physical atomic rollback. A failed or delayed compensating action transitions to `COMPENSATION_FAILED_MANUAL_INTERVENTION_REQUIRED` for human queue escalation.
* **Hardware & Kernel Claims**: HSM, TDX, SEV-SNP, eBPF LSM, and CTAP 2.2 components are explicitly flagged as software emulations or hardware-untested prototypes until validated on physical enclaves.
* **Regulatory Language**: All mappings to DORA, GDPR, NIST, and the EU AI Act are designated as *informative engineering mappings and evidence-generation tools*, not legal or regulatory certifications.
* **External Reproduction**: Independent third-party reproduction remains the mandatory final credibility gate before commercial production deployment.

---

## 🎯 5. Final Epistemic Classification

* **Strongly Established**:
  * Real, executable core state machine and deterministic synthetic fault harness (`run_episodes.py`).
  * Transport-to-disposition mapping contract (`DISPATCHED_UNCONFIRMED`).
  * Local SQLite and PostgreSQL authoritative out-of-band state probing.
  * **Zero observed duplicate effects in 500 deterministic episodes** under the stated synthetic fault model (approximate Rule-of-Three 95% upper bound ~0.60%).
  * Fail-closed disposition handling and RFC 8785 JCS CAID derivation.
  * Reproducible single-archive packaging and manifest verification (`15/15 files matched`).

* **Experimental / Prototype Extensions**:
  * Behaviour under live WAN network splits, multi-resource primary failover, or physical database replication lag.
  * Hardware-backed attestation (TDX/SEV-SNP), eBPF kernel enforcement, and physical PKCS#11 HSM integration.
  * Broad multi-framework adapters and automated regulatory dossier exports.
