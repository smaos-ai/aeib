# Key Management & Cryptographic Agility Policy
## Hardware Custody, 90-Day Rotation Cadence, and Multi-Party Quorum Revocation

> **Regulatory Reference:** Regulation (EU) 2022/2554 (DORA) Article 9(4)(c); NIST SP 800-57 Part 1; NIST FIPS 186-5; NIST FIPS 204 (ML-DSA)  
> **Classification:** Pre-Production Security Governance & Cryptographic Custody Policy  
> **Epistemic Notice:** This policy governs key lifecycle management and post-quantum migration evaluated under the stated model of our execution boundary architecture.

---

### 1. Key Custody & Hardware Security Boundaries

All cryptographic keys utilized by the AEIB boundary are maintained under strict hardware or system-enforced isolation:

1. **Production Boundary Signing Keys:**
   - Reside strictly within Hardware Security Modules (FIPS 140-3 Level 3+), Cloud Key Management Services (AWS KMS, Azure Key Vault with HSM protection), or local hardware enclaves (Apple Secure Enclave).
   - Zero plaintext private keys are ever stored on persistent disk or in environment variables in production.
2. **Local CI & Developer Scaffolding:**
   - Uses ephemeral, memory-only key pairs generated via `cryptography.hazmat` (Ed25519) during test execution, cleaned up immediately upon process exit.
3. **Agent MicroVM Credential Starvation:**
   - Agent guest processes possess zero private signing keys and zero bearer credentials. All cryptographic signatures over tool requests and external wire dispatches are executed exclusively by host-side Station 1 and Station 2 adapters.

---

### 2. Key Rotation Cadence & Epoch Verification

```
+-----------------------------------------------------------------------------------+
|                       KEY LIFECYCLE & ROTATION TIMELINE                           |
+-----------------------------------------------------------------------------------+
| Active Epoch:  |-------------------- 90 Days Active Signing -------------------->|
| Read-Only:                               |------ 7-Year Historical Verification ->|
| Transition:    [Epoch N Active] -> [30-Day Overlap Window] -> [Epoch N+1 Active]  |
+-----------------------------------------------------------------------------------+
```

* **90-Day Rotation Cadence:** Primary boundary signing keys rotate every 90 days (`gate-key-v1` $\to$ `gate-key-v2`).
* **Epoch-Bound Public Key Registry:** Historical public keys remain permanently accessible in a read-only epoch verification map (`evidence/key_epoch_registry.json`).
* **Historical Ledger Verifiability:** Rotating the signing key does not invalidate past entries in `ledger.jsonl`; verifiers query the public key associated with the `policy_epoch` recorded in the entry.

---

### 3. Emergency Compromise Revocation Protocol

In the event of suspected key compromise:

1. **Quorum Requirement:** Emergency revocation requires a 2-of-3 human supervisor quorum (CISO Delegate, Lead Security Engineer, Risk Officer).
2. **Key Revocation List (KRL):** A canonical RFC 8785 JCS revocation statement containing the compromised key thumbprint, revocation timestamp, and successor key thumbprint is generated.
3. **SCITT Log Anchoring:** The KRL is signed by the 2-of-3 quorum and published to the external SCITT transparency service.
4. **Immediate Fail-Closed Halt:** Upon ingesting the KRL, all Station 1 instances reject any incoming warrants signed by the revoked key and require supervisor step-up authorization.
