# PHASE 2A: Integration Guide
## Merging Intent Verification + Egress Controls (Weeks 7-8)

**Timeline:** Jul 1 - Jul 14, 2027 (2 weeks, final integration & deployment)  
**Owner:** Solo engineer  
**Success Criteria:** 250+ combined tests passing, zero regressions in Phase 1 pilots  
**Integration Path:** L1 → L3B → L5A → L5B → L5C → L8

---

## 1. EXECUTIVE SUMMARY

Phase 2A delivers two independent modules (Intent Verification, Egress Controls) in parallel (Weeks 1-6). **Integration Phase (Weeks 7-8)** merges both into the L1-L8 harness with zero regressions.

**Key Integration Points:**
- **L3B ↔ L1:** Intent commitment before tool execution
- **L5A ↔ L3:** Policy gate after tool selection, before egress
- **L5B/L5C ↔ L4:** Rate limiting + kernel enforcement at socket layer
- **Both ↔ L8:** Audit trail (immutable proof)

**Testing Strategy:**
1. **Unit tests** (200 existing + 50 new): isolated modules
2. **Integration tests** (100 new): module pairs (L3B↔L1, L5A↔L3, etc.)
3. **Adversarial tests** (20 new): known attack patterns
4. **Compliance tests** (20 new): regulatory requirements (GDPR, AI Act)
5. **Regression tests** (200): Phase 1 pilots (hotel, glass, school)
6. **Load tests** (10 new): 100 concurrent agents, 10k req/sec

**Total: 590 tests, target 100% pass rate**

---

## 2. MODULE DEPENDENCY GRAPH

```
┌────────────────────────────────────────────────────────────────┐
│                        L1: Reasoning                           │
│  (Claude SDK policy routing + intent statement generation)    │
│  ↓ (generates intent JSON, calls generate_cic)                │
├────────────────────────────────────────────────────────────────┤
│                   L3: Permit Gates                             │
│  ├─ L3A: Tool Registry (existing)                             │
│  └─ L3B: Intent Commitment Validator (NEW)                    │
│      (verifies CIC before any tool execution)                 │
│  ↓ (tool allowed; intent committed)                          │
├────────────────────────────────────────────────────────────────┤
│                 L4: Orchestration                              │
│  (LangGraph orchestrates tool execution)                      │
│  ↓ (tool invokes network call)                                │
├────────────────────────────────────────────────────────────────┤
│                L5: Communication                               │
│  ├─ L5A: Policy Gate (DNS, DNSSEC, whitelisting) (NEW)        │
│  ├─ L5B: Encryption & Rate Limiting (NEW)                     │
│  └─ L5C: Kernel Enforcement (iptables, cgroup, seccomp)       │
│      (validates egress, enforces rate limits, blocks SSRF)   │
│  ↓ (socket layer, actual network)                             │
├────────────────────────────────────────────────────────────────┤
│                  L8: Proof Layer                               │
│  (AP2 ledger + KMS: intent CIC + egress audit log)           │
│  ↓ (immutable record of all decisions)                        │
└────────────────────────────────────────────────────────────────┘
```

### 2.1 Data Flow (Request → Response)

```
User Intent
  ↓
[L1] Parse intent JSON
  ↓
[L1] Call L3B: generate_cic(intent_json)
  ↓
[L3B] Generate Ed25519 signature → return CIC
  ↓
[L3A] Tool selected (from L1 reasoning)
  ↓
[L3B] Call verify_intent_commitment(CIC, intent_json)
  ↓ NO: log denial → return error
  ↓ YES: proceed
  ↓
[L4] Execute tool (e.g., score_credit)
  ↓
[L4] Tool makes HTTP call to 'api.stripe.com:443'
  ↓
[L5A] Policy Gate: is 'api.stripe.com' whitelisted?
  ↓ NO: drop → return error
  ↓ YES: continue
  ↓
[L5A] Resolve 'api.stripe.com' → '18.216.1.100'
  ↓
[L5A] Verify DNSSEC signature
  ↓ INVALID: deny → return error
  ↓ VALID: continue
  ↓
[L5B] TLS check: cert pinning valid?
  ↓ NO: drop connection
  ↓ YES: continue
  ↓
[L5B] Rate limit check: agent within quota?
  ↓ NO: drop request, return 429
  ↓ YES: consume quota
  ↓
[L5C] Kernel layer: iptables rule matches?
  ↓ NO: DROP (packet lost)
  ↓ YES: forward to socket
  ↓
[Socket] Network egress (TLS 1.3)
  ↓
[Tool] Receives response, processes data
  ↓
[L5B] Log egress event: bytes_sent, duration
  ↓
[L8] Append to AP2 ledger: CIC + egress audit record
  ↓
[Response] Return to L1 (execution complete)
```

