# EDEN Cluster D: DigitalWitnessCapsule Spec

**Date:** 2026-05-29  
**Status:** Implementation Ready (TDD)  
**Crate:** `siss-agent-shell`  
**File:** `crates/siss-agent-shell/src/missions/witness.rs`  
**Deliverable:** 400-500 LOC, 10+ tests passing, zero clippy warnings

---

## Overview

DigitalWitnessCapsule enables cryptographic witness provenance for authoritarian/conflict-zone contexts. Core design:
- **Immutable witness generation** — UUID-based cryptographic identity with AP2 ledger signing
- **QR code distribution** — Offline-safe encoding for censorship bypass
- **DID support** — W3C-compatible Decentralized Identity integration
- **Ledger integration** — AP2 burn ledger signing for tamper-proof audit trail
- **Resilience** — All content distributable offline (Tor + mesh-compatible)

---

## Core Data Structures

### DigitalWitnessCapsule (Main)

```rust
pub struct DigitalWitnessCapsule {
    pub witness_id: Uuid,          // Unique witness identity
    pub did: String,                // W3C DID (e.g., "did:soverign:abc123")
    pub content_hash: String,       // SHA-256 of witness content
    pub timestamp: DateTime<Utc>,  // Creation time (UTC)
    pub nonce: Uuid,               // AP2 ledger nonce (for burn signature)
    pub signature: Vec<u8>,        // Cryptographic signature from AP2 ledger
    pub qr_code: String,           // QR-encoded witness (base64)
    pub resilience_tags: Vec<String>, // ["tor", "mesh", "offline"]
}
```

### WitnessContent

```rust
pub struct WitnessContent {
    pub evidence: String,          // Text evidence or testimony
    pub context: String,           // Contextual metadata
    pub origin: String,            // Geographic/organizational origin
    pub timestamp: DateTime<Utc>,
}
```

### WitnessGenerationError

```rust
pub enum WitnessGenerationError {
    QrEncodingFailed(String),
    DidGenerationFailed(String),
    LedgerSigningFailed(String),
    ContentHashFailed(String),
    ResilienceIntegrationFailed(String),
}
```

---

## Core Functions

### 1. `new(content: WitnessContent) -> Self`
- Create capsule with fresh UUID, DID
- Hash content (SHA-256)
- Generate nonce for AP2 ledger
- Initialize resilience_tags with ["offline", "tor", "mesh"]
- **Signature:** Deferred (call sign_with_ap2_ledger next)

### 2. `sign_with_ap2_ledger(&mut self, ledger: &Ap2BurnLedger, signer: impl Signer) -> Result<(), WitnessGenerationError>`
- Use AP2 ledger burn nonce (from witness_id)
- Sign witness_id + content_hash with ledger signer
- Populate signature field
- Register in ledger with MandateState::Active

### 3. `generate_did(&self) -> String`
- Format: `did:sovereign:<witness_id_hex>`
- Update self.did
- Return DID for external use

### 4. `generate_qr_code(&self) -> Result<String, WitnessGenerationError>`
- Serialize capsule to JSON
- Encode as base64
- Generate QR (using `qrcode` crate or mock in tests)
- Return base64-encoded QR

### 5. `validate_offline_distribution(&self) -> Result<(), WitnessGenerationError>`
- Verify all resilience_tags populated
- Verify QR code exists and is valid base64
- Verify DID format correct
- Verify signature not empty
- Return Ok(()) if all pass

### 6. `sync_to_ledger(&self, ledger: &mut Ap2BurnLedger) -> Result<(), WitnessGenerationError>`
- Call ledger.register() with witness_id nonce
- On success, return Ok(())
- On NonceAlreadyBurned, return WitnessGenerationError::LedgerSigningFailed

---

## Test Suite (10+ tests required)

### Basic Generation Tests

1. `test_witness_new_creates_valid_capsule`
   - Create capsule with sample content
   - Assert witness_id is UUID v4
   - Assert timestamp is recent (within 1s)
   - Assert resilience_tags include ["offline", "tor", "mesh"]

2. `test_witness_generate_did_format_valid`
   - Create capsule, call generate_did()
   - Assert DID matches pattern `did:sovereign:[0-9a-f]{32}`

3. `test_witness_content_hash_deterministic`
   - Create two capsules with same content
   - Assert content_hash values match

### QR Code Tests

4. `test_witness_qr_code_generation_succeeds`
   - Create capsule, call generate_qr_code()
   - Assert qr_code is non-empty
   - Assert qr_code decodes as valid base64

5. `test_witness_qr_code_contains_all_fields`
   - Generate QR, decode base64
   - Parse as JSON
   - Assert all fields present: witness_id, did, content_hash, timestamp, resilience_tags

6. `test_witness_qr_code_roundtrip_decode`
   - Create capsule, generate QR
   - Decode QR payload
   - Re-deserialize to DigitalWitnessCapsule struct
   - Assert fields match original

### Ledger Integration Tests

7. `test_witness_ap2_ledger_signing`
   - Create capsule
   - Create mock AP2 burn ledger
   - Call sign_with_ap2_ledger()
   - Assert signature is non-empty
   - Assert witness registered in ledger

8. `test_witness_ledger_nonce_collision_rejected`
   - Create two capsules
   - Sign both with same ledger
   - Assert second signing fails with LedgerSigningFailed

9. `test_witness_sync_to_ledger_idempotent`
   - Create capsule, sign it
   - Call sync_to_ledger() twice
   - First succeeds, second fails gracefully (idempotent)

### Resilience & Validation Tests

10. `test_witness_offline_distribution_validation_passes`
    - Create signed capsule with QR code
    - Call validate_offline_distribution()
    - Assert Ok(())

11. `test_witness_offline_distribution_rejects_unsigned`
    - Create capsule (not signed)
    - Call validate_offline_distribution()
    - Assert Err(WitnessGenerationError::...)

12. `test_witness_resilience_tags_persistent`
    - Create capsule
    - Assert resilience_tags unchanged after serialization

---

## Integration Points

### AP2 Ledger
- Import `Ap2BurnLedger` from `ap2_ledger.rs`
- Nonce = witness_id (no secondary UUID)
- Register witness on sign_with_ap2_ledger()

### Signer Trait (from siss-gatekeeper)
- Import `Signer` trait for signing witness_id + content_hash
- Implement trait for mock signer in tests

### Serialization
- Use `serde` + `serde_json` for JSON encoding
- Ensure all fields serialize for QR distribution

---

## Success Criteria

- [ ] `cargo test -p siss-agent-shell witness -- --nocapture` 10+ tests pass
- [ ] `cargo clippy -p siss-agent-shell -- -D warnings` zero warnings
- [ ] `cargo check -p siss-agent-shell` passes
- [ ] All functions implemented per spec
- [ ] QR codes generate and decode correctly
- [ ] AP2 ledger integration working
- [ ] DID format valid (W3C-compatible)
- [ ] All resilience tags persist through serialization

---

## Notes

- **Immutability:** Once signed, capsule contents should be considered read-only (no internal mutations after signature).
- **Offline-first:** QR code is the primary distribution mechanism; design for low-bandwidth scenarios.
- **Timestamping:** All timestamps use UTC via `chrono::Utc`.
- **Error handling:** Return WitnessGenerationError for all fallible operations (no panics).

---

**Status:** Ready for TDD implementation (tests first, then code).
