# PILOT 1: Hotel Credit Scoring
**Regulatory Deadline:** Dec 2, 2027 (Annex III, Essential Service)  
**Complexity Level:** L1→L2→L3→L4→L6→L8→L7  
**KARP Classification:** Article 6(2) High-Risk (Credit Access)

---

## 1. Risk Classification & Regulatory Mapping

### Article 6(2) Analysis
This pilot falls under **Article 6(2) high-risk category**: AI system used to evaluate creditworthiness for access to credit. Hotel guest credit applications (pre-authorization for incidentals, damage deposits) constitute consumer credit under financial regulation.

### Annex III Scope
- **Section 5 (Credit & Finance):** AI used in consumer credit decisions
- **Timeline:** Dec 2, 2027 (compliance deadline, 16 months from Phase 1 close)
- **Regulatory Bodies:** ECB (supervision), national banking authorities (enforcement)

### Failure Impact
- **Accuracy:** Systematic bias against protected classes (nationality, age, disability) violates GDPR Article 9
- **Availability:** System downtime blocks legitimate credit inquiries
- **Integrity:** Model drift causes unequal credit terms

---

## 2. Use Case Narrative

### Context
A 4-star hotel chain (100+ properties) processes ~500 credit applications daily from international guests. Current process: manual review (5-10 min/application) by night staff. Goal: Real-time pre-authorization within 15 seconds, human escalation for edge cases.

### Workflow (Happy Path)
1. Guest arrives at check-in
2. Front desk requests credit pre-auth (30-second form: name, card, stay duration)
3. SMAOS L1-L8 orchestration:
   - **L1 (Policy):** Verify guest country code not in sanctions list (OFAC)
   - **L2 (Retrieval):** Look up guest credit history in hotel database + external API
   - **L3 (Gates):** Check credit score meets threshold (Article 5 non-discrimination)
   - **L4 (Orchestration):** Route to model (LLM + structured output)
   - **L6 (FreeToken):** Validate inference fits budget (<0.5¢ per decision)
   - **L8 (Proof):** Log decision in AP2 ledger (immutable audit trail)
   - **L7 (RAGAS):** Baseline decision against known-good cases
4. Response: Approve | Decline | Escalate-to-Human (within 15s)
5. Hotel staff execute decision (grant room key or request alternative payment)

### Failure Scenarios
1. **System Down:** Guest still checks in (manual fallback by manager)
2. **Credit Lookup Fails:** Default deny (conservative, no guest data leakage)
3. **Model Prediction Uncertain:** Escalate to human (no guessing)
4. **Bias Detected (e.g., nationality):** Audit trigger, block deployment until root-caused

---

## 3. Success Metrics

| Metric | Target | Verification |
|--------|--------|--------------|
| **Latency** | <15s end-to-end | AWS CloudWatch P95 latency |
| **Accuracy** | 87%+ match to human decision (RAGAS) | 50-question golden set |
| **Uptime** | 99.9% (max 43s downtime/month) | Healthcheck probe every 10s |
| **False Negative Rate** | <5% (miss bad credit = loss) | Weekly audit vs. actual defaults |
| **False Positive Rate** | <10% (deny good credit = lost guest) | Guest complaint resolution time |
| **Bias Detection** | Zero systematic disparities by protected class | Monthly fairness audit (disparate impact <1.25x) |
| **Escalation Rate** | <5% to human | Alert if >10% escalations |

---

## 4. SMAOS Layer Alignment

| Layer | Role | Implementation |
|-------|------|-----------------|
| **L1: Policy Routing** | OFAC check, country risk scoring | Policy rules: "deny if country.ofac_flag=true" |
| **L2: Knowledge Retrieval** | Guest credit history, hotel DB, external API | pgvector: guest records + credit bureau data; BM25: hotel booking patterns |
| **L3: Permit Gates** | Article 5 non-discrimination enforcement | Gate rule: "block if decision_delta[nationality] > 5%" |
| **L4: Orchestration** | Credit score decision logic | LangGraph: policy → retrieval → model → response |
| **L6: FreeToken Validation** | Cost control (0.5¢/decision) | Verify API calls fit monthly budget |
| **L8: Proof (AP2 Ledger)** | Immutable decision log | Sign every decision with Ed25519; digest in git |
| **L7: RAGAS Baseline** | Decision quality scoring | Compare AI decision to "known-good" historical decisions |

---

## 5. Regulatory Deadline & Compliance

- **Phase 1 Close:** May 31, 2027 (hotel pilot must be production-ready)
- **Annex III Deadline:** Dec 2, 2027 (7 months for final compliance audit)
- **ECB Submission:** Dec 1, 2027 (1 day before deadline)
  - Dossier: Architecture diagram, bias audit, 6-month performance log
  - Evidence: AP2 ledger (all decisions), RAGAS report, fairness metrics

---

## 6. Failure Modes & Human Escalation

| Failure Mode | Trigger | Escalation Path | Owner |
|--------------|---------|-----------------|-------|
| Credit lookup timeout | API >30s | Escalate to human | Front desk manager |
| Model confidence <60% | Prediction uncertainty | Escalate to human | Credit analyst |
| Bias detection alarm | Disparate impact >1.25x | Block model + alert CISO | Compliance officer |
| Guest disputes decision | Appeal within 48h | Human review + manual correction | Credit team |
| System downtime | All requests fail | Fallback: manual review + post-audit | Night manager |

---

## 7. Proof Collection (What We Measure)

- **AP2 Ledger:** All 50,000+ decisions (May 31 - Dec 2) with:
  - Guest ID, country, card type, decision (approve/deny/escalate), latency, confidence score
  - Model version, retrieval source, policy rules applied
  - Human escalation reason (if any)
  
- **RAGAS Report:** 50-question golden set
  - Q: "Should German guest with 720 FICO be approved?" → Expected: Yes → Model: Yes ✓
  - Accuracy target: 87%+ on credit decisions
  
- **Fairness Audit:** Monthly disparate impact analysis
  - Is approval rate for EU citizens > US citizens? If delta > 5%, investigate
  - Root cause: missing data vs. legitimate risk factors
  
- **Latency Histogram:** P50, P95, P99 end-to-end
  - Target: P95 <15s

---

## 8. Success Criteria (KARP Submission)

- ✅ L1→L8→L7 flow runs without error on 100+ test cases
- ✅ AP2 ledger captures all decisions (immutable audit trail)
- ✅ RAGAS baseline 87%+ on 50-question set
- ✅ Fairness audit shows <1.25x disparate impact
- ✅ 99.9% uptime for 4 weeks (production dry-run)
- ✅ Human escalation path documented and tested
- ✅ Annex III compliance dossier generated (auto-filled from AP2 ledger)

---

## 9. Integration with SMAOS Infrastructure

**Database Schema:**
- `credit_decisions` table: guest_id, country, decision, confidence, timestamp, ledger_hash
- `policy_rules` table: rule_name, version, article_6_category, effective_date

**MCP Server:** Credit evaluation (input: guest data → output: decision + confidence + escalation reason)

**LangGraph Node:** `hotel_credit_score` orchestrates L1→L3→L4 with fallback to human

**FreeToken:** 500 decisions/day × 0.001¢ = ~$0.15/day = $45/month (well under budget)
