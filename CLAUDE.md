# CLAUDE.md — SMAOS Phase 1 + Correctness Doctrine v2.1
**Execution Mode: Parallel Tracks A-D, TDD-Disciplined, Sep 1, 2026 - May 31, 2027**  
**Doctrine Version: 2.1 (Hands-On-Silicon Invariant deployed Aug 31, 2026)**

---

## RULE 0: HANDS-ON-SILICON INVARIANT ⚡ [SUPREME OVERRIDING RULE]

**No work is complete until manually tested by a human with their hands on the silicon.**

This is the non-negotiable foundation of all other rules. Passing automated tests + clean linters ≠ working feature. AI systems must verify their own work end-to-end in the actual execution environment **before claiming completion**. This rule overrides all other processes, guidelines, and optimizations.

### Why This Rule Exists
Earlier in Phase 1, this codebase experienced repeated failures:
- Feature flagged "complete" by automated tests but buttons didn't work in browser
- Components claimed fixed despite hook-order errors that appeared only on user interaction
- Signatures marked "verified" but displayed incorrectly in UI due to payload structure mismatch
- The root cause: **tests verified logic in isolation; they did not verify the actual user experience**

**Lesson:** Automated tests are verification of *implementation logic*. Manual testing is verification of *actual product behavior*. Both are required. Neither is optional.

### MMV Protocol: Mandatory Manual Verification (5 Steps)

Every feature, bug fix, and integration **must** complete these steps **in the actual browser/device** before being marked done:

1. **Physical Isolation Verification** (Sovereignty + Security)
   - Open DevTools → Network tab → set throttle to "Offline"
   - Confirm the feature still responds to valid local interactions
   - If it pings external services, confirm they fail gracefully (no silent false success)
   - Reason: Prevent accidental internet dependencies in "offline-first" systems

2. **Click-Every-Button Sweep** (Completeness)
   - Literally click or interact with every interactive element in the feature
   - For workflows: follow the happy path, then all sad paths
   - For UI state: verify visibility/visibility toggling, form validation, error states
   - Document: which buttons exist, what each does, what state changes result
   - Reason: Automated tests often skip UI interaction states that matter to users

3. **Visual State Validation** (UX Correctness)
   - Verify every state change is **visually distinct** (color, animation, text, layout)
   - Confirm no "silent failures" (action taken with no visual feedback)
   - For async operations: verify loading states, completion states, error states are visible
   - Reason: "The feature works" ≠ "The user knows the feature worked"

4. **End-to-End Journey Walkthrough** (Integration)
   - Execute a complete user story: Intent → Classification → Execution → Authorization → Ledger
   - Verify data flows correctly from left pane → center pane → right pane
   - Confirm cryptographic proofs (signatures, hashes) are real and displayed correctly
   - Reason: End-to-end flows expose interface mismatches and timing issues tests don't catch

5. **Console Hygiene** (Debugging Trust)
   - Open DevTools Console, refresh, walk through feature again
   - Confirm: no errors, no warnings, no undefined errors, no failed network calls
   - If warnings appear: document why they exist + whether they're acceptable
   - Reason: Console warnings are often harbingers of latent bugs; silence is golden

### Enforcement

**Claim "complete" only when all 5 steps pass on the actual device.** If you cannot access the device (e.g., running a pure backend service), substitute with:
- Automated integration test that exercises the complete flow (not just unit logic)
- Peer review from someone with device access + their sign-off in git commit
- Explicit documentation: "tested via [integration test name]" + evidence URL

**Violation consequence:** If you mark work "complete" and MMV fails, you revert the commit and redo the work with the correct process. Repeated violations trigger a review with project leadership.

---

## PHASE 1 THESIS

Agent = Model + Harness. **Harness is the moat.** Governance Membrane (proof layer) is competitive advantage.  
This phase delivers: Natural-Language Harness (1500+ lines) + 3 pilots + Annex IV dossier + KARP 120k voucher.

## CRITICAL DATES (immovable)