---

## 3. MODULE PSEUDO-CODE INTEGRATION

### 3.1 L1 ↔ L3B: Intent Commitment

```python
# smaos/l1_reasoning.py (Reasoning Layer)

from smaos.l3_permit_gates import IntentCommitmentValidator
from smaos.l8_proof import AP2Ledger

class ReasoningEngine:
    def __init__(self):
        self.intent_validator = IntentCommitmentValidator()
        self.ap2_ledger = AP2Ledger()
    
    def plan_and_execute(self, user_intent: str):
        """
        Plan execution and get intent commitment.
        """
        # Step 1: Parse intent into JSON
        intent_json = self._parse_intent(user_intent)
        # {
        #   'requestor_id': 'alice@org.tld',
        #   'intent_statement': 'Score credit for user 123',
        #   'scope': {'tools': ['score_credit'], ...},
        #   'delegation_chain': [],
        #   'expires_at': '...'
        # }
        
        # Step 2: Get requestor's private key (from KMS)
        requestor_privkey = self._get_requestor_privkey()
        
        # Step 3: Generate Intent Commitment
        cic = self.intent_validator.generate_cic(
            intent_json=intent_json,
            requestor_privkey=requestor_privkey
        )
        # {
        #   'commitment_id': 'uuid-...',
        #   'signature': 'ed25519-sig...',
        #   'proof_anchor': 'ap2-ledger-tx-hash',
        #   'expires_at': '...'
        # }
        
        # Step 4: Log intent commitment to AP2 ledger
        self.ap2_ledger.append({
            'event_type': 'intent_commitment_issued',
            'commitment_id': cic['commitment_id'],
            'intent_statement': intent_json['intent_statement'],
            'requestor_id': intent_json['requestor_id'],
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Step 5: Verify intent commitment (early gate)
        if not self.intent_validator.verify_intent_commitment(
            cic=cic,
            intent_json=intent_json,
            requestor_pubkey=requestor_privkey.public_key
        ):
            log_error(f"Intent commitment verification failed: {cic['commitment_id']}")
            return {'status': 'denied', 'reason': 'invalid_intent_commitment'}
        
        # Step 6: Use CIC to inform tool selection
        # (If intent was hijacked, tools outside scope are filtered)
        tools_in_scope = self._get_tools_in_scope(intent_json)
        
        # Step 7: Orchestrate (L4 calls tools with CIC attached)
        result = self._orchestrate_tools(
            tools=tools_in_scope,
            intent_commitment_id=cic['commitment_id'],
            user_intent=user_intent
        )
        
        return {
            'status': 'completed',
            'commitment_id': cic['commitment_id'],
            'result': result
        }
    
    def _get_tools_in_scope(self, intent_json: dict) -> List[str]:
        """Extract tools from intent scope."""
        return intent_json['scope']['tools']
    
    def _orchestrate_tools(self, tools: List[str], 
                          intent_commitment_id: str, 
                          user_intent: str):
        """Delegate to L4 Orchestration with CIC context."""
        from smaos.l4_orchestration import Orchestrator
        
        orchestrator = Orchestrator()
        return orchestrator.execute(
            tools=tools,
            intent_commitment_id=intent_commitment_id,
            user_intent=user_intent
        )
```

### 3.2 L4 ↔ L5A: Policy Gate Before Egress

