# Related Work & Epistemic Positioning

This document maps the Agent Evidence Interlock Boundary (AEIB) against prior art in distributed systems, idempotency mechanisms, cryptographic provenance, and autonomous agent safety.

---

## 1. Tool-Call Side Effects & Execution Ambiguity in Autonomous Agents

* **Li et al. (2026) — *Limbo* (arXiv:2609.29095):**  
  *Limbo* comprehensively benchmarks duplicate side effects across 25,930 episodes and 9 language models, establishing that autonomous agents repeatedly re-issue state-mutating actions when transport drops or timeouts obscure execution outcomes.  
  *AEIB Differentiation:* AEIB does not claim novelty in observing the duplicate-side-effect failure mode. Instead, AEIB provides a runtime interlock architecture: upon transport failure (e.g., `HTTP 504 Gateway Timeout`, `TCP RST`), AEIB freezes execution into the typed `DISPATCHED_UNCONFIRMED` disposition with `retry_safe: false`, enforcing out-of-band reconciliation probes before re-dispatch is permitted.

* **Memory Distortion & LLM Summarization Risks (arXiv:2609.28820):**  
  Empirical investigations demonstrate that LLM-generated summaries systematically introduce recall distortions and hallucinated compliance states.  
  *AEIB Differentiation:* AEIB's review portal enforces a strict raw-evidence review policy. Operators inspect canonical RFC 8785 JSON Canonicalization Scheme (JCS) envelopes and cryptographic receipts directly without intermediate LLM summarization, aligning with EU AI Act Article 14 human oversight requirements.

---

## 2. Idempotency Mechanisms & Transport Standards

* **IETF `draft-ietf-httpapi-idempotency-key-header` & RFC 9110:**  
  The HTTP idempotency key specification enables clients to attach an `Idempotency-Key` header so servers can deduplicate retries.  
  *AEIB Differentiation:* Standard HTTP idempotency keys rely on client diligence and server caching. When client prompts drift semantically across attempts, client-derived keys diverge. AEIB anchors idempotency to the Content-Derived Action Identifier (`CAID = caid:sha256:H(Noun || Verb || JCS(Payload))`), combined with local outbox staging and authoritative state probes that handle replica lag and pre-commit connection severance.

* **Durable Execution Frameworks (Temporal, Restate, DBOS):**  
  Durable execution runtimes log workflow state transitions to replay deterministic code following crashes.  
  *AEIB Differentiation:* Durable execution requires hosting workflow code inside specialized orchestration engines. AEIB operates as a lightweight protocol and wire-level interlock boundary governing state mutations across external, untrusted, or heterogeneous APIs (including Model Context Protocol / MCP servers).

---

## 3. Verifiable Receipts & Cryptographic Transparency

* **IETF SCITT (Supply Chain Integrity, Transparency, and Trust) & COSE (RFC 9052):**  
  SCITT defines standards for signed statements anchored to append-only transparency ledgers.  
  *AEIB Differentiation:* AEIB implements offline-verifiable COSE/SCITT-aligned receipt envelopes. Receipts bind the `CAID`, transport observations, probe authority bounds, and execution disposition using RFC 8785 canonicalization. Under hybrid policy modes, receipts incorporate classical Ed25519 and post-quantum NIST FIPS 204 (ML-DSA-65) dual signatures.

---

## 4. Epistemic Scope Summary

AEIB is evaluated as a runtime interlock pattern under the stated failure models. It does not universally eliminate distributed consensus challenges, but provides structured, fail-closed handling of ambiguous wire events in agentic execution pipelines.
