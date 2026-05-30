# wterm + siss-command-center Integration — Complete Research Index

**Track:** TRACK D — wterm Observability Prototype (2 weeks)  
**Status:** 🟢 RESEARCH COMPLETE — IMPLEMENTATION READY  
**Date:** 2026-05-29  
**Next Phase:** Implementation Week 1 (May 29–Jun 2)  

---

## 📋 Document Structure

This research package contains 4 complete documents. **Start here, then pick your path:**

### 1. **WTERM_RESEARCH_SUMMARY.md** ← START HERE
**Purpose:** Executive summary + quick reference  
**Time to read:** 10 minutes  
**Contains:**
- Technology recommendations (wterm vs. ttyd)
- Performance baselines
- Risk assessment + mitigations
- Decision gate (GO recommendation)
- Quick copy-paste commands

**Best for:** Managers, decision-makers, quick overview

---

### 2. **WTERM_INTEGRATION_BLUEPRINT.md** ← FOR ARCHITECTS
**Purpose:** Complete technical reference + design patterns  
**Time to read:** 45 minutes  
**Contains:**
- 11 sections covering:
  1. Executive summary
  2. wterm SDK integration (detailed API reference)
  3. WebSocket patterns (architecture, Axum code)
  4. USB tethering flow (gnirehtet, 3 scenarios)
  5. Accessibility (VoiceOver/TalkBack, WCAG checklist)
  6. Fallback patterns (ttyd comparison, swap-in guide)
  7. Phase-by-phase implementation breakdown
  8. Performance baselines + scaling recommendations
  9. Risk assessment + mitigation
  10. References + resources
  11. Final recommendation

**Best for:** Engineers, architects, code reviewers

---

### 3. **WTERM_GLUE_CODE_REFERENCE.md** ← FOR IMPLEMENTERS
**Purpose:** Production-ready copy-paste code  
**Time to read:** 30 minutes (skim), 2 hours (implement)  
**Contains 6 parts:**
1. React component (`CommandCenter.tsx`) — Full wterm integration with WebSocket + reconnection logic
2. Axum WebSocket route (`src/routes/ws.rs`) — Backend message loop, event formatting
3. Event injection (`src/routes/job_events.rs`) — How to subscribe to siss-job-router
4. USB bootstrap script (`bootstrap-usb-tether.sh`) — One-command tether + server setup
5. Configuration (`package.json`, `Cargo.toml`) — Dependencies
6. Testing script (`test-wterm-integration.sh`) — Sanity checks

**Best for:** Implementation engineers, copy-paste developers

---

### 4. **WTERM_FIELD_TESTING_STRATEGY.md** ← FOR QA/TESTING
**Purpose:** Complete test plan with metrics, scenarios, troubleshooting  
**Time to read:** 60 minutes  
**Contains:**
- Hardware setup (3-node test cluster)
- 6 test scenarios:
  1. Latency (<100ms p95)
  2. Memory stability (24-hour soak)
  3. USB reconnection (graceful handling)
  4. Accessibility (VoiceOver/TalkBack)
  5. Load testing (10+ concurrent)
  6. Offline resilience (intermittent connectivity)
- Success criteria + baselines
- Data collection checklist
- Failure mode troubleshooting table
- Report template + sign-off

**Best for:** QA engineers, test leads, field testers

---

## 🎯 Quick Navigation

**I need to...**

| Goal | Start Here | Then Read |
|------|-----------|-----------|
| **Decide:** Use wterm or ttyd? | WTERM_RESEARCH_SUMMARY (§2, 6) | WTERM_INTEGRATION_BLUEPRINT (§6) |
| **Implement:** Build the integration | WTERM_GLUE_CODE_REFERENCE (Parts 1-3) | WTERM_INTEGRATION_BLUEPRINT (§7) |
| **Deploy:** USB tethering setup | WTERM_GLUE_CODE_REFERENCE (Part 4) | WTERM_INTEGRATION_BLUEPRINT (§4) |
| **Test:** Validate in field | WTERM_FIELD_TESTING_STRATEGY (§2-3) | WTERM_GLUE_CODE_REFERENCE (Part 6) |
| **Understand:** Architecture deep-dive | WTERM_INTEGRATION_BLUEPRINT (§1-3) | WTERM_RESEARCH_SUMMARY (§8) |
| **Troubleshoot:** Something broken | WTERM_FIELD_TESTING_STRATEGY (§5) | WTERM_GLUE_CODE_REFERENCE (Debugging section) |
| **Compare:** wterm vs alternatives | WTERM_INTEGRATION_BLUEPRINT (§6) | WTERM_RESEARCH_SUMMARY (§9) |

---

## 📊 Document Relationships

