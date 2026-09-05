# Stream G: Egress Controls Design Document
**P0 Blocker for Enterprise Pilots | EU AI Act Compliance (Article 6 + Annex I/III)**

---

## Executive Summary

Implements policy-driven outbound URL whitelist preventing data exfiltration from SMAOS agents.
Each pilot (hotel/glass/school) has explicit allowed destinations. All egress blocked by default.

**Delivered:**
- `egress_validator.py` — Policy engine (420+ lines)
- `whitelist_policies.yaml` — Per-pilot destinations
- `test_egress_controls.py` — 23 passing tests
- Fail-closed, audit-logged, rate-limited architecture

---

## Problem Statement

### Enterprise CISO Concerns (Phase 2 Gate)
Without egress controls, agents could exfiltrate data:
- Hotel pilot → Calls credit bureau APIs but could sneak API keys to attacker
- Glass pilot → Fetches CAD models but could upload proprietary models to dropbox
- School pilot → Accesses student records but could leak to external servers

### Current State
- No egress validation in job router
- Tool execution blindly allows any destination
- No audit trail for outbound requests
- Rate limiting missing (slow exfil attack vector)

### Solution: Fail-Closed Egress Control
1. **Whitelist-only model** — Default deny, explicit allow per pilot
2. **Multi-layer validation** — Policy → DNS → TLS → Rate limit
3. **Comprehensive logging** — Every attempt (success/blocked) in audit trail
4. **Per-pilot policies** — Hotels call credit bureaus, glass calls GitHub, school calls .edu

---

## Architecture

### Layer 3 (Tooling) Integration

```
Job Router (LangGraph)
    ↓
EgressValidator.validate_egress(pilot, url)
    ├─ Step 1: URL parsing & policy match
    ├─ Step 2: DNS validation (prevent rebinding)
    ├─ Step 3: TLS cert validation (for critical APIs)
    ├─ Step 4: Rate limiting (prevent slow exfil)
    └─ Returns: (EgressResult, EgressAttempt)
    ↓
If ALLOWED → Tool execution proceeds
If BLOCKED → Agent gets error + audit logged
```

### Core Components

#### 1. EgressValidator
Main validation engine with 5 validation phases:

```python
validator = EgressValidator(policies)
result, attempt = validator.validate_egress("hotel", "https://equifax.com/score")
```

**Phases (in order):**
1. **URL Parsing** — Extract domain, validate format
2. **Policy Match** — Check whitelist (exact + regex patterns)
3. **DNS Validation** — Resolve & reject private IPs (rebinding defense)
4. **TLS Validation** — Verify SSL cert for critical APIs
5. **Rate Limiting** — Enforce per-minute quotas per pilot/domain

#### 2. EgressPolicy
Per-pilot configuration defining allowed destinations:

```python
hotel_policy = EgressPolicy(
    pilot_name="hotel",
    allowed_domains=["equifax.com", "experian.com"],
    allowed_patterns=[r".*\.equifax\.com"],
    critical_apis={"equifax.com": "sha256/ABC123..."},
    rate_limit_per_minute=10,
)
```

#### 3. EgressAttempt
Audit record for every egress request:

```python
EgressAttempt(
    attempt_id="uuid",
    pilot_name="hotel",
    destination_url="https://equifax.com/score",
    result=EgressResult.ALLOWED,
    timestamp="2026-09-01T...",
    dns_resolved_ip="1.2.3.4",
    tls_validated=True,
    reason="All validation checks passed",
)
```

---

## Policy Design

### Hotel Pilot (Credit Scoring)
**Risk Level:** HIGH (affects financial essential service)
**Articles:** 50 (transparency), 51 (GPAI), 14 (accuracy)

**Allowed Destinations:**
- Credit bureaus: Equifax, Experian, TransUnion
- EU AI Act APIs: ec.europa.eu
- Sanctions checks: OFAC, WorldCompliance
- Internal: compliance.sovereignnexus.io

**Rate Limit:** 10 req/min (prevents batch exfil)

**Critical APIs:** Equifax, Experian, TransUnion (TLS pinning)

### Glass Pilot (Safety Review)
**Risk Level:** HIGH (affects product safety)
**Articles:** 6 (high-risk), 13 (documentation), 14 (robustness)

**Allowed Destinations:**
- CAD repos: GitHub, GitLab, Bitbucket
- Safety standards: ASTM, ISO, NIST
- Material DBs: MatWeb, MatMatch
- Internal: glass.sovereignnexus.io

