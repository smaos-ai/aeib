# siss-ios-core Architecture Specifications — Master Index

**Status:** LOCKED (May 29, 2026)  
**Phase:** Pre-Implementation (Specifications Only)  
**Effective Date:** June 11, 2026 (Phase 32 Merge)  
**Owner:** Architecture Planning (TRACK H)  
**Handoff:** iOS Development Agent (8-week sprint, June 11 - Aug 6)

---

## Quick Links

1. **UNIFFI_BINDINGS_SPEC.md** — Rust↔Swift FFI architecture
   - Defines which Rust crates expose to Swift (4 crates)
   - Lists all callable functions (9 total)
   - Type mapping (Rust → Swift)
   - Testing strategy + build configuration

2. **SECURE_ENCLAVE_SPEC.md** — Cryptographic key management
   - P-256 master key in Secure Enclave (hardware-protected)
   - Ed25519 wrapped with AES-256-GCM + stored in Keychain
   - AP2 mandate signing workflow
   - Key rotation strategy (quarterly)

3. **MLX_SWIFT_INTEGRATION_SPEC.md** — Local LLM inference
   - Option A: Rapid-MLX subprocess (fallback, proven)
   - Option B: MLX-Swift direct (preferred, if available)
   - Qwen 3.5-4B Q4 quantization (4 GB model)
   - Unified inference interface (switchable implementations)

4. **PRIVACY_MANIFEST_SPEC.md** — App Store compliance
   - PrivacyInfo.xcprivacy XML structure
   - Data collection declaration (Keychain, UserDefaults)
   - Privacy policy + metadata (screenshots, keywords)
   - Pre-submission checklist

5. **DEVELOPMENT_TIMELINE_SPEC.md** — 8-week execution plan
   - Week-by-week breakdown (June 11 - Aug 6)
   - Parallel execution model (iOS + backend independence)
   - Handoff checklist (to iOS dev agent)
   - Risk mitigation + contingencies

6. **INDEX.md** — This file. Master navigation.

---

## Why These Specs Exist

**Problem:** iOS development has many moving parts:
- FFI bindings (Rust → Swift)
- Cryptographic key management (Secure Enclave + Keychain)
- Local LLM inference (on-device, no cloud)
- App Store compliance (privacy, permissions, review)
- 8-week timeline with dependencies

**Solution:** Lock the architecture before writing code. 5 detailed specs define:
- What functions are callable (UNIFFI)
- How keys are protected (SECURE_ENCLAVE)
- How inference works (MLX_SWIFT)
- What Apple approves (PRIVACY_MANIFEST)
- When everything ships (TIMELINE)

**Benefit:** iOS dev agent starts June 11 with **zero ambiguity**. No mid-project pivots. No App Store surprises.

---

## Specification Overview

### 1. UNIFFI_BINDINGS_SPEC.md (11 KB)

**Problem:** How does Swift call Rust code?

**Solution:**
- UniFFI (Mozilla framework) auto-generates Swift bindings
- 4 Rust crates expose functions: gatekeeper, agent-shell, context-cartography, behavioral-firewall
- 9 callable functions total (policy eval, mandate creation, agent execution, context queries, audit logging)

**Locked Decisions:**
- Use UniFFI (not hand-written FFI) — safer, less bugs
- Expose 4 crates only — minimal API surface
- All functions return Result<T> — consistent error handling
- Compile-time type safety via UniFFI marshalling

**Week 5 Deliverable:** Xcode project imports SovereignCoreLib module. Swift calls Rust functions directly.

---

### 2. SECURE_ENCLAVE_SPEC.md (15 KB)

**Problem:** iPhone Secure Enclave only supports P-256 (not Ed25519). But AP2 ledger requires Ed25519. How to sign with non-native key?

**Solution:**
- P-256 master key lives in Secure Enclave (hardware-protected, non-extractable)
- Ed25519 key wrapped with AES-256-GCM (using P-256 ephemeral key)
- Wrapped key stored in Keychain (encrypted + Secure Enclave integration)
- At signing time: Unwrap Ed25519 → Sign → Immediately overwrite memory

