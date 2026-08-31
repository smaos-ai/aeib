# Phase 2 Coverage Roadmap: Scaling from 83% to 90%+
**Timeline:** June 1 - June 30, 2026 (after Phase 1 May 31 delivery)
**Target:** 90%+ coverage, <150 uncovered lines, mutation testing baseline

---

## Executive Overview

Phase 1 baseline: **83% (1,537/1,862 lines)**
Phase 2 target: **90%+ (1,672/1,862 lines)**
Effort required: **15 days (120 hours)** across 6 weeks
Priority focus: **KMS/crypto (HIGH), Intent verification (MEDIUM), Egress controls (LOW)**

---

## Week-by-Week Execution Plan

### Week 1: KMS Integration & Key Rotation (CRITICAL PATH)

**Goal:** 49% → 75% (24 additional lines covered)

#### Task 1.1: LocalStack KMS Setup (1 day)
**Owner:** Engineer
**Files:** Tests/integration/test_kms_integration.py (NEW)
**Changes:**
```python
# Docker-compose service for LocalStack KMS
# Replace mocks with real LocalStack KMS calls
# Test scenarios: key generation, rotation, deletion, unavailability
```
**Success Criteria:**
- [ ] LocalStack KMS running in CI
- [ ] 10+ integration tests passing
- [ ] kms_signer.py coverage: 49% → 65%

**Deliverable:** test_kms_integration.py (150 lines)

---

#### Task 1.2: Key Rotation & Versioning (1 day)
**Owner:** Engineer
**Files:** smaos/l6_infrastructure/kms_signer.py
**Changes:**
- Implement rotation_interval tracking
- Add version pinning for backward compatibility
- Error handling for rotation failures
- Audit logging for all key operations

**Test Matrix:**
| Scenario | Lines | Est. Time |
|----------|-------|-----------|
| Rotate active key | 8 | 2 hrs |
| Handle rotation race | 6 | 1.5 hrs |
| Verify old version still works | 4 | 1 hr |
| Log rotation audit trail | 4 | 1 hr |

**Success Criteria:**
- [ ] key_rotation_interval enforced
- [ ] All 9 rotation edge cases tested
- [ ] Coverage: 65% → 72%

**Deliverable:** test_key_rotation.py (120 lines)

---

#### Task 1.3: HSM Communication Paths (1 day)
**Owner:** Engineer
**Files:** smaos/l6_infrastructure/kms_signer.py
**Changes:**
- Test hardware token insertion/removal
- Timeout handling for HSM calls
- Recovery from HSM crash
- Fallback to backup keys

**Test Coverage:**
| Path | Lines | Notes |
|------|-------|-------|
| HSM online → offline | 4 | Simulate network failure |
| Slow HSM response | 5 | Add delays, test timeout |
| HSM permission denied | 3 | Test ACL violations |
| Backup key fallback | 3 | Ensure secondary works |

**Success Criteria:**
- [ ] All 15 HSM paths covered
- [ ] Fallback mechanism tested
- [ ] Coverage: 72% → 80%

**Deliverable:** test_hsm_resilience.py (100 lines)

---

### Week 2: Post-Quantum Cryptography Testing (CRITICAL PATH)

**Goal:** 50% → 75% (37 additional lines covered)

#### Task 2.1: CRYSTALS-Dilithium Integration (1 day)
**Owner:** Engineer
**Files:** Tests/integration/test_pqc_signatures.py (NEW)
**Changes:**
- Import liboqs bindings
- Test Dilithium key generation
- Test signature generation/verification
- Compare to secp256k1 performance

**Implementation:**
```python
# Test scenarios:
# 1. Generate 100 random keypairs, verify signatures
# 2. Cross-verify Ed25519 ↔ Dilithium signatures
# 3. Benchmark: 1000 signatures in <5s
# 4. Key size validation (Dilithium: 2544 bytes public)
```

**Success Criteria:**
- [ ] liboqs imported without errors
- [ ] 50+ Dilithium signatures verified
- [ ] Performance baseline recorded
- [ ] Coverage: 50% → 62%