- **Sep 1, 2026:** Phase 1 starts (Monday)
- **Sep 16-22, 2026:** KARP voucher submission deadline (Romana Cernikova)
- **May 31, 2027:** Phase 1 delivery date (triggers Phase 2 + BIC Plzeń 1M)
- **Dec 2, 2027:** Annex III compliance (hotels/spas) — 3 months after Phase 1
- **Aug 2, 2028:** Annex I compliance (glass/auto) — 14 months after Phase 1

## PARALLEL EXECUTION (4 tracks, all simultaneous)

**TRACK A: Memory & Ingest (L1, L2, L3)**
- L1 Reasoning: Claude SDK policy routing (2 wks, 200-300 lines)
- L2 Knowledge: pgvector + BM25 + RRF (2 wks, 400-500 lines)
- L3 Permit Gates: Tool registry + enforcement (2 wks, 300-400 lines)
- Owner: Engineer (solo, no blocking)
- Deliverable: SQL dump + pgvector CSV + policy accuracy report
- **MMV Checkpoint:** L3 gate enforcement tested end-to-end: malicious tool call → caught + logged

**TRACK B: Orchestration & Communication (L4, L5)**
- L4 Orchestration: LangGraph 3 pilots (3 wks, 600-800 lines)
- L5 Communication: 4 MCP servers (2 wks, 400-500 lines)
- Owner: Engineer (solo, no blocking)
- Deliverable: 3 LangGraph pilots (hotel/glass/school) + MCP servers live
- **MMV Checkpoint:** Each pilot: submit intent → classify → execute → authorize → ledger entry (manual click-through required)

**TRACK C: Infrastructure (L6)**
- FreeToken serve validation (2 wks, 100-200 lines)
- Hardware benchmarking: Qwen 39.3 tok/s on 8GB
- CanIRun.ai integration (screenshot proof)
- Owner: Engineer (solo, no blocking)
- Deliverable: FreeToken benchmark + hardware detection
- **MMV Checkpoint:** Run `npm run dev`, open browser, verify /health endpoint returns real metrics (not mocked)

**TRACK D: Proof Layer (L8, L7)**
- L8 Proof: agentacct + unlazy + AP2 ledger + KMS (3 wks, 300-400 lines)
- L7 RAGAS: 50-question golden set (ongoing, target 87%+ accuracy)
- Owner: Engineer (solo, no blocking)
- Deliverable: Immutable proof trail + RAGAS baseline report
- **MMV Checkpoint:** Create receipt → open DevTools Console → click "Verify" button → confirm signature validation passes live on-screen

## BLOCKING DEPENDENCY (only one)

```
L2 Knowledge (Week 2) → L3 Permit Gates (Week 3+)
Reason: L3 needs policy rules from L2 to test gate enforcement
```

## INTEGRATION PHASES

- **Weeks 5-8:** Merge tracks (L1→L2→L3→L4→L5→L6→L8→L7)
- **Weeks 9-10:** Code quality + RAGAS 87%+ target + **MMV sweep of all 3 pilots**
- **Weeks 11-12:** Annex IV dossier + KARP submission package

## DELIVERABLES (by May 31, 2027)

### MUST HAVE (non-negotiable for Phase 2)

1. **Natural-Language Harness** — 1500+ lines, all 8 layers, readable, testable
   - *MMV:* Run hotel + treasury pilots end-to-end, all steps clickable and working
2. **Database schema** — SQL dump + pgvector CSV (compliance_timeline, governance_risks, tech_stack, evidence_by_process)
   - *MMV:* Query pgvector, confirm <100ms latency on actual machine
3. **1 working pilot** — Hotel credit scoring (full L1→L8 flow, 50+ logged actions)
   - *MMV:* Submit hotel intent → block triggered → Authorize → ledger written (manual click, real signature, real ledger row)
4. **RAGAS 50Q baseline** — 87%+ accuracy on compliance questions
   - *MMV:* Run golden set, screenshot console with passing test count
5. **Annex IV 9-section dossier** — Auto-generated, PDF + JSON + KMS signed
   - *MMV:* Open PDF, verify all 9 sections populated; verify KMS signature in browser DevTools
