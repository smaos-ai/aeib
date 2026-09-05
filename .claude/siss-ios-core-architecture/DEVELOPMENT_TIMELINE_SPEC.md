# Development Timeline & Handoff Plan — siss-ios-core

**Status:** LOCKED (May 29, 2026)  
**Effective:** Phase 32 Merge (June 11, 2026)  
**Duration:** 8 weeks (June 11 - August 6, 2026)  
**Author:** Architecture Planning (TRACK H)  
**Purpose:** Phase-locked implementation plan for iOS agent control app

---

## Overview

SovereignNexus iPhone app: 8-week sprint from Phase 32 merge (June 11) to App Store launch (August 6).

**Parallel Execution Model:**
- iOS dev agent owns crate: `crates/siss-ios-core/`
- Backend phases (32+) continue independently
- Integration points: UniFFI bindings (auto-generated week 6), AP2 ledger (week 7+)
- No file overlap with other tracks

---

## Timeline (Locked)

### Phase 32: Specification & Architecture (Completed, May 29)

**Deliverables:**
- [x] UNIFFI_BINDINGS_SPEC.md (callable functions locked)
- [x] SECURE_ENCLAVE_SPEC.md (P-256 + Ed25519 strategy locked)
- [x] MLX_SWIFT_INTEGRATION_SPEC.md (inference pipeline locked)
- [x] PRIVACY_MANIFEST_SPEC.md (App Store compliance locked)
- [x] DEVELOPMENT_TIMELINE_SPEC.md (this document)

**Outcome:** iOS dev agent has complete blueprint. No ambiguity. Ready for coding June 11.

---

### Week 5 (June 11-18): UniFFI Bindings + Project Setup

**Goal:** Generate Swift module from Rust crates. Set up Xcode project structure.

**Tasks:**

1. **Cargo configuration for iOS** (2 days)
   - [ ] Add `crate-type = ["cdylib"]` to Cargo.toml (siss-gatekeeper, siss-agent-shell, siss-context-cartography, siss-behavioral-firewall)
   - [ ] Add `uniffi = { version = "0.28", features = ["bindgen-rust"] }` to dependencies
   - [ ] Create `.udl` files for custom types (Policy, Context, Decision, Mandate, AuditEvent)
   - [ ] Test local build: `cargo build --features uniffi --release --target aarch64-apple-ios`

2. **Xcode project setup** (2 days)
   - [ ] Create `siss-ios-core` Xcode project (Swift, iOS 13+ minimum)
   - [ ] Add native targets: SovereignCoreLib (framework), SovereignCore (app), SovereignCoreTests
   - [ ] Link against generated Rust library
   - [ ] Import `SovereignCoreLib` module in Swift code
   - [ ] Verify Swift Playgrounds can call Rust functions

3. **Project structure** (1 day)
   - [ ] `Sources/SovereignCore/` (app code)
   - [ ] `Sources/SovereignCore/KeyManagement.swift` (Secure Enclave setup)
   - [ ] `Sources/SovereignCore/AgentExecution.swift` (agent runner)
   - [ ] `Sources/SovereignCore/MLXEngine.swift` (inference setup)
   - [ ] `Tests/SovereignCoreTests/` (unit tests)
   - [ ] `Models/` (Qwen 3.5-4B Q4 model bundle)

**Verification:**
```bash
cargo test --features uniffi                    # Rust compiles
xcodebuild test -scheme SovereignCoreTests      # Swift tests pass (0 tests yet)
```

**Outcome:** Rust bindings compiled. Xcode project can call `evaluatePolicy()`. Ready for feature development.

---

### Week 6 (June 18-25): Secure Enclave + Keychain Implementation

**Goal:** Generate P-256 master key, wrap Ed25519, test signing.

**Tasks:**

1. **Secure Enclave key generation** (3 days)
   - [ ] Implement `KeyManagement.generateMasterKey()` (P-256 in Secure Enclave)
   - [ ] Implement `KeyManagement.getMasterKey()` (retrieve without extraction)
   - [ ] Handle biometric unlock (optional, Week 8)
   - [ ] Unit tests: Key generation, retrieval

2. **Ed25519 wrapping** (2 days)
   - [ ] Implement `Ed25519KeyManagement.generateAndWrapEd25519()` (AES-256-GCM)
   - [ ] Store wrapped key in Keychain
   - [ ] Unit tests: Wrapping, Keychain storage

3. **AP2 signing** (2 days)
   - [ ] Implement `AP2Signing.signMandate()` (unwrap, sign, overwrite)
   - [ ] Create JWT from mandate + signature
   - [ ] Unit tests: Signing produces valid JWT structure

