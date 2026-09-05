# SISS LLM Wiki — Structured Agent Memory

Inspired by Karpathy's LLM Wiki v2: instead of raw RAG over documents,
this wiki is a continuously maintained synthesis that agents query directly.

## Layers

### `working/` — Short-term, session-scoped
Active decisions, in-progress specs, current phase state.
Cleared or promoted after each development session.
- `current-task.md` — what is being built right now
- `open-questions.md` — unresolved decisions blocking progress

### `episodic/` — What happened (event log)
Immutable record of what was built, when, and why it was done that way.
Agents read this to avoid re-litigating past decisions.
- `phase-log.md` — phase completion records
- `decisions.md` — architectural decisions with rationale

### `semantic/` — What things mean (concepts)
Stable definitions of SISS concepts, protocols, and invariants.
This is the "compiled" understanding — not raw docs, but synthesized truth.
- `smaos-concepts.md` — SMAOS terminology and invariants
- `ap2-protocol.md` — Agent Payment Protocol spec
- `mcp-contracts.md` — frozen MCP interface definitions

### `procedural/` — How to do things (recipes)
Runbooks and repeatable patterns. Agents execute these, not invent them.
- `how-to-add-a-crate.md`
- `how-to-run-federation-test.md`
- `how-to-review-a-diff.md`

## Rule
When an agent needs context, it reads the relevant wiki layer — not raw source files or chat history.
When a session ends, promote working notes to episodic or semantic as appropriate.
