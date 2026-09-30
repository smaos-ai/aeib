# ANNEX 1: LPNU & AEIB "Kryvda" Integration

## 1. Context and Strategic Alignment
This annex details the collaboration between the Sovereign Multi-Agent OS (SMAOS) AEIB framework and Lviv Polytechnic National University (LPNU)'s "Kryvda" AI system. Designed for critical infrastructure and defense deployments (e.g., Horizon Europe and NATO DIANA grant applications), the integration addresses the fundamental problem of **execution ambiguity** in high-stakes kinetic or industrial environments.

## 2. The Vulnerability in "Kryvda" Implementations
When a "Kryvda" AI agent issues a mutating physical or logical command, a transport-layer drop (e.g., a jammed signal or `HTTP 504 Gateway Timeout`) creates an ambiguous operational state. If the agent utilizes standard semantic retries, it is vulnerable to C2 semantic drift, resulting in duplicate firings of a critical action.

## 3. The AEIB Solution
AEIB provides the "Kryvda" system with a deterministic execution boundary ($T_0 \rightarrow \Delta N \rightarrow T_n$):
- **Frozen Cascade**: Traps ambiguous drops and halts speculative retries (`retry_permitted = false`).
- **Out-of-Band Probing**: Uses verifiable, hardened side-channels to query the terminal node.
- **Cryptographic Receipts**: Issues Ed25519-signed `OUTCOME_VERIFIED` or `DISPATCHED_UNCONFIRMED` receipts, guaranteeing that Kryvda's internal state machine remains perfectly synchronized with physical reality.

## 4. Grant Application Positioning
For NATO DIANA and Horizon Europe evaluators, this integration demonstrates a mature, mathematically grounded approach to AI safety. It mitigates OWASP LLM06 (Excessive Agency) by cryptographically sealing the gap between agent intent and physical side-effects.