**Threat Model:**
- Attacker extracts Keychain: Ed25519 is encrypted (useless without P-256)
- Attacker accesses Secure Enclave: Impossible (hardware-protected)
- Device compromised at runtime: Ed25519 unwrapped only during signing, then overwritten

**Week 6-7 Deliverable:** Generate P-256 master key. Wrap + store Ed25519. Sign real AP2 mandates.

---

### 3. MLX_SWIFT_INTEGRATION_SPEC.md (14 KB)

**Problem:** iPhone needs local LLM inference (Qwen 3.5-4B) for agent reasoning. No cloud dependency.

**Solution:**
- Option A (Fallback): Launch Rapid-MLX as subprocess, HTTP to localhost:8000, OpenAI-compatible API
- Option B (Preferred): Use mlx-swift bindings (if available by July 2), native Swift FFI to MLX
- Both implement same interface (switchable via build flag)
- Unified InferenceEngine protocol

**Model:** Qwen 3.5-4B Q4 (4 GB, quantized, fits in app bundle)

**Performance:**
- TTFT: 0.08s (proven on M-series)
- Token generation: 30-50ms/token
- iPhone 16 Pro (12 GB RAM): 3-4 concurrent agents possible

**Week 6-8 Deliverable:** Load model from bundle (or subprocess). Test concurrent inference. Verify latency < 0.2s TTFT.

---

### 4. PRIVACY_MANIFEST_SPEC.md (12 KB)

**Problem:** Apple requires PrivacyInfo.xcprivacy for any app using Keychain, NSUserDefaults, networking, etc. Missing or false declarations → App Store rejection.

**Solution:**
- Declare Keychain access (Ed25519 wrapped key storage)
- Declare NSUserDefaults access (operator session state)
- Declare no camera, location, health, analytics (not used)
- Privacy policy hosted at sovereignnexus.com/privacy

**App Store Metadata:**
- Screenshots (A2UI interface, mandate signing, agent monitoring)
- Description (secure operator control, agent deployment, local inference)
- Privacy policy URL + privacy manifest XML included in bundle

**Week 10 Deliverable:** PrivacyInfo.xcprivacy + privacy policy + App Store screenshots ready for submission.

---

### 5. DEVELOPMENT_TIMELINE_SPEC.md (11 KB)

**Problem:** 8-week sprint from June 11 to App Store launch (Aug 6). Many dependencies (Phase 32 merge, UniFFI generation, model loading, privacy audit, App Store review). How to sequence?

**Solution:**
- Week 5 (June 11-18): UniFFI setup + Xcode project creation
- Week 6 (June 18-25): Secure Enclave + Keychain implementation
- Week 7 (June 25-July 2): Inference pipeline + integration tests
- Week 8 (July 2-9): Load testing + thermal profiling
- Week 9 (July 9-16): Error handling + edge cases
- Week 10 (July 16-23): Privacy audit + App Store prep
- Week 11 (July 23-30): Beta testing on real hardware
- Week 12 (July 30-Aug 6): App Store submission + review
- Week 13 (Aug 8-15): Post-launch monitoring

**Parallel Model:** iOS dev (siss-ios-core) works independently from backend (Phases 32+). Zero file overlap. Integration via UniFFI bindings + REST APIs.

**Week 12 Outcome:** App released to public App Store.

---

## Critical Assumptions (Unlocked Risks)

| Assumption | Lock Status | Contingency |
|-----------|------------|-------------|
| Phase 32 merges by June 11 | ASSUMED | If delayed → iOS start pushed to June 18 |
| mlx-swift available by July 2 | UNCERTAIN | If unavailable → Use Option A (Rapid-MLX), no schedule impact |
| Secure Enclave works on iPhone 12+ | CONFIRMED | If older devices required → Support plaintext key (security trade-off) |
| 4 GB model fits in App Store | ASSUMED | If rejected → Implement download-on-first-launch (Week 8 patch) |
| App Store review takes 2-3 days | TYPICAL | If delayed → Contingency: Aug 8-15 launch instead of Aug 6 |

---

## Integration Points (Cross-Track Dependencies)

