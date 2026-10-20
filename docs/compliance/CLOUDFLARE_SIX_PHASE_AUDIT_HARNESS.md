# Cloudflare 6-Phase Audit & Fresh Disproving Verifier Harness
## Technical Specification, Epistemic Framework, and DORA Article 17 Conformity

> [!NOTE]
> **EPISTEMIC BOUNDARIES & DISCLAIMER:**
> This document describes a pre-production verification harness evaluated under the stated model as part of the Sovereign Multi-Agent OS (SMAOS) / Agent Execution Integrity Benchmark (AEIB) prototype.
> All cryptographic operations utilize real Ed25519 asymmetric primitives (`cryptography.hazmat.primitives.asymmetric.ed25519`), SHA-256 cryptographic digests, and strict RFC 8785 JSON Canonicalization Scheme (JCS).
> In accordance with repository epistemic boundaries, statements reflect evaluated test vectors, observed execution artifacts, and configured verification gates.

---

## 1. Executive Summary: The Disproving Verifier Paradigm

In automated vulnerability discovery and AI-assisted security analysis, automated scanners and large language model (LLM) red-teaming agents frequently generate excessive false positive candidates. Unsubstantiated hypotheses, hallucinated taint paths, and non-exploitable theoretical mutations place an unsustainable cognitive burden on security engineers.

The Cloudflare vulnerability discovery architecture addresses this challenge by inverting the verification burden:
1. **The Null Hypothesis**: The verification system starts with the explicit assumption that any candidate vulnerability finding is a **false positive** or an unexploitable hallucination.
2. **Fresh Disproving Verifiers**: Rather than attempting merely to "confirm" an attack, independent verifiers actively seek to **disprove** the candidate finding by executing counter-examples, evaluating defensive interlocks, and testing sandbox containment boundaries.
3. **Binary Epistemic Classification**:
   - `DISPROVED_FALSE_POSITIVE`: The candidate exploit is blocked, neutralized, or invalidated by an observed defensive gate or containment mechanism.
   - `VALIDATED_BREACH`: The candidate exploit survives active disproving, penetrates sandbox boundaries without mitigation, and demonstrates verifiable impact under the stated model.

The AEIB harness implements this methodology across six distinct phases, culminating in RFC 8785 JCS canonical formatting and Ed25519 cryptographic signing.

---

## 2. Six-Phase Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Architecture Mapping & Coverage Ledgers (ArchitectureMapper)  │
│  - Static AST indexation of endpoints, handlers, and trust boundaries  │
│  - Generation of deterministic coverage ledger with SHA-256 digest     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Phase 2: Coverage-Led Parallel Hunting (CoverageLedHunter)             │
│  - Systematic hypothesis generation across 5 vulnerability classes     │
│  - Target parameterization: payloads, context, and expected behaviors   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Phase 3: Candidate Validation via Fresh Disproving Verifiers           │
│  - Null hypothesis initialization (Candidate = False Positive)         │
│  - Counter-example injection, sandbox checks, cryptographic defense    │
│  - Classification: DISPROVED_FALSE_POSITIVE vs VALIDATED_BREACH        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Phase 4: Structured Canonical Output (StructuredCanonicalOutput)       │
│  - Byte-deterministic RFC 8785 JCS serialization                       │
│  - UTF-16 code-unit sorted mapping with immutable SHA-256 digest      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Phase 5: Independent Cryptographic Verification (IndependentReceiptSigner)│
│  - Ed25519 digital signature over canonical findings payload           │
│  - Offline-verifiable cryptographic receipt and CAID derivation        │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Phase 6: Target-Neutral Report Generation (generate_report_markdown)   │
│  - Objective factual markdown output conforming to AGENTS.md rules     │
│  - Zero promotional language; explicit evidence linkage               │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Phase Breakdown

### Phase 1: Architecture Mapping & Coverage Ledgers (`ArchitectureMapper`)
- **Objective**: Establish an immutable baseline of the target codebase structure before hunting commences.
- **Mechanism**:
  - Recursively traverses Python source trees (`.py`), parsing code into Abstract Syntax Trees (AST).
  - Identifies HTTP routes and RPC endpoints through route decorator patterns (`@app.get`, `@router.post`, etc.) and mutation pools (e.g., `FINANCIAL_MUTATION_POOL`).
  - Indexes all AST symbols (classes, functions, async functions) and classifies trust boundaries using structural heuristics (`gate`, `guard`, `boundary`, `interlock`, `governor`, `hsm`, `signer`, `verifier`, `latch`, `admission`, `lockout`, `sanitizer`).
  - Serializes the resulting `CoverageLedger` into RFC 8785 canonical bytes to derive the `mapping_digest`.

### Phase 2: Coverage-Led Parallel Hunting (`CoverageLedHunter`)
- **Objective**: Formulate concrete, testable exploit hypotheses spanning critical agentic failure modes.
- **Five Target Vulnerability Classes**:
  1. `PATH_TRAVERSAL`: Relative path injection (`../../etc/...`) targeting evidence or artifact download endpoints.
  2. `PAYEE_ALTERATION`: Mutating the recipient identifier (e.g. IBAN) in an inflight financial settlement payload.
  3. `BUDGET_ESCALATION`: Exceeding single-transaction limits or cumulative sprint-window quota ceilings.
  4. `CONTEXT_TAINT_DOWNGRADE`: Attempting to de-escalate untrusted MCP tool outputs to trusted system context without supervisor authorization.
  5. `NONCE_REPLAY`: Resubmitting a previously observed execution nonce or transaction CAID to trigger duplicate effects.