6. **7 proof artifacts** — CanIRun, FreeToken, Is Agentic, agentacct, unlazy, RAGAS, AP2 ledger
   - *MMV:* For each: screenshot the actual proof output (not a mock message claiming it exists)

### STRETCH (for Series A narrative)

- 3 working pilots (hotel + glass + school) **— All tested via MMV Protocol**
- Full Is Agentic A+ report **— With actual screenshots of tests passing**
- EU Database pre-registration number

## QUALITY GATES (before shipping)

**All gates include automated test evidence AND manual verification evidence:**

- [ ] Harness code: <0.1 bugs per 100 lines (static analysis clean) **+ console hygiene on all pilots**
- [ ] Database: pgvector latency <100ms on compliance queries **+ screenshot from real query on target hardware**
- [ ] RAGAS: 87%+ accuracy on 50-question golden set **+ vitest screenshot**
- [ ] Pilots: hotel L1→L8 flow runs without error, all 7 proofs captured **+ recorded click-through walkthrough**
- [ ] Annex IV: 9 sections auto-filled, KMS signature verified **+ browser verification button click captured**

## WORKFLOW: FEATURE DEVELOPMENT

### Phase 1: Planning
- Define user story: "As [user], I can [action], so [benefit]"
- Identify MMV checkpoints: which user interactions must be tested manually?
- List test scenarios (happy path + sad paths)

### Phase 2: TDD Implementation
- Write failing test (unit + integration)
- Implement code until test passes
- Run full suite locally, confirm clean

### Phase 3: Integration
- Merge to main (atomic commit: test + code)
- Run CI/CD pipeline
- Confirm all checks pass

### Phase 4: **MANDATORY MANUAL VERIFICATION** ⚡
- Open browser, point to `http://127.0.0.1:5173`
- Execute MMV Protocol (all 5 steps)
- Document results in commit message
- If any step fails: revert, debug, fix, re-test

### Phase 5: Demo + Sign-Off
- Record a screencast of complete feature (all 5 MMV steps)
- Share with stakeholders
- Confirm: "Yes, this is the behavior we wanted"

**Handoff criteria:** Code merged + MMV complete + screencast recorded

## WORKFLOW: BUG FIX

### Discovery Phase
- User reports: "Feature X doesn't work"
- Reproduce manually in browser
- Take screenshot of broken state

### Root-Cause Analysis
- Check DevTools Console for errors
- Read relevant code paths
- Write a failing test that captures the bug

### Fix + Verify
- Implement fix
- Confirm test passes
- **Execute MMV Protocol** (the original bug scenario + all related interactions)
- If MMV fails: fix is incomplete

### Acceptance
- User or peer clicks through fixed feature
- Confirms: "Now it works"
- Sign-off in commit message

## WORKFLOW: HIGH-STAKES INTEGRATION (Cryptographic, Regulatory, Financial)

**Extra rigor** for changes to:
- Signature generation/verification
- Regulatory compliance logic
- Capital adequacy calculations (CET1 ratio)
- Ledger writes
- Permission gates

### Process (Mandatory)
1. **Threat Model** (15 min)
   - Attacker tries to forge signature → Can they?
   - False compliance signal → Can they trigger it?
   - Malicious ledger entry → Can they write it?
   - Document the three attack scenarios + mitigations

2. **Unit Tests** (Adversarial)
   - Test happy path (valid input → correct output)
   - Test attack scenarios (malicious input → rejected with reason)
   - Test edge cases (boundary values, empty inputs, overflows)
   - Coverage target: >95% on high-stakes code

3. **Integration Test** (End-to-End)
   - Complete workflow: User action → Cryptographic proof → Ledger write → Verification
   - Verify at each stage: data format correct, signatures validate, ledger row exists

4. **Manual Verification** ⚡
   - Execute the integration scenario in browser
   - Open DevTools → Console, Crypto, Network tabs
   - Walk through MMV Protocol
   - Confirm: signature verification button works live, ledger displays correctly, no console errors

5. **Peer Review** (Mandatory)
   - Second engineer reviews: threat model + code changes
   - Reviews MMV evidence: does the screenshot actually show it working?
   - Sign-off: "Reviewed. Threat model mitigated. MMV passed. Approved for merge."