```python
# smaos/l4_orchestration.py (Orchestration Layer)

from smaos.l5_communication import EgressPolicyGate, RateLimiter
from smaos.l8_proof import AP2Ledger

class Orchestrator:
    def __init__(self):
        self.egress_gate = EgressPolicyGate()  # L5A
        self.rate_limiter = RateLimiter()       # L5B
        self.ap2_ledger = AP2Ledger()          # L8
    
    def execute(self, tools: List[str], 
                intent_commitment_id: str,
                user_intent: str) -> dict:
        """
        Execute tools with egress controls.
        """
        results = {}
        
        for tool_name in tools:
            tool = self._get_tool(tool_name)
            
            # Wrap tool execution with egress monitoring
            result = self._execute_tool_with_egress_controls(
                tool=tool,
                intent_commitment_id=intent_commitment_id,
                user_intent=user_intent
            )
            
            results[tool_name] = result
        
        return results
    
    def _execute_tool_with_egress_controls(self, tool, 
                                           intent_commitment_id: str,
                                           user_intent: str):
        """
        Execute tool with L5A (Policy) + L5B (Rate) + L5C (Kernel).
        """
        agent_id = self._get_agent_id()
        
        # Hook tool's HTTP/gRPC calls
        # (Monkey-patch requests.get, etc.)
        
        original_request = requests.request
        
        def monitored_request(method: str, url: str, **kwargs):
            # Parse destination
            parsed = urllib.parse.urlparse(url)
            hostname = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            
            # L5A: Check egress policy
            policy_result = self.egress_gate.check_egress(
                destination=hostname,
                port=port,
                protocol=parsed.scheme,
                agent_id=agent_id
            )
            
            if not policy_result.allowed:
                log_warning(
                    f"Egress denied: {agent_id} → {hostname}:{port} "
                    f"({policy_result.reason})"
                )
                self.ap2_ledger.append({
                    'event_type': 'egress_denied',
                    'agent_id': agent_id,
                    'destination': f"{hostname}:{port}",
                    'reason': policy_result.reason,
                    'intent_commitment_id': intent_commitment_id,
                    'timestamp': datetime.utcnow().isoformat()
                })
                raise PermissionError(f"Egress denied: {policy_result.reason}")
            
            # L5B: Check rate limits
            # Estimate request size
            body_size = len(json.dumps(kwargs.get('json', {})))
            
            rate_result = self.rate_limiter.check_rate_limit(
                destination=hostname,
                agent_id=agent_id,
                bytes_to_send=body_size
            )
            
            if not rate_result.allowed:
                log_warning(
                    f"Rate limit exceeded: {agent_id} → {hostname} "
                    f"({rate_result.reason})"
                )
                self.ap2_ledger.append({
                    'event_type': 'rate_limit_exceeded',
                    'agent_id': agent_id,
                    'destination': hostname,
                    'reason': rate_result.reason,
                    'intent_commitment_id': intent_commitment_id
                })
                raise OverflowError(f"Rate limit exceeded: {rate_result.reason}")
            
            # L5C: Kernel enforcement (iptables) will drop if not whitelisted
            # (This happens at OS level, but we log the allowed attempt)
            
            # Proceed with original request
            start_time = time.time()
            try:
                response = original_request(method, url, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                response_size = len(response.content)
                
                # Log egress event
                self.ap2_ledger.append({
                    'event_type': 'egress_allowed',
                    'agent_id': agent_id,
                    'destination': f"{hostname}:{port}",
                    'method': method,
                    'status_code': response.status_code,
                    'bytes_sent': body_size,
                    'bytes_received': response_size,
                    'duration_ms': duration_ms,
                    'intent_commitment_id': intent_commitment_id,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                return response
                
            except Exception as e:
                log_error(f"Egress request failed: {hostname} ({e})")
                self.ap2_ledger.append({
                    'event_type': 'egress_error',
                    'agent_id': agent_id,
                    'destination': f"{hostname}:{port}",
                    'error': str(e),
                    'intent_commitment_id': intent_commitment_id
                })
                raise
        
        # Monkey-patch
        requests.request = monitored_request
        
        try:
            # Execute actual tool
            result = tool.execute()
            return {'status': 'success', 'result': result}
        
        except PermissionError as e:
            return {'status': 'denied', 'reason': str(e)}
        except OverflowError as e:
            return {'status': 'rate_limited', 'reason': str(e)}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
        
        finally:
            # Restore original
            requests.request = original_request
```

### 3.3 L5 ↔ L8: Egress Audit Trail

