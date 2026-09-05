# Skill: /decide — NotebookLM-Powered Strategic Synthesis

## Trigger
User types: `/decide [question]`

## Purpose
Transform strategic questions into decision-gated, covenant-aligned implementation plans by synthesizing project state, NotebookLM context, and real-time market data.

## Context Assembly (Auto-Pinned)
1. Read `@STATE.md` → Phase, Next Step, Tests, Critical Gates
2. Read `@EXEC_LOG.json` → Latest Merkle root, covenant audit trail
3. Read `@CLAUDE.md` → Protocol v2 guardrails, personal mode flags, patent strategy
4. Query `notebooklm://SMAOS-Strategy` → Market position, patent timeline, investor narrative, hardware recommendations

## NotebookLM Query Template

```
Synthesize all information to answer: [user's /decide question]

LOCKED CONTEXT:
- Current phase: [from STATE.md]
- Last commit: [from STATE.md]
- Merkle root: [from EXEC_LOG.json]
- Patent deadline: June 2 EOD
- Demo date: Israel, June 3–5
- Series A timeline: Post-Israel
- Execution mode: [from CLAUDE.md: personal/multi-agent]

PRIORITIZE OUTPUT BY:
1. Patent filing deadline impact
2. Demo readiness impact (Prague, Israel)
3. Series A narrative impact (post-trip)

OUTPUT FORMAT:
✅ GO / ⚠️ CONDITIONAL / ❌ NO-GO decision gate
📋 Implementation plan (ordered, timeboxed, test-gated)
🔒 Covenant alignment check (1%/99%, fail-closed, local-first)
📎 Source links (NotebookLM entries, live 2026 market data if available)
⏱️ Time estimate + resource requirements
```

## Output Constraints
- **Length:** <500 tokens (sovereign, token-smart)
- **Format:** Decision gate first (✅/⚠️/❌), then plan, then covenant check
- **Completeness:** Include all 5 sections above; no abbreviations
- **Audit:** Append execution hash to `EXEC_LOG.json` (Merkle-rooted, private)

## Personal Mode Guardrails
- If `SMAOS_MODE=personal`: Use local NotebookLM export only; skip cloud escalation
- If `SMAOS_CLOUD_ESCALATION=true`: Allow live market data fetch (opt-in, logged)
- All outputs Merkle-rooted + Ed25519-signed (private audit trail)
- Never auto-execute; human (you) approves final plan before implementation

## Usage Examples

```
/decide "Should we integrate C2PA before Israel demo or after?"
→ Decision gate + implementation plan prioritized by demo readiness

/decide "What is the minimal viable patent claim set for provisional filing?"
→ Decision gate + 3-claim outline (RCE, Capsule, IVB) prioritized by USPTO defensibility

/decide "How do we frame Series A narrative around personal-mode covenant proof?"
→ Decision gate + dual-deck strategy (Fortress vs. Platform) prioritized by investor fit

/decide "What is the unified next-step roadmap before Israel trip?"
→ Full 3-phase synthesis: patent → demo → narrative, with all gates and deadlines
```

## Implementation Notes
- **Trigger fires:** User types `/decide [question]`
- **Latency:** ~30–60s (NotebookLM query + synthesis)
- **Fallback:** If NotebookLM unavailable, use local `~/.smaos/notebook_exports/strategy.md` export
- **Logging:** Every `/decide` execution logged to private `EXEC_LOG.json` with Merkle proof

## Covenant Alignment
- ✅ Fail-closed: Output includes covenant check; human approves before execution
- ✅ Local-first: NotebookLM data sourced from local export; cloud is opt-in
- ✅ 1%/99%: All decisions logged privately; extraction logged separately
- ✅ Protocol v2: Implementation plan includes diff-only, @file scoping, test gates
- ✅ Cryptographic audit: Execution hash → Merkle root → `EXEC_LOG.json`