6. **Merge + Retroactive Incident Review**
   - After 1 week in production: did any attack scenario actually occur? Log it.
   - After 1 month: incident retro — did the mitigations work? Update threat model.

## TESTING REQUIREMENTS

### Level 1: Unit Tests (Pure Logic)
- **When:** Every function, every calculation
- **How:** Vitest + chai, focus on edge cases
- **Coverage target:** >80% on business logic
- **MMV:** Not required (logic verified in isolation)
- **Example:** `classifyIntent({ amount: 100M })` → severity='block' ✓

### Level 2: Integration Tests (Component + State)
- **When:** Feature workflows that span multiple components
- **How:** Playwright or `@testing-library/react` + vitest
- **Coverage target:** >60% on UI interaction paths
- **MMV Required:** Yes — integration test must exercise the complete user flow
- **Example:** Submit intent → Classify → Show block badge → Click Authorize → Sign receipt
- **Evidence:** Test name + passing output + screenshot of test execution

### Level 3: Manual Verification (Real Browser + Device)
- **When:** Every merged feature (per RULE 0)
- **How:** MMV Protocol (5 steps, executed on actual hardware)
- **Coverage:** 100% of user-facing workflows
- **Evidence:** Console screenshot (clean, no errors) + click-through walkthrough recorded
- **Failure recovery:** If MMV fails, revert commit immediately

**CRITICAL:** No feature is "done" without Level 3. Levels 1 + 2 prove the code works; Level 3 proves the **feature works**.

## KARPATHY CODING RULES (apply to Phase 1)

1. **No over-engineering.** 1500 lines harness is final size. No abstractions beyond what pilots require.
2. **No drive-by refactoring.** Only modify code directly related to the 8 layers. Don't clean up adjacent.
3. **Test-First (TDD).** Write failing test BEFORE implementation. `npm run test` → red, then green.
4. **Comments only for WHY.** Never explain WHAT (well-named code does that). Only hidden constraints, workarounds.
5. **No backwards-compatibility hacks.** Delete unused code completely.

## TOOL DISCIPLINE

- **Read before Edit.** Always read a file first, then edit it.
- **Git commits are atomic.** One feature/fix per commit. Include test + implementation.
- **No git reset --hard.** Suggest reversible moves (stash, revert, new branch).
- **AP2 ledger anchoring.** Every commit signed with Ed25519 (PQC). Digest in public git.

## SOVEREIGN CONSTRAINTS (Non-Negotiable)

### Local-First Invariant
- No data persists outside `/tmp/agentacct.db` without explicit user approval
- No cloud sync, no telemetry, no external HTTP calls except where documented
- Default: fail closed (no network = feature still works on cached data)

### Cryptographic Audit Trail
- Every decision (authorize/veto/kill-switch) → signed receipt
- Receipt → ledger row → git commit digest
- Enables regulatory post-mortem: "Prove this decision was authorized"