```python
# smaos/l5_communication.py (Communication Layer)

from smaos.l8_proof import AP2Ledger

class EgressPolicyGate:
    def __init__(self):
        self.ap2_ledger = AP2Ledger()
    
    def check_egress(self, destination: str, port: int, 
                     protocol: str, agent_id: str) -> EgressResult:
        """
        Check if egress is allowed.
        Log all decisions to AP2 ledger.
        """
        result = self._check_policy(destination, port, protocol, agent_id)
        
        # Log to AP2 ledger (immutable proof)
        audit_entry = {
            'event_type': 'egress_decision',
            'agent_id': agent_id,
            'destination': f"{destination}:{port}",
            'protocol': protocol,
            'allowed': result.allowed,
            'policy_matched': result.policy_id,
            'reason': result.reason if not result.allowed else None,
            'timestamp': datetime.utcnow().isoformat(),
            'proof_hash': hashlib.sha256(
                json.dumps(result.to_dict(), sort_keys=True).encode()
            ).hexdigest()
        }
        
        self.ap2_ledger.append(audit_entry)
        
        return result
    
    def _check_policy(self, destination: str, port: int,
                      protocol: str, agent_id: str) -> EgressResult:
        """
        Actual policy checking logic.
        (Resolve DNS, check DNSSEC, etc.)
        """
        # Load policy
        policy = self.load_policy()
        
        # Find matching destination
        matched_dest = None
        for dest in policy['destinations']:
            if not dest['enabled']:
                continue
            
            # Match by hostname or IP
            if self._matches_destination(destination, dest):
                matched_dest = dest
                break
        
        if not matched_dest:
            return EgressResult(
                allowed=False,
                reason='destination_not_whitelisted',
                policy_id=None
            )
        
        # Check port
        if port not in matched_dest['ports']:
            return EgressResult(
                allowed=False,
                reason='port_not_allowed',
                policy_id=matched_dest['id']
            )
        
        # Check protocol
        if protocol not in matched_dest['protocols']:
            return EgressResult(
                allowed=False,
                reason='protocol_not_allowed',
                policy_id=matched_dest['id']
            )
        
        # DNS resolution + DNSSEC
        try:
            resolved_ips = self.resolver.resolve(destination)
            
            # Verify IPs match policy
            if not self._ips_match_policy(resolved_ips, matched_dest):
                return EgressResult(
                    allowed=False,
                    reason='resolved_ip_mismatch',
                    policy_id=matched_dest['id']
                )
            
            # Verify DNSSEC (if required)
            if matched_dest.get('dns', {}).get('require_dnssec'):
                if not self.dnssec_validator.validate(destination):
                    return EgressResult(
                        allowed=False,
                        reason='dnssec_validation_failed',
                        policy_id=matched_dest['id']
                    )
        
        except Exception as e:
            log_error(f"DNS resolution error: {destination} ({e})")
            return EgressResult(
                allowed=False,
                reason='dns_resolution_error',
                policy_id=matched_dest['id']
            )
        
        # All checks passed
        return EgressResult(
            allowed=True,
            policy_id=matched_dest['id']
        )
```

### 3.4 Both Modules ↔ L8: Immutable Proof

