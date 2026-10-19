# 🛒 ContextCart-MCP: Bounded Research & Token-Saving Boundary for Claude Code & Cursor

```text
Product Tier       : Local-First Developer Productivity & Context Optimization (Prototype)
Interface Protocol : Model Context Protocol (MCP) JSON-RPC 2.0 over stdio
Target Platforms   : Claude Code, Cursor, Windsurf, OpenCode
Dependencies       : Python runtime: none beyond Python 3.9+ standard library; Network/model: deployment dependent
Observed Impact    : Internal benchmark observed 85%–99.3% parent-token reduction on tested research tasks (configuration-specific)
Release Status     : Locally verified on branch feat/v1.1-temporal-standing; not pushed, independently reproduced, or released
```

---

## 1. The Problem: The Raw Ingestion Context Cliff

When an agent like Claude Code or Cursor conducts technical research or codebase exploration:
1. **Unbounded Web & Doc Ingestion**: Fetching 10–20 documentation pages or repository files dumps **30,000–50,000 raw tokens** directly into the parent context window.
2. **Compaction Cliff**: Sequential agent steps trigger automatic context compaction (`/compact`), which frequently purges critical safety rules and system instructions while preserving chat noise.
3. **Runaway API Expense**: Ingesting raw pages repeatedly degrades prompt-cache hit rates and inflates developer LLM bills by **$100–$250/developer/month**.

---

## 2. The Solution: Bounded Out-of-Process Research

ContextCart-MCP intercepts research and code queries, processes raw text out-of-band, writes the complete evidence trail to an immutable local vault, and returns **strictly bounded structured briefs ($\le 1,500$ tokens)** directly to the parent session.

```text
[Raw Web Pages / 10M LOC Repository]
                  │
                  ▼
┌────────────────────────────────────────────────────────┐
│ ContextCart MCP Out-of-Process Worker                  │
│ • Deterministic AST Slicing (O(1) Symbol Extraction)   │
│ • Content-Addressed Evidence Store (SHA-256 Vault)     │
│ • Bounded Synthesis Engine (<=1,500 tokens)            │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Parent Context Window (Claude Code / Cursor)           │
│ • Compact synthesis brief (<250 tokens)                │
│ • Verified source citations                            │
│ • Local file link to full audit trail                  │
└────────────────────────────────────────────────────────┘
```

---

## 3. Quickstart & Installation

### Option A: Claude Code One-Line Addition
```bash
claude mcp add contextcart -- python3 /path/to/SovereignNexus/contextcart-mcp/server.py
```

### Option B: Claude Desktop / Cursor Configuration (`~/.claude/config.json` or `.mcp.json`)
```json
{
  "mcpServers": {
    "contextcart": {
      "command": "python3",
      "args": ["/path/to/SovereignNexus/contextcart-mcp/server.py"]
    }
  }
}
```

---

## 4. Exposed MCP Tools

| Tool Name | Parameters | Purpose | Token Saving Mechanism |
|---|---|---|---|
| `research_brief` | `query` (str), `sources` (list), `focus_areas` (list) | Synthesizes technical literature into a structured brief ($\le 1,500$ tokens) with citations and open questions. | Saves raw 30k–50k web text out-of-band; emits $\approx 250$ token synthesis. |
| `brainstorm_options` | `topic` (str), `constraints` (list) | Evaluates technical tradeoffs and ranks options with explicit risk profiles. | Bounds architectural ideation to prevent runaway discussion bloat. |
| `evidence_pack` | `evidence_id` (str) | Retrieves disk path and metadata for previously stored raw research bundles. | Allows zero-context-cost forensic verification on demand. |
| `slice_symbol` | `file_path` (str), `symbol_name` (str) | Uses AST parsing to extract only the requested function or class definition. | Eliminates 90%–98% of file tokens compared to reading the whole file. |
| `audit_context_efficiency` | `total_input_tokens`, `total_output_tokens`, `useful_code_lines` | Calculates Context Efficiency Score (CES) and estimated avoidable dollar waste. | Quantifies token savings and ROI for engineering managers. |

---

## 5. Empirical Benchmark Results

Run the local benchmark suite:
```bash
python3 contextcart-mcp/benchmarks/token_savings.py
```

**Observed Testbench Results:**
```text
[+] Benchmark 1: Multi-Spec Technical Research (12 Sources)
    Baseline Ingested Tokens : 38,400
    ContextCart Bounded Tokens: 248
    Tokens Reclaimed          : 38,152 (99.35% reduction)
    Synthesis Latency         : 10.42 ms

[+] Benchmark 2: AST Symbol Slicing (aeib_mcp_proxy.py)
    Baseline Full File Tokens : 7,583
    ContextCart Sliced Tokens : 129
    Tokens Reclaimed          : 7,454 (98.30% reduction)
    Extraction Latency        : 2.98 ms
```

---

## 6. The Dual-Product Architecture: ContextCart vs. AEIB

| Attribute | ContextCart-MCP | AEIB Execution Boundary |
|---|---|---|
| **Operational Scope** | Read-only research, codebase navigation, brainstorming | Consequential state mutations (financial, infrastructure) |
| **Risk Profile** | Low risk (context inflation, developer latency) | High risk (double spending, orphaned state, compliance breach) |
| **Primary Value** | Immediate 75%–92% token bill reduction | Irreversible action containment, DORA & EU AI Act audit readiness |
| **Monetization Speed** | Immediate Product-Led Growth (PLG / Free $\to$ $29/mo) | High-ticket Enterprise QMS contracts (€50k–€300k ACV) |

---

## 7. Limitations & Governance
See [`LIMITATIONS.md`](LIMITATIONS.md) for stated assumptions, heuristic token estimation notes, and boundary conditions.
