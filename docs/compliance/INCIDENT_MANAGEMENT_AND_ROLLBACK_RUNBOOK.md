# AEIB Incident Management and Rollback Runbook
**Regulatory Cross-Reference:** DORA (Regulation (EU) 2022/2554) Articles 17, 18, 19; EBA Guidelines on ICT and Security Risk Management; ISO/IEC 27035.
**Operational Scope:** Pre-production and staging environments for AEIB core services, eBPF-LSM security profiles, WebAssembly verifiers, and Direct-I/O Write-Ahead Logs.
**Status:** Configured and evaluated under operational testing procedures.

---

## 1. Incident Severity Classification Framework

In accordance with DORA Article 18 criteria (clients affected, data loss, duration, geographic spread, economic impact), AEIB incidents are triaged into three severity tiers:

| Severity | Definition | Target Response (Triage) | Target Containment | Authority Required |
|---|---|---|---|---|
| **SEV-1 (Critical)** | Split-brain consensus failure, un-latched financial mutation, kernel BPF hook panic, or cryptographic signing key compromise. | $\le 5\text{ minutes}$ | $\le 15\text{ minutes}$ | CISO + Lead Systems Architect |
| **SEV-2 (Major)** | Asymmetric cluster node partition, group-commit WAL latency degradation ($p99 > 50\text{ms}$), or elevated rate of `EFFECT_INDETERMINATE` states ($> 5\%$). | $\le 15\text{ minutes}$ | $\le 60\text{ minutes}$ | Lead SRE / Security Engineer |
| **SEV-3 (Minor)** | Non-blocking telemetry ingestion drop, transient client wire formatting errors ($400\text{ Bad Request}$), or minor documentation drift. | $\le 4\text{ hours}$ | $\le 24\text{ hours}$ | On-Call Engineer |

---

## 2. Four-Stage Incident Response Workflow

```
[ Stage 1: Detection & Triage ]
  - Prometheus metrics trigger (wal_fsync_latency, indeterminate_latch_total)
  - Tetragon BPF-LSM kill signal notification
  - Pure-Python standalone verifier tamper alert
            |
            v
[ Stage 2: Automated & Manual Containment ]
  - Fail-closed circuit breaker tripped
  - UDS boundary socket unlinked (local isolation)
  - Station 1 financial dispatch latch engaged
            |
            v
[ Stage 3: Remediation & Out-of-Band Reconciliation ]
  - Bitemporal WAL replay from last confirmed Merkle checkpoint
  - Saga compensation triggered for unconfirmed reservations
  - Subsystem rollback (eBPF profile, WASM binary, controller)
            |
            v
[ Stage 4: Post-Incident Review & Regulatory Notification ]
  - DORA Article 19 initial notification within 4 hours
  - Offline cryptographic evidence pack assembled (JCS + Ed25519)
  - Root cause analysis and mitigation ledger update
```

---

## 3. Immediate Containment Actions (Kill-Switches)

### 3.1 Emergency Execution Freeze (Station 1 Circuit Breaker)
To immediately block all outbound mutations without terminating host processes:
```bash
# Trips the global pre-dispatch interlock into lock-down mode
python3 -c "from src.eo1_write_before_execute import PreDispatchIntentInterlock; PreDispatchIntentInterlock.trip_global_lockout()"
```
*Expected Result*: All subsequent `/v1/aeib/dispatch` requests immediately return HTTP 503 with disposition `HALT_SYSTEM_CIRCUIT_BREAKER_ACTIVE`.

### 3.2 Kernel-Level Egress Isolation (Tetragon BPF-LSM)
If an agent process displays rogue network activity:
```bash
# Enforce immediate Sigkill override via Tetragon CLI
tetra tracingpolicy delete tetragon-aeib-enforcer
tetra tracingpolicy apply compliance/emergency_isolation_policy.yaml
```

### 3.3 Unix Domain Socket Severance
To sever untrusted client agent IPC access:
```bash
rm -f /var/run/aeib/mcp_boundary.sock
```

---

## 4. Subsystem Rollback Procedures

### 4.1 Layer 1: eBPF-LSM Security Profile Rollback
**Trigger**: Kernel log indicates verifier errors or unintended syscall blocking on benign operational paths.
1. Revert to the previous certified profile:
   ```bash
   python3 src/bpf_lsm_profile_compiler.py --compile compliance/tetragon_aeib_enforcer.yaml --output-manifest output/bpf_lsm_profile.json
   ```
2. Validate profile integrity:
   ```bash
   python3 src/bpf_lsm_profile_compiler.py --lint output/bpf_lsm_profile.json
   ```
3. Reload policy into kernel subsystem.

### 4.2 Layer 2: WebAssembly Verifier Rollback
**Trigger**: WASM engine crashes or digest mismatch against signed release manifest.
1. Re-build reproducible WASM from pinned source:
   ```bash
   ./scripts/build_reproducible_wasm.sh
   ```
2. Assert SHA-256 matches the pinned release receipt:
   ```bash
   shasum -a 256 smaos_verify.wasm | grep -q "6ecc360af19008632c950d94910b70220e3c2cc36a5cc29fe0c33ba64d2bb041"
   ```
3. Run verification test suite:
   ```bash
   node tests/test_smaos_verify_wasm.js
   ```

### 4.3 Layer 3: Direct-I/O WAL & Bitemporal Ledger Restoration
**Trigger**: Filesystem corruption, unplanned power failure, or out-of-sync cluster node.
1. Mount the cold vault backup from external physical NVMe SSD:
   ```bash
   # Mount external drive
   test -d /Volumes/EXTssd/SovereignNexus_Backup || exit 1
   ```
2. Verify backup SHA-256 digest against `evidence-hashes.txt`:
   ```bash
   python3 tools/standalone_offline_verifier.py --verify-bundle /Volumes/EXTssd/SovereignNexus_Backup
   ```
3. Replay WAL entries strictly up to the last verified bitemporal checkpoint:
   ```bash
   python3 -m src.storage.postgres_tcc_ledger --replay-wal --from-checkpoint /Volumes/EXTssd/checkpoint.json
   ```

### 4.4 Layer 4: Cryptographic Key Revocation and Step-Up
**Trigger**: Suspected leakage of an operational dispatch signing key.
1. Issue key revocation warrant signed by 2-of-3 quorum:
   ```bash
   python3 -m src.auth.key_revocation --revoke-key-id KEY_DISPATCH_OPERATIONAL_01 --quorum-certs cert1.json cert2.json
   ```
2. Invalidate policy epoch; Station 1 will reject any dispatch bearing the revoked key thumbprint with `HALT_REVOKED_SIGNING_KEY`.
3. Activate standby key from TPM 2.0 enclave.

---

## 5. DORA Article 19 Regulatory Notification Protocol

1. **Initial Notification ($\le 4\text{ hours}$)**:
   - Identify incident classification, affected services, and preliminary root cause.
   - Transmit formal notice to competent authority (e.g. National Competent Authority / EBA).
2. **Intermediate Report ($\le 24\text{ hours}$)**:
   - Provide status of containment, estimated recovery time, and observed financial impact.
3. **Final Report ($\le 1\text{ month}$ post-resolution)**:
   - Submit comprehensive root cause analysis with cryptographic evidence bundle signed via `tools/standalone_offline_verifier.py`.