```python
# smaos/l8_proof.py (Proof Layer)

from smaos.ap2_ledger import AP2Ledger
from smaos.kms import KMS

class ProofLayer:
    def __init__(self):
        self.ap2_ledger = AP2Ledger()
        self.kms = KMS()
    
    def log_intent_commitment(self, cic: dict, intent_json: dict):
        """Log intent commitment to immutable ledger."""
        entry = {
            'event_type': 'intent_commitment_issued',
            'commitment_id': cic['commitment_id'],
            'signature': cic['signature'],
            'proof_anchor': cic['proof_anchor'],
            'intent_hash': hashlib.sha256(
                json.dumps(intent_json, sort_keys=True).encode()
            ).hexdigest(),
            'requestor_id': intent_json['requestor_id'],
            'expires_at': intent_json['expires_at'],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Append to AP2 ledger
        tx_hash = self.ap2_ledger.append(entry)
        
        # Sign with KMS (immutable)
        entry['kms_signature'] = self.kms.sign_ed25519(
            json.dumps(entry, sort_keys=True)
        )
        
        return tx_hash
    
    def log_egress_decision(self, 
                           agent_id: str,
                           destination: str,
                           allowed: bool,
                           policy_id: str,
                           reason: Optional[str]):
        """Log egress decision to immutable ledger."""
        entry = {
            'event_type': 'egress_decision',
            'agent_id': agent_id,
            'destination': destination,
            'allowed': allowed,
            'policy_matched': policy_id,
            'denial_reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Append to AP2 ledger
        tx_hash = self.ap2_ledger.append(entry)
        
        # Sign with KMS
        entry['kms_signature'] = self.kms.sign_ed25519(
            json.dumps(entry, sort_keys=True)
        )
        
        return tx_hash
    
    def generate_compliance_report(self, 
                                   start_date: datetime,
                                   end_date: datetime) -> dict:
        """
        Generate regulatory compliance report.
        Pulled from immutable AP2 ledger.
        """
        # Query ledger for all events in date range
        intent_events = self.ap2_ledger.query(
            event_type='intent_commitment_issued',
            start_date=start_date,
            end_date=end_date
        )
        
        egress_events = self.ap2_ledger.query(
            event_type='egress_decision',
            start_date=start_date,
            end_date=end_date
        )
        
        # Compute stats
        total_intents = len(intent_events)
        total_egress = len(egress_events)
        egress_allowed = sum(1 for e in egress_events if e['allowed'])
        egress_denied = total_egress - egress_allowed
        
        return {
            'period': f"{start_date} - {end_date}",
            'total_intents_committed': total_intents,
            'total_egress_decisions': total_egress,
            'egress_allowed_count': egress_allowed,
            'egress_denied_count': egress_denied,
            'egress_denial_rate': egress_denied / total_egress if total_egress > 0 else 0,
            'top_denial_reasons': self._compute_denial_stats(egress_events),
            'kms_signatures_verified': self._verify_all_kms_sigs(intent_events + egress_events),
            'ap2_ledger_intact': self.ap2_ledger.verify_integrity()
        }
    
    def _compute_denial_stats(self, egress_events: list) -> dict:
        """Compute top denial reasons."""
        denials = [e for e in egress_events if not e['allowed']]
        reasons = {}
        for denial in denials:
            reason = denial.get('denial_reason')
            reasons[reason] = reasons.get(reason, 0) + 1
        return sorted(reasons.items(), key=lambda x: x[1], reverse=True)
    
    def _verify_all_kms_sigs(self, events: list) -> bool:
        """Verify all KMS signatures."""
        for event in events:
            if not self.kms.verify_ed25519(
                event.get('kms_signature'),
                json.dumps({k: v for k, v in event.items() 
                           if k != 'kms_signature'}, sort_keys=True)
            ):
                return False
        return True
```

---

## 4. TEST ORCHESTRATION STRATEGY

### 4.1 Test Pyramid (590 tests total)

```
                    Compliance Tests (20)
                    Adversarial Tests (20)
                    Load Tests (10)
              ___________________________
             |   Integration Tests (100)  |
         ____|____________________________|____
        |        Unit Tests (250)              |
        |   (Phase 1: 200 + Phase 2A: 50)    |
        |__________________________________|
             Regression Tests (200)
                (Phase 1 pilots)
```

### 4.2 Test Execution Plan

#### Phase 1: Unit Tests (Days 1-2)
```bash
# L3B Intent Commitment tests
pytest tests/l3_intent_commitment/test_cic_generation.py -v
pytest tests/l3_intent_commitment/test_cic_verification.py -v
pytest tests/l3_intent_commitment/test_delegation_chain.py -v
# → 20 tests, expect <2 sec total

# L5A Policy Gate tests
pytest tests/l5_policy_gate/test_dns_resolution.py -v
pytest tests/l5_policy_gate/test_dnssec_validation.py -v
pytest tests/l5_policy_gate/test_whitelist_matching.py -v
# → 15 tests, expect <5 sec total

# L5B Rate Limiter tests
pytest tests/l5_rate_limiter/test_sliding_window.py -v
pytest tests/l5_rate_limiter/test_quota_enforcement.py -v
# → 10 tests, expect <2 sec total

# L5C Kernel tests (mock only; real tests in staging)
pytest tests/l5_kernel/test_iptables_rules.py -v
pytest tests/l5_kernel/test_seccomp_filter.py -v
# → 5 tests, expect <1 sec total
```

