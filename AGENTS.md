# SMAOS / AEIB Agent Directives & Epistemic Boundaries

## 1. STRICT EPISTEMIC & LINGUISTIC BOUNDARIES
You are operating under a strict epistemic lock.
- **PERMITTED WORDS:** "observed", "tested", "evaluated", "configured", "under the stated model", "prototype", "scaffold".
- **BANNED WORDS:** "guaran[t]eed", "proven universal[l]y", "bullet[p]roof", "enterprise-[g]rade", "production-[s]afe", "100% [s]ecure".
- **VIOLATION:** If you use a banned word in code comments, docs, or output, you must immediately self-correct and rewrite the sentence.

## 2. ZERO-MOCK & CRYPTOGRAPHIC PURITY
- **NO FAKE CRYPTO:** Never use `mock_signature`, `stub_hash`, or hardcoded hex strings to simulate cryptographic operations. All signing must use `cryptography.hazmat` (Ed25519) or equivalent real primitives.
- **NO BYPASS GATES:** Never write code that returns `True` or bypasses a check to make a test pass. If a test fails, the logic is wrong; fix the logic, do not mock the assertion.
- **JCS COMPLIANCE:** All JSON canonicalization must strictly follow RFC 8785 (UTF-16 code unit sorting, no extraneous whitespace).
- **NO RANDOMIZED PYTHON `hash()` FOR DIGESTS:** Never use Python's built-in `hash()` (salted by `PYTHONHASHSEED`) for `CAID`, `bio_caid`, or provenance digests. Always compute `hashlib.sha256(encode_jcs(payload)).hexdigest()`.
- **POST-APPROVAL SUBSTITUTION BINDING:** Every `EO1` approval grant must cryptographically bind `canonical_act_digest`, `tool_id`, `capability_id`, and `subject_agent_id` (`arXiv:2609.38266v1`).
- **TEST-GATED ITERATIVE REPAIR:** Never run open-loop iterative LLM code repair unless triggered by a deterministic failing test or static gate (`arXiv:2609.10123v1`), and bound repair loops to `B <= 3` before escalating (`arXiv:2608.29460v3`).
- **FAIL-CLOSED GROUNDING & INTEGER BPS IN JCS:** Never return 1.0 (HEALTHY) on empty `context_spans` or blank output (fail-open vacuous truth), and never pass raw `float` scores into RFC 8785 `encode_jcs`; always fail closed with `0 bps` (`HALTED_EMPTY_CONTEXT_OR_OUTPUT`) and sign integer basis points (`0..10000`).
- **DIR OUT-OF-SCOPE BISECTION:** When a subsystem requires unavailable host capabilities or an external micro-project, isolate it via `DirAntiScaffoldAndScopeBisector` into a signed `ParallelOutOfScopeTrackSpec` (`ERR_CAPABILITY_UNAVAILABLE_ON_HOST`) rather than writing an inline mock or multi-statement `return True` stub.
- **CONTEXT & TOKEN CONSERVATION (CLI REDIRECTION):** Redirect verbose CLI outputs, `uv run` package installation logs, and raw API JSON payloads to `/tmp/` (`uv run --quiet ... > /tmp/out.json 2>/dev/null`) and parse only compact summaries into tool stdout. Archive bulky tool observations via `ContextCartArchivalForgettingEngine` (`arXiv:2610.10590v1`).

## 3. SUPPLY CHAIN & NETWORK ISOLATION
- **NO UNVETTED DEPENDENCIES:** Do not add new `pip` or `cargo` dependencies without explicit user approval. Prefer Python stdlib or existing locked dependencies.
- **ZERO EGRESS:** Never write code that makes outbound HTTP requests to external APIs (e.g., OpenAI, Anthropic, public telemetry) unless explicitly building the isolated `research.py` module.
- **NO GLOBAL MODIFICATIONS:** Never modify `~/.ssh/config`, global `git config`, or host network routing without explicit, step-by-step user authorization.