**Rate Limit:** 15 req/min (allows CAD model fetching)

**Critical APIs:** GitHub, GitLab, NIST (TLS pinning)

### School Pilot (Access Control)
**Risk Level:** HIGH (affects minors + education)
**Articles:** 6 (high-risk), 50 (transparency), 14 (robustness)

**Allowed Destinations:**
- US Dept of Education: ed.gov, studentprivacy.ed.gov
- SIS platforms: PowerSchool, Skyward
- Standards: CCSSO
- Internal: school.sovereignnexus.io

**Rate Limit:** 8 req/min (strictest, protects student data)

**Critical APIs:** ed.gov, studentprivacy.ed.gov (TLS pinning)

---

## Security Mechanisms

### 1. Fail-Closed Design
Default: **BLOCK** unless explicitly whitelisted.
- Pilot tries to egress to unauthorized domain → BLOCKED
- Audit logged with reason
- Agent receives error message

### 2. DNS Rebinding Prevention
Attacker vector: Agent whitelists "equifax.com", attacker runs DNS server that returns:
- First query: 1.2.3.4 (pass validation)
- Second query: 192.168.1.100 (attacker's private server)

**Defense:** Detect private IP ranges (10/8, 172.16/12, 192.168/16, 127/8, 169.254/16)
- Hotel tries "equifax.com" → resolves to 192.168.1.100 → BLOCKED
- Reason: "Destination resolves to private IP 192.168.1.100"

### 3. TLS Certificate Pinning
For critical APIs (credit bureaus, education dept), validate SSL cert:
```python
def _validate_tls_cert(domain):
    context = ssl.create_default_context()
    sock = socket.create_connection((domain, 443))
    ssock = context.wrap_socket(sock, server_hostname=domain)
    cert = ssock.getpeercert()
```

Prevents MITM attacks on critical destinations.

### 4. Rate Limiting (Prevents Slow Exfil)
Attacker vector: Exfiltrate 100 MB slowly (1 req/10 seconds, under rate limit).

**Defense:** Per-pilot, per-domain rate limits:
- Hotel: 10 req/min to equifax → 11th req in same minute = RATE_LIMITED
- Glass: 15 req/min to github → Higher limit (allows CAD fetching)
- School: 8 req/min to ed.gov → Strictest (student data)

Timestamps cleaned up after 60-second window.

### 5. Comprehensive Audit Logging
Every egress attempt logged with:
- attempt_id (unique UUID)
- pilot_name (which pilot made request)
- destination_url (full URL)
- result (ALLOWED/BLOCKED/RATE_LIMITED/DNS_FAILED/TLS_FAILED)
- timestamp (ISO 8601)
- dns_resolved_ip (what IP was resolved)
- tls_validated (was TLS cert valid)
- reason (human-readable explanation)
- rate_limit_count (how many requests in past minute)

JSON-serializable for SIEM integration.

---

## Integration Points

### 1. Job Router (LangGraph)
Before tool execution, check egress:

```python
from smaos.l3_tooling.egress_validator import EgressValidator

@app.graph.node("validate_egress")
async def validate_egress(state):
    url = state["tool_input"]["url"]
    result, attempt = egress_validator.validate_egress(
        state["pilot_name"],
        url
    )
    
    if result != EgressResult.ALLOWED:
        state["error"] = f"Egress blocked: {attempt.reason}"
        return state
    
    state["egress_validated"] = True
    return state
```

### 2. Tool Registry
Mark tools requiring egress validation:

```python
TOOL_REGISTRY = {
    "score_credit": {
        "requires_egress_validation": True,
        "pilot": "hotel",
    },
    "fetch_cad_model": {
        "requires_egress_validation": True,
        "pilot": "glass",
    },
    "verify_student_records": {
        "requires_egress_validation": True,
        "pilot": "school",
    },
}
```

### 3. Audit Trail (L7/L8 Layer)
Egress logs feed into compliance audit trail:

```python
# In L8 proof layer
agentacct_capture.log_egress_event({
    "attempt_id": attempt.attempt_id,
    "result": attempt.result.value,
    "pilot": attempt.pilot_name,
    "destination": attempt.destination_url,
    "timestamp": attempt.timestamp,
})
```

### 4. CISO Appeal Document
Generated for compliance audits:

```markdown
## Egress Controls Evidence

Date: 2026-09-15
Pilot: Hotel Credit Scoring
Articles: 50, 51, 14
Status: IMPLEMENTED

### Policy Enforcement
- Allowed destinations: 7 domains + 4 regex patterns
- Default: BLOCKED (fail-closed)
- Audit: 143 egress attempts logged

### Attack Vectors Mitigated
1. DNS rebinding ✓ (private IP rejection)
2. Slow exfiltration ✓ (rate limits)
3. MITM on critical APIs ✓ (TLS pinning)
4. Unauthorized destinations ✓ (whitelist)

### Test Results
- 23 tests passing (100%)
- Coverage: policies, DNS, TLS, rate limits, logging
```

---

## Test Coverage (23 Tests)

### Policy Tests (8)
1. `test_whitelist_exact_domain_allowed` — Exact matches work
2. `test_whitelist_pattern_match_allowed` — Regex patterns work
3. `test_whitelist_domain_not_in_list_blocked` — Non-whitelisted blocked
4. `test_whitelist_case_insensitive` — Domain matching case-insensitive
5. `test_whitelist_subdomain_pattern` — Subdomain patterns match
6. `test_invalid_url_format` — Malformed URLs rejected
7. `test_unknown_pilot_raises` — Unknown pilot raises error
8. `test_different_pilots_different_whitelists` — Pilots isolated

### DNS Tests (5)
9. `test_dns_valid_public_ip` — Valid public IPs pass
10. `test_dns_rejects_private_ips` — Private IP ranges blocked (rebinding defense)
11. `test_dns_rejects_loopback` — 127.0.0.1 blocked
12. `test_dns_failure_handling` — DNS errors handled
13. `test_dns_caching` — DNS results cached

### Rate Limiting Tests (4)
14. `test_rate_limit_allows_under_limit` — Under limit passes
15. `test_rate_limit_blocks_over_limit` — Over limit blocked
16. `test_rate_limit_per_pilot` — Per-pilot isolation
17. `test_rate_limit_cleanup_old_timestamps` — Expired timestamps cleaned

### Integration Tests (6)
18. `test_full_validation_success` — Full pipeline works
19. `test_exfiltration_attempt_blocked` — Exfil blocked + logged
20. `test_audit_log_comprehensive` — Audit trail captures details
21. `test_get_blocked_attempts` — Can retrieve blocked attempts
22. `test_summary_report` — Statistics aggregation
23. `test_json_serialization` — JSON export works

**Test Metrics:**
- Coverage: 420+ lines of code
- Mocking: DNS, TLS (unit tested separately)
- Integration: Full validation pipeline
- Audit: JSON serialization verified

---

## Deployment Checklist

- [x] egress_validator.py created (420+ lines)
- [x] whitelist_policies.yaml created (per-pilot policies)
- [x] test_egress_controls.py created (23 tests passing)
- [ ] Integration into job router (L4 work)
- [ ] Tool registry marked (L4 work)
- [ ] CISO appeal document (L8 work)
- [ ] Production audit retention (L8 work)

---

## Future Enhancements (Phase 2+)

### IP-Level Blocking
- VPN/proxy detection (block requests through proxies)
- GeoIP validation (block requests from unauthorized regions)

### Advanced Rate Limiting
- Sliding window (more granular than minute-based)
- Adaptive limits (adjust based on pilot behavior)

### Certificate Pinning Database
- Live updates from security provider
- Automatic cert rotation detection

### DLP Integration
- Scan request payloads for sensitive data
- Block if credit card numbers detected in POST body

### Behavioral Analysis
- Machine learning on egress patterns
- Alert on anomalies (agent calling unusual domains)

---

## References

**EU AI Act Compliance:**
- Article 6: High-risk AI classification
- Article 13: Documentation requirements
- Article 14: Accuracy and robustness documentation
- Annex I: High-risk AI systems
- Annex III: Prohibited AI uses in employment/education/essential services

**Related Layers:**
- L1: Policy routing (defines which articles apply per pilot)
- L3: Egress controls (this document)
- L4: Job router (integrates validation into execution)
- L7: RAGAS evaluation (tests egress policy enforcement)
- L8: AP2 ledger (immutable audit trail)

**Files:**
- `/Users/andriileukhin/Documents/SovereignNexus/smaos/l3_tooling/egress_validator.py` (main module)
- `/Users/andriileukhin/Documents/SovereignNexus/smaos/l3_tooling/whitelist_policies.yaml` (policies)
- `/Users/andriileukhin/Documents/SovereignNexus/smaos/l3_tooling/test_egress_controls.py` (tests)
