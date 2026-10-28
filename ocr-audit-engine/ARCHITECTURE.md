# Architecture Deep-Dive: The 5-Stage Deterministic Hybrid Audit Pipeline

## Overview

The OCR Audit Engine implements a 5-stage hybrid pipeline uniting **deterministic engineering** with **agentic forensic interrogation**. This architecture addresses the **Signal-to-Noise Ratio (SNR) Crisis** in enterprise AI security auditing.

```
[ Raw JSONL Trace Log ] (100,000 Lines)
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 1: Deterministic Dispatcher (Python Layer)       │
│ • Mutating verb detection (POST, PUT, DELETE, SQL)     │
│ • Transport fault filters (504, 502, 503, TCP_RST)     │
│ • 85-95% noise reduction at $0 token cost (<15ms)      │
└────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 2: Smart Action Bundler                          │
│ • Groups by (action_id, idempotency_key, ±5s cascade)  │
│ • Context envelope capped at 2,000 tokens max          │
│ • Prevents LLM Context Compaction Cliff decay          │
└────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 3: Scenario-Tuned Forensic Interrogator          │
│ • Micro-agent isolated evaluation                      │
│ • 4 read-only forensic primitives                      │
│ • No arbitrary bash or python tool access              │
└────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 4: Wire-Truth Reflector (Zero-Hallucination Gate)│
│ • Hard ground-truth filter: wire facts override LLM    │
│ • Discards double execution if commit xid count == 1   │
│ • Discards egress breach if eBPF dropped fail-closed   │
└────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────┐
│ Stage 5: Deterministic Anchor                          │
│ • Programmatically binds findings to byte offsets      │
│ • Invariant: 0.00% line drift                          │
│ • Cryptographic SHA-256 evidence digests               │
└────────────────────────────────────────────────────────┘
           │
           ▼
[ Audit Findings & DORA Art. 17 Remediation Patch ]
```

---

## Detailed Stage Invariants

### Stage 1: Deterministic Dispatcher (`dispatcher.py`)
- **Execution Cost:** \$0.00 in LLM tokens (runs 100% in local Python runtime).
- **Latency:** Sub-15 milliseconds over 100,000 log lines.
- **Pass Invariant:** Every record with `is_mutating == True`, HTTP status $\in \{500, 502, 503, 504, 409, 429\}$, `TCP_RST`, `TIMEOUT`, `jcs_digest_match == False`, or post-fault retry is forwarded to Stage 2.
- **Drop Invariant:** All healthy `GET`/`HEAD`/`OPTIONS` 200/304 operations and unattached thought tokens are silently anchored as healthy.

### Stage 2: Smart Action Bundler (`bundler.py`)
- **Cascade Window:** Default $\pm 5.0$ seconds grouping window.
- **Correlation Keys:** Primary `action_id`, secondary `idempotency_key`, shared session actor.
- **Context Guard:** Ensures each bundle never exceeds 2,000 tokens, eliminating the attention degradation cliff observed in long-context models.

### Stage 3: Scenario-Tuned Forensic Interrogator (`interrogator.py`)
- **Restricted Primitives:**
  1. `GetWireStatus(trace_id)`: Inspects socket handshake, HTTP error codes, eBPF actions.
  2. `CompareJCSDigest(envelope)`: Computes RFC 8785 canonical hash deltas.
  3. `CheckRetryPolicy(action_id)`: Verifies whether `retry_held: true` was respected.
  4. `InspectDisbursementLineage(action_id)`: Checks commit transaction IDs (`xid`).

### Stage 4: Wire-Truth Reflector (`reflector.py`)
- **Zero-Hallucination Invariant:** Socket-level ground truth strictly supersedes LLM speculation.
- Eliminates phantom double-spend alerts when database records confirm single atomic commit.
- Eliminates phantom exfiltration alerts when eBPF kernel gate intercepted the connection.

### Stage 5: Deterministic Anchor (`anchor.py` / `reflector.py`)
- **0.00% Line-Number Drift:** Line numbers and byte offsets are extracted during Stage 1 ingestion and injected into findings via code. LLMs are never allowed to emit line numbers.
