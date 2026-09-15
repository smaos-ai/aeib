---
name: External Reproduction Report
about: Submit independent reproduction telemetry for AEIB v0.1.0
title: "[Reproduction]: <OS/Platform> - <Reviewer/Handle>"
labels: "reproduction, telemetry"
assignees: ""
---

## Reproduction Telemetry

> **Notice:** Do NOT submit proprietary logs, production data, or confidential credentials. Submit ONLY synthetic benchmark telemetry or sanitized public artifacts.

### 1. Reviewer Information
- **Reviewer / Organization**: <!-- e.g., @username, Independent Researcher, or anonymous -->
- **Execution Timestamp (UTC)**: <!-- e.g., 2026-09-16T12:00:00Z -->

### 2. Environment & Runtime
- **Commit / Tag Tested**: `v0.1.0` (commit `7df056e6e49bb119efb611a9a17241b7c8b2c68c`)
- **Operating System**: <!-- e.g., Ubuntu 24.04.1 LTS / macOS 15.3.1 -->
- **Architecture**: <!-- e.g., x86_64 / arm64 -->
- **Docker Version**: <!-- e.g., Docker 27.3.1 -->
- **Docker Compose Version**: <!-- e.g., v2.29.1 -->
- **Python Version (if run directly)**: <!-- e.g., Python 3.12.3 -->
- **Container Isolation Verified**: <!-- [x] Yes, confirmed `network_mode: "none"` -->

### 3. Execution Results
- **Command Executed**: `docker compose run --rm benchmark` <!-- or `python3 run.py fixtures/ && python3 score.py` -->
- **Runner Exit Code**: <!-- e.g., 0 -->
- **Scenarios Tested**: <!-- 10 -->
- **Expected Scorecards Matched**: <!-- e.g., 10/10 -->
- **Scorecard Match Rate**: <!-- e.g., 100% -->
- **Generated Result Artifacts Digest (SHA-256)**: <!-- optional sha256sum of generated scorecard.json or results.json -->
- **Consecutive Rerun Console Output Difference**: <!-- e.g., 0 bytes -->

### 4. Observations & Notes
- **Spec Ambiguities (if any)**: <!-- Did any scenario precedence logic behave unexpectedly? -->
- **Issues or Platform-Specific Behaviors**: <!-- Any container mounting or permission issues? -->
- **Permission to Include in Public Reproduction Tracker**: <!-- [ ] Yes, include handle / [ ] Yes, anonymous only / [ ] Internal verification only -->