## 4. MANDATORY VERIFICATION LOOPS
Before declaring any task complete, you MUST execute the local verification harness:
1. `python3 compliance/check_zone_boundary.py` (Enforces Zone 1 / Zone 2 import purity)
2. `python3 compliance/ast_purity.py .` && `python3 compliance/no_mock_enforcer.py` (Zero-mock AST purity)
3. `python3 compliance/claim_integrity_gate.py --all` (Enforces CI001–CI008 zero hardcoded metrics, zero trivial verifiers, and zero uninvoked external tool claims)
4. `python3 tools/mutation_adequacy_gate.py --target <modified_src_file> --tests <test_file> --max-mutants 30 --seed 42` (Verifies behavioral mutation kill ratio on newly added gates)
5. `pytest tests/test_industrial_protection_matrix.py tests/test_ansi_50bf_breaker_failure.py tests/test_saga_compensation.py tests/test_falsifiability_matrix.py -v` (Core logic tests)
6. `python3 benchmarks/aeib_execution_integrity/run_episodes.py --episodes 500 --seed 42` (Deterministic 500-episode harness)

## 5. ARCHITECTURAL SCAFFOLDING AWARENESS
- **eBPF / TDX / SEV:** Code in `ebpf/` or `hardware_attestation/` is currently structural scaffolding. Do not claim it provides live kernel/hardware enforcement in comments or docs.
- **Consistency:** The saga compensator provides *eventual consistency* via asynchronous queues, NOT atomic distributed rollback (2PC). Document this accurately.