**Deliverable:** test_pqc_signatures.py (180 lines)

---

#### Task 2.2: Signature Verification Error Paths (1 day)
**Owner:** Engineer
**Files:** smaos/l6_infrastructure/verify_signatures.py
**Changes:**
- Invalid signature format handling
- Expired certificate detection
- Revocation list checking (CRL/OCSP)
- Algorithm mismatch detection

**Test Matrix:**
| Error Type | Lines | Cause |
|-----------|-------|-------|
| Malformed sig | 4 | Corruption |
| Expired cert | 3 | Time-based |
| Revoked key | 5 | CRL lookup |
| Wrong algo | 2 | Type mismatch |
| Batch failure | 3 | Partial batch |

**Success Criteria:**
- [ ] All 17 error paths tested
- [ ] Each error returns correct message
- [ ] Coverage: 62% → 70%

**Deliverable:** test_signature_errors.py (140 lines)

---

#### Task 2.3: Batch Verification Optimization (1 day)
**Owner:** Engineer
**Files:** smaos/l6_infrastructure/verify_signatures.py
**Changes:**
- Implement batch verification (Ed25519: 4x faster)
- Partial batch handling (some sigs invalid)
- Concurrent verification pools
- Memory limits for large batches

**Scenarios:**
```
- Verify 1000 signatures in parallel → 20 lines
- Handle OOM for 1M signatures → 5 lines
- Graceful degradation → 4 lines
- Rollback on batch failure → 3 lines
```

**Success Criteria:**
- [ ] 1000-sig batch <500ms
- [ ] Memory limit enforced
- [ ] Coverage: 70% → 75%

**Deliverable:** test_batch_verification.py (120 lines)

---

### Week 3: Intent Verification & Egress Control (MEDIUM PRIORITY)

**Goal:** L3 = 79% → 90% (28 additional lines)

#### Task 3.1: Intent Constraint Edge Cases (1 day)
**Owner:** Engineer
**Files:** smaos/l3_tooling/intent_commitment.py
**Changes:**
- Latency constraint: negative elapsed time, NaN handling
- Data access: null scope, wildcard validation
- API constraint: unknown endpoint, type mismatch

**Parametrized Test Approach:**
```python
@pytest.mark.parametrize("elapsed_ms,expected_violation", [
    (0, False),          # Instant execution
    (-1, True),          # Clock skew
    (float('nan'), True) # Invalid value
])
def test_latency_edge_cases(elapsed_ms, expected_violation):
    ...
```

**Coverage Details:**
| Constraint Type | Missing Lines | Effort |
|-----------------|---------------|--------|
| Latency | 3 | 1 hr |
| Data Access | 3 | 1 hr |
| API Constraint | 2 | 0.5 hr |
| Totals | 8 | 2.5 hrs |

**Success Criteria:**
- [ ] All 8 edge cases tested
- [ ] Coverage: 76% → 81%

---

#### Task 3.2: Egress Validator TLS Certificate Chains (1 day)
**Owner:** Engineer
**Files:** smaos/l3_tooling/egress_validator.py
**Changes:**
- Self-signed certificate handling
- Expired certificate detection
- Certificate chain validation
- OCSP stapling support

**Test Scenarios:**
```
- Valid chain (3 levels deep) → 4 lines
- Self-signed bypass → 3 lines
- Chain gap (missing intermediate) → 3 lines
- Expired cert in chain → 2 lines
- OCSP revocation → 2 lines
```

**Success Criteria:**
- [ ] All 14 TLS paths covered
- [ ] Coverage: 84% → 90%

---

#### Task 3.3: Rate Limiting Reset & Enforcement (0.5 day)
**Owner:** Engineer
**Files:** smaos/l3_tooling/egress_validator.py
**Changes:**
- Implement reset_rate_limits() call path
- Test rate limit expiration
- Enforce per-IP vs per-user limits

**Success Criteria:**
- [ ] reset_rate_limits() tested
- [ ] Coverage: 90% → 92%

---

