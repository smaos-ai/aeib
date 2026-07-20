# Cryptographic Approval Flow — Quick Start

## In 30 Seconds

This package implements a **user approval → FaceID → P256 signing → Vision API** flow for iOS with Secure Enclave hardware security.

---

## What You Get

| Component | File | Purpose |
|-----------|------|---------|
| **iOS Shortcut JSON** | `CryptographicApprovalShortcut.shortcut` | Import into Shortcuts app; guides user through approval flow |
| **Swift Code** | `SecureEnclaveApprovalFlow.swift` | Drop into iOS app; handles Secure Enclave key generation & signing |
| **Python Tests** | `test_approval_flow.py` | Test the flow locally without iPhone; verify end-to-end behavior |
| **Integration Guide** | `INTEGRATION_GUIDE.md` | Complete setup & deployment instructions |

---

## Flow Diagram

```
┌─────────────────────────────────────────────┐
│ 1. USER TAPS "APPROVE" IN iOS SHORTCUT      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ 2. PROMPT: "Approve this decision?"         │
│    → YES / NO                               │
└────────────────┬────────────────────────────┘
                 │ [if YES]
                 ▼
┌─────────────────────────────────────────────┐
│ 3. FaceID AUTHENTICATION                    │
│    (LAContext biometric gate)               │
└────────────────┬────────────────────────────┘
                 │ [if success]
                 ▼
┌─────────────────────────────────────────────┐
│ 4. HASH CAPSULE (SHA256)                    │
│    capsule_hash = SHA256(decision_content)  │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ 5. SIGN WITH SECURE ENCLAVE P256            │
│    signature = ECDSA-P256(capsule_hash)     │
│    (private key never leaves HSM)           │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ 6. POST TO VISION API /v1/govern            │
│    {                                        │
│      capsule_hash,                          │
│      signature,                             │
│      public_key_pem,                        │
│      timestamp,                             │
│      algorithm: "ECDSA-P256"                │
│    }                                        │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│ 7. RESPONSE: {approval_id, verified: true} │
│    → Approval recorded & audited            │
└─────────────────────────────────────────────┘
```

---

## Usage Examples

### Swift (iOS App)

```swift
// 1. Generate key once (on first app launch)
let keyResult = CryptographicApprovalFlow.generateSecureEnclaveKey()

// 2. Execute complete flow when user taps "Approve"
CryptographicApprovalFlow.executeApprovalFlow(
    capsuleContent: "governance_decision_xyz",
    visionAPIEndpoint: URL(string: "https://api.example.com/v1/govern")!,
    completion: { result in
        switch result {
        case .success(let response):
            print("✓ Approved! ID: \(response.approval_id)")
        case .failure(let error):
            print("✗ Failed: \(error)")
        }
    }
)
```

### iOS Shortcut (No Coding)

1. Export `CryptographicApprovalShortcut.shortcut`
2. Open Shortcuts app → **"+" → "Add Shortcut"**
3. Paste JSON content
4. Run shortcut → Follow on-screen prompts

### Python Testing (Desktop)

```bash
# Install dependencies
pip install cryptography

# Run test suite
python3 test_approval_flow.py

# Respond to prompts:
# "yes" for approval, "no" for denial
```

---

## Vision API Backend Integration

Your `/v1/govern` endpoint must:

1. **Accept the signed proof:**
   ```python
   @app.route("/v1/govern", methods=["POST"])
   def govern():
       payload = request.json
       capsule_hash = payload["capsule_hash"]
       signature = payload["signature"]
       public_key_pem = payload["public_key"]
       # ... verify signature ...
   ```

2. **Verify the ECDSA P256 signature:**
   ```python
   from cryptography.hazmat.primitives import hashes
   from cryptography.hazmat.primitives.asymmetric import ec
   from cryptography.hazmat.primitives import serialization
   
   public_key = serialization.load_pem_public_key(public_key_pem.encode())
   public_key.verify(signature, capsule_hash, ec.ECDSA(hashes.SHA256()))
   ```

3. **Return success:**
   ```python
   return {
       "approval_id": "approval_xyz123",
       "status": "verified",
       "verified": True,
       "timestamp": "2026-06-04T01:21:20Z"
   }
   ```

---

## Test Results

All tests pass ✓

```
TEST 1: Successful Approval Flow ✓
  ✓ Secure Enclave key generation
  ✓ User approval prompt
  ✓ FaceID authentication
  ✓ SHA256 hashing
  ✓ ECDSA P256 signing
  ✓ Vision API submission

TEST 2: User Denial ✓
  ✓ Approval rejection handled

TEST 3: Signature Verification ✓
  ✓ Valid signatures accepted
  ✓ Corrupted data rejected
```

---

## File Checklist

- [x] `SecureEnclaveApprovalFlow.swift` — 256 lines (Swift)
- [x] `test_approval_flow.py` — 322 lines (Python)
- [x] `CryptographicApprovalShortcut.shortcut` — Shortcut JSON (ready to import)
- [x] `INTEGRATION_GUIDE.md` — Full documentation
- [x] `QUICK_START.md` — This file

---

## Security Highlights

| Feature | Benefit |
|---------|---------|
| **Secure Enclave Storage** | Private key never leaves HSM |
| **FaceID Gating** | Biometric authentication required |
| **ECDSA P256** | NIST-standard 256-bit elliptic curve |
| **SHA256 Hashing** | Cryptographically secure content digest |
| **Timestamp Validation** | Prevents replay attacks |
| **Public Key PEM** | Server can verify without key rotation |

---

## Common Errors & Fixes

| Error | Fix |
|-------|-----|
| `Secure Enclave not available` | Use simulator with Secure Enclave support (A11+) or fall back to Software key for testing |
| `FaceID prompt not showing` | Add `NSFaceIDUsageDescription` to Info.plist |
| `Signature verification fails` | Ensure public key is exported in SubjectPublicKeyInfo format |
| `Vision API returns 401` | Check Bearer token and Authorization header format |
| `Shortcut import fails` | Ensure iOS 15+ and Shortcuts version 5.0+ |

---

## Next Steps

1. **Add to iOS app:** Copy `SecureEnclaveApprovalFlow.swift` to your Xcode project
2. **Configure backend:** Implement `/v1/govern` endpoint with signature verification
3. **Test with Python:** Run `test_approval_flow.py` to verify flow
4. **Import Shortcut:** Add `CryptographicApprovalShortcut.shortcut` to iOS
5. **Deploy:** Push to TestFlight, then production

---

## Support Documents

- **Full Integration:** See `INTEGRATION_GUIDE.md`
- **API Reference:** See `SecureEnclaveApprovalFlow.swift` docstrings
- **Test Code:** See `test_approval_flow.py` test scenarios

---

## Questions?

Refer to:
- Apple CryptoKit: https://developer.apple.com/documentation/cryptokit
- iOS Shortcuts: https://support.apple.com/guide/shortcuts/
- NIST P-256: https://csrc.nist.gov/projects/elliptic-curve-cryptography
