# AEIB Native Runtime v1.0 — Adversarial Code Audit

This report details the findings from an independent clean-room security and logic audit of the AEIB Native Java Runtime implemented in `aeib-native-runtime/`.

## 1. JSON Injection Vulnerability in CAID Envelope (Station 1)
**Severity: CRITICAL**
**Location**: `Station1DispatchInterlock.java:44`

**Issue**: The `caidEnvelope` is constructed using `String.format("{\"capabilityIdentifier\":\"%s\"...", action.capabilityIdentifier())`. If an attacker crafts a `capabilityIdentifier` or `noun` containing double quotes (`"`), they can inject arbitrary JSON fields or manipulate the canonicalized envelope, defeating the cryptographic binding.
**Impact**: CAID collisions or signature bypassing.
**Fix**: Use Jackson's `ObjectMapper` (which is already on the classpath via `aeib-crypto`) to safely serialize the map before passing it to `JsonCanonicalizer`.

## 2. Semaphore Leak & Uncancelled Virtual Threads (Station 2)
**Severity: CRITICAL**
**Location**: `Station2EffectReconciler.java:34`

**Issue**: In `resolveIndeterminate()`, if the probe future exceeds the reconciliation deadline, a `TimeoutException` is caught, and the method correctly returns `EFFECT_INDETERMINATE`. However, `probeFuture.cancel(true)` is NEVER called.
**Impact**: 
1. The virtual thread continues executing in the background forever if the network hangs.
2. The `Semaphore` permit acquired inside `executeReconciliationProbe()` will not be released until the hanging network call finishes (if ever). Over time, this leads to a silent Semaphore starvation (Denial of Service) where all budget permits are locked by abandoned ghost threads.
**Fix**: Call `probeFuture.cancel(true)` in the `TimeoutException` block to issue an interrupt to the Virtual Thread, allowing the underlying target status client to abort its socket and release the Semaphore.

## 3. Unbounded File Load in Verifier (CLI)
**Severity: LOW / MEDIUM**
**Location**: `VerifierCli.java:19`

**Issue**: `Files.readAllBytes(Paths.get(args[0]))` loads the entire payload directly into memory. While acceptable for a prototype, this opens the door to out-of-memory (OOM) Denial of Service attacks if the verifier is fed a maliciously large file (e.g., a 10GB payload).
**Fix**: Implement a bounded payload check (e.g., maximum 50 MB) before reading the bytes.

## 4. Operation ID Collision in Hash-Chain Binding (Station 3)
**Severity: MEDIUM**
**Location**: `Station3ContinuousLedger.java:39`

**Issue**: The `eventBinding` string relies on colon (`:`) separators: `String.format("%s:%s:%d:%s", event.operationId(), ...)`. If an `operationId` string naturally contains colons, it could create ambiguous hash structures (parsing collisions).
**Fix**: Use a canonical JSON structure (RFC 8785) for the ledger event binding, just like in Station 1, to eliminate ambiguity.
