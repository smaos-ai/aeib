# AEIB Gate 3 Independent Reproduction Instructions (`v1.0.0-rc.1`)

## Current Gate 3 Status
**Gate 3 remains pending and is not called complete until separate-party reproduction evidence from the signed tag `v1.0.0-rc.1` exists.**

- **Repository URL:** `https://github.com/smaos-ai/aeib.git`
- **Release Tag:** `v1.0.0-rc.1` (Commit SHA: `b2166a3ffc8f9535a4299dac382dad12ffce85ec`)
- **Hosted CI Reference Runs:**
  - Branch CI (`release/v1.0-review-candidate`): `https://github.com/smaos-ai/aeib/actions/runs/38055110173`
  - Tag CI (`v1.0.0-rc.1`): `https://github.com/smaos-ai/aeib/actions/runs/38055279949`
  - Release Evidence Bundle: `https://github.com/smaos-ai/aeib/releases/tag/v1.0.0-rc.1` (mirrored on disk at `aeib-reproducibility/evidence/v1.0.0-rc.1/`)

The transcript stored at `aeib-reproducibility/gate3/local_developer_verification_log.txt` is explicitly a **local developer verification log** (NOT independent clean-room reproduction). It documents local verification of the harness mechanics on the developer workstation and does not satisfy Gate 3 independent reproduction requirements.

---

## Container Build Context & Network Isolation Policy
- **Build Context (`context: ../..`)**: `aeib-reproducibility/gate3/docker-compose.yml` configures `context: ../..` (the repository root) with `dockerfile: aeib-reproducibility/gate3/Dockerfile` so that `aeib-native-runtime/`, `aeib-reproducibility/`, `benchmarks/`, and `src/` are available inside the image build context.
- **Build-Time vs. Runtime Network Policy**: `docker compose build` may use network access to install OS-level packages (`curl`, `git`, `python3`, `python3-cryptography`) into the `eclipse-temurin:21-jdk-jammy` image. Once built, `aeib-reproducibility/gate3/docker-compose.yml` keeps the runtime container at `network_mode: none` to enforce zero network egress during compilation, test execution, and offline cryptographic receipt verification under the stated model.

---

## Exact Reproduction Sequence from Signed Tag `v1.0.0-rc.1`

A separate person or independent CI runner executing on an isolated machine must run the following sequence from the signed tag `v1.0.0-rc.1`:

1. **Clone the repository and verify/checkout the signed release candidate tag `v1.0.0-rc.1`:**
   ```bash
   git clone https://github.com/smaos-ai/aeib.git
   cd aeib
   git fetch --tags
   git tag -v v1.0.0-rc.1 || git show v1.0.0-rc.1 --quiet
   git checkout v1.0.0-rc.1
   git rev-parse HEAD
   ```

2. **Enter the Gate 3 reproduction harness directory:**
   ```bash
   cd aeib-reproducibility/gate3
   ```

3. **Build the verification image and record its Docker image digest:**
   ```bash
   docker compose build --no-cache
   docker images --digests | grep gate3
   ```

4. **Confirm runtime `network_mode: none` and execute the harness, capturing `third_party_verification_transcript.txt`:**
   ```bash
   grep "network_mode: none" docker-compose.yml
   docker compose run --rm aeib-reproduction 2>&1 | tee third_party_verification_transcript.txt
   ```

---

## Gate 3 Checklist (The Only Remaining Release Blocker)

```text
[ ] Select separate operator or separate CI runner.
[ ] Clone repository from signed tag v1.0.0-rc.1.
[ ] Verify tag signature and commit SHA (b2166a3ffc8f9535a4299dac382dad12ffce85ec).
[ ] Run the exact commands in REPRODUCER.md.
[ ] Run Docker Compose clean-room harness.
[ ] Confirm runtime container uses network_mode: none.
[ ] Capture operator or runner identity.
[ ] Capture host OS and architecture.
[ ] Capture Docker image digest.
[ ] Capture receipt SHA-256 digest.
[ ] Capture public-key fingerprint (SHA-256).
[ ] Capture valid-receipt verifier exit code (expected: 0).
[ ] Capture tampered-receipt verifier exit code (expected: non-zero / 2).
[ ] Capture full command transcript.
[ ] Publish third_party_verification_transcript.txt.
[ ] Document any discrepancy.
[ ] Only then mark Gate 3 complete.
```

---

## Gate 5 Checklist (Subsequent to Gate 3)

```text
[ ] Select single-tenant observe-only pilot.
[ ] Define written pilot scope.
[ ] Deploy AEIB in observe-only mode.
[ ] Test kill-switch drill.
[ ] Test rollback procedure.
[ ] Obtain named design-partner sign-off.
[ ] Do not claim operational pilot readiness until complete.
```
