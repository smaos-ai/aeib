---
name: aeib-delivery
description: Scoped repository intelligence, reverse blast-radius analysis, asymmetric diff verification, and oracle-gated escalation workflow via the AEIB Repo-Intelligence MCP server (tools/aeib_repo_intelligence_mcp_server.py). Use when refactoring, fixing bugs, or verifying diffs with minimal token overhead.
---

# AEIB Delivery Skill (Scoped Repo-Intelligence & Oracle Verification)

Use the AEIB Repo-Intelligence MCP tools (`tools/aeib_repo_intelligence_mcp_server.py`) to inspect only the minimal AST slice and verify diffs deterministically before accepting changes.

## 1. MCP Server Registration (`~/.gemini/config/mcp_config.json`)

```json
{
  "mcpServers": {
    "aeib-repo-intelligence": {
      "command": "python3",
      "args": ["tools/aeib_repo_intelligence_mcp_server.py"],
      "env": {
        "AEIB_REPO_ROOT": ".",
        "PYTHONHASHSEED": "0"
      }
    }
  }
}
```

## 2. Mandatory 7-Step Workflow

1. **Map interfaces (`repo_map`)**: Retrieve AST skeletons, Merkle roots, and Tarjan SCC topological refactoring stages instead of reading whole files.
2. **Check callers (`blast_radius`)**: Before altering any function or class signature, run `blast_radius` with `fail_on_budget_overflow=true` so reverse callers are never silently omitted.
3. **Pack minimal slice (`repo_slice`)**: Load only the target symbol's file and its direct import/caller closure within `token_budget`.
4. **Produce unified diff**: Emit a minimal unified diff touching the target and any affected reverse callers.
5. **Compress test logs (`compress_test_output`)**: When a test fails, extract failing assertion lines and the full-log `sha256` digest instead of pasting raw terminal dumps.
6. **Verify diff (`verify_diff`)**: Evaluate the unified diff via `OpenCodeReviewAsymmetricReflector` and `AcceptanceOracle` (including the UTBoost mutation-adequacy floor `min_mutation_kill_bps`).
7. **Escalate failed slice (`escalation_pack`)**: If `verify_diff` rejects the candidate, build a bounded repair packet ($B \le 3$) containing only the failed slice and contract digest.
