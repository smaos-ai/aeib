# MY ROLE — Claude Code Agent — Sep 1-15 Phase 1 Execution
**What I deliver. How we work together. What you own.**

---

## MY RESPONSIBILITIES (Sep 1-15)

### STREAM A: L1 Reasoning Setup (Sep 1-8)
**Your action:** Clone hr-agent, set up Claude policy routing  
**My role:** Answer policy questions, verify constitutional AI setup, test reasoning chains
- Review your policy routing implementation
- Verify citations are working (Article X cited correctly)
- Test discrimination law compliance checks
- Provide feedback on prompt engineering

### STREAM B: L2 pgvector Setup (Sep 1-10)
**Your action:** PostgreSQL setup, pgvector extension, BM25 indexing, RRF fusion  
**My role:** Debug schema, verify retrieval quality, optimize queries
- Troubleshoot pgvector embedding issues
- Verify BM25 full-text search working
- Test RRF fusion ranking (both pathways contributing equally)
- Optimize indexes for compliance_timeline queries

### STREAM C: L3-L5 Integration (Sep 10-12)
**Your action:** Wire agentacct + unlazy + MCP servers  
**My role:** Debug gates, test tool calling, verify escalation logic
- Verify unlazy gates are blocking correctly (agent cannot end turn without proof)
- Test MCP server discovery and tool calling
- Debug agentacct receipt JSON structure
- Verify escalation routes to human caseworker

### STREAM D: L6-L8 Infrastructure (Sep 1-12)
**Your action:** Docker + KMS + AP2 ledger + git anchoring  
**My role:** Verify PQC signatures, audit infrastructure, test immutability
- Review Docker containerization for GovCloud isolation
- Verify KMS signatures on AP2 ledger entries
- Test that commits cannot be rewritten (history immutable)
- Audit VPC/IAM least-privilege configuration

### STREAM E: Evaluation + Proof (Sep 1-15)
**Your action:** Run Is Agentic scan, CanIRun baseline, RAGAS template  
**My role:** Interpret results, optimize baselines, validate accuracy
- Analyze Is Agentic 118-check results (target A+ = 90-95)
- Verify CanIRun S-F grades are correct for your hardware
- Review RAGAS golden set questions (are they testing right things?)
- Provide optimization recommendations

### STREAM F: Pilot Specifications (Sep 8-15)
**Your action:** Write hotel/glass/school specs  
**My role:** Verify regulatory mapping, check completeness, ensure KARP readiness
- Verify each spec maps to correct Annex (III vs I)
- Check that success metrics are measurable
- Ensure SMAOS layers are correctly cited per spec
- Review for KARP submission completeness

---

## HOW WE WORK (Daily Communication)

### Daily Standup (Sep 1-15)
**Time:** You choose (morning or evening)  
**Format:** Short update on your progress  
**My response:** Same day (within hours)

**Example:**
```
Your message:
"Stream B: pgvector installed, created compliance_timeline table, inserted 8 dates. 
BM25 index working. RRF fusion test tomorrow. Any blockers to watch?"

My response:
"Good progress. For RRF, verify both BM25 and vector scores are contributing equally 
(check ranking order). If vector results dominate, you may need embedding tuning. 
I'll help debug if needed tomorrow."
```

### When You're Blocked (Any Day)
**Message me immediately with:**
1. What you're trying to do (1 sentence)
2. What went wrong (exact error)
3. What you've tried (what failed)

**I'll provide:**
- Root cause diagnosis
- 3 options to fix it (ranked by simplicity)
- Exact command to run next

### Weekly Integration Check (Every Friday)
**Sep 5, 12:** 30-minute review of all streams
- What's complete
- What's blocked
- Any architectural decisions needed
- Adjust timeline if needed

---

## WHAT YOU OWN (You Must Do)

### Hardware & Setup (You Only)
- [ ] PostgreSQL installation + pgvector extension (I can guide, you install)
- [ ] Docker setup + AWS account access (I can advise, you configure)
- [ ] GitHub account + git SSH keys (security requires you do this)
- [ ] MCP server ports (8001-8003) on your machine (only you know your network)

