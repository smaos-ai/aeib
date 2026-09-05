# PILOT 2: Glass Factory Safety (CAD Review)
**Regulatory Deadline:** Aug 2, 2028 (Annex I, Safety Component)  
**Complexity Level:** L1→L2→L3→L4→L5→L6→L8→L7 (All 8 layers)  
**KARP Classification:** Article 6(1) Regulated Product (Safety-Critical)

---

## 1. Risk Classification & Regulatory Mapping

### Article 6(1) Analysis
This pilot falls under **Article 6(1) regulated product category**: AI system embedded in the design review process for a safety-critical component (tempered glass for automotive/architectural use). Failure to detect edge-stress weakness can result in:
- Automotive: glass failure at highway speeds → injury/death
- Architecture: catastrophic glass failure in high-rise → severe injury/death

### Annex I Scope
- **Product Category:** Tempered glass (safety component under EU Machinery Directive 2006/42/EC)
- **Risk Level:** High (unintended injury or death)
- **Timeline:** Aug 2, 2028 (compliance deadline, 14 months after Phase 1 close)
- **Regulatory Bodies:** NANDO (notified body), national market surveillance authorities

### Failure Impact
- **False Negative (missed defect):** Safety incident, legal liability, market withdrawal
- **False Positive (reject good design):** Production delay, customer dissatisfaction
- **Model Drift:** Changes to glass composition not reflected in training data
- **Audit Trail Gap:** No proof of review → product non-compliant

---

## 2. Use Case Narrative

### Context
A glass manufacturer (100K units/month) receives CAD designs from automotive and architectural customers. Current review: 2 expert engineers, ~30 minutes per design, ~200 designs/month. Goal: AI pre-screen (1-2 minutes) to flag high-risk designs, escalate to human engineer.

### Workflow (Happy Path)
1. Customer uploads CAD file (STEP format, stress analysis metadata)
2. SMAOS L1-L8 orchestration:
   - **L1 (Policy):** Verify CAD meets baseline specs (thickness, material grade, customer class)
   - **L2 (Retrieval):** Retrieve similar historical designs from glass DB + failure case library
   - **L3 (Gates):** Check design against safety rules (edge strength, thermal stress, safety factor)
   - **L4 (Orchestration):** Run multi-step review:
     - Extract CAD geometry (stress points, edge condition, thickness variation)
     - Compare to known-safe designs (BM25 similarity)
     - Run ML model (anomaly detection on stress distribution)
   - **L5 (Communication):** Return structured output (pass/fail/escalate + risk factors)
   - **L6 (FreeToken):** Validate CAD processing cost (<$0.50/design)
   - **L8 (Proof):** Log design review decision in AP2 ledger + CAD metadata
   - **L7 (RAGAS):** Baseline decision against 100 historical designs (known-safe vs. failed)
3. Decision: Pass (auto-approve) | Escalate (human engineer review) | Fail (reject design)
4. Engineer executes decision:
   - Pass: Proceed to production
   - Escalate: 2-hour expert review window
   - Fail: Notify customer with defect report

### Failure Scenarios
1. **CAD Processing Fails:** Unknown file format → Escalate (assume worst-case)
2. **Model Predicts Uncertain:** Risk score 40-60% → Escalate (no guessing on safety)
3. **Historical Data Missing:** New material composition not in training set → Escalate
4. **False Negative Detected:** Post-production failure → Audit trigger, retrain, retest all in-flight designs
5. **Stress Analysis Invalid:** CAD metadata corrupted → Reject (integrity failure)

---

## 3. Success Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| **False Negative Rate** | <1 per 10,000 designs (0.01%) | Track production failures vs. AI decisions |
| **False Positive Rate** | <10% (avoid rejecting good designs) | Retrospective human review of "escalate" pile |
| **Latency** | <2 minutes per design | File upload → decision timestamp |
| **Precision** | 95%+ (if AI says "escalate", human confirms 95% of the time) | Weekly audit logs |
| **Recall** | 99%+ (catch 99% of actually-unsafe designs) | Post-failure root-cause analysis |
| **Audit Trail Completeness** | 100% of decisions logged | AP2 ledger row count = design count |
| **RAGAS Baseline** | 90%+ on 100-design golden set | Compare AI to known-safe vs. known-failed |
| **Human Agreement** | 85%+ concordance (AI vs. engineer on 50 designs) | Double-blind review study |

---

## 4. SMAOS Layer Alignment

| Layer | Role | Implementation |
|-------|------|-----------------|
| **L1: Policy Routing** | Material grade validation, baseline specs | Policy rules: "must be safety_class=S2 or S3; thickness >= 4mm" |
| **L2: Knowledge Retrieval** | Similar historical designs, failure cases | pgvector: CAD embeddings (geometry); BM25: failure narratives + material specs |
| **L3: Permit Gates** | Safety rule enforcement (edge strength, thermal) | Gate rule: "block if safety_factor < 2.0 for edge stress" |
| **L4: Orchestration** | Multi-step CAD review (geometry → model → decision) | LangGraph: parse CAD → retrieve similar → run anomaly model → escalate decision |
| **L5: Communication** | Structured review output (pass/fail/risk factors) | MCP server: CAD Review Agent (input: CAD file → output: JSON decision + risk score) |
| **L6: FreeToken Validation** | Cost control (0.5¢/design target) | Verify CAD parsing + API calls fit budget |
| **L8: Proof (AP2 Ledger)** | Immutable design review audit trail | Sign every review decision; store CAD hash + decision + risk factors |
| **L7: RAGAS Baseline** | Safety decision quality | Compare AI risk score to human engineer consensus on 100 designs |

