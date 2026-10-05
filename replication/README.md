# AEIB Independent Academic Replication Package

This replication package contains the complete, self-contained verification suite for the **Agent Execution Integrity Benchmark (AEIB v1.0)** Zone 1 open-core research prototype.

## Quick Start (Single Command)

To run the complete verification suite and generate a structured JSON replication audit report:

```bash
python3 replication/reproduce_all.py --json
```

Or run directly with standard terminal output:

```bash
python3 replication/reproduce_all.py
```

## Evaluated Verification Axes

1. **Zone 1 Import Boundary Isolation**: Confirms zero Zone 2 proprietary leaks or unvetted external dependencies.
2. **AST Zero-Mock Enforcement**: Confirms unmocked execution along cryptographic and state reconciliation paths.
3. **Negative-Vector Security Matrix**: Evaluates fail-closed latching and invalid state transitions.
4. **Vector B Concurrency Race**: Evaluates persistence-layer mutual exclusion using `INSERT ... ON CONFLICT DO NOTHING RETURNING`.
5. **Research MCP Interceptor**: Evaluates RFC 8785 JCS CAID action binding, Figshare dataset staging, and Dimensions query execution.
6. **Chaos Petri Network Faults**: Evaluates 5 network edge scenarios (HTTP 504 drops, TCP resets, replica lag, probe timeouts, signature tampering).
7. **Human Review Console**: Evaluates plain-language ASD-STE100 formatting and Merkle-chained operator decision logging.