#### Phase 2: Integration Tests (Days 3-4)
```bash
# L1 ↔ L3B: Intent commitment flow
pytest tests/integration/test_l1_l3b_intent_flow.py -v
# → 10 tests

# L3A ↔ L3B: Tool registry + intent commitment
pytest tests/integration/test_l3a_l3b_tool_selection.py -v
# → 8 tests

# L4 ↔ L5A/L5B: Tool execution with egress controls
pytest tests/integration/test_l4_l5_egress_monitoring.py -v
# → 20 tests

# L5A ↔ L5C: Policy gate + kernel enforcement
pytest tests/integration/test_l5a_l5c_policy_kernel.py -v
# → 15 tests

# Both ↔ L8: Proof layer integration
pytest tests/integration/test_l8_proof_logging.py -v
# → 25 tests
```

#### Phase 3: Adversarial Tests (Day 5)
```bash
# Attack scenarios from OWASP ASI01 + egress threats
pytest tests/adversarial/test_intent_hijacking.py -v
# → 5 tests (goal-hijacking, Byzantine delegation, etc.)

pytest tests/adversarial/test_egress_attacks.py -v
# → 10 tests (DNS rebinding, SSRF, IPv6 escape, TOCTOU, etc.)

pytest tests/adversarial/test_combined_attacks.py -v
# → 5 tests (simultaneous intent hijacking + egress exploit)
```

#### Phase 4: Compliance Tests (Day 5-6)
```bash
# GDPR compliance
pytest tests/compliance/test_gdpr_audit_trail.py -v
# → 5 tests

# EU AI Act
pytest tests/compliance/test_ai_act_transparency.py -v
# → 5 tests

# OWASP ASI01
pytest tests/compliance/test_owasp_asi01_defense.py -v
# → 10 tests
```

#### Phase 5: Regression Tests (Days 6-7)
```bash
# Run Phase 1 pilot tests
pytest tests/pilots/test_hotel_scoring_l1_l8.py -v
pytest tests/pilots/test_glass_ml_l1_l8.py -v
pytest tests/pilots/test_school_reporting_l1_l8.py -v
# → 200 tests (existing), expect zero failures
```

#### Phase 6: Load Tests (Day 7)
```bash
# 100 concurrent agents, 10k req/sec
pytest tests/load/test_concurrent_agents.py -v --workers=10
pytest tests/load/test_high_throughput.py -v
# → 10 tests
```

### 4.3 Test Failure Recovery

If any test fails, **do not proceed** to next phase:

```python
def test_failure_recovery():
    """
    Test failure → investigate → fix → re-run affected tests.
    """
    
    # Example: L3B.verify_intent_commitment returns False unexpectedly
    
    # Step 1: Isolate failure
    # - Run single test in debug mode
    # - Check stack trace
    
    # Step 2: Root cause
    # - Check: signature verification? delegation chain? time-lock?
    
    # Step 3: Fix
    # - Modify L3B or L1 code
    # - Add unit test to catch regression
    
    # Step 4: Re-run
    # - Re-run affected test + all dependent tests
    # - Re-run full integration suite
    
    # Step 5: Continue
    # - Proceed to next test phase only if 100% pass
```

---

## 5. DEPLOYMENT SEQUENCE (Weeks 7-8)

### Week 7 (Jul 1-7): Integration on Staging

```
Day 1 (Jul 1):
  - Deploy L3B + L5A/B/C to staging VPC
  - Configure egress_policy.yaml (whitelist Stripe, internal DB, etc.)
  - Run unit tests (590 tests)
  ✓ Target: 580+ passing

Day 2 (Jul 2):
  - Deploy iptables rules (L5C1)
  - Deploy cgroup rules (L5C2)
  - Deploy seccomp filter (L5C3)
  - Test kernel enforcement (egress to 127.0.0.1 drops)
  ✓ Target: 0 iptables rule failures

Day 3-4 (Jul 3-4):
  - Run integration tests (100 tests)
  - Test L1 ↔ L3B → L4 ↔ L5A/B ↔ L8 flow
  - Fix any issues
  ✓ Target: 100+ passing

Day 5 (Jul 5):
  - Run adversarial tests (20 tests)
  - Verify: no DNS rebinding, no SSRF, no lateral movement
  ✓ Target: 20+ passing, 0 bypasses

Day 6 (Jul 6):
  - Run compliance tests (20 tests)
  - Generate audit reports from AP2 ledger
  - Verify GDPR/AI Act alignment
  ✓ Target: 20+ passing

Day 7 (Jul 7):
  - Run regression tests (200 existing Phase 1 tests)
  - Verify hotel, glass, school pilots still work
  - Zero regressions acceptable
  ✓ Target: 200+ passing, 0 failures
```

