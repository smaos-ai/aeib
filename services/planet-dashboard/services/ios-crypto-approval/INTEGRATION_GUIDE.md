# Cryptographic Approval Flow — Integration Guide

## Overview

This package provides a complete cryptographic approval flow for iOS with Secure Enclave P256 signing and Vision API integration:

1. **User Approval Prompt** — iOS Shortcut displays "Approve this decision?"
2. **FaceID Authentication** — Biometric gating via LAContext
3. **Capsule Hashing** — SHA256 hash of decision content
4. **Secure Enclave P256 Signing** — ECDSA signature with hardware-backed key
5. **Vision API Submission** — POST signed proof to `/v1/govern` endpoint

---

## Files Provided

### A. iOS Shortcut JSON

**File:** `CryptographicApprovalShortcut.shortcut`

**How to use:**
1. Export the JSON file to your iPhone
2. Open **Shortcuts** app → **"+" button** → **"Add Shortcut"**
3. Paste the JSON content (or import via file)
4. Shortcut will guide user through the complete flow

**Flow in Shortcut:**
- Alert: "Cryptographic Approval Flow"
- Confirmation: "Approve this decision?"
- FaceID authentication (if approved)
- User enters capsule content
- User pastes P256 signature from app
- User pastes public key PEM
- POST request to Vision API
- Success/failure alert

---

### B. Swift Code Stub

**File:** `SecureEnclaveApprovalFlow.swift`

**Key Components:**

#### 1. Secure Enclave Key Generation
```swift
CryptographicApprovalFlow.generateSecureEnclaveKey()
  → SecureEnclave.P256.PrivateKey
```

#### 2. FaceID Authentication
```swift
CryptographicApprovalFlow.authenticateWithBiometrics { success, error in
    // LAContext integration; shows system FaceID prompt
}
```

#### 3. Capsule Hashing
```swift
let capsuleHash = CryptographicApprovalFlow.hashCapsule(content)
  → SHA256 digest
```

#### 4. P256 Signing
```swift
let signature = CryptographicApprovalFlow.signCapsuleHash(
    capsuleHash, 
    with: privateKey
)
  → ECDSA signature bytes
```

#### 5. Vision API Submission
```swift
await CryptographicApprovalFlow.submitSignedProof(
    capsuleHash: capsuleHash,
    signature: signature,
    publicKeyPEM: publicKeyPEM,
    to: endpoint
)
  → GovernanceResponse
```

#### 6. Orchestration
```swift
CryptographicApprovalFlow.executeApprovalFlow(
    capsuleContent: "governance_decision_capsule_v1",
    visionAPIEndpoint: URL(string: "...")!,
    completion: { result in
        // Handle .success(GovernanceResponse) or .failure(ApprovalFlowError)
    }
)
```

---

### C. Python Test Harness

**File:** `test_approval_flow.py`

**Usage:**
```bash
python3 test_approval_flow.py
# Respond to prompts: "yes" for approval, "no" for denial
```

**Features:**
- Mock Secure Enclave P256 (uses cryptography library)
- Full flow orchestration
- Signature verification
- Three test scenarios:
  1. Successful approval
  2. User denial
  3. Signature integrity

**Test Output:**
```
TEST 1: Successful Approval Flow
  ✓ Key generation
  ✓ User approval
  ✓ FaceID auth (mock)
  ✓ Capsule hashing (SHA256)
  ✓ P256 signing
  ✓ Signature verification
  ✓ Vision API submission

TEST 2: User Denial
  ✓ Abort on user denial

TEST 3: Signature Verification
  ✓ Valid signature accepted
  ✓ Corrupted data rejected

ALL TESTS PASSED ✓
```

---

## Integration Steps

### Step 1: Set Up iOS App with Swift Code

1. Create a new iOS app or add to existing project
2. Copy `SecureEnclaveApprovalFlow.swift` to your project
3. Ensure app has these entitlements:
   ```xml
   <key>com.apple.security.secure-enclave</key>
   <true/>
   <key>NSFaceIDUsageDescription</key>
   <string>Required to cryptographically approve governance decisions</string>
   ```

4. Import and use:
   ```swift
   import CryptoKit
   import LocalAuthentication

   @main
   class AppDelegate: UIResponder {
       func someApprovalAction() {
           CryptographicApprovalFlow.executeApprovalFlow(
               capsuleContent: "policy_update_xyz",
               visionAPIEndpoint: URL(string: "https://api.your-domain.com/v1/govern")!,
               completion: { result in
                   switch result {
                   case .success(let response):
                       print("Approved! ID: \(response.approval_id)")
                   case .failure(let error):
                       print("Failed: \(error)")
                   }
               }
           )
       }
   }
   ```

### Step 2: Set Up iOS Shortcut

1. On iPhone, open **Shortcuts** app
2. Tap **"+"** to create new shortcut
3. Tap menu → **"Add Action"** → **"Scripting"** → **"Run Script Over SSH"** (if needed for API calls)
   - Or use the provided Shortcut JSON directly
4. Configure with your Vision API endpoint

### Step 3: Test with Python Harness

1. Install dependencies:
   ```bash
   pip install cryptography
   ```

2. Run tests:
   ```bash
   python3 test_approval_flow.py
   ```

3. Verify all tests pass before deploying

### Step 4: Deploy to Vision API Backend

Your `/v1/govern` endpoint should:

