# SovereignNexus Staging Audit (Zero-Data Egress)

This containerized audit engine analyzes your agent execution logs to detect silent HTTP 504 retry storms and settlement gaps that evade pre-execution policy engines like Microsoft AGT.

## Prerequisites
- Docker installed locally
- A sample of your agent execution logs (JSONL format)

## Execution Instructions

Because we deal with Tier-1 banking regulations, we do not want your data. You will run this audit completely isolated on your own machine.

### 1. Pull the Air-Gapped Engine
```bash
docker pull sovereignnexus/provenance-auditor:v0.2.0
```

### 2. Execute the Audit in Network Isolation
To mathematically guarantee that 0 bytes of your proprietary trace data leave your machine, run the container with `--network none`.

```bash
cat your_agent_traces.jsonl | docker run -i --rm --network none sovereignnexus/provenance-auditor:v0.2.0
```

### 3. Review the Output
The engine will parse the traces and generate a `dora_art17_gap_report.json` mapping any identified execution gaps (e.g., false `CONFIRMED` statuses on dropped TCP connections) directly to DORA Article 9 Major Incident thresholds.

*To see this run live, reply to the email to schedule a 10-minute terminal screen-share.*
