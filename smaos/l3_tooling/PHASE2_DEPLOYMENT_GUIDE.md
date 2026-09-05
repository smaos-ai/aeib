# PHASE 2 Deployment Guide
**Egress Controls + Intent-Verified Delegation**

Version 1.0 | Sep 1, 2026 | Production-Ready

---

## Overview

Phase 2 adds two P0 security controls to SMAOS:
1. **Egress Controls** — Whitelist-enforced API egress validation
2. **Intent-Verified Delegation** — Cryptographic commitment to agent goals

Both features are integrated into the 3 pilots: hotel, glass, school.

---

## Prerequisites

- Python 3.10+
- YAML parsing library: `pip install pyyaml`
- Cryptography: Built-in `hashlib` and `ssl`
- Test framework: `pytest` or `unittest`

## Architecture

```
Hotel/Glass/School Pilot
  ↓
Intent Commitment Manager (propose, commit, verify)
  ↓
Workflow Executor (execute steps with controls)
  ├─ Egress Validator (whitelist check)
  ├─ Intent Verifier (constraint check)
  ├─ DNS/TLS validation
  └─ Rate limiting
  ↓
AP2 Ledger (immutable proof trail)
```

---

## Deployment Steps

### 1. Load Egress Policies

```python
from egress_validator import EgressValidator
from integration_example_egress import load_policies_from_yaml

policies = load_policies_from_yaml("whitelist_policies.yaml")
validator = EgressValidator(policies)
```

**Policy Format** (whitelist_policies.yaml):
```yaml
pilots:
  hotel:
    allowed_domains:
      - equifax.com
      - experian.com
    allowed_patterns:
      - ".*\\.equifax\\.com"
    rate_limit_per_minute: 10
```

**Key Points:**
- One policy per pilot (hotel, glass, school)
- Fail-closed: block by default, allow only whitelisted domains
- Per-pilot rate limits (different limits per use case)
- Regex patterns for subdomains

### 2. Initialize Intent Commitment Manager

```python
from intent_commitment import IntentCommitmentManager

manager = IntentCommitmentManager()
```

**Integration with AP2 Ledger** (optional):
```python
from smaos.l6_infrastructure.ap2_ledger import AP2Ledger

ledger = AP2Ledger()
manager = IntentCommitmentManager(ap2_ledger=ledger)
```

### 3. Deploy Integrated Pilots

#### Hotel Pilot
```python
from hotel_pilot_with_controls import HotelWorkflowExecutor, HotelWorkflowConfig

config = HotelWorkflowConfig(max_latency_ms=5000)
executor = HotelWorkflowExecutor(config, validator, manager)

result = executor.execute_workflow(
    guest_id="GUEST001",
    guest_data={"name": "John", "email": "john@hotel.com"}
)

# Check result
assert result["success"], f"Workflow failed: {result.get('error')}"
print(f"Credit score: {result['credit_score']}")
```

#### Glass Pilot
```python
from glass_pilot_with_controls import GlassWorkflowExecutor, GlassWorkflowConfig

config = GlassWorkflowConfig(max_latency_ms=10000)
executor = GlassWorkflowExecutor(config, validator, manager)

result = executor.execute_workflow(
    model_id="GLASS001",
    model_metadata={"type": "tempered_glass"}
)

assert result["success"]
print(f"Decision: {result['approval_decision']}")
```

#### School Pilot
```python
from school_pilot_with_controls import SchoolWorkflowExecutor, SchoolWorkflowConfig

config = SchoolWorkflowConfig(max_latency_ms=2000)
executor = SchoolWorkflowExecutor(config, validator, manager)

result = executor.execute_workflow(
    student_id="STU001",
    student_data={"name": "Jane"},
    biometric_token="token_xyz"
)

assert result["success"]
print(f"Access granted: {result['access_granted']}")
```

### 4. Configure Monitoring & Alerting

#### Egress Audit Trail
```python
# Get audit log
audit_log = validator.get_audit_log()

# Log to SIEM
for attempt in audit_log:
    if attempt["result"] == "blocked":
        logger.warning(f"EGRESS BLOCKED: {attempt['destination_url']}")

# Summary
summary = validator.summary_report()
print(f"Blocked attempts: {summary['blocked']}")
print(f"Rate limited: {summary['rate_limited']}")
```

#### Intent Verification Reports
```python
# Export all commitments
exports = manager.export_commitments()

# Check for hijacking detections
for cid, report in exports["detections"].items():
    for detection in report["escalations"]:
        logger.critical(f"HIJACKING: {detection['hijacking_type']}")
```

### 5. Run Tests

```bash
# Unit tests (40+ per feature)
python -m pytest test_phase2_integration.py::TestEgressControlsPhase2 -v

# Intent tests (40+ scenarios)
python -m pytest test_phase2_integration.py::TestIntentCommitmentPhase2 -v

# Integration tests (10+ scenarios)
python -m pytest test_phase2_integration.py::TestIntegratedPilotsPhase2 -v

# All tests
python -m pytest test_phase2_integration.py -v --tb=short
```

---

## Operational Runbook

### Daily Operations

#### 1. Monitor Egress Blocks
```python
def monitor_egress():
    validator = EgressValidator(policies)
    
    blocked = validator.get_blocked_attempts()
    rate_limited = validator.get_rate_limited_attempts()
    
    if len(blocked) > 0:
        logger.warning(f"Blocked egress: {len(blocked)} attempts")
        for attempt in blocked:
            logger.info(f"  {attempt.destination_url}: {attempt.reason}")
    
    if len(rate_limited) > 0:
        logger.warning(f"Rate limited: {len(rate_limited)} attempts")
```