### Fail-Closed Defaults
- Pre-execution gate: block-by-default, require human authorize to proceed
- Signature verification: reject if unverifiable (don't fall back to "unsigned")
- Permission check: deny-by-default, explicit allow only

### Human Gates (Layer 7)
- High-risk decisions → human review + signature required
- "High-risk" = CAR-impacting (Basel III) or PII-processing (Annex III)
- System waits for human; never proceeds without explicit authorization

## SYNTHESIS & INSPIRATION

This doctrine synthesizes best practices from:

- **Google SRE (2016-2024):** Blameless postmortems, fail-closed defaults, test reliability
- **Karpathy TDD (2023-2025):** Test-first development, ruthless simplicity, real verification
- **Alibaba Constitutional Testing (2022):** Architectural invariants precede functional tests; test your assumptions about the system before testing the code
- **DeepSeek Adversarial Pairs (2023-2025):** Writer/Attacker/Verifier triangle; security testing as core development practice
- **Huawei Zero-Trust CI (2022):** Cryptographic test attestation; every test run is signed and immutable
- **Shanghai AI Lab Regression Graphs (2024):** Track fix attempts; detect circular patterns (fixing A breaks B breaks A again)

**Hands-On-Silicon Invariant:** Unique to SMAOS Phase 1 — developed through lived experience in this codebase in Aug 2026.

## TRACKING (weekly)

- **Monday:** Update `/PHASE1_STATUS.md` with progress (Track A-D completion %)
- **Wednesday:** Code review (static analysis, test coverage, MMV evidence for merged PRs)
- **Friday:** Integration checkpoint (all tracks merge-tested, MMV walkthrough recording)

## SUCCESS CRITERIA (May 31, 2027)

- ✅ Harness ships with 1500+ clean lines **+ console hygiene evidence**
- ✅ KARP voucher approved (120k CZK in) **+ KARP submission signed**
- ✅ BIC Plzeń application ready (1M CZK next) **+ BIC financial statement attached**
- ✅ Regulatory timeline locked (Annex III Dec 2027, Annex I Aug 2028) **+ calendar invite confirmations**
- ✅ Series A narrative ready (proof artifacts in data room) **+ screenshot evidence of all 7 artifacts**

## NEXT PHASE (BIC Plzeń, Jun-Dec 2027)

- Egress controls (2-3 wks, CISO appeal)
- Intent-verified delegation (4-6 wks, OWASP ASI01 defense)
- 3 full pilots in production **— MMV Protocol for each in live environment**
- EU Database registration + CE marking

---

## SESSION MANAGEMENT: RULE OF TWO

To prevent context overload and maintain clarity:

**Rule of Two (per session):**
- Max 2 open tasks at once (focus over parallelism)
- Max 2 major feature branches in flight (reduces merge conflicts)
- Max 2 "pending review" PRs before blocking new work (forces closure)

**Rationale:** When too many things are in-flight, MMV Protocol gets skipped under time pressure. Better to ship 2 things perfectly than 5 things half-tested.

---

## ENFORCEMENT CLAUSES

### Violation: Claiming Work Complete Without MMV

If you mark a feature "done" and it fails MMV, the consequence is:
1. Immediate revert of commit
2. Documentation of what failed (attach screenshot of broken state)
3. Redo the work with correct process
4. Update git log with note: "Redone after MMV failure: [reason]"

**Repeated violations (3+ in a month):** Mandatory retrospective with project leadership.

### Violation: Silent Console Errors

If merged code produces console errors and MMV didn't catch them:
1. Immediate revert of commit
2. Add console-check step to MMV Protocol (already there; recheck procedure)
3. Fix code + re-test
4. Commit with note: "Fixed console error [message]"

### Violation: Fake Data in Production Paths

If any signature/metric/status is hardcoded or randomly generated in merged code:
1. Immediate revert of commit
2. Implement real computation (cryptographic signing, actual metrics, real state)
3. Verify with MMV Protocol before re-merge
4. Future commits flagged as "requires console hygiene check"

---

## APPENDIX: QUICK REFERENCE

### Before You Claim "Complete"
- [ ] Automated tests pass (`npm run test`)
- [ ] Linter clean (`npm run lint`)
- [ ] Commit message references MMV evidence
- [ ] Browser test complete (MMV Protocol 5 steps)
- [ ] Console clean (no errors, no warnings)

### If You're Blocked
1. Check BLOCKING DEPENDENCY section (L2 → L3 only)
2. Check RULE OF TWO (2 tasks max at once)
3. Post blocker in Monday standup + git branch note
4. Suggest workaround or parallel track

### If You're Unsure About Testing
- Unit test = code logic correct? (Vitest) → No MMV needed
- Integration test = workflow correct? (Playwright) → MMV needed
- Manual test = user happy? (Browser click) → MMV required
- **Always use all three for high-stakes code**

### If MMV Fails
1. Take screenshot of broken state
2. Revert commit immediately
3. Read error message + console log
4. Fix root cause (not a band-aid)
5. Repeat all 5 MMV steps before re-merge

---

**Doctrine Deployed:** Aug 31, 2026  
**Version:** 2.1 (Hands-On-Silicon Invariant)  
**Last Updated:** Sep 2, 2026  
**Next Review:** Oct 2, 2026 (after Week 4 of Phase 1)