### Week 8 (Jul 8-14): Production Deployment + Monitoring

```
Day 1-2 (Jul 8-9):
  - Performance tuning
  - Benchmark: <1ms per policy decision, 10k req/sec
  - Load test with 100 concurrent agents
  ✓ Target: <1ms latency, 0 errors

Day 3-4 (Jul 10-11):
  - Canary deployment to 10% of production
  - Monitor: false denials, latency, error rate
  - Phase 2 pilots (small subset of hotel, glass, school)
  ✓ Target: 0 unintended denials, <1ms

Day 5-6 (Jul 12-13):
  - Full production rollout
  - Monitor all three pilots
  - Automated alerts: policy reload failures, rate limit spikes
  ✓ Target: 100% uptime, 0 regressions

Day 7 (Jul 14):
  - Finalize documentation
  - Hand off to ops (monitoring, incident response)
  - Prepare Phase 2B kickoff (federated GaaS)
```

---

## 6. MODULE DEPENDENCIES (Build Order)

```
Phase 1 (Parallel, Weeks 1-6)
  ├─ L3B Intent Commitment (Week 1-2)
  │   └─ AP2 Ledger (dependency: complete)
  │   └─ KMS (dependency: complete)
  │
  └─ L5A Policy Gate (Week 1-3)
      ├─ DNS Stub Resolver (dependency: dnspython)
      ├─ DNSSEC Validator (dependency: dnssec library)
      └─ Policy YAML schema (dependency: complete)
  
  └─ L5B Rate Limiter (Week 1-2)
      └─ Redis (dependency: complete, for bucket storage)
  
  └─ L5C Kernel Enforcement (Week 2-3)
      ├─ iptables configuration (dependency: Linux kernel)
      ├─ cgroup v2 (dependency: Linux kernel 5.2+)
      ├─ seccomp (dependency: libseccomp)
      └─ kprobes (dependency: Linux kernel tracing)

Phase 2 (Sequential, Weeks 7-8)
  ├─ Integration (L1 ↔ L3B, L4 ↔ L5A/B/C, both ↔ L8)
  │   ├─ Blocking: L3B complete (from Week 2)
  │   └─ Blocking: L5A/B/C complete (from Week 3)
  │
  ├─ Testing (unit → integration → adversarial → compliance → regression → load)
  │   └─ Blocking: all modules integrated
  │
  └─ Deployment (staging → canary → production)
      └─ Blocking: 250+ tests passing, 0 regressions
```

---

## 7. ROLLBACK PROCEDURE

If integration fails at any phase:

### Option A: Partial Rollback (Keep Phase 1, Roll Back New Modules)
```bash
# If L3B integration breaks L1:
1. Revert L3B to mock (return True for all CIC verifications)
2. L3A (Tool Registry) continues to gate execution
3. L1 continues normal reasoning flow
4. No change to L4, L5, L8
5. Impact: Intent commitment layer disabled; integrity reduced but functional
6. Timeline: <5 min to revert

# If L5A/B/C breaks L4 tool execution:
1. Revert L5A policy gate to mock (allow all)
2. Disable kernel enforcement (iptables permissive)
3. L4 tool execution resumes normally
4. Phase 1 pilots continue unaffected
5. Impact: Egress controls disabled; compliance posture reduced but functional
6. Timeline: <10 min to revert
```

### Option B: Full Rollback (Return to Phase 1)
```bash
# If integration is fundamentally broken:
1. git revert <phase2a-commits>
2. Reload Phase 1 harness (L1-L8 without L3B/L5A/B/C)
3. Restart pilots
4. Impact: Phase 2A abandoned; no intent/egress controls
5. Timeline: <30 min to full restoration

# Next steps:
- Post-mortem: why did integration fail?
- Re-plan Phase 2A with fixes
- Re-attempt in Phase 2B window (Aug 2027)
```

---

## 8. SUCCESS METRICS