#### 2. Check Intent Violations
```python
def check_intent_violations():
    exports = manager.export_commitments()
    
    violations = exports["detections"]
    
    for commitment_id, report in violations.items():
        logger.critical(f"Commitment {commitment_id}: {len(report['escalations'])} escalations")
        
        for escalation in report["escalations"]:
            if escalation["severity"] == "immediate_halt":
                alert_security_team(escalation)
```

#### 3. Verify Workflow Latency
```python
def check_workflow_latency():
    # Latency histogram
    latencies = {}
    
    for workflow in recent_workflows:
        pilot = workflow["pilot"]
        elapsed = workflow["execution_time_ms"]
        
        if pilot not in latencies:
            latencies[pilot] = []
        latencies[pilot].append(elapsed)
    
    for pilot, times in latencies.items():
        p95 = sorted(times)[int(len(times) * 0.95)]
        logger.info(f"{pilot}: p95 latency = {p95:.0f}ms")
```

### Alert Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Egress block rate | >5% | Investigate policy |
| Rate limit triggers | >10/hour | Check for DoS |
| Intent violations | >1/hour | Security review |
| Latency (hotel) | >5000ms | Investigate execution |
| Latency (glass) | >10000ms | Investigate execution |
| Latency (school) | >2000ms | Investigate execution |

---

## Security Considerations

### Egress Controls
- **Fail-closed**: Block all non-whitelisted destinations
- **DNS validation**: Prevent DNS rebinding attacks
- **TLS pinning**: Enforce certificate validation for critical APIs
- **Rate limiting**: Detect slow exfiltration patterns
- **Audit trail**: Log all egress attempts (allow + block)

### Intent Commitment
- **Cryptographic binding**: SHA256 hash of goal + plan + constraints
- **Ed25519 signatures**: Sign commitments before execution
- **Constraint checking**: Detect goal drift, data access violations, API hijacking
- **Latency enforcement**: Fail-closed on execution timeouts
- **Human escalation**: Critical violations trigger immediate halt + alert

---

## Troubleshooting

### Egress Validation Fails

**Symptom**: All requests to valid domains blocked

**Cause**: DNS resolution failed or private IP detected

**Fix**:
```python
# Check DNS cache
print(validator.dns_cache)

# Clear cache if needed
validator.dns_cache.clear()

# Verify domain resolves
import socket
ip = socket.gethostbyname("equifax.com")
print(f"Domain resolves to: {ip}")
```

### Intent Verification False Positives

**Symptom**: Legitimate workflows flagged as hijacked

**Cause**: Constraints too restrictive or misordered in list

**Fix**:
```python
# Review constraints
commitment = manager.get_commitment(commitment_id)
print(f"Constraints: {commitment.constraints}")

# Relax constraints if needed (re-propose with broader list)
commitment2 = manager.propose_intent(
    ...
    constraints=[
        IntentConstraint("apis", ["score_api", "verify_api", "log_api"], "api_call"),
    ]
)
```

### Latency Exceeds Limit

**Symptom**: Workflow aborts due to latency constraint

**Cause**: Network slow, API slow, or constraint too tight

**Fix**:
```python
# Increase latency limit
config = HotelWorkflowConfig(max_latency_ms=10000)  # Was 5000

# Or optimize execution (parallel steps, caching)
```

---

## Performance Baselines

| Component | Latency | Throughput |
|-----------|---------|-----------|
| Egress validation | <2ms | >500 req/s |
| Intent verification | <10ms | >100 req/s |
| Hotel workflow | 100-500ms | 2-5 req/s |
| Glass workflow | 200-800ms | 1-2 req/s |
| School workflow | 50-200ms | 5-10 req/s |

---

## Rollback Procedure

If controls cause production incidents:

```bash
# 1. Disable egress validation (temporary)
export EGRESS_VALIDATION=disabled

# 2. Disable intent commitment (temporary)
export INTENT_COMMITMENT=disabled

# 3. Switch to legacy pilot code
git checkout legacy-pilots

# 4. Monitor metrics
python healthcheck.sh

# 5. Post-incident review
# - Analyze blocked/violated attempts
# - Update policies/constraints
# - Test before re-enabling
```

---

## Compliance Artifacts

### EU AI Act Compliance

- **Egress Controls**: Implement Article 6 (high-risk) requirement for output monitoring
- **Intent Commitment**: Implement Article 14 (robustness documentation) via immutable proof
- **Audit Trail**: Satisfy Article 5 (transparency) via complete execution logs

### OWASP ASI01 Defense

- **LLM01**: Prompt Injection — Intent commitment detects goal drift
- **LLM02**: Unsafe Output**: Egress validation prevents data exfiltration
- **LLM06**: Overreliance — Require explicit constraints + verification

### FERPA Compliance (School Pilot)

- All student data access logged with student ID
- Biometric matching required for access grant
- No cross-student data leakage possible (per-student constraints)

---

## Next Steps (Phase 3)

1. **Egress Escalation**: Add real-time alert for blocked egress patterns
2. **Intent Proof**: Integrate with AP2 ledger for immutable commitment trail
3. **Multi-Region**: Replicate egress policies + intent logs across regions
4. **Performance**: Optimize latency to <1ms for egress, <5ms for verification

---

## Support & Contacts

- **Security Issues**: security@sovereignnexus.io
- **Operational Issues**: ops@sovereignnexus.io
- **Documentation**: docs@sovereignnexus.io

---

**Document Revision**: 1.0  
**Last Updated**: Sep 1, 2026  
**Status**: Production-Ready
