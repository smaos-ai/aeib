# L1 Reasoning: SMAOS Policy Router

**Purpose:** EU AI Act compliance routing for SMAOS Phase 1 pilots.

Each decision flows through PolicyRouter → determines applicable Articles/Annexes → generates audit trail → passes to L2/L3 enforcement layers.

---

## Architecture

### Key Design Decisions

**Why this approach?**
- **Policy-bound decisions:** Compliance enforced upfront, not retroactively
- **Risk-proportional:** High-risk pilots (glass, hotel, school) all get strict oversight
- **Transparent audit trail:** Every decision includes articles, reasoning, timestamp
- **Downstream integration:** Router output feeds L2 (Knowledge) and L3 (Permit Gates) layers

### Components

#### 1. PolicyRouter (main class)
```python
router = PolicyRouter()
route = router.route_request(
    pilot_name="hotel",  # One of: hotel, glass, school
    request_description="Credit scoring for guest financing",
    compliance_assessment=90,  # 0-100 score
)
```

#### 2. PolicyRoute (decision record)
```
route.pilot_name       # Which pilot (hotel/glass/school)
route.risk_level       # RiskLevel.HIGH for all SMAOS pilots
route.articles         # List of applicable Articles
route.annex_sections   # List of applicable Annexes
route.decision         # APPROVED | DENIED (based on compliance score)
route.compliance_score # 0-100 (must be ≥80 to route)
route.audit_trail      # Human-readable compliance reasoning
```

#### 3. RiskLevel Enum
- **LOW:** Non-critical use cases (not used in SMAOS)
- **MEDIUM:** Medium-risk (not used in SMAOS)
- **HIGH:** Safety-critical or sensitive sectors (all SMAOS pilots)
- **PROHIBITED:** Explicitly banned by Article 5 (not used in SMAOS)

---

## SMAOS Pilot Routing

### Hotel (Credit Scoring)

| Attribute | Value |
|-----------|-------|
| **Risk Level** | HIGH |
| **Articles** | 50, 51, 14 |
| **Annexes** | Annex III |
| **Min Compliance** | 90% |

**Why:**
- Article 50: Chatbot must disclose it's AI (transparency)
- Article 51: GPAI (general-purpose AI model) governance applies
- Article 14: Must document accuracy and robustness (credit decisions affect livelihoods)
- Annex III: Credit/financial decisions in essential services prohibited without strict controls

**Audit Trail Example:**
```
Pilot: HOTEL
Risk Level: HIGH

Applicable Articles:
  ✓ Article 50: Transparency and disclosure obligations
  ✓ Article 51: General-purpose AI (GPAI) governance
  ✓ Article 14: Model cards and documentation for accuracy/robustness

Applicable Annexes:
  ✓ Annex III: Prohibited AI uses in employment, education, essential services

Compliance Reasoning:
Credit scoring affects essential financial service. GPAI (Article 51) applies.
Must disclose chatbot nature (Article 50), document accuracy (Article 14),
and avoid Annex III prohibited use in employment/finance decisions.
```

### Glass (Safety Review)

| Attribute | Value |
|-----------|-------|
| **Risk Level** | HIGH |
| **Articles** | 6, 13, 14 |
| **Annexes** | Annex I |
| **Min Compliance** | 85% |

**Why:**
- Article 6: High-risk AI system classification required
- Article 13: Documentation and records mandatory for safety-critical systems
- Article 14: Robustness documentation (safety affects user protection)
- Annex I: Safety components in high-risk category (glass defect detection prevents injuries)

**Audit Trail Example:**
```
Pilot: GLASS
Risk Level: HIGH

Applicable Articles:
  ✓ Article 6: High-risk AI classification and management
  ✓ Article 13: Documentation and record-keeping requirements
  ✓ Article 14: Model cards and documentation for accuracy/robustness

Applicable Annexes:
  ✓ Annex I: High-risk AI systems (8 categories: biometric, critical infrastructure, etc)

Compliance Reasoning:
Safety-critical system (glass defect detection affects user safety).
Annex I applies (safety component in high-risk category).
Requires robust documentation (Article 13, 14) and risk management.
```

### School (Access Control)

| Attribute | Value |
|-----------|-------|
| **Risk Level** | HIGH |
| **Articles** | 6, 50, 14 |
| **Annexes** | Annex III |
| **Min Compliance** | 88% |

