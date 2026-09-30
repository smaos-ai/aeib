# Appendix: CAID and AER-1 Mapping

## Identity Mapping (`action_id.type = "caid"`)

This document outlines the identity mapping methodology for bridging the AEIB disposition framework to broader interoperability targets, specifically CAID (Causal Action Identifier) and AER-1 concepts.

In this implementation, the `action_id` field utilizes the `caid` type mapping to provide deterministic structural identity for mutating agent actions:

* **Valid Retries:** A deterministic agent retry that preserves the exact canonical payload representation (including whitespace, intent framing, and operational parameters) will hash to the **exact same CAID**. The idempotency gateway can use this stable CAID to safely deduplicate the request and return the cached outcome.
* **Semantic Drift (C2):** If an agent alters the payload structure, generates a fresh client UUID, or rephrases metadata during a retry attempt, the canonical hash will produce a **new CAID**. Under CAID semantics, this is structurally interpreted as a **distinct logical action**. Without the AEIB execution boundary suppressing the retry, this semantic drift bypasses exact-match caches and results in a duplicate side-effect.

By explicitly anchoring `action_id.type = "caid"`, we guarantee that causal identity is bound precisely to payload structure, providing a rigorous mathematical boundary for evaluating gateway deduplication efficacy.
