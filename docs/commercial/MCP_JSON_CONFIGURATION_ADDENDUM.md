# 📄 Technical Addendum: In-Line Deployment of `smaos-mcp-guard` via Standard `mcp.json`
## Zero-Code Hardening for Claude Code, Cursor, Windsurf & Enterprise Agent Runtimes

**Document Ref:** SMAOS-ADD-2026-MCP-01  
**Target Moat:** Moat 10 (Shadow MCP Wire Firewall & Drift Sentinel)  
**Applicability:** Any MCP Server over stdio or SSE (Node.js, Python, Go, Docker)  

---

## 1. 🎯 The Challenge: Unconstrained Tool Injection (OWASP MCP03)

In standard MCP configurations, client IDEs and agent harnesses execute MCP servers directly. If an open-source or third-party MCP server package is updated upstream to silently append an `export_db_keys` tool or modify a tool description (a **"Rug Pull"**), the agent automatically ingests the expanded capability into its active prompt context without security review.

`smaos-mcp-guard` acts as a transparent, zero-overhead stdio wrapper that enforces **Tool Schema Hash Pinning** and **Credential Redaction** before JSON-RPC messages touch the agent's context.

---

## 2. ⚙️ Drop-In `mcp.json` Configuration

Upgrading an existing MCP setup requires zero code changes. You simply prefix the existing server command with `smaos-mcp-guard`:

### Before: Unprotected `mcp.json`
```json
{
  "mcpServers": {
    "payment-gateway": {
      "command": "node",
      "args": ["/opt/twisto/services/payment-mcp-server.js"],
      "env": {
        "DB_CONNECTION": "postgresql://app:pass@internal-db:5432/core",
        "API_KEY": "sk-live-992819028401928"
      }
    }
  }
}
```

### After: Hardened SMAOS-Protected `mcp.json`
```json
{
  "mcpServers": {
    "payment-gateway": {
      "command": "python3",
      "args": [
        "-m", "smaos_mcp.mcp_guard",
        "--pin-manifest", "/opt/twisto/config/payment-mcp.pinned.json",
        "--fail-closed",
        "--",
        "node", "/opt/twisto/services/payment-mcp-server.js"
      ],
      "env": {
        "DB_CONNECTION": "postgresql://app:pass@internal-db:5432/core",
        "API_KEY": "sk-live-992819028401928"
      }
    }
  }
}
```

---

## 3. 🔒 Step-by-Step Pinning Workflow

### Step 1: Generate the Pinned Schema Manifest (During CI/CD Build)
Run the generator command against your server to calculate the canonical SHA-256 schema hash:
```bash
python3 -m smaos_mcp.mcp_guard --generate-pin -- node /opt/twisto/services/payment-mcp-server.js > payment-mcp.pinned.json
```

**Resulting `payment-mcp.pinned.json`:**
```json
{
  "pinned_schema_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "pinned_at": "2026-09-22T10:30:00Z",
  "tool_count": 2,
  "tools": ["check_balance", "transfer_funds"]
}
```

### Step 2: Runtime Enforcement (Zero-Latency Interception)
When the agent connects, `smaos-mcp-guard`:
1. **Schema Check:** Verifies the runtime `tools/list` against the pinned SHA-256 hash. If an unannounced tool appears or a description changes, the call is blocked immediately with a `REFUSED` disposition.
2. **Credential Redaction:** Automatically scrubs OpenAI (`sk-...`), AWS (`AKIA...`), GitHub (`ghp_...`), and `.env` assignments from tool returns before they reach the model.
3. **Transport Verification:** If the underlying process exits with an error or timeout, the return payload is forced to fail-closed `UNKNOWN`, stopping false confirmations.

---

## 4. 🚀 Enterprise Compatibility Matrix

| Environment | Supported Runtimes | Invariant Guarantees |
| :--- | :--- | :--- |
| **Claude Code CLI** | Node.js, Python, Go, Docker | Zero external network calls (`--network none` safe) |
| **Cursor & Windsurf** | Local stdio & remote SSE pipes | Sub-millisecond JSON-RPC parsing latency |
| **Custom LangGraph / Celery** | Subprocess & socket transports | DORA Article 17 audit trail emitted locally |
