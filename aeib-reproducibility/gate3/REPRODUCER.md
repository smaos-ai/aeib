# AEIB Gate 3 Independent Reproduction Instructions

This document provides the exact sequence required for a third-party auditor or independent CI runner to reproduce the Gate 3 clean-room verification. 

**Note on Network Policy:** The Docker image build utilizes network egress to install OS-level dependencies (Git, Python 3). The runtime verification container is strictly executed with `network_mode: none` to guarantee zero egress during compilation and cryptographic verification.

### Execution Sequence

1. Clone the repository and checkout the signed release candidate tag:
   ```bash
   git clone <repository-url>
   cd aeib-v1.0
   git checkout v1.0.0-rc.1
   ```

2. Enter the Gate 3 harness directory:
   ```bash
   cd aeib-reproducibility/gate3
   ```

3. Execute the clean-room verification:
   ```bash
   docker compose up --build
   ```

4. Capture the verification transcript output from the terminal.

### Required Evidence for Gate 3 Completion
To clear Gate 3, the independent reproducer must publish a transcript that includes:
* Independent operator identity or CI runner identity
* Repository URL and Signed Tag (or commit SHA)
* Docker image digest
* Host operating system and architecture
* Full command transcript
* Receipt digest and verifier exit codes
* Timestamp of execution