### Week 4: AP2 Ledger & Merkle Integrity (MEDIUM PRIORITY)

**Goal:** 75% → 88% (19 additional lines)

#### Task 4.1: Merkle Tree Consistency Checks (1 day)
**Owner:** Engineer
**Files:** smaos/l6_infrastructure/ap2_ledger.py
**Changes:**
- Implement merkle_verify_chain()
- Test tree rebalancing on insert
- Verify root hash consistency
- Detect ledger tampering

**Coverage:**
```
- Insert entry, verify root changes → 3 lines
- Detect malicious edit (mid-leaf tamper) → 4 lines
- Rebuild tree from leaf set → 3 lines
- Cross-chain merkle root verification → 2 lines
```

**Success Criteria:**
- [ ] 12 merkle scenarios tested
- [ ] Coverage: 75% → 80%

---

#### Task 4.2: Signature Rollback Prevention (1 day)
**Owner:** Engineer
**Files:** smaos/l6_infrastructure/ap2_ledger.py
**Changes:**
- Prevent replaying old signatures
- Nonce/timestamp validation
- Detect fork detection in ledger
- Immutability enforcement

**Test Scenarios:**
```
- Replay old signature → reject → 3 lines
- Timestamp order violation → 3 lines
- Fork detection (competing chain) → 4 lines
- Immutability proof verification → 3 lines
```

**Success Criteria:**
- [ ] 13 rollback scenarios tested
- [ ] Coverage: 80% → 88%

---

### Week 5: Integration Testing & Mutation Testing

**Goal:** 88% → 90%+ (10+ additional lines)

#### Task 5.1: Full Hotel Pilot Coverage (1 day)
**Owner:** Engineer
**Files:** Tests/integration/test_hotel_pilot_e2e.py
**Changes:**
- End-to-end hotel credit scoring L1→L8
- Capture all 7 proof artifacts
- Verify audit trail completeness
- RAGAS golden set alignment

**Flow:**
```
Request → L1 (Policy) → L3 (Intent) → L6 (Proof) → L8 (Ledger)
          + Audit trail at each layer
          + KMS signature at completion
          + Merkle root in ledger
```

**Success Criteria:**
- [ ] Full flow executes
- [ ] All 7 proofs captured
- [ ] Coverage: 88% → 90%

---

#### Task 5.2: Mutation Testing Baseline (1 day)
**Owner:** Engineer (separate from coverage)
**Tool:** mutmut + cosmic-ray
**Goal:** Verify test quality (not just line coverage)

**Strategy:**
```
- Run mutmut on each module
- Generate mutation score (target: >80%)
- Identify weak tests (high mutation survival)
- Prioritize mutation killers for Phase 2
```

**Output:** mutation_baseline.json (artifact for Series A)

---

### Week 6: Documentation & Sign-off

#### Task 6.1: Final Coverage Report (0.5 day)
- Merge all branch coverage data
- Generate Phase 2 coverage summary
- Identify remaining gaps (<10%)
- Plan Phase 3 (if any)

#### Task 6.2: Series A Evidence Package (0.5 day)
- Copy coverage.html to data room
- Export coverage.json with annotations
- Create "Coverage Improvement" narrative
- Add mutation testing results

---

## Critical Path Summary

```
Week 1: KMS → Week 2: PQC → Week 3: Intent → Week 4: AP2 → Week 5: Integration
(Days: 3    +    3         +     1        +      2       +       2        = 11 days)
```

**Slack:** 4 days for buffer, unplanned issues

---

## Success Metrics (Phase 2 Exit Criteria)

| Metric | Target | How to Verify |
|--------|--------|---------------|
| Overall coverage | 90%+ | `coverage report` |
| Uncovered lines | <150 | `coverage report --skip-covered` |
| Modules >85% | 12+ | Coverage JSON inspection |
| Modules <50% | 0 | Audit all red modules |
| Mutation score | >80% | `mutmut results` |
| Test count | 150+ | `pytest --collect-only` |
| Hotel pilot flow | ✅ passing | `pytest tests/hotel_pilot/` |
| KMS integration | ✅ passing | LocalStack tests pass |
| PQC signatures | ✅ verified | Dilithium key tests pass |
| Series A data room | 📦 ready | Coverage HTML + JSON exported |