### Phase 3: Candidate Validation via Fresh Disproving Verifiers (`FreshDisprovingVerifier`)
- **Objective**: Actively disprove candidate findings by evaluating defense mechanisms and counter-examples.
- **Execution Matrix**:

| Vulnerability Class | Disproving Test Vector / Counter-Example | Defense Mechanism Evaluated | Observed Disproving Outcome |
|---|---|---|---|
| `PATH_TRAVERSAL` | Injects relative traversal path against base directory | `GatewayPathContainmentGuard` | Resolved path prefix violates containment boundary; blocked with `DISPROVED_FALSE_POSITIVE`. |
| `PAYEE_ALTERATION` | Mutates payee IBAN; evaluates RFC 8785 JCS CAID and real Ed25519 signature | `Ed25519SignatureAndJCSCAIDInterlock` | CAID mutation detected and Ed25519 signature verification fails; blocked with `DISPROVED_FALSE_POSITIVE`. |
| `BUDGET_ESCALATION` | Submits payment amount exceeding single-transaction ceiling and sprint window | `DualWindowFinancialLedgerGovernor` | Dual-window ledger verifies amount > allowance; blocked with `DISPROVED_FALSE_POSITIVE`. |
| `CONTEXT_TAINT_DOWNGRADE` | Requests promotion of untrusted MCP context without cryptographic de-escalation token | `MCPToolProvenanceTaintCeilingGovernor` | Monotonic taint ceiling enforced; unauthorized promotion blocked with `DISPROVED_FALSE_POSITIVE`. |
| `NONCE_REPLAY` | Submits duplicate nonce already logged in the observed nonce registry | `ServerIdempotencyLatchAdapter` | Nonce registry detects replay; returns conflict disposition with `DISPROVED_FALSE_POSITIVE`. |

If a candidate is evaluated in an unmitigated environment (e.g., sandbox controls disabled or missing signature checks), the exploit executes without rejection and is classified as `VALIDATED_BREACH`.

### Phase 4: Structured Canonical Output (`StructuredCanonicalOutput`)
- **Objective**: Prevent format ambiguity, key re-ordering, and whitespace discrepancies across distributed verifiers.
- **Standard**: RFC 8785 JSON Canonicalization Scheme (JCS).
- **Invariants**:
  - Keys sorted lexicographically by UTF-16 code units.
  - Zero redundant whitespace separators (`,`, `:`).
  - Unescaped UTF-8 string encoding.
  - Deterministic SHA-256 payload digest calculation.

### Phase 5: Independent Cryptographic Verification (`IndependentReceiptSigner`)
- **Objective**: Provide offline-verifiable, mathematically binding non-repudiation for audit receipts.
- **Cryptographic Primitives**:
  - Algorithm: Ed25519 (`cryptography.hazmat.primitives.asymmetric.ed25519`).
  - Signature Input: Raw RFC 8785 canonical bytes from Phase 4.
  - Receipt Schema: Includes `payload_sha256`, `signer_public_key_hex`, `signature_hex`, `signed_at_utc`, and `receipt_caid`.
- **Offline Verification**:
  - Independent parties verify that `SHA-256(canonical_bytes) == receipt.payload_sha256`.
  - Independent parties verify `Ed25519PublicKey.verify(signature, canonical_bytes)`.
  - Tampering with even a single bit of the findings invalidates the cryptographic proof.

### Phase 6: Target-Neutral Report Generation (`generate_report_markdown`)
- **Objective**: Deliver an audit report adhering strictly to scientific and regulatory disclosure requirements.
- **Linguistic Standards**:
  - Restricts descriptions to observed behaviors, empirical measurements, and configured mechanisms.
  - Omits unverified promotional claims or absolute assertions.
  - Formats tables of disproved candidates and validated breaches with clear rationale linkage.

---

## 4. DORA Article 17 Auditability & Compliance Alignment

The European Union Digital Operational Resilience Act (Regulation (EU) 2022/2554, DORA) establishes comprehensive requirements for digital operational resilience testing in the financial sector.

### Article 17 Alignment Matrix

| DORA Article 17 Mandate | AEIB Cloudflare 6-Phase Audit Harness Implementation |
|---|---|
| **Art. 17(1): General Requirements for Digital Operational Resilience Testing** | Provides an automated, deterministic framework to evaluate software components, API endpoints, and financial transaction boundaries. |
| **Art. 17(2): Scope of Testing Tools & Methodologies** | Integrates static AST architecture mapping (Phase 1), vulnerability hunting (Phase 2), and active disproving verification (Phase 3). |
| **Art. 17(3): Independent Verification of Results** | Employs asymmetric Ed25519 signatures and RFC 8785 canonical outputs, allowing independent supervisors and competent authorities to verify audit receipts offline. |
| **Art. 17(4): Remediation and Flaw Tracking** | Formats disproved false positives and validated breaches into structured JSON and target-neutral markdown, documenting exact root-cause counter-examples. |

---

## 5. CLI Verification Commands

The harness provides a command-line interface for local evaluation:

```bash
# Execute deterministic internal self-test suite
python3 src/audit_disproving_verifier.py --self-test

# Audit designated target directory and emit canonical JSON bundle and Markdown report
python3 src/audit_disproving_verifier.py \
  --target-dir src \
  --output-json scratch/findings.json \
  --output-md docs/compliance/AUDIT_REPORT_OBSERVED.md
```

All evaluation runs execute without external network egress or simulated mocks.