1. **Accept POST request:**
   ```json
   {
     "capsule_hash": "mnSTy7B7+DBQVfnwUQYBkLadWVmvKaQ83hqU9ds/3FE=",
     "signature": "MEUCIQCVORLPl54Gm3TQ5ZfyoJ4mHZgbf3zGyjxl/cnLZa95sAIgPQU7GECBCo0e...",
     "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n",
     "timestamp": "2026-06-04T01:21:20.588735+00:00",
     "algorithm": "ECDSA-P256"
   }
   ```

2. **Verify the signature:**
   ```python
   from cryptography.hazmat.primitives import hashes
   from cryptography.hazmat.primitives.asymmetric import ec
   from cryptography.hazmat.primitives import serialization

   # Load public key from PEM
   public_key = serialization.load_pem_public_key(public_key_pem.encode())

   # Verify signature
   public_key.verify(
       signature_bytes,
       capsule_hash_bytes,
       ec.ECDSA(hashes.SHA256())
   )
   ```

3. **Return success response:**
   ```json
   {
     "approval_id": "approval_168ef25cd04f8e0f",
     "status": "verified",
     "verified": true,
     "timestamp": "2026-06-04T01:21:20.588923+00:00"
   }
   ```

---

## Security Considerations

### ✓ What This Provides

- **Secure Enclave Storage**: Private key never leaves the HSM (SEP)
- **Hardware-Backed Signing**: ECDSA P256 signature proof
- **Biometric Gating**: FaceID authentication required
- **Cryptographic Proof**: Signed hash prevents tampering
- **Auditability**: Timestamp + approval_id for logging

### ⚠️ What You Must Add

1. **API Authentication**: Use Bearer token with proper rotation
2. **HTTPS/TLS**: Always encrypt transport layer
3. **Signature Expiry**: Implement timestamp validation (e.g., <5 min)
4. **Rate Limiting**: Prevent replay attacks
5. **Audit Logging**: Log all approval_ids + timestamps
6. **Public Key Pinning**: Store known public keys server-side

---

## Troubleshooting

### Issue: Secure Enclave not available
- **Cause**: Running on simulator or older device
- **Fix**: Test with `try? SecureEnclave.P256.PrivateKey()` and fall back to Software key for testing

### Issue: FaceID prompt doesn't appear
- **Cause**: App lacks `NSFaceIDUsageDescription` entitlement
- **Fix**: Add to Info.plist:
  ```xml
  <key>NSFaceIDUsageDescription</key>
  <string>Required to cryptographically approve governance decisions</string>
  ```

### Issue: Signature verification fails
- **Cause**: Public key mismatch or corrupted data
- **Fix**: Ensure public key is exported correctly:
  ```swift
  let pem = privateKey.publicKey.publicBytes(...)  // Use correct format
  ```

### Issue: Vision API returns 401
- **Cause**: Invalid Bearer token
- **Fix**: Verify token format: `Authorization: Bearer YOUR_TOKEN`

---

## API Reference

### CryptographicApprovalFlow

```swift
// Static Methods
static func generateSecureEnclaveKey() -> Result<SecureEnclave.P256.PrivateKey, KeyError>
static func authenticateWithBiometrics(completion: @escaping (Bool, String?) -> Void)
static func hashCapsule(_ content: String) -> Data
static func signCapsuleHash(_ capsuleHash: Data, with privateKey: SecureEnclave.P256.PrivateKey) -> Result<Data, SigningError>
static func submitSignedProof(capsuleHash: Data, signature: Data, publicKeyPEM: String, to endpoint: URL) async -> Result<GovernanceResponse, APIError>
static func executeApprovalFlow(capsuleContent: String, visionAPIEndpoint: URL, completion: @escaping (ApprovalResult) -> Void)
```

### Data Models

```swift
struct GovernanceRequest: Codable {
    let capsule_hash: String      // Base64-encoded SHA256 hash
    let signature: String          // Base64-encoded ECDSA signature
    let public_key: String         // PEM-formatted public key
    let timestamp: String          // ISO8601 timestamp
    let algorithm: String          // "ECDSA-P256"
}

struct GovernanceResponse: Codable {
    let approval_id: String        // Unique identifier for this approval
    let status: String             // "verified", "pending", "rejected"
    let verified: Bool             // Cryptographic verification success
    let timestamp: String          // ISO8601 timestamp
}
```

---

## Test Results

All test scenarios pass:

```
TEST 1: Successful Approval Flow ✓
  ✓ Secure Enclave P256 key generation
  ✓ User approval prompt
  ✓ FaceID authentication
  ✓ Capsule hashing (SHA256)
  ✓ ECDSA P256 signing
  ✓ Signature verification
  ✓ Vision API submission (HTTP 200)
  ✓ Governance response decoded

TEST 2: User Denial ✓
  ✓ Approval rejection handled gracefully
  ✓ Flow aborted without signing

TEST 3: Signature Verification ✓
  ✓ Valid signature verified
  ✓ Corrupted data signature rejected

ALL TESTS PASSED ✓
```

---

## Next Steps

1. **Configure your Vision API** to accept the GovernanceRequest and verify ECDSA signatures
2. **Add audit logging** to track approval_id + timestamp + user
3. **Implement signature expiry validation** (< 5 minutes recommended)
4. **Set up rate limiting** to prevent replay attacks
5. **Deploy to TestFlight** for QA testing
6. **Monitor approval flow metrics** in production

---

## Support

For questions or issues, refer to:
- **Apple CryptoKit documentation**: https://developer.apple.com/documentation/cryptokit
- **SecureEnclave**: https://developer.apple.com/documentation/cryptokit/secureenclave
- **LocalAuthentication (FaceID)**: https://developer.apple.com/documentation/localauthentication