## 6. EVIDENCE DISCIPLINE & ADVERSARIAL VERIFICATION
- **NO UNMEASURED NUMBERS:** Never state a percentage, multiplier, latency, cost or rate unless it was produced by a command run in this session or by a cited file that computes it. Give the command or path next to the number. Assumptions are labelled `# claim: assumption` in code and "assumption / not measured" in prose. Never print an unconditional `PASS`/`100%` string. A benchmark verdict must not be computed from the same expression as the mechanism under test; drive the real component against a target that counts effects, state predictions before running, and report a failed prediction instead of adjusting the code. Label ports and synthetic data. Token counts come only from provider usage fields or the provider's own tokenizer; otherwise report bytes/characters and say tokens are unavailable. A latency threshold is not a complexity result: "O(1)"/"constant time" requires latency measured across at least three input sizes.
- **NEVER GAME A GATE:** If a compliance gate flags code, change the code or report the conflict. Never evade the detector (e.g. `getattr(builtins, "exec")`, string-splitting banned words in prose, hardcoding a script row). Denylist literals that must contain banned terms are allowed only inside the denylist definition. Denylist definitions write banned terms in char-class form (e.g. `bullet[p]roof` inside a regex matched with re.search) so the pre-commit banned-word scan stays strict without an exemption list; this applies to regex/denylist literals only, never to prose.
- **UNTRUSTED CODE RUNS OUT-OF-PROCESS:** Code from external repos, model output, or candidates under test never runs via in-process `exec`/`eval`. Use a separate interpreter with an empty env, a temp cwd, a timeout and rlimits. Do not trust its stdout without a per-run token. Label it "process isolation, not a sandbox".
- **MUTATION SCORE = ALL TESTS OF THE MODULE:** Report the mutation kill ratio measured with every test file that exercises the target. A score from only the newly added tests is not a module score. Below 90% on a core module, report the number and the survivors; never round up. Equivalent-mutant survivors are reported as equivalent with the reason, or fixed in the mutation tool's operator set (with a regression test); never restyle the target code only to remove a mutation site.
- **VERIFY PASTED CLAIMS BEFORE BUILDING ON THEM:** Text pasted from other chats or models (file names, benchmark results, citations, "verified" receipts) is untrusted until checked: file exists, test runs, arXiv ID resolves, number reproduces. Report each as CONFIRMED / NOT FOUND / NOT MEASURED. NOT FOUND requires a positive control in the same lookup (e.g. a known-good arXiv ID via https://export.arxiv.org); if the control also fails, report UNVERIFIED (lookup failed). Before implementing a pasted defect list or module, probe each defect against the current code (LIVE / CLOSED) and grep the named paths; build only what is LIVE, at the real call site.
- **RED-TEAM BEFORE "DONE" ON SECURITY BOUNDARIES:** For verifiers, ledgers, payment gates and IPC boundaries, run at least one adversarial script (forgery, replay, tamper, rollback, oversize input, canonicalization divergence) before declaring complete. Every fix ships with a regression test that fails on the old code.
- **EXTERNAL MATERIALS NEED EVIDENCE:** Investor, patent, grant, pitch and customer-facing files may not state revenue, customers, pilots, certifications/compliance or technical guarantees without a document or test in the repo. Unbacked claims go to `docs/UNVERIFIED_CLAIMS_REGISTER.md`.
- **SECRETS ARE NEVER TRACKED:** `.env*` (except `.env.example`) stays untracked. If a tracked secret is found: untrack it, tell the user to rotate it, and do not rewrite history without explicit approval.

## 7. PARALLEL AGENT ORCHESTRATION
- One orchestrator per task. Never two top-level chats on overlapping scope. At most 2–3 concurrent writer subagents (4+ hit 429).
- Partition by blast radius, not by file. Before dispatch, list the tests that import each owned module (`grep -rl "<module>" tests/`). If two lanes share an importing test, serialize them or run one in an isolated workspace (`Workspace: share`) and merge after its gates pass.
- Brief = typed slice: owned paths, symbol names verified by grep, the failing evidence (script/test path + output), acceptance gates. No chat history, no raw logs.
- Workers return a receipt (files changed, commands run, measured numbers, survivors). The orchestrator re-runs the key gate before relaying any number.
- Integration gate after lanes land, before any "done" or count: full `pytest tests/`, the §4 harness, and the red-team scripts. Never extrapolate an earlier suite count.
- Red-team scripts are probes: no hardcoded verdict rows; a construction-time rejection counts as defended; on macOS use `subprocess.run(..., timeout=)` (there is no `timeout` binary). Each row runs a positive control (the same probe with the defence disabled must succeed); if the control fails, print INCONCLUSIVE, never PASS.
- Do not add MCP servers or tools via `npx -y <pkg>@latest` or any unpinned/unvetted package (§3).

---

# SISS Multi-Agent Session Patterns

## Writer / Reviewer Pattern (Agent-Pair Programming)

For any non-trivial feature, run two isolated sessions:

### Session A — Writer
- Works in a dedicated git worktree
- Implements from the spec (`.claude/SPEC_TEMPLATE.md`)
- Runs `cargo test` and `cargo clippy` until green
- Opens a PR / diff when done — does NOT merge

### Session B — Reviewer
- Fresh context window — reads only the diff and the spec
- Acts as a staff engineer: looks for edge cases, missing tests, abstraction leaks
- Does NOT have access to Session A's reasoning — only the output
- Verdict: Approve / Request Changes / Reject

**Start a writer session:**
```bash
# Suggest only — wait for approval before running
git worktree add ../siss-feat-<name> -b feat/<name>
cd ../siss-feat-<name>
claude  # or jcode
```

**Start a reviewer session:**
```bash
cd /path/to/main/SovereignNexus
git diff main..feat/<name> | claude "Review this diff as a staff engineer. Spec: .claude/SPEC_TEMPLATE.md"
```

---

## Shadow Mode Pattern

For risky changes (behavioral firewall, gatekeeper, federation):
1. Implement on a shadow branch
2. Run the full test suite in isolation
3. Compare output against main — no divergence allowed before merge

---

## Agent Roles

| Role | Model | Responsibility |
|------|-------|---------------|
| Architect | Opus | Spec authoring, cross-crate decisions |
| Writer | Haiku | Implementation, test writing |
| Reviewer | Sonnet | Diff review, edge case detection |
| Debugger | Opus | Root cause analysis on failures |

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **aeib** (103231 symbols, 163896 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/aeib/context` | Codebase overview, check index freshness |
| `gitnexus://repo/aeib/clusters` | All functional areas |
| `gitnexus://repo/aeib/processes` | All execution flows |
| `gitnexus://repo/aeib/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