**Why:**
- Article 6: High-risk classification (affects vulnerable population)
- Article 50: Transparency (students/parents must know AI is making decisions)
- Article 14: Robustness documentation (education decisions affect minors' futures)
- Annex III: Education is explicitly listed as prohibited use without strict controls

**Audit Trail Example:**
```
Pilot: SCHOOL
Risk Level: HIGH

Applicable Articles:
  ✓ Article 6: High-risk AI classification and management
  ✓ Article 50: Transparency and disclosure obligations
  ✓ Article 14: Model cards and documentation for accuracy/robustness

Applicable Annexes:
  ✓ Annex III: Prohibited AI uses in employment, education, essential services

Compliance Reasoning:
Education access control affects minors and essential service.
Annex III applies (education). Requires transparency (Article 50),
risk mitigation (Article 6), and robustness documentation (Article 14).
```

---

## Usage Examples

### Example 1: Route a Hotel Credit Decision

```python
from smaos.l1_reasoning import PolicyRouter

router = PolicyRouter()

route = router.route_request(
    pilot_name="hotel",
    request_description="Credit scoring for guest financing",
    compliance_assessment=92,  # System passed compliance audit
)

print(f"Decision: {route.decision}")  # APPROVED
print(f"Articles: {route.articles}")  # ['Article 50', 'Article 51', 'Article 14']
print(route.audit_trail)

# Pass to L2 for policy enforcement
enforcement = router.enforce_policy(route)
print(f"Enforce level: {enforcement['enforcement_level']}")  # STRICT
```

### Example 2: Route a School Access Control Request

```python
router = PolicyRouter()

try:
    route = router.route_request(
        pilot_name="school",
        request_description="Student access control",
        compliance_assessment=75,  # Too low!
    )
except ValueError as e:
    print(f"Rejected: {e}")  # "compliance ≥80"
```

### Example 3: Query Available Articles

```python
router = PolicyRouter()

citation = router.cite_article("Article 50")
print(citation)  # "Article 50: Transparency and disclosure obligations"

citation = router.cite_annex("Annex I")
print(citation)  # "Annex I: High-risk AI systems..."
```

### Example 4: Audit Log All Decisions

```python
router = PolicyRouter()

router.route_request("hotel", "Credit check 1", 90)
router.route_request("glass", "Safety review", 85)
router.route_request("school", "Access control", 88)

all_routes = router.get_routes()
for route in all_routes:
    print(f"{route.pilot_name}: {route.decision} (score={route.compliance_score})")
```

---

## Integration with Other Layers

### L1 → L2 Flow
1. **L1 (PolicyRouter)** determines which Articles apply
2. **L2 (pgvector)** loads policy knowledge for those Articles
3. **L3 (PermitGates)** enforces the policies

```
Request → PolicyRouter.route_request()
              ↓
          PolicyRoute with articles=['Article 50', 'Article 51', ...]
              ↓
          L2: Load Article 50, 51 from pgvector
              ↓
          L3: Enforce permit gates for Articles 50, 51
              ↓
          Decision (APPROVED/DENIED)
```

### Vision API Integration (port 8000)
The router outputs PolicyRoute objects that can be serialized for Vision API:

```python
# In Vision API handler
from smaos.l1_reasoning import PolicyRouter

router = PolicyRouter()
route = router.route_request("glass", "Safety check", 92)

# Serialize for Vision API
response = {
    "route_id": route.route_id,
    "pilot": route.pilot_name,
    "articles": route.articles,
    "decision": route.decision,
    "enforcement_level": router.enforce_policy(route)["enforcement_level"],
}

return response  # Send to Vision API on port 8000
```

---

## Compliance Thresholds

| Pilot | Minimum Score | Reasoning |
|-------|---------------|-----------|
| Hotel | 90% | GPAI (Article 51) strict governance |
| Glass | 85% | Annex I (safety-critical) less flexible |
| School | 88% | Annex III (education) high stakes |

All require ≥80% base compliance (global minimum).

---

## Testing

Run test suite:

```bash
cd smaos/l1_reasoning
python -m pytest test_policy_router.py -v

# Or with coverage:
python -m pytest test_policy_router.py -v --cov=policy_router
```

**Test Categories:**
- `TestPolicyRouterBasics`: Core routing for all 3 pilots
- `TestPolicyValidation`: Input validation and constraints
- `TestAuditTrail`: Audit trail generation
- `TestArticleCitations`: Article/Annex lookup
- `TestPolicyEnforcement`: Enforcement metadata
- `TestAuditLog`: Route history tracking
- `TestCompliance`: Compliance threshold enforcement

**Coverage:** 11+ tests, targeting 100% code coverage.

---

## EU AI Act Reference

### Articles Referenced

- **Article 5:** Prohibited AI practices (behavioral manipulation, discrimination)
- **Article 6:** High-risk AI systems classification and requirements
- **Article 13:** Documentation and record-keeping for high-risk systems
- **Article 14:** Model cards and technical documentation
- **Article 50:** Transparency obligation to disclose AI involvement
- **Article 51:** General-Purpose AI (GPAI) governance requirements

### Annexes Referenced

- **Annex I:** List of high-risk AI systems (8 categories)
  - Examples: Biometric identification, critical infrastructure, safety components
- **Annex III:** List of prohibited AI practices
  - Examples: Employment decisions, education access, essential services discrimination

---

## Design WHYs

### 1. Why Policy-Bound Decisions?
Compliance must be enforced at decision time, not retroactively. If a request doesn't meet compliance thresholds, it fails immediately rather than creating audit liability later.

### 2. Why Different Thresholds per Pilot?
Risk varies:
- **Hotel (90%):** GPAI governance is strictest
- **Glass (85%):** Safety-critical but lower bar than GPAI
- **School (88%):** Education is sensitive but not GPAI-regulated

### 3. Why Audit Trail in PolicyRoute?
Article 14 requires "model cards" and documentation. The audit trail IS that documentation—human-readable explanation of which Articles apply and why.

### 4. Why Separate Articles and Annexes?
Articles describe obligations (what the system must do).
Annexes describe scope (when those obligations apply).
Separating them makes audit trail clearer.

---

## Next Steps

After L1 routes a decision:

1. **L2 Knowledge Layer:** Load Article-specific policies from pgvector
2. **L3 Permit Gates:** Apply enforcement rules based on Articles
3. **L4 Orchestration:** Execute the decision with policy constraints
4. **L8 Proof Layer:** Create immutable audit record in AP2 ledger

This creates an unbroken compliance chain from policy → decision → audit trail.

---

## Author

**Stream A: L1 Reasoning**
- Implementation: SMAOS Phase 1 (Sep 1, 2026)
- Lines: ~400 (policy_router.py + tests)
- Tests: 11+ covering all pilots and edge cases
- Status: Production-ready for KARP submission
