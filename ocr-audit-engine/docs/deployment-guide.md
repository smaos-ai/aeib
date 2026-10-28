# Deployment Guide: Enterprise On-Premise & Air-Gapped Setup

## Prerequisites
- Linux / macOS / Windows with Python 3.11+
- Pure standard library + `cryptography`
- 0 inbound or outbound network connectivity required for core audit

## Deployment Topologies

### 1. Air-Gapped Local Scanner
Run directly inside compliance and risk management subnets:
```bash
git clone https://github.com/sovereignnexus/ocr-audit-engine.git
cd ocr-audit-engine
pip install -e .
ocr-audit /mnt/logs/agent_traces_2026-09-18.jsonl --output-findings /var/reports/dora_report.json
```

### 2. CI/CD Audit Gate (GitHub Actions / GitLab CI)
Block promotion of autonomous agent harnesses if the Toxic Receipt Index (TRI %) exceeds 0.0%:
```yaml
- name: Audit Agent Traces
  run: |
    ocr-diff staging_traces.jsonl --threshold 0.0 --patch-out fix.patch
```
