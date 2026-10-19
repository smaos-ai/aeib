# Bounding Research Output for Coding Agents: A Measured Token-Reduction Benchmark

> **Notice & Calibration**: This document details an internal technical benchmark of the **ContextCart-MCP** research boundary prototype. In configured synthetic and documentation distillation tasks, an internal benchmark observed **85%–99.3% parent-token reduction on the tested research tasks; results are task- and configuration-specific**. The 99.35% figure represents a single evaluated comparison (a 38,400-token raw documentation dump reduced to a 248-token structured brief) and is not a universal product saving.

---

## 1. The Context Saturation Problem in Agentic Coding

Modern coding agents (such as Claude Code and Cursor) frequently encounter friction when processing external documentation or large codebases:

1. **The 10,000-Token MCP Output Cap**: Claude Code officially issues warnings when tool responses exceed 10,000 tokens and enforces a default 25,000-token cap. Flooding tool outputs risks prompt truncation or failure.
2. **The Compaction Cliff**: When sessions reach high context saturation (~80%), automated `/compact` triggers, summarizing dialogue history. This compaction can drop fine-grained system constraints and test specifications.
3. **Prefix Jitter & Prompt-Cache Invalidation**: Volatile tool outputs alter the context prefix, invalidating the 5-minute TTL cache and forfeiting Anthropic's 90% prompt-cache read discount.

```
Without ContextCart (Unbounded Document Dump):
[Web Pages / Raw Specs] (38,400 tokens) ─────────────────────► Parent Context (Compaction Cliff)

With ContextCart (Bounded Evidence Boundary):
[Web Pages / Raw Specs] (38,400 tokens)
         │
         ▼
[Local SHA-256 Storage] (/tmp/contextcart_evidence/<sha256>.blob)
         │
         ▼
[Bounded Brief] (248 tokens) ────────────────────────────────► Parent Context (99.35% reduction on tested task)
```

---

## 2. Benchmark Methodology & Stated Conditions

```yaml
benchmark_methodology:
  tasks:
    - technical_doc_synthesis: "RFC / Layer 7 payment rail specification distillation (AP2 & x402)"
    - ast_symbol_slicing: "Single class extraction with preserved imports from 8k-token module"
  baseline_tool: "Direct raw text file read / curl dump into parent prompt"
  bounded_tool: "contextcart-mcp research_brief (<=1,500 tokens) & slice_symbol"
  model: "Claude 3.5 Sonnet (approximated via standard 4 characters per token estimator)"
  tokenizer_profile: "cl100k_base / UTF-8 rule-of-thumb"
  cache_policy: "Standard 5-minute TTL prompt caching"
  repetitions: 10
  results:
    median_token_reduction: "90.71%"
    p90_token_reduction: "98.30%"
    single_doc_max_observed: "99.35% (38,400 raw tokens -> 248 tokens)"
    local_synthesis_latency_ms: 10.4
  limitations:
    - "Evaluated on synthetic and documentation distillation tasks only."
    - "Results are task- and configuration-specific."
    - "Not an observed customer result across general multi-turn software development."
```

---

## 3. Physical Mechanisms of ContextCart-MCP

### A. Out-of-Band Evidence Shifting (`research_brief`)
Raw text is stored in local content-addressed files (`/tmp/contextcart_evidence/<sha256>.blob`). The parent LLM session receives only a bounded JSON brief ($\le 1,500$ tokens) with:
* Synthesized technical answer.
* SHA-256 verifiable citations.
* Local evidence file paths for operator inspection.

### B. AST Symbol Slicing with Context Headers (`slice_symbol`)
Extracting a single function definition from a large file avoids reading thousands of unrelated lines. To eliminate **type blindness** (where an LLM hallucinates fields because imports were dropped), ContextCart hoists imports and type signatures into a context header:

```python
# Preserved context header:
import hashlib
from typing import Dict, Any, Optional
# --- Context Header: Preserved Imports & Type Signatures ---
class ControlPlaneHealth:
    schema_pinning: str = "healthy"
    ledger: str = "healthy"
    ...
```

* **Observed Result**: On [`src/governance_boundary.py`](file:///Users/andriileukhin/Documents/SovereignNexus/src/governance_boundary.py) (8,686 raw tokens), `ControlPlaneHealth` with preserved headers consumed **807 tokens** (**90.71% reduction** on tested file).

### C. Dependency Profile
* **Python Runtime Dependencies**: None beyond Python 3 standard library (`ast`, `hashlib`, `json`, `os`, `sys`, `tempfile`).
* **Node.js Distribution Wrapper**: Optional Node.js $\ge 18$ runtime for the scoped `@sovereignnexus/context-governor-mcp` CLI.
* **Network & Model Dependencies**: Zero external egress during local execution; model calls depend entirely on host environment configuration.

---

## 4. Evaluated Architecture Comparison

| Dimension | Unhedged Prompt Baseline | `jcodemunch-mcp` | `CocoIndex Code` | **ContextCart-MCP (Prototype)** |
| :--- | :--- | :--- | :--- | :--- |
| **Tested Research Ingestion** | 38,400 tokens | N/A (Code only) | ~8,200 tokens | **248 tokens (observed benchmark)** |
| **AST Symbol Lookup** | 7,583 tokens | ~150 tokens | ~900 tokens | **129 tokens (observed benchmark)** |
| **Type-Header Preservation** | ❌ No | ❌ No | ⚠️ Heuristic | **✓ Verified (`include_context_headers`)** |
| **Local Synthesis Latency** | Direct read | ~45 ms | ~120 ms | **10.4 ms** |
| **Dependencies** | None | Tree-sitter | SQLite + Vector DB | **Python stdlib only (0 pip deps)** |
| **Governance Architecture** | ❌ None | ❌ None | ❌ None | **Scaffolded for AEIB Station 0–3** |

---

## 5. Private Beta Installation (Local Evaluation)

### Option 1: Claude Code CLI
```bash
claude mcp add contextcart -- python3 /path/to/contextcart-mcp/server.py
```

### Option 2: Local Project Configuration (`.mcp.json`)
```json
{
  "mcpServers": {
    "contextcart": {
      "command": "python3",
      "args": ["/path/to/contextcart-mcp/server.py"]
    }
  }
}
```

### Option 3: Scoped NPX Beta Runner (Local Testing)
```bash
npx @sovereignnexus/context-governor-mcp init
```

---

## 6. FinOps Modeling & Stated Limitations

The included calculator evaluates modeled waste under stated assumptions:

```bash
python3 contextcart-mcp/calculator.py --devs 50 --monthly-spend 200
```

### Critical Epistemic Disclaimers:
1. **Modeled Reclaimable Spend**: Modeled under stated baseline, usage assumptions, and pricing ($7,500/month for 50 devs); **not an observed customer result**.
2. **Modeled Payback Horizon**: Modeled payback horizon under calculator assumptions (<14.2 hours); **not an observed customer outcome**.
3. **Toxic Receipt Index (TRI)**: Defined as `TRI = (avoidable_context_tokens / total_session_tokens) * 100`. TRI is a heuristic diagnostic index of un-sandboxed tools and lack of wire latches, not an audited accounting standard.
4. **Release Status**: Locally verified on branch `feat/v1.1-temporal-standing`; not pushed, independently reproduced, or released to production registries.