```
┌─ WTERM_RESEARCH_SUMMARY.md
│  ├─ Recommendation: Use wterm (with ttyd fallback)
│  ├─ Timeline: 1.4 weeks (fits 2-week TRACK D budget)
│  └─ Risk: LOW-MEDIUM (< 25% blocker)
│
├─ WTERM_INTEGRATION_BLUEPRINT.md
│  ├─ 11 detailed sections (architecture, APIs, patterns)
│  ├─ SDK APIs for @wterm/react (Props, hooks, event handlers)
│  ├─ WebSocket pattern (client ↔ server protocol)
│  ├─ USB tethering flow (gnirehtet, 3 deployment scenarios)
│  ├─ Accessibility deep-dive (WCAG 2.1 AA, VoiceOver/TalkBack)
│  ├─ Fallback guide (ttyd, when to swap)
│  └─ Phase-by-phase implementation (3 phases, 2 weeks)
│
├─ WTERM_GLUE_CODE_REFERENCE.md
│  ├─ Part 1: React component with WebSocket + reconnection
│  ├─ Part 2: Axum backend (message loop, event formatting)
│  ├─ Part 3: Event subscription from siss-job-router
│  ├─ Part 4: USB bootstrap script (one-command setup)
│  ├─ Part 5: Dependencies (npm, Cargo)
│  └─ Part 6: Testing script (sanity checks)
│
└─ WTERM_FIELD_TESTING_STRATEGY.md
   ├─ 3-node cluster setup (hardware checklist)
   ├─ 6 test scenarios (latency, memory, USB, a11y, load, offline)
   ├─ Performance baselines (targets vs. acceptable)
   ├─ Data collection (metrics, logs, profiles)
   ├─ Troubleshooting (failure modes, fixes)
   └─ Report template (sign-off checklist)
```

---

## 🚀 Implementation Timeline

**Week 1 (May 29–Jun 2):**
- [ ] **Day 1:** Read WTERM_RESEARCH_SUMMARY.md + WTERM_INTEGRATION_BLUEPRINT.md (§1-3)
- [ ] **Day 2:** Implement WTERM_GLUE_CODE_REFERENCE.md Parts 1-2 (React + Axum)
- [ ] **Day 3:** Implement WTERM_GLUE_CODE_REFERENCE.md Parts 3 (Event subscription)
- [ ] **Day 3-4:** Run WTERM_FIELD_TESTING_STRATEGY.md Scenarios 1-2 (latency, memory)
- [ ] **Day 5:** Deploy bootstrap script, run Scenarios 3-4 (USB, accessibility)

**Week 2 (Jun 2–5):**
- [ ] **Day 6:** Run Scenarios 5-6 (load test, offline resilience)
- [ ] **Day 7-9:** Compile WTERM_FIELD_TESTING_STRATEGY.md report + sign-off
- [ ] **Day 10:** Code review + documentation cleanup

---

## 📈 Success Criteria (Go/No-Go)

**Must Have (Week 1):**
- ✅ Real-time job events visible in wterm terminal
- ✅ <100ms latency (p95) on localhost
- ✅ USB tether working (gnirehtet + Android phone)

**Should Have (Week 2):**
- ✅ <50ms latency (p95) verified
- ✅ 24-hour memory stability test passed
- ✅ WCAG 2.1 AA accessible (VoiceOver/TalkBack)
- ✅ 10+ concurrent terminals working

**Nice to Have:**
- ✅ Automatic reconnection logic
- ✅ Load test (50+ concurrent)
- ✅ ttyd fallback tested

---

## 🔧 Key Technical Decisions (Made)

| Decision | Choice | Why | Risk |
|----------|--------|-----|------|
| **Terminal library** | wterm | DOM-based (a11y), WASM (fast), React integration | None (Vercel Labs) |
| **WebSocket backend** | Axum + Tokio | Rust async, minimal code, proven | None (tokio-rs) |
| **USB tethering** | gnirehtet | No app install, Starlink compatible | Low (XDA forums tested) |
| **Fallback** | ttyd | Zero integration, drop-in replacement | Low (proven fallback) |
| **Timeline** | 1.4 weeks | Fits TRACK D budget | Low (<25% slip risk) |

---

## 📁 File Locations

All documents stored in project root `.claude/` directory:

```
/Users/andriileukhin/Documents/SovereignNexus/.claude/
├─ WTERM_INDEX.md ............................ This file (navigation)
├─ WTERM_RESEARCH_SUMMARY.md ................. Executive summary + decision gate
├─ WTERM_INTEGRATION_BLUEPRINT.md ........... Complete technical reference
├─ WTERM_GLUE_CODE_REFERENCE.md ............ Copy-paste code (5 parts)
└─ WTERM_FIELD_TESTING_STRATEGY.md ......... Test plan + scenarios
```

---

## 📞 Questions? Use This Lookup Table

