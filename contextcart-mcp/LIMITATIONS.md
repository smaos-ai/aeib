# ContextCart MCP Limitations & Boundary Assumptions

## 1. Scope & Operational Posture
ContextCart-MCP is a developer productivity tool and bounded research boundary designed to mitigate context window inflation during research, brainstorming, and code inspection workflows in Claude Code, Cursor, and related agent frameworks.
- **Read-Only Focus**: ContextCart governs information retrieval, AST symbol slicing, and option synthesis. It does NOT enforce financial transaction finality, distributed 2PC rollback, or eBPF kernel egress blocking (those capabilities require the AEIB Data Plane).
- **Heuristic Token Metrics**: Token counts and savings percentages are calculated using standardized whitespace and 4-character estimates. Actual tokenization overhead may vary slightly across specific BPE tokenizers (e.g., cl100k_base vs. o200k_base).
- **Retrieval Fidelity**: Bounded research summaries depend on the fidelity and relevance of the underlying queried sources. While ContextCart isolates raw text processing out-of-band to prevent parent context bloat, it does not claim to eliminate model hallucination risks entirely.

## 2. Epistemic Lock & Stated Boundary
- All benchmark metrics reflect **observed and tested** behaviors in local development environments.
- ContextCart does not claim universal exactly-once delivery where target external endpoints lack an in-flight bound or idempotency key support.
- Consequential financial or infrastructure actions following a research brief must pass through the verified AEIB Station 1–3 execution boundary.
