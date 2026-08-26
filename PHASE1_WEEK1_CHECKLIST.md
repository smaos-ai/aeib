# PHASE 1 WEEK 1 CHECKLIST (Sep 1-7, 2026)

## HARDWARE & ENV (DO IMMEDIATELY)
- [ ] Order RTX 4060 8GB (local supplier, Ostrov/Plzeň) — delivery by Sep 3
- [ ] Install Python 3.11 + Rust toolchain
- [ ] Clone repo + initialize workspace (Cargo.toml structure)
- [ ] Set up git hooks: Ed25519 signing (PQC), automatic test gate
- [ ] Confirm Claude API key + LangChain/LangGraph SDK
- [ ] Verify FreeToken API access (pip install freeinference)

**KARP CHECKPOINT:** Contact Romana Cernikova — Sep 1 morning email confirming project start

---

## TRACK A: L1 Reasoning (Sep 1-3, 2 days)
- [ ] Read `.claude/notebooks/SMAOS-Complete-Research` (15 min) — policy framework
- [ ] Create test file: `tests/test_l1_policy_routing.py` (failing tests)
  - Test: policy_routing.cite_article_50() → returns exact EU AI Act text
  - Test: policy_routing.route_to_policy() → returns correct policy module
  - Test: policy_routing.enforce_bound() → Claude refuses unbound request
- [ ] Implement `src/l1_reasoning.py` (200-300 lines) + make tests pass
- [ ] Commit: "L1: Policy-bound reasoning with EU AI Act enforcement"

**Output:** `policy_accuracy_baseline.json` (1 report file)

---

## TRACK B: L4 Orchestration (Sep 1-3, 3 days)
- [ ] Create test file: `tests/test_l4_langgraph.py` (failing tests)
  - Test: hotel_pilot.flow() → runs without error, 5+ checkpoint logs
  - Test: hotel_pilot.human_escalation() → pauses at permit gate
  - Test: glass_pilot.state() → returns correct state dict
- [ ] Implement `src/l4_orchestration/` — hotel pilot (200 lines)
  - 3-state machine: REQUEST → EVALUATE → APPROVE/DENY
  - LangGraph checkpoints: JSON logging
- [ ] Implement glass + school pilots (2x100 lines each, same structure)
- [ ] Commit: "L4: LangGraph 3 pilots with checkpoints"

**Output:** `src/l4_orchestration/` + 3 working pilots (no dependencies yet)

---

## TRACK C: L6 Infrastructure (Sep 1-7, ongoing)
- [ ] Test FreeToken: `python -m freeinference benchmark --model=Qwen --tokens=100`
  - Capture screenshot: throughput (39.3 tok/s expected)
  - Log hardware spec: CPU, RAM, GPU
- [ ] Create test: `tests/test_l6_hardware.py`
  - Test: can_run_qwen_on_this_hardware() → True/False
  - Test: get_hardware_tier() → "S" | "F" | "N/A"
- [ ] Integrate CanIRun.ai: screenshot + proof artifact
- [ ] Commit: "L6: FreeToken benchmark + hardware detection"

**Output:** `hardware_benchmark.json` + 2 proof artifacts (FreeToken, CanIRun)

---

## TRACK D: L8 Proof Layer (Sep 1-7, ongoing)
- [ ] Clone agentacct (npm install) — proof receipts
- [ ] Clone unlazy (npm install) — gate enforcement
- [ ] Clone AP2 ledger (git clone) — PQC anchoring
- [ ] Create test: `tests/test_l8_proof.py`
  - Test: create_work_receipt() → returns valid agentacct format
  - Test: sign_ledger_entry() → Ed25519 signature valid
  - Test: verify_immutable() → Git anchor unchanged
- [ ] Implement `src/l8_proof.py` (300-400 lines) — stub integration
- [ ] Commit: "L8: Proof layer scaffolding (agentacct + AP2 + KMS)"

**Output:** `proof_artifacts_checklist.md` (track 7 artifacts as they complete)

---

## TRACK L2 BLOCKER (Sep 1-7, prepare)
- [ ] Read notebook: SMAOS Founding Database Schema (30 min)
- [ ] Design SQL schema: `schema/compliance_timeline.sql` (test-first)
- [ ] Plan pgvector config: embedding size, distance metric
- [ ] DON'T IMPLEMENT YET — L2 is Week 2 critical path

**Output:** None (preparation only; blocks L3 Week 3)

---

## SHARED DELIVERABLES (Week 1 end)
- [ ] All 4 tracks have working tests + passing implementations
- [ ] Git log shows 4 atomic commits (one per track)
- [ ] Update `PHASE1_STATUS.md`: Track A=33%, B=50%, C=50%, D=20%, L2=0%
- [ ] All code <0.1 bugs/100 lines (run `cargo clippy`)
- [ ] No uncommitted changes (git status clean)

---

## GOTCHAS (read before coding)
1. **L2 blocks L3:** Don't start L3 (permit gates) until L2 schema is done. This is the only dependency.
2. **Test-first:** Write test → red → green. Never implement without failing test first.
3. **Single commits:** Each track is ONE commit. No micro-commits.
4. **TDD discipline:** `cargo test` must pass before commit.
5. **KARP timeline:** Sep 16-22 deadline. Week 1 = early traction proof for submission.

---

## NEXT WEEK (Sep 8-14)
- L2: Knowledge layer + pgvector setup (2 wks, critical path)
- L3: Permit gates (depends on L2; starts when L2 schema done)
- L5: MCP servers scaffolding (start Week 2, 2 wks)
- Continue L4, L6, L8 integration

---

## COMMAND SHORTCUTS
```bash
# Test single track
cargo test --package siss-l1-reasoning
cargo test --package siss-l4-orchestration

# Test all
cargo test

# Lint
cargo clippy

# Commit
git add -A && git commit -m "L1: Policy-bound reasoning..."

# Week status
git log --oneline --since="1 week ago"
```