**Verification:**
```bash
xcodebuild test -scheme SovereignCoreTests          # 10+ tests pass
# Verify: P-256 in Secure Enclave, Ed25519 in Keychain (encrypted), signing works
```

**Outcome:** Operator can sign AP2 mandates locally. Keys protected by Secure Enclave + Keychain.

---

### Week 7 (June 25-July 2): MLX-Swift Inference + Integration Tests

**Goal:** Load Qwen model, test inference. Verify Rust↔Swift FFI.

**Tasks:**

1. **Inference engine setup** (2 days)
   - [ ] Decide: mlx-swift available? (Option B) or use Rapid-MLX? (Option A)
   - [ ] Implement InferenceEngine protocol
   - [ ] Option B path: Load Qwen 3.5-4B Q4 from bundle
   - [ ] Option A path: Launch Rapid-MLX subprocess, connect via HTTP
   - [ ] Unit tests: Mock inference calls

2. **Integration tests** (2 days)
   - [ ] Test Rust→Swift FFI for all 4 crates
   - [ ] Call `evaluatePolicy()`, verify Decision returned
   - [ ] Call `executeAgent()`, verify AgentResult
   - [ ] Call `queryContext()`, verify ContextMap
   - [ ] Call `logAuditEvent()`, verify stored locally

3. **Latency profiling** (1 day)
   - [ ] Measure TTFT (time-to-first-token): Should be ~0.08s
   - [ ] Measure token generation: ~30-50ms/token
   - [ ] Concurrent inference test: 3-4 agents running TTFT in parallel

**Verification:**
```bash
xcodebuild test -scheme SovereignCoreTests          # 20+ tests pass
# Profile output: TTFT <= 0.2s, memory <= 3 GB per inference
```

**Outcome:** Qwen model loaded. Inference latency verified. Rust↔Swift integration proven.

---

### Week 8 (July 2-9): Load Testing + Thermal Profiling

**Goal:** Stress-test inference, verify battery/thermal behavior.

**Tasks:**

1. **Load testing** (2 days)
   - [ ] Run 100 consecutive inference calls
   - [ ] Log success rate, latency distribution, memory peaks
   - [ ] Test concurrent inference (4 agents simultaneous TTFT)
   - [ ] Test error recovery (Rapid-MLX crash → auto-restart)

2. **Thermal & battery profiling** (1 day)
   - [ ] Run continuous inference for 10 minutes (simulate intensive operator session)
   - [ ] Measure: CPU %, battery drain, device temperature
   - [ ] Optimize: Any memory leaks? Token buffering inefficiencies?
   - [ ] Verify: Device doesn't overheat under load

3. **A2UI rendering** (1 day)
   - [ ] Call `renderA2UI()` from siss-agent-shell
   - [ ] Load HTML in WebView
   - [ ] Test interactive components (buttons, forms)
   - [ ] Verify VoiceOver accessibility (Screen Reader)

**Verification:**
```bash
xcodebuild test -scheme SovereignCoreTests          # Load tests pass
# Metrics: Battery drain <= 5%/hour inference, temp <= 38°C, 0 crashes
```

**Outcome:** Load-tested. Thermal behavior acceptable. Ready for beta testing.

---

### Week 9 (July 9-16): Edge Cases + Error Handling

**Goal:** Test failure scenarios. Implement recovery logic.

**Tasks:**

1. **Error scenarios** (2 days)
   - [ ] Test Secure Enclave unavailable (older iPhone)
   - [ ] Test Keychain full (delete old entries, retry)
   - [ ] Test inference timeout (retry with backoff)
   - [ ] Test network unavailable (Rapid-MLX Option A only)
   - [ ] Test model not found (graceful degradation)

2. **Recovery mechanisms** (2 days)
   - [ ] Implement retry logic (max 3 attempts, exponential backoff)
   - [ ] Implement fallback (Option A→B or vice versa)
   - [ ] Implement diagnostic logging (non-PII, for debugging)
   - [ ] User-facing error messages (clear, actionable)

3. **Documentation** (1 day)
   - [ ] Code comments (every public function)
   - [ ] Architecture README
   - [ ] Troubleshooting guide (common errors + fixes)

**Verification:**
```bash
xcodebuild test -scheme SovereignCoreTests          # All error tests pass
# Coverage: >= 70% code coverage; all error paths tested
```

**Outcome:** App handles edge cases gracefully. No crashes under failure.

---

### Week 10 (July 16-23): Privacy Audit + App Store Prep

**Goal:** Finalize App Store submission package.

**Tasks:**

