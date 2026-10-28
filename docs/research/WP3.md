# Work Package 3 (WP3): eBPF LSM Hooks & Hardware TEE Attestation

**Target Milestone**: Phase 3 Enterprise Security & Kernel-Level Containment  
**Status**: Deferred from Phase 0/1; Architectural Specification & Verification Protocol  
**Standards Alignment**: Linux LSM BPF (Kernel 5.7+), Intel TDX Attestation, AMD SEV-SNP API  

---

## 1. Executive Summary

Autonomous AI agents executing arbitrary bash commands or dynamic tools represent high-risk execution environments. User-space policy engines and prompt guardrails are susceptible to bypass through sub-process spawning, unshare namespaces, and memory tampering.

Work Package 3 specifies the Phase 3 kernel containment and physical hardware attestation layers:
1. **Linux eBPF LSM Security Hooks**: Enforce system-call-level containment directly inside the Linux kernel, preventing unauthorized binary execution, non-allowlisted network egress, and memory write-and-execute (\(W \oplus X\)) violations.
2. **Hardware TEE Attestation (Intel TDX & AMD SEV-SNP)**: Cryptographically bind the AEIB Agent Application Server to physical confidential virtual machine (CVM) character devices (`/dev/tdx_guest` and `/dev/sev-guest`), providing tamper-evident root-of-trust evidence.

---

## 2. Kernel eBPF LSM Architecture

eBPF LSM (Linux Security Module) attaches verifiable in-kernel programs to critical security hooks:

```
[ Agent Application Server / Tool Execution ]
                     │
                     ▼
          [ User-Space System Call ]
                     │
    ┌────────────────┴────────────────┐
    │          Linux Kernel           │
    │  [ LSM Hook: bprm_check_security ] ──► Validates binary against allowlisted CAID sha256
    │  [ LSM Hook: socket_connect ]      ──► Enforces Zero-Egress / Unix Domain Socket only
    │  [ LSM Hook: file_mprotect ]       ──► Enforces strict W^X memory protection
    └────────────────┬────────────────┘
                     │
                     ▼
             [ Hardware CPU / RAM ]
```

### Hook Implementation Contract:
- `LSM_HOOK(bprm_check_security)`: Inspects binary hash before execution. If the binary is not signed or registered in the immutable task manifest, returns `-EPERM`.
- `LSM_HOOK(socket_connect)`: Blocks AF_INET / AF_INET6 egress unless directed to an explicit localhost proxy port or authoritative database socket.
- `LSM_HOOK(file_mprotect)`: Prevents dynamic code generation from marking writable heap/stack pages as executable.

---

## 3. Confidential VM Hardware Attestation

To establish a zero-trust hardware boundary, the agent execution receipts bind a 64-byte `REPORTDATA` nonce directly to the hardware quote:

```
          64-Byte Unique Hash
  H(CAID || SessionId || EpochTime)
                 │
                 ▼
     [ /dev/tdx_guest or /dev/sev-guest ]
                 │
                 ▼
       [ Physical Security Engine ]
  (Intel SGX/TDX Quoting Enclave or AMD Secure Processor)
                 │
                 ▼
  [ Signed Hardware Quote (ECDSA P-384 / Ed25519) ]
```

### Fail-Closed Hardware Contract:
- Under Phase 0/1 evaluation, synthetic stubs are strictly purged.
- When running in an enterprise deployment without hardware CVM devices, the runtime raises `HardwareAttestationUnavailable` rather than synthesizing fake quotes.
- In Phase 3, production enclaves verify quotes against the Intel PCS (Provisioning Certification Service) or AMD KDS (Key Distribution Service) offline roots of trust.

---

## 4. Phase 3 Deliverables & Milestones

1. **eBPF Agent Guard Deployment**:
   - Production loader using `libbpf-rs` or `cilium/ebpf`.
   - Dynamic map updates for agent ephemeral execution scopes.
2. **TDX / SEV Attestation Verifier**:
   - WebAssembly-based offline quote verifier for DORA and ISO 42001 Category H compliance audits.
