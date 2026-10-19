# Independent Reproducer Cleanroom Runbook
## Step-by-Step Cleanroom Verification Instructions for External Reviewers

```text
Document ID        : AEIB-CLEANROOM-RUNBOOK-v1.1
Release Candidate  : v1.0.0-rc.3 / v1.0.0-rc.25
Governing Policy   : Strict zero-egress, zero-mock, caller-supplied public key offline verification
Target Evidence    : artifacts/aeib-pilot-evidence-pack-v1.1.0.tar.gz
Prerequisites      : Python >= 3.11, standard POSIX shell (bash/zsh), OpenSSL
Network Mode       : Disconnected / Air-Gapped (connect-src 'none', zero network calls)
```

---

## 1. Cleanroom Isolation Protocol

To verify that AEIB's evidence bundles and standalone verifiers execute without hidden network dependencies, telemetry exfiltration, or host environment pollution:

### Step 1: Create an Isolated Cleanroom Directory
```bash
# Create an ephemeral cleanroom directory outside the SovereignNexus repository
CLEANROOM_DIR=$(mktemp -d -t aeib_cleanroom_XXXXXX)
echo "[*] Cleanroom staging directory: ${CLEANROOM_DIR}"
cd "${CLEANROOM_DIR}"
```

### Step 2: Extract the Independent Evidence Pack
```bash
# Copy the sealed evidence pack from the release candidate
cp /path/to/SovereignNexus/artifacts/aeib-pilot-evidence-pack-v1.1.0.tar.gz .

# Verify archive integrity
shasum -a 256 aeib-pilot-evidence-pack-v1.1.0.tar.gz

# Extract archive
tar -xzf aeib-pilot-evidence-pack-v1.1.0.tar.gz
cd aeib-pilot-evidence-pack-v1.1.0
```

---

## 2. Air-Gapped Verification Commands

Execute the following commands with `PYTHONPATH=""` and network egress disabled (or verify `0 B` network egress):

### Step 3: Run the Autonomous Pack Verifier
```bash
# Verifies all 21 evidence files against MANIFEST.json, recomputes RFC 8785 JCS digests,
# and verifies Ed25519 cryptographic signatures using the bundled public key:
python3 verifiers/verify_pack.py
```
**Expected Output:**
```text
================================================================================
  AEIB ZERO-MOCK BENCHMARK PACK VERIFIER (v1.1.0)
  Evaluated under the stated model. Preserves strict epistemic lock.
================================================================================
[*] Verifying 21 files against MANIFEST.json...
  ✓ All file digests match MANIFEST.json.
[*] Verifying Proof 1 (MITRE T1048 Exfiltration Prevention)...
  ✓ Proof 1 Ed25519 signatures and RFC 8785 JCS digests valid.
...
  ALL EVIDENCE BUNDLES VERIFIED: ZERO MOCKS, CRYPTOGRAPHIC DETERMINISM OBSERVED
================================================================================
```

### Step 4: Run the Adversarial Negative Vectors
```bash
# Runs the 14-scenario rehearsal matrix and negative falsification suites:
pytest tests/test_enforced_halt_and_delegation.py tests/test_mitre_adversarial_matrix.py -v
```
**Expected Output:**
All adversarial assertions pass fail-closed (`100% PASS` across evaluated vectors).

### Step 5: Standalone WebAssembly Verifier (Zero-Network Browser Verification)
1. Open `smaos-wasm-verifier/smaos-verify.html` in any web browser.
2. Note the strict Content Security Policy (`connect-src 'none'`).
3. Drag and drop any `.json` receipt from `evidence/` along with the public key `evidence/ledger-public.pem`.
4. Inspect local cryptographic verification result in the browser UI.

---

## 3. Reporting Verification Findings

Submit reproduction results to the SovereignNexus repository issue tracker or audit liaison:
```text
Independent Reproducer: <Organization / Reviewer Name>
Environment           : <OS, Kernel Version, Python Version, CPU Architecture>
Execution Date        : <YYYY-MM-DD>
Network Egress Status : Verified 0 bytes transmitted
Pack Verification     : PASS / FAIL
Adversarial Tests     : PASS / FAIL
Identified Anomalies  : <None / Discrepancies noted>
```
