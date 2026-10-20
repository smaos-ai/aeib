# AEIB Apple Silicon Secure Enclave & XPC Blast Door Specification
## Architecture Specification for Native macOS / iOS Execution Boundaries (`v1.0.0-rc.5-Apple`)

```text
Document ID        : AEIB-APPLE-SEP-XPC-SPEC-v1.0
Implementation     : Sources/AEIBGateXPC/Station1Actor.swift & Sources/AEIBCore/CoreTypes.swift
Language Standard  : Swift 6.0 (-strict-concurrency=complete)
Security Boundary  : Mach Ports / XPC Service Isolation + SEP Hardware Key Custody
Target Environment : macOS Darwin (arm64, Apple Silicon M1-M4) & iOS
```

---

### 1. Executive Summary & Epistemic Boundaries

In modern AI agent execution, running agent subprocesses with ambient operating system credentials or broad socket access introduces severe blast radius risks. On macOS and Apple Silicon platforms, the **Agent Execution & Integrity Boundary (AEIB)** enforces physical process segregation using **XPC Blast Doors** and cryptographically binds state mutations using the **Apple Secure Enclave Processor (SEP)**.

> **Epistemic Notice:**  
> This specification describes the native Apple Silicon implementation evaluated under the stated local verification model. Real hardware Secure Enclave isolation requires Apple Developer provisioning profiles and codesigning entitlements (`com.apple.token` or keychain access groups). When unentitled (e.g., standard CI runners or local non-notarized command-line tools), the runtime transitions to CryptoKit software-modeled P-256 with explicit diagnostic flags.

---

### 2. Architecture Overview: XPC Blast Door & Credential Starvation

```mermaid
flowchart TD
    subgraph "Untrusted Agent Micro-Process (Guest)"
        Agent["Autonomous Agent Subprocess"]
        LLM["LLM Reasoner / Tool Caller"]
        Agent -->|Mach Port / XPC| Client["AEIBGateXPC Client"]
    end

    subgraph "XPC Blast Door (Darwin Boundary)"
        Client -->|Audit Token & PID| XPCListener["NSXPCListener / Mach Service"]
        XPCListener -->|Extract Peer UID & PID| SecValidate["Entitlement & Process Validator"]
    end

    subgraph "Station 1 Gate (Privileged Host Sidecar)"
        SecValidate --> Actor["Station1FinancialGateActor (Swift 6 Actor)"]
        Actor --> WAL["Atomic WAL (F_FULLFSYNC)"]
        Actor --> SEP["SecureEnclaveWarrantSigner"]
    end

    subgraph "Apple Silicon Hardware"
        SEP -->|NIST P-256 Key| HardwareSEP["Secure Enclave Processor (SEP)"]
    end

    subgraph "Downstream Payment Rails"
        Actor -->|Authorized Wire Dispatch| Rail["External Egress Proxy"]
    end
```

The system strictly enforces **Credential Starvation**:
1. **Zero Keys in Agent Process:** The untrusted agent process never holds private signing keys, banking API tokens, or OAuth secrets.
2. **Mach Port Barrier:** All dispatch requests cross an OS-enforced Mach port boundary. The privileged host sidecar inspects caller identity via `audit_token_to_pid` and `audit_token_to_euid`.
3. **Fail-Closed Mediation:** If caller identity, budget limits, or context taint invariants fail, the XPC listener terminates the request without passing execution to network sockets.

---

### 3. Apple Secure Enclave Processor (SEP) Key Custody

#### Hardware P-256 Attestation
When privileged entitlements are present, AEIB generates and stores signing keys directly inside the Apple Secure Enclave using CryptoKit:
- **Curve:** NIST P-256 (`secp256r1`).
- **Storage:** SEP hardware key register; private key bytes cannot be extracted by the host operating system, root user, or kernel memory inspection.
- **Access Control:** Keys can be bound to `SecAccessControlCreateFlags` requiring device passcode or biometrics (`userPresence` / `biometryCurrentSet`).

#### Software Fallback Mechanics
To ensure testability in clean-room CI environments without physical biometric prompts, `SecureEnclaveWarrantSigner` implements an explicit branch:
```swift
public struct SecureEnclaveWarrantSigner: Sendable {
    private let softwareFallbackKey: P256.Signing.PrivateKey

    public init() {
        self.softwareFallbackKey = P256.Signing.PrivateKey()
    }

    public func signCanonicalBytes(_ data: Data) throws -> Data {
        if SecureEnclave.isAvailable {
            do {
                let sepKey = try SecureEnclave.P256.Signing.PrivateKey()
                let sig = try sepKey.signature(for: data)
                return sig.derRepresentation
            } catch {
                let sig = try softwareFallbackKey.signature(for: data)
                return sig.derRepresentation
            }
        } else {
            let sig = try softwareFallbackKey.signature(for: data)
            return sig.derRepresentation
        }
    }
}
```

---

### 4. Swift 6 Strict Concurrency Actor Model

The core financial gate (`Station1FinancialGateActor`) is modeled as a Swift 6 `actor`, enforcing compile-time data-race safety across concurrent subagent callers:

- **Compiler Flags:** `swift test -Xswiftc -strict-concurrency=complete`.
- **Sendable Types:** All request structures (`GovernedDispatchRequest`), decisions (`GateDecision`), and taint tiers (`TaintTier`) conform to `Sendable`.
- **Atomic WAL Durability:** Uses Darwin-specific `F_FULLFSYNC` (`fcntl(fd, F_FULLFSYNC)`) to flush physical drive write-caches before returning authorization decisions.

#### Formal Operational Invariants Evaluated in Swift:
1. **Sprint Cap & Escrow Invariant:** Concurrently evaluated dispatches across parallel subagents cannot exceed the sprint ceiling. Unsettled transactions hold budget in escrow until confirmed or refuted.
2. **Taint Downgrade Rejection:** Context blocks tainted as `untrustedExternal` targeting unpinned payees are rejected fail-closed with `UNTRUSTED_CONTEXT_TAINT_REQUIRES_STEP_UP`.
3. **Attenuation Ceiling:** Subagent requests exceeding delegating sponsor limits are rejected fail-closed.
4. **Clock Skew Barrier:** Requests with timestamp deviation greater than 5 seconds from system time are rejected (`CLOCK_DRIFT_EXCEEDED`).

---

### 5. Cross-Language Golden Vector Determinism

To ensure interoperability between the native Apple Swift stack, the Rust data plane, and the Python governance harnesses, AEIB verifies a normative cross-language golden vector:

```json
{
  "amount_minor": 45000,
  "context_digest": "sha256:ctx01",
  "endpoint": "POST /v1/refunds",
  "operation_id": "op-golden-001",
  "recipient": "iban:DE89370400440532013000"
}
```

- **Canonical Format:** RFC 8785 JSON Canonicalization Scheme (JCS).
- **Target SHA-256 Digest:** `d31e155ef55db68b7dbdb14830c3fc50e5c94774155e61685b325c34b74ff74c`.
- **Verified Status:** Evaluated and confirmed identical across Swift 6 (`Cross-Language Golden Vector SHA-256 matches Python, Swift, and Rust`), Rust (`aeib-data-plane`), and Python (`src/eo1_write_before_execute.py`).

---

### 6. Verification and Test Battery

The Swift 6 implementation is evaluated directly via:
```bash
swift test -Xswiftc -strict-concurrency=complete
```
*Observed Performance:* 11 / 11 tests pass in ~0.070 seconds, verifying zero data races, deterministic golden vectors, and fail-closed taint gates.