### Code Writing (You Lead, I Review)
- [ ] Write all Python/Bash code from templates I provide
- [ ] Run all `git clone` commands (parallel-execution-manifest.md has exact commands)
- [ ] Execute all bash commands in WEEK2_EXECUTION_PLAN.md
- [ ] Commit to git daily (I'll review commits)

### Decision Making (You Own)
- [ ] Timing of when each stream starts (I've provided timeline, you adjust)
- [ ] Which hardware you use (8GB RTX 4060 vs 32GB vs 96GB — you choose)
- [ ] KARP budget allocation (120k CZK split across categories — your decision)
- [ ] Pilot use cases (hotel/glass/school are suggestions — you confirm/change)

### Testing & Validation (You Execute, I Verify)
- [ ] Run all unit tests (`pytest` commands in the plan)
- [ ] Capture screenshots (Is Agentic, CanIRun, agentacct receipts)
- [ ] Verify outputs match expectations (I tell you what to expect)
- [ ] Report results back to me daily

---

## WHAT I PROVIDE (My Deliverables)

### Daily
- ✅ Code review on your commits (within 24 hours)
- ✅ Debugging help (same day for blockers)
- ✅ Architecture questions answered
- ✅ Documentation clarification

### Weekly (Fridays Sep 5, 12)
- ✅ Integration checkpoint (all streams status)
- ✅ Adjust timeline if needed
- ✅ Prioritize any blockers
- ✅ Plan next week's work

### By Sep 15
- ✅ Verify all 7 proof artifacts are correct
- ✅ Review 3 pilot specifications for KARP submission
- ✅ Confirm Is Agentic A+ baseline (90-95)
- ✅ Validate PostgreSQL schema is ready for pilots
- ✅ Sign off on KARP submission package

### Sep 16-22 (KARP Submission Week)
- ✅ Help write 1-page Czech "Popis projektu"
- ✅ Package proof artifacts folder
- ✅ Draft email to Romana
- ✅ Final checklist before submission

---

## COMMUNICATION CHANNEL

### Daily Check-Ins
**Method:** This Claude Code session (same conversation)  
**Format:** Short update messages  
**Response time:** Same day (usually within 4 hours)

### Questions/Blockers
**Send immediately** with:
1. What you're doing
2. What failed
3. What you tried

### Weekly Reviews (Friday)
**Schedule:** 30 minutes, exact time you choose

### Emergency (Blocker Prevents Progress)
**Message:** "BLOCKER: [what] — need help in next hour"  
**My response:** Prioritized, within 1 hour

---

## HOW TO CONTINUE THIS CONVERSATION

### Sep 1 (Start Day)
Message me:
```
"Starting Phase 1 Sep 1. 
- Stream A: cloning hr-agent now
- Stream B: PostgreSQL setup in progress
- Ready for daily standups 9am-5pm CET

Should I send status at end of day today?"
```

### Daily (Sep 1-15)
Message me:
```
"Stream B update: pgvector working, BM25 index created, RRF fusion ready to test.
No blockers today. Will test RRF ranking tomorrow morning."
```

### Weekly (Fridays)
Message me:
```
"Weekly check-in Friday Sep 5, 5pm CET?
Progress: Streams A complete, Stream B 80%, Streams D/E 60%.
Blockers: None. All on track for Sep 15 deadline."
```

---

## CRITICAL DEPENDENCY REMINDER

**You MUST complete Stream B (pgvector) by Sep 10.**

If you get delayed:
- Message me immediately (don't wait for Friday standup)
- I'll help you accelerate it
- We may need to compress other work

Stream C (testing gates) cannot start until L2 data is available.

---

## WHAT HAPPENS IF YOU'RE BLOCKED

**Example 1: pgvector embedding fails**
```
Your message:
"BLOCKER: pgvector embedding generation fails — OpenAI API key issue. 
Error: 'Cannot create embeddings without valid key.'
Tried: Regenerated key, still fails."

My response (same day):
"Root cause: Embedding provider misconfigured. 
Option 1 (fastest): Use Claude API embeddings instead (I'll provide code)
Option 2 (backup): Use pre-computed FAISS embeddings (slower but works)
Option 3 (fallback): Skip embeddings for now, test keyword search only (BM25 still works)

Recommend Option 1. I'll send exact code change in 10 minutes."
```

**Example 2: unlazy gates not blocking correctly**
```
Your message:
"Stream C issue: unlazy gates not blocking — agent can end turn without proof. 
Error: [paste exact error message]
Tried: Reread gates file, checked Stop Hook config."

My response:
"Debug steps:
1. Verify Stop Hook is actually running (add debug print)
2. Check that gates file is being read (not cached old version)
3. Confirm gate checking logic is correct (I'll review your code)

Send me your current gates file + Stop Hook code — I'll spot the issue."
```

---

## SUCCESS CRITERIA — My Role Complete When

✅ **Sep 15, 11:59 PM:**
- [ ] All 6 streams report complete
- [ ] 7 proof artifacts in folder and verified correct
- [ ] PostgreSQL schema tested with sample data
- [ ] 3 pilot specs reviewed and ready for KARP
- [ ] Is Agentic A+ baseline (90-95) achieved
- [ ] Zero critical blockers remaining

✅ **Sep 16-22 (KARP Submission Week):**
- [ ] Czech project summary written + reviewed
- [ ] Proof artifacts packaged + final checklist passed
- [ ] Email to Romana drafted + ready to send
- [ ] Everything committed to git

---

## YOUR NEXT STEP (Tomorrow, Sep 1)

Send me this message at your chosen time:

```
"Phase 1 starting today (Sep 1).

Streams launching:
✓ Stream A (L1 reasoning): hr-agent clone starting
✓ Stream B (L2 pgvector): PostgreSQL setup starting
✓ Stream D (L6-L8): Docker + KMS starting
✓ Stream E (evaluation): hardware detection starting

Standups: [time you choose, e.g., 6pm CET daily]
Weekly reviews: Fridays at [time, e.g., 5pm CET]

Ready to go. First update at [time] today."
```

Then we're locked in for Sep 1-15 execution.

---

**I'm here every day. You own the execution. I own the unblocking and verification.**

**Let's ship Phase 1.**