**Phase 32 (Backend) → iOS:**
- UniFFI bindings: siss-gatekeeper, siss-agent-shell, siss-context-cartography, siss-behavioral-firewall
- AP2 mandate structure (for signing)
- Audit event schema (for local logging)

**iOS → Phase 33+ (Backend):**
- Signed AP2 mandates (submitted to ledger)
- Agent execution results (sent to backend for processing)
- Audit trail sync (if Phase 33 adds)

**No bidirectional wait.** iOS development proceeds independently. Integrations happen asynchronously.

---

## Success Metrics (Definition of Done)

### Architecture Specs
- [x] All 5 specs locked by May 29
- [x] Zero ambiguity on implementation approach
- [x] Risk mitigation documented for each spec

### Week 5-6 Deliverables
- [ ] UniFFI bindings generated + tested
- [ ] Secure Enclave key generation working
- [ ] Swift unit tests pass (10+ tests)

### Week 7 Deliverables
- [ ] Inference pipeline (Option A or B) operational
- [ ] Integration tests pass (20+ tests)
- [ ] TTFT <= 0.2s verified

### Week 8-9 Deliverables
- [ ] Load testing complete (100 calls, 0 crashes)
- [ ] Error handling for all failure scenarios
- [ ] Concurrent inference stable (3-4 agents)

### Week 10 Deliverables
- [ ] Privacy Manifest complete + verified
- [ ] App Store metadata (screenshots, description, privacy policy)
- [ ] TestFlight build submitted

### Week 11 Deliverables
- [ ] Beta testing on iPhone 16 Pro (real device)
- [ ] Zero crashes under real load
- [ ] Accessibility verified (VoiceOver)

### Week 12 Deliverable
- [ ] App Store released (expected Aug 6-10)

---

## How to Use These Specs

### For iOS Dev Agent (June 11+)

1. **Read all 5 specs** (1 hour total). Understand the architecture.
2. **Week 5:** Follow DEVELOPMENT_TIMELINE_SPEC (Week 5 section). Use UNIFFI_BINDINGS_SPEC for implementation details.
3. **Week 6:** Follow Week 6 section. Reference SECURE_ENCLAVE_SPEC for key management code.
4. **Week 7:** Follow Week 7 section. Reference MLX_SWIFT_INTEGRATION_SPEC for inference setup.
5. **Week 10:** Follow Week 10 section. Reference PRIVACY_MANIFEST_SPEC for compliance.
6. **Week 12:** Follow Week 12 section. Submit to App Store.

### For Backend Agents (Continuous)

- **Phase 32 → iOS Integration:** Ensure UniFFI bindings are compiled + included in Cargo.lock
- **Phase 33+:** Provide REST APIs for audit log sync (if needed)
- **No blocking dependencies.** iOS work is isolated via UniFFI.

### For Project Management

- **May 29:** Architecture locked. Specs ready.
- **June 11:** iOS dev starts. Timeline begins.
- **July 30:** TestFlight submission. App under review.
- **Aug 6-10:** Expected App Store release.

---

## Document Status

**Locked Specifications** (May 29, 2026):
1. ✅ UNIFFI_BINDINGS_SPEC.md — Callable functions, type mapping, FFI strategy
2. ✅ SECURE_ENCLAVE_SPEC.md — Key management, threat model, signing workflow
3. ✅ MLX_SWIFT_INTEGRATION_SPEC.md — Inference options, model distribution, performance
4. ✅ PRIVACY_MANIFEST_SPEC.md — App Store compliance, metadata, privacy policy
5. ✅ DEVELOPMENT_TIMELINE_SPEC.md — 8-week execution plan, handoff checklist

**Next Phase:** iOS development agent (June 11 - Aug 6). Specs remain locked unless critical blocking issue discovered (unlikely).

---

## Contact & Questions

**Architecture Owner:** TRACK H (May 29, 2026)

**iOS Dev Agent:** Ready June 11

**Backend Phases:** Proceed independently, no blocking iOS work

**Questions/Clarifications:** Update specs here, notify all agents via git commit

---

## Revision Log

| Date | Change | Reason |
|------|--------|--------|
| May 29, 2026 | Initial specs locked | Architecture planning (TRACK H) |

---

Last updated: May 29, 2026 14:32 UTC
