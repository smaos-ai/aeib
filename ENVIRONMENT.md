# Clean-Machine Environment Specifications

**Benchmark:** Agent-Effect Integrity Benchmark (AEIB) v0.1.0  
**Execution Mode:** Air-Gapped Clean-Room (`network_mode: "none"`)  

---

## 🖥️ Target Execution Environments

### 1. Isolated Container Environment (Canonical Reference)
* **Base Image:** `python:3.12-slim` (Multi-arch OCI image)
* **User Isolation:** Non-root execution (`uid=1000(appuser)`, `gid=1000(appuser)`)
* **Network Mode:** `none` (offline, zero external network sockets or DNS resolution)
* **Filesystem:** Ephemeral read-only root with dedicated `/app/out` writable mount
* **Dependencies:** Python 3.12 Standard Library only (zero pip packages)

### 2. Host Verification Platforms
The benchmark has been evaluated and confirmed bit-exact across both major Unix architectures:

* **Platform A: Darwin ARM64 (Apple Silicon)**
  - Host OS: macOS Sonoma / Sequoia (Darwin kernel 24.x)
  - Python Runtime: Python 3.12.x / 3.14.x
  - Container Engine: Docker Engine 27.x / Docker Desktop
* **Platform B: Linux x86_64**
  - Host OS: Ubuntu 22.04 / 24.04 LTS (Linux kernel 6.8.x)
  - Python Runtime: Python 3.12.x
  - Container Engine: Docker Engine 26.x / 27.x

---

## 🔬 Determinism Guarantee
Successive executions of `make test` or `docker compose run --rm benchmark` produce a 0-byte difference in console output and identical SHA-256 digests for `results.json` and `scorecard.json`.
