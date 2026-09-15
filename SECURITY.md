# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| v0.1.x  | :white_check_mark: |
| < v0.1  | :x:                |

## Scope and Isolation Model

AEIB (Agent-Effect Integrity Benchmark) is designed to evaluate agent harnesses offline. The reference container configuration runs with:
- Non-root execution (`uid=1000`, `gid=1000`)
- Explicit network isolation (`network_mode: "none"`)
- Local filesystem mounts limited strictly to inputs and output destinations

AEIB is a deterministic test harness over synthetic test fixtures. It does not handle live credentials, production API keys, or external network connections.

## Reporting a Vulnerability

If you discover a security issue—such as an unexpected network egress vector, a container escape vulnerability, or an issue that could compromise an evaluator host environment—please report it responsibly:

1. **Do not open a public GitHub issue.**
2. Use GitHub [Private Vulnerability Reporting](https://github.com/smaos-ai/aeib/security/advisories/new) on this repository, or email **`security@smaos.ai`**.
3. Include:
   - A description of the vulnerability and its potential impact.
   - Exact steps or script to reproduce the behavior.
   - Your host OS, Docker version, and container configuration.

## Disclosure Policy

We acknowledge receipts within 48 business hours and provide an assessment and timeline within 5 business days. Once a fix is verified, a release advisory will be published.