---

## Contingency Plans

### If KMS tests fail (unlikely with LocalStack)
**Fallback:** Mock KMS with deterministic key IDs
**Impact:** -2% coverage, but KMS contract still verified
**Time:** +1 day

### If CRYSTALS-Dilithium library unavailable
**Fallback:** Use liboqs Python wrapper (pure Python implementation)
**Impact:** +2 days, but coverage achieved
**Time:** +2 days

### If mutation testing impossible
**Fallback:** Manual code review of untested branches
**Impact:** -5 confidence, but coverage target still met
**Time:** +1 day

---

## Post-Phase-2 Coverage Roadmap (Phase 3+)

After reaching 90%+, next improvements are:
1. **Mutation testing** (87%+ survivors → killers)
2. **Performance benchmarks** (latency/throughput regression)
3. **Fuzz testing** (policy routing, egress validation)
4. **Security testing** (OWASP ASI01 coverage)
5. **End-to-end pilots** (glass, school full flows)

Each Phase 3 increment targets +2-3% coverage.

---

## Delivery Artifacts

- [ ] coverage_baseline_report.md ← Phase 1 (THIS DOCUMENT is Phase 2 roadmap)
- [ ] coverage.json (Phase 2 final)
- [ ] htmlcov/ (Phase 2 final visual)
- [ ] mutation_baseline.json (Phase 2 quality metric)
- [ ] hotel_pilot_e2e_report.md (Phase 2 integration proof)
- [ ] phase3_roadmap.md (future: optional)

---

## Notes for Implementation

### Testing Best Practices to Follow
1. **Parametrized tests:** Use `@pytest.mark.parametrize` for matrix coverage
2. **Fixtures:** Share LocalStack/MockKMS setup across test suites
3. **Markers:** Tag tests as `@pytest.mark.integration`, `@pytest.mark.crypto`
4. **Isolation:** Each test file independent (no state pollution)
5. **Cleanup:** Use `try/finally` or `pytest.fixture(autouse=True)` for teardown

### Coverage Exclusion Rules
- `# pragma: no cover` for unreachable code (e.g., platform-specific)
- Main execution blocks (if __name__) excluded by default
- Test helper functions excluded from coverage

### Continuous Improvement
- After each week, run `coverage report` and update roadmap
- If ahead of schedule, add stretch goal (mutation testing, fuzz)
- If behind, prioritize: KMS > Intent > Egress > AP2

---

## Success Narrative for Series A

**Current State (Phase 1 End):**
- 83% coverage: solid engineering foundation
- Excellent L1 (98%): policy routing production-ready
- Weak L6 (49-50%): crypto/proof still in development

**Phase 2 Improvement:**
- KMS/HSM integration tests: +10% (enables real deployments)
- PQC signature verification: +8% (post-quantum claim verified)
- Intent verification edge cases: +4% (hijacking detection hardened)
- AP2 merkle/rollback: +5% (immutability proven)

**Phase 2 End Result:**
- 90%+ coverage: enterprise-grade testing
- All 6 layers >85%: consistent quality
- Mutation score >80%: tests actively kill bugs
- Hotel pilot verified: real end-to-end flow working

**Series A Message:**
"SMAOS went from 83% baseline coverage to 90%+ in one month, demonstrating disciplined engineering. KMS/crypto modules, the trust anchor, now have battle-tested integration. Post-quantum signatures verified. Ready for production deployment."

---

## Conclusion

Phase 2 is an **execution plan to unlock Series A confidence** in the proof layer (L6) and crypto infrastructure. The 15-day effort is achievable with focused TDD. Success requires weekly discipline and rapid iteration on test scenarios.

**Recommended:** Begin Week 1 immediately upon Phase 1 delivery (June 1). Target: 90%+ by June 30 for Series A materials submission by July 15.