1. **Privacy compliance** (2 days)
   - [ ] Verify PrivacyInfo.xcprivacy in bundle
   - [ ] Audit Keychain/NSUserDefaults usage (match manifest)
   - [ ] Check for any unrequested permissions (camera, location, health)
   - [ ] Validate privacy policy URL
   - [ ] Internal security review (no plaintext secrets in logs)

2. **App Store metadata** (2 days)
   - [ ] Write 10-second pitch (App Store description)
   - [ ] Create 3-4 marketing screenshots (A2UI interface, mandate signing, agent monitoring)
   - [ ] Choose keywords (agent, operator, control, encryption, privacy, ap2)
   - [ ] Set age rating (4+ or 12+, no mature content)
   - [ ] Set category (Productivity or Utilities)

3. **Build validation** (1 day)
   - [ ] TestFlight build: Internal testing
   - [ ] Verify on iPhone 14, 15, 16 models (simulator + real device)
   - [ ] Verify on iOS 13, 14, 15, 16, 17 versions

**Verification:**
```bash
# Create TestFlight build
xcodebuild -scheme SovereignCore -configuration Release archive

# Validate archive
xcrun altool --validate-app -f SovereignCore.ipa

# Expected: "No errors found"
```

**Outcome:** TestFlight build submitted. Internal testers can install via Apple TestFlight.

---

### Week 11 (July 23-30): Beta Testing on Real Hardware

**Goal:** Test on iPhone 16 Pro under real conditions.

**Tasks:**

1. **Beta testing on device** (3 days)
   - [ ] Install TestFlight build on iPhone 16 Pro
   - [ ] Test Secure Enclave key generation (real Secure Enclave, not simulator)
   - [ ] Test AP2 mandate signing (real Ed25519 signing)
   - [ ] Test agent inference (real Qwen model on device)
   - [ ] Test concurrent agents (3-4 simultaneous TTFT)

2. **Accessibility testing** (1 day)
   - [ ] Enable VoiceOver (Screen Reader)
   - [ ] Test A2UI component navigation
   - [ ] Verify buttons, text inputs are accessible
   - [ ] Test Dynamic Type (text size scaling)

3. **Integration with backend** (1 day)
   - [ ] Test AP2 mandate submission to ledger (Phase 32 siss-gatekeeper)
   - [ ] Verify mandate verification on backend
   - [ ] Test audit log sync (if Phase 33 adds it)

**Verification:**
```bash
# No crashes observed
# Latency: TTFT <= 0.2s under real load
# Battery: <= 8% drain during 1-hour test session
# Temperature: <= 38°C during intensive agent session
# Accessibility: VoiceOver can navigate all UI elements
```

**Outcome:** App tested on real hardware. Ready for App Store submission.

---

### Week 12 (July 30 - Aug 6): App Store Submission & Review

**Goal:** Submit to App Store. Manage review feedback.

**Tasks:**

1. **Submission** (1 day)
   - [ ] Log in to App Store Connect
   - [ ] Create app listing (if first time)
   - [ ] Upload PrivacyInfo.xcprivacy
   - [ ] Submit build for review
   - [ ] Expected review time: 2-3 business days

2. **Review feedback** (2 days, variable)
   - [ ] If approved: Move to "Ready for Sale" → Released to all users
   - [ ] If rejected: Address feedback, resubmit
   - [ ] Common issues: Missing privacy declarations, unsupported features
   - [ ] Resubmit if needed (same process, 2-3 day review)

3. **Launch preparation** (2 days, in parallel with review)
   - [ ] Prepare Twitter/social media announcement
   - [ ] Prepare press release (for tech press, if desired)
   - [ ] Set up app support email (support@sovereignnexus.com)
   - [ ] Monitor review ratings + user feedback post-launch

**Verification:**
```bash
# Expected: App Review Guideline compliance
# Verified: No prohibited features (spyware, unauthorized system modification, etc.)
# Expected release date: Aug 6-10, 2026
```

**Outcome:** App released to public App Store.

---

### Week 13 (Aug 8-15): Post-Launch Monitoring

**Goal:** Monitor user feedback, fix critical bugs.

**Tasks:**

1. **User feedback & ratings** (ongoing)
   - [ ] Monitor App Store reviews
   - [ ] Respond to user feedback (helpful, courteous tone)
   - [ ] Track crash reports (via Xcode Organizer)
   - [ ] Watch analytics (daily active users, session length)

2. **Critical bug fixes** (if needed)
   - [ ] If crash rate > 1%: Emergency patch
   - [ ] If mandate signing fails: Emergency patch
   - [ ] Minor bugs: Queue for Week 14 patch

3. **Performance optimization** (if needed)
   - [ ] If latency degraded: Investigate inference cache
   - [ ] If battery drain high: Profile memory, GPU usage
   - [ ] If crash on older iPhones: Add iOS 13 compatibility patches