### Functional Success
- [x] 250+ tests passing (590 total: unit, integration, adversarial, compliance, regression, load)
- [x] Zero regressions in Phase 1 pilots (hotel, glass, school)
- [x] <1ms latency per policy decision (L5A)
- [x] <5ms latency per CIC verification (L3B)
- [x] 10k req/sec throughput per agent
- [x] 100% of egress validated against whitelist
- [x] 0 undetected egress (kernel-enforced)
- [x] All attack vectors (15+) blocked

### Regulatory Success
- [x] GDPR compliance memo (Art. 32: encryption in transit)
- [x] EU AI Act alignment (§5.2: security, §4.3: transparency)
- [x] OWASP ASI01 coverage (all 6 risks mitigated)
- [x] Audit trail (AP2 ledger, KMS-signed, immutable)
- [x] Compliance report generation (monthly, automated)

### Operational Success
- [x] Deployment runbook (staging → canary → production)
- [x] Monitoring dashboards (intent denials, egress denials, rate limits)
- [x] Incident response playbooks
- [x] Documentation (pseudocode, threat model, regulatory summary)
- [x] Rollback procedure (≤30 min restoration)

---

## 9. POST-DEPLOYMENT MONITORING (Jul 15+)

### Metrics to Track
```
Intent Layer (L3B):
  - CIC generation rate (expected: ~100/hour)
  - CIC verification success rate (expected: 99%+)
  - Mean CIC latency (target: <5ms)
  - Delegation chain depth (expected: avg 1-2 levels)

Egress Layer (L5A/B/C):
  - Policy decisions/sec (expected: 10k+)
  - Deny rate (expected: <0.1%, normal variation)
  - Mean policy latency (target: <1ms)
  - Rate limit triggers (expected: 0-1/day, normal)
  - Top deny reasons (dashboard)

Proof Layer (L8):
  - AP2 ledger append rate (expected: 10k+/hour)
  - KMS signature latency (target: <50ms)
  - Audit report generation (monthly, <5 min)

Pilot Health (Phase 1):
  - Hotel credit scoring: 0 errors, <2s per request
  - Glass ML inference: 0 errors, normal throughput
  - School reporting: 0 errors, audit trail intact
```

### Alerting Rules
```
Critical:
  - CIC verification failure rate > 1%
  - Egress policy latency > 10ms
  - AP2 ledger append timeout (>5 min)
  - Kernel enforcement iptables down

Warning:
  - Deny rate spike (>10x normal)
  - Rate limit triggers clustered (suggests DDoS)
  - KMS signature latency > 200ms
```

---

## 10. DELIVERABLES (End of Phase 2A)

### Code
- [ ] L3B Intent Commitment module (300 LOC, fully tested)
- [ ] L5A Policy Gate module (400 LOC, fully tested)
- [ ] L5B Rate Limiter module (200 LOC, fully tested)
- [ ] L5C Kernel Enforcement rules (100 LOC, deployed)
- [ ] Integration glue (200 LOC, L1 ↔ L3B ↔ L4 ↔ L5 ↔ L8)

### Tests
- [ ] 590 tests (250 unit, 100 integration, 20 adversarial, 20 compliance, 200 regression)
- [ ] 100% pass rate
- [ ] Coverage: >95% code coverage on new modules
- [ ] Load test results (100 concurrent agents, 10k req/sec)

### Documentation
- [ ] Integration architecture (pseudocode)
- [ ] Threat model (attack vectors + mitigations)
- [ ] Regulatory alignment memo (GDPR, AI Act, OWASP)
- [ ] Deployment runbook (staging → production)
- [ ] Incident response playbook
- [ ] Monitoring dashboard setup

### Proof
- [ ] Phase 1 pilots verified (zero regressions)
- [ ] Compliance reports (intent + egress audit trails)
- [ ] Performance benchmarks (<1ms latency, 10k req/sec)
- [ ] Security assessment (0 bypasses on 15+ attack vectors)

---

## 11. PHASE 2B KICKOFF (Jul 15, 2027)

Once Phase 2A completes successfully (Jul 14):
- Intent Verification + Egress Controls are production-ready
- Federated GaaS (Phase 2B, Jul 15 - Sep 30) can now safely delegate between agents
- Multi-agent orchestration inherits intent + egress controls automatically
- Expected: €15M → €20M ARR growth (50%) from secure, compliant architecture