**Topic** | **Document** | **Section** | **Time**
----------|------------|-----------|--------
Architecture overview | WTERM_INTEGRATION_BLUEPRINT | §1 | 5 min
wterm API details | WTERM_INTEGRATION_BLUEPRINT | §2 | 15 min
WebSocket protocol | WTERM_INTEGRATION_BLUEPRINT | §3 | 10 min
USB tethering setup | WTERM_INTEGRATION_BLUEPRINT | §4 | 10 min
Accessibility compliance | WTERM_INTEGRATION_BLUEPRINT | §5 | 10 min
Fallback (ttyd) | WTERM_INTEGRATION_BLUEPRINT | §6 | 5 min
Implementation plan | WTERM_INTEGRATION_BLUEPRINT | §7 | 20 min
Performance targets | WTERM_RESEARCH_SUMMARY | §3 | 5 min
Risk mitigation | WTERM_RESEARCH_SUMMARY | §4 | 5 min
React component code | WTERM_GLUE_CODE_REFERENCE | Part 1 | 20 min
Backend WebSocket code | WTERM_GLUE_CODE_REFERENCE | Part 2 | 20 min
USB bootstrap script | WTERM_GLUE_CODE_REFERENCE | Part 4 | 10 min
Test Scenario 1 (latency) | WTERM_FIELD_TESTING_STRATEGY | §2.1 | 10 min
Test Scenario 2 (memory) | WTERM_FIELD_TESTING_STRATEGY | §2.2 | 10 min
Test Scenario 4 (a11y) | WTERM_FIELD_TESTING_STRATEGY | §2.4 | 15 min
Performance baselines | WTERM_FIELD_TESTING_STRATEGY | §3 | 5 min

---

## ✅ Recommended Reading Order

1. **5 min:** WTERM_RESEARCH_SUMMARY.md (overview + decision)
2. **30 min:** WTERM_INTEGRATION_BLUEPRINT.md (skim §1-4, detailed review §2-3)
3. **30 min:** WTERM_GLUE_CODE_REFERENCE.md (Part 1 + Part 2 code)
4. **20 min:** WTERM_FIELD_TESTING_STRATEGY.md (§2.1-2.4 scenarios, §3 baselines)

**Total:** ~85 minutes to full understanding

---

## 🎬 Ready to Implement?

**Step 1:** Read WTERM_RESEARCH_SUMMARY.md (10 min)  
**Step 2:** Read WTERM_INTEGRATION_BLUEPRINT.md §7 (implementation plan)  
**Step 3:** Copy code from WTERM_GLUE_CODE_REFERENCE.md  
**Step 4:** Follow WTERM_FIELD_TESTING_STRATEGY.md for testing  

**Estimated effort:**
- Phase 1 (core): 3 days
- Phase 2 (testing): 4 days
- **Total:** 7 days (fits 2-week TRACK D budget with 1 week buffer)

---

## 🚨 Blockers / Critical Decisions

**None identified.** All major decisions made:
- ✅ Technology stack (wterm + Axum + gnirehtet)
- ✅ Architecture (WebSocket + broadcast channel)
- ✅ Timeline (1.4 weeks)
- ✅ Fallback strategy (ttyd)
- ✅ Accessibility approach (WCAG 2.1 AA)

**Go decision:** ✅ **APPROVED** (see WTERM_RESEARCH_SUMMARY.md §10)

---

## 📋 Checklist Before Implementation

- [ ] Read WTERM_RESEARCH_SUMMARY.md (understand recommendation)
- [ ] Read WTERM_INTEGRATION_BLUEPRINT.md §2-3 (understand APIs + WebSocket)
- [ ] Review WTERM_GLUE_CODE_REFERENCE.md Part 1 (React component)
- [ ] Review WTERM_GLUE_CODE_REFERENCE.md Part 2 (Axum backend)
- [ ] Verify Node.js & Rust toolchain available
- [ ] Verify Android phone + USB cable available
- [ ] Create feature branch (git checkout -b feat/wterm-integration)
- [ ] Schedule Week 2 for testing (WTERM_FIELD_TESTING_STRATEGY.md)

---

## 📞 Contact & Support

**Questions about:**
- **Architecture / Design** → Review WTERM_INTEGRATION_BLUEPRINT.md
- **Code / Implementation** → Review WTERM_GLUE_CODE_REFERENCE.md
- **Testing / Validation** → Review WTERM_FIELD_TESTING_STRATEGY.md
- **Decision / Timeline** → Review WTERM_RESEARCH_SUMMARY.md

**External references:**
- wterm GitHub: https://github.com/vercel-labs/wterm
- gnirehtet GitHub: https://github.com/Genymobile/gnirehtet
- Axum examples: https://github.com/tokio-rs/axum

---

**🟢 Status:** READY TO BUILD  
**🎯 Target:** Phase 1 complete by June 2, Phase 2 by June 5  
**📅 Next Review:** June 2 (after Phase 1 implementation)  

---

**Document Version:** 1.0  
**Last Updated:** 2026-05-29  
**Track Owner:** TRACK D — wterm Observability Prototype  