---

## 5. Regulatory Deadline & Compliance

- **Phase 1 Close:** May 31, 2027 (pilot production-ready, 100+ designs reviewed)
- **Annex I Deadline:** Aug 2, 2028 (15 months for compliance audit)
- **NANDO Submission:** Aug 1, 2028 (1 day before deadline)
  - Dossier: Technical file (ML model, training data, safety analysis), AP2 ledger, RAGAS report
  - Evidence: 12-month production history (0 false-negative failures), 100-design RAGAS baseline

---

## 6. Failure Modes & Human Escalation

| Failure Mode | Trigger | Escalation Path | Owner |
|--------------|---------|-----------------|-------|
| CAD parsing fails | File format unknown or corrupted | Escalate to human + reject design | Engineer |
| Model confidence <70% | Prediction uncertainty on stress | Escalate to human (2-hour review window) | Safety engineer |
| False negative detected | Production failure traced to AI approval | Audit trigger, retrain model, re-review all in-flight designs | ML engineer + safety team |
| Stress analysis invalid | FEA metadata missing or inconsistent | Reject design (data integrity failure) | Quality engineer |
| Material not in training set | New alloy composition not in DB | Escalate + request expert material assessment | Materials engineer |
| Systematic bias detected | e.g., AI rejects 15% of designs from Supplier A, 5% from B | Investigate supplier process differences; if AI bias, block deployment | CISO + safety officer |

---

## 7. Proof Collection (What We Measure)

- **AP2 Ledger:** All 2,400+ design reviews (May 31, 2027 - Aug 2, 2028) with:
  - Design ID, customer, material, thickness, risk score, decision (pass/escalate/fail)
  - CAD hash, stress analysis metadata, model version
  - Escalation reason (if any), engineer outcome (final approval vs. revision)
  - Post-production outcome (failure vs. success)
  
- **RAGAS Report:** 100-design golden set (50 known-safe, 50 known-failed historical designs)
  - Q: "CAD for 6mm tempered glass, auto glass (high-stress) — pass?" → Expected: Escalate → Model: Escalate ✓
  - Accuracy target: 90%+ agreement with human consensus
  
- **False Negative Analysis:** Monthly tracking
  - If 1+ production failures occur, immediate audit: Was design reviewed by AI? If yes, why missed?
  - Root cause: model drift, corrupt metadata, ambiguous design?
  - Mitigation: retrain, retest, re-review in-flight designs
  
- **Latency Histogram:** P50, P95, P99 CAD processing time
  - Target: P95 <2 minutes

---

## 8. Success Criteria (KARP Submission)

- ✅ L1→L8→L7 flow processes 100+ real CAD designs without error
- ✅ AP2 ledger captures all design reviews (immutable audit trail)
- ✅ Zero false-negative failures in 12-month production run
- ✅ RAGAS baseline 90%+ on 100-design golden set
- ✅ Human engineer audit: 95%+ precision (escalates are justified)
- ✅ <2 minute latency for 95% of designs (P95)
- ✅ Annex I compliance dossier generated (technical file + audit trail)

---

## 9. Integration with SMAOS Infrastructure

**Database Schema:**
- `cad_reviews` table: design_id, customer, material, risk_score, decision, ledger_hash, timestamp
- `safety_rules` table: rule_name, safety_factor_min, edge_stress_limit, version
- `known_designs` table: design_hash, outcome (pass/fail), failure_mode, date_reviewed

**MCP Server:** CAD Safety Reviewer (input: CAD file + metadata → output: risk_score + decision + explanation)

**LangGraph Node:** `glass_factory_review` orchestrates L1→L2→L3→L4→L5 with escalation logic

**FreeToken:** 2,400 designs/year × 0.005¢ = ~$1.20/year (trivial cost)

---

## 10. Long-Tail Risk: Post-Deployment False Negatives

**Scenario:** AI approves design X. Six months later, design X fails in customer vehicle → death/injury.

**Detection:** Customer failure report → Glass QA team → "Was design reviewed by AI?"

**Response (24-hour SLA):**
1. Immediate: Pull AP2 ledger for design X (risk score, model version, retrieval sources)
2. Root cause: Did AI miss edge stress? Was material unknown? Was FEA metadata corrupt?
3. If AI error: Trigger emergency retraining
   - Incorporate failure case into training set
   - Re-test RAGAS baseline (target remains 90%+)
   - Re-review all in-flight designs approved by old model
4. If not AI error: Document decision rationale; proceed to production issue investigation
5. Report: Escalate to notified body (NANDO) within 5 business days (EU product safety directive)

**Contingency:** Manual review of all remaining in-flight designs (1-week window, engineering team)
