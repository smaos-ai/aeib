# Provisional Patent Claim Dossier: Governed Autonomous Agent Execution

**Target Jurisdiction:** USPTO / PCT  
**Priority Date Anchor:** October 20, 2026  
**Status:** Pre-filing Claim Specification  

---

### Claim 1: Resumable Human-Governed Agent Execution (RCE) via Effect Handlers
A method and computer-implemented system for intercepting an autonomous software agent's tool call immediately prior to network dispatch, comparing the canonical action identifier against a pre-authorized delegation warrant, interrupting execution upon detecting transport ambiguity (`HTTP 504` or connection reset) into a durable `EFFECT_INDETERMINATE` state, and reconciling the indeterminate state via a bounded single-flight authoritative probe (`ProbeBudget: 1`).

### Claim 2: SCITT-Anchored Anti-Reset State Continuity for Sliding-Window Spend Gates
A method for preventing multi-agent quota bypass and memory-wipe reset attacks, comprising: maintaining an append-only cryptographic journal of financial reservations, periodically publishing signed tree heads to an RFC 9162 / RFC 9943 transparency log, and halting boot initialization upon detecting that local state files have been deleted while the remote transparency log contains recorded history, unless un-halted by a cryptographically signed human supervisor recovery warrant.

### Claim 3: Bit-Isolated Constant-Time Predicate Evaluation for Multi-Tenant Tool Dispatches
A hardware-accelerated or constant-time predicate evaluator that evaluates each of a plurality of admissibility conditions (canonical action digest, harness digest, tool schema digest, payee allowlist, and per-call budget attenuation) in parallel without early-exit branch short-circuiting, mapping failures to independent bits of a bitmask to prevent timing-based side-channel discovery of authorization rules.