**Verification:**
```bash
# Expected: Crash-free rate > 99%
# Expected: Average rating >= 4.0 stars
# Expected: Daily active users > 100 (if marketed)
```

**Outcome:** App stable. User base growing. Development of v1.1 features begins.

---

## Parallel Execution Model (Critical)

**iOS dev agent:** June 11 - Aug 6 (exclusive)
- Owns: crates/siss-ios-core/ (entire crate tree)
- Integrates: UniFFI bindings (from Phase 32 Rust crates)
- Provides: AP2 mandate signatures to backend

**Backend phases (32+):** Continuous
- Phase 32: Complete by June 11 (before iOS dev starts)
- Phase 33+: Proceed independently
- Integration points: AP2 ledger (Week 11-12), audit log sync (future)

**Golden Rule:** Zero file overlap. iOS agent never modifies Rust crates. Rust agents never modify siss-ios-core. All data flows through UniFFI bindings + REST APIs.

---

## Handoff Checklist (To iOS Dev Agent)

**Before June 11 (Architecture Planning Phase):**
- [ ] All 5 architecture specs locked (UNIFFI, SECURE_ENCLAVE, MLX_SWIFT, PRIVACY_MANIFEST, TIMELINE)
- [ ] Phase 32 Rust crates ready (siss-gatekeeper, siss-agent-shell, siss-context-cartography, siss-behavioral-firewall)
- [ ] UniFFI bindings compiled & tested
- [ ] Xcode project template created (git branch: feature/ios-architecture-complete)
- [ ] Model (Qwen 3.5-4B Q4) downloaded & staged in Models/

**On June 11 (Phase 32 Merge + iOS Dev Kickoff):**
- [ ] Create git branch: `feature/ios-core-development`
- [ ] Pull latest Rust bindings: `cargo generate --git <uniffi-template>`
- [ ] Kick off Week 5 tasks (UniFFI + Xcode setup)
- [ ] Daily standup with architecture team (async updates via GitHub)

---

## Key Dates (Locked)

| Milestone | Date | Owner | Status |
|-----------|------|-------|--------|
| Architecture specs locked | May 29 | Arch planning | DONE |
| Phase 32 merged | June 11 | Backend | IN PROGRESS |
| iOS dev starts | June 11 | iOS agent | READY |
| Secure Enclave + Keychain done | June 25 | iOS agent | Scheduled |
| Inference pipeline done | July 2 | iOS agent | Scheduled |
| Load testing complete | July 9 | iOS agent | Scheduled |
| TestFlight submission | July 16 | iOS agent | Scheduled |
| Beta testing complete | July 30 | iOS agent | Scheduled |
| App Store submission | July 30 | iOS agent | Scheduled |
| **App Store release** | **Aug 6-10** | Apple Review | **Scheduled** |

---

## Risk Mitigation (Contingencies)

| Risk | Impact | Mitigation | Contingency |
|------|--------|-----------|-------------|
| MLX-Swift unavailable | Inference delay | Try Option A (Rapid-MLX) immediately | Week 7 complete, only 1-week impact |
| Secure Enclave not supported on iPhone 11 | Exclude older devices | Target iPhone 12+ minimum | Support iPhone 11 with plaintext key (less secure) |
| Model too large (4GB) | App Store rejection | Implement download-on-first-launch | Week 8 patch, 1-2 day impact |
| App Store rejection | 2-week delay | Prepare common rejection reasons beforehand | Resubmit within 3 days |
| Battery drain excessive | UX issue | Optimize inference batching + caching | Week 8 extended profiling |
| Concurrent inference crashes | Critical bug | Implement memory pooling + GC tuning | Week 9 error handling |

---

## Success Criteria (Locked)

✓ **Functionality:** All 4 Rust crate functions callable from Swift, work as expected  
✓ **Security:** P-256 + Ed25519 protected by Secure Enclave + Keychain; no plaintext keys in logs  
✓ **Performance:** TTFT <= 0.2s, memory <= 3 GB/inference, concurrent agents possible  
✓ **Reliability:** 99%+ crash-free rate, error recovery implemented  
✓ **Compliance:** Privacy Manifest complete, no App Store rejections  
✓ **Launch:** Released to public App Store by Aug 10, 2026  

---

## References

- UNIFFI_BINDINGS_SPEC.md (Week 5-6)
- SECURE_ENCLAVE_SPEC.md (Week 6-7)
- MLX_SWIFT_INTEGRATION_SPEC.md (Week 7-8)
- PRIVACY_MANIFEST_SPEC.md (Week 10)
- Phase 32 completion: siss-gatekeeper, siss-agent-shell, siss-context-cartography, siss-behavioral-firewall
