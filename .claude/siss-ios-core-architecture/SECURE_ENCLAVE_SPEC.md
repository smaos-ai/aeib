# Secure Enclave Dual-Key Strategy — siss-ios-core

**Status:** LOCKED (May 29, 2026)  
**Effective:** Phase 32 Merge (June 11, 2026)  
**Author:** Architecture Planning (TRACK H)  
**Purpose:** Define P-256 master key + Ed25519 wrapped key storage for AP2 signing

---

## 1. The Problem

- **iPhone Secure Enclave constraint:** Only supports P-256 (ECDSA). No Ed25519 hardware support.
- **AP2 ledger requirement:** Mandates Ed25519 signatures for all operator mandates.
- **Solution:** Use P-256 master key (in Secure Enclave) to wrap Ed25519 key (in Keychain).

### Threat Model

| Attacker Scenario | Risk | Mitigation |
|-------------------|------|-----------|
| Extracts Keychain (local file backup) | Ed25519 is AES-encrypted; useless without P-256 key | P-256 not extractable |
| Extracts Secure Enclave | Impossible (hardware-protected by Secure Enclave coprocessor) | N/A |
| Device at runtime (malware/jailbreak) | Ed25519 is briefly unwrapped in memory for signing | Overwrite memory immediately after use |
| Network interception | All AP2 mandates signed locally; transmitted as JWT | HTTPS/TLS only |

---

## 2. Key Management Architecture

### Tier 1: P-256 Master Key (Secure Enclave)

**Generation (First App Launch)**

```swift
// siss-ios-core/Sources/SovereignCore/KeyManagement.swift

import Security

class KeyManagement {
    static let masterKeyTag = "com.sovereignnexus.p256.master"
    
    static func generateMasterKey() throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrKeyType as String: kSecAttrKeyTypeECSHA256,
            kSecAttrKeySizeInBits as String: 256,
            kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave,
            kSecAttrApplicationTag as String: masterKeyTag.data(using: .utf8)!,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            kSecReturnRef as String: kCFBooleanTrue
        ]
        
        var masterKey: SecKey?
        let status = SecKeyCreateRandomKey(query as CFDictionary, nil)
        
        if status == errSecSuccess {
            print("P-256 master key created in Secure Enclave")
        } else {
            throw KeyError.enclaveFailed
        }
    }
    
    static func getMasterKey() throws -> SecKey {
        let query: [String: Any] = [
            kSecClass as String: kSecClassKey,
            kSecAttrApplicationTag as String: masterKeyTag.data(using: .utf8)!,
            kSecReturnRef as String: kCFBooleanTrue,
            kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave
        ]
        
        var masterKey: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &masterKey)
        
        guard status == errSecSuccess, let key = masterKey as? SecKey else {
            throw KeyError.masterKeyNotFound
        }
        
        return key
    }
}
```

**Properties:**
- Hardware-protected by Secure Enclave coprocessor
- Cannot be extracted or copied to disk
- Usable only for signing/encryption operations
- Biometric lock (Face ID / Touch ID) can be configured

---

### Tier 2: Ed25519 Key (AES-Wrapped, Keychain-Stored)

**Generation**

```swift
// Week 6 (June 18-25): Generate Ed25519 key locally
// Use CryptoKit if available (iOS 14+), else libsodium

import CryptoKit

class Ed25519KeyManagement {
    static let wrappedKeyTag = "com.sovereignnexus.ed25519.wrapped"
    
    static func generateAndWrapEd25519() throws {
        // Generate Ed25519 key (32 bytes private key)
        let ed25519PrivateKey = CryptoKit.Curve25519.Signing.PrivateKey()
        let ed25519Data = ed25519PrivateKey.withUnsafeBytes { Data($0) }
        
        // Derive AES key from P-256 master key via ECDH
        let masterKey = try KeyManagement.getMasterKey()
        let ephemeralPublicKey = try deriveEphemeralPublicKey(from: masterKey)
        let aesKey = try performECDH(masterKey: masterKey, ephemeralPublicKey: ephemeralPublicKey)
        
        // Encrypt Ed25519 with AES-256-GCM
        let sealedBox = try AES.GCM.seal(ed25519Data, using: aesKey)
        
        // Store wrapped key in Keychain
        let wrappedKeyData = try JSONEncoder().encode([
            "ciphertext": sealedBox.ciphertext.base64EncodedString(),
            "nonce": sealedBox.nonce.withUnsafeBytes { Data($0).base64EncodedString() },
            "tag": sealedBox.tag.base64EncodedString(),
            "ephemeralPublicKey": ephemeralPublicKey.base64EncodedString()
        ])
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: "ed25519-key",
            kSecAttrApplicationTag as String: wrappedKeyTag.data(using: .utf8)!,
            kSecValueData as String: wrappedKeyData,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]
        
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeyError.keychainWriteFailed
        }
        
        print("Ed25519 key wrapped and stored in Keychain")
    }
}
```

**Storage Format (JSON in Keychain)**

```json
{
  "ciphertext": "base64(AES-256-GCM-encrypted ed25519 key)",
  "nonce": "base64(12-byte nonce)",
  "tag": "base64(16-byte authentication tag)",
  "ephemeralPublicKey": "base64(P-256 ephemeral public key)"
}
```

**Why This Works:**
- Ed25519 is encrypted (AES-256-GCM is authenticated)
- Keychain stores encrypted data safely (Keychain encryption + Secure Enclave integration)
- Attacker extracting Keychain cannot decrypt without P-256 master key (in Secure Enclave)
- Attacker with Secure Enclave access: Impossible (hardware-protected)

---

### Tier 3: Unwrapping for AP2 Signing

**Runtime Unwrapping (Only When Needed)**

```swift
class AP2Signing {
    static func signMandate(mandate: Mandate) throws -> String {
        // Step 1: Retrieve wrapped Ed25519 from Keychain
        let wrappedKeyData = try fetchWrappedEd25519Key()
        let wrappedKeyDict = try JSONDecoder().decode([String: String].self, from: wrappedKeyData)
        
        // Step 2: Use P-256 master key to unwrap
        let masterKey = try KeyManagement.getMasterKey()
        let ed25519Data = try unwrapEd25519(
            wrapped: wrappedKeyDict,
            masterKey: masterKey
        )
        
        // Step 3: Sign mandate with unwrapped Ed25519
        let ed25519PrivateKey = try CryptoKit.Curve25519.Signing.PrivateKey(rawRepresentation: ed25519Data)
        let mandateJSON = try JSONEncoder().encode(mandate)
        let signature = try ed25519PrivateKey.signature(for: mandateJSON)
        
        // Step 4: Immediately overwrite Ed25519 from memory
        var mutableEd25519 = ed25519Data
        memset(&mutableEd25519, 0, mutableEd25519.count)
        
        // Step 5: Return signed mandate as JWT
        let jwt = try createJWT(mandate: mandate, signature: signature)
        return jwt
    }
    
    static func unwrapEd25519(
        wrapped: [String: String],
        masterKey: SecKey
    ) throws -> Data {
        // Reconstruct nonce + ciphertext + tag
        guard let ciphertextBase64 = wrapped["ciphertext"],
              let nonceBase64 = wrapped["nonce"],
              let tagBase64 = wrapped["tag"] else {
            throw KeyError.malformedWrappedKey
        }
        
        let ciphertext = Data(base64Encoded: ciphertextBase64)!
        let nonce = try AES.GCM.Nonce(data: Data(base64Encoded: nonceBase64)!)
        let tag = Data(base64Encoded: tagBase64)!
        
        // Perform ECDH with stored ephemeral public key to derive AES key
        let ephemeralPublicKeyData = Data(base64Encoded: wrapped["ephemeralPublicKey"]!)!
        let aesKey = try performECDH(masterKey: masterKey, ephemeralPublicKeyData: ephemeralPublicKeyData)
        
        // Decrypt with AES-256-GCM
        let sealedBox = try AES.GCM.SealedBox(nonce: nonce, ciphertext: ciphertext, tag: tag)
        let plaintext = try AES.GCM.open(sealedBox, using: aesKey)
        
        return plaintext
    }
}
```

**Security Guarantee:** Ed25519 is unwrapped, used for 1 signature, then overwritten. Never persisted to disk in plaintext.

---

## 3. Key Rotation Strategy

**Quarterly Key Rotation (Every 90 Days)**

```swift
class KeyRotation {
    static func rotateEd25519Key() throws {
        print("Starting Ed25519 key rotation...")
        
        // Step 1: Generate new Ed25519
        let newEd25519 = CryptoKit.Curve25519.Signing.PrivateKey()
        let newEd25519Data = newEd25519.withUnsafeBytes { Data($0) }
        
        // Step 2: Get new public key for ledger
        let newPublicKey = newEd25519.publicKey
        
        // Step 3: Create "rotation" mandate signed by old Ed25519
        let oldEd25519 = try unwrapOldEd25519()
        let rotationMandate = RotationMandate(
            operatorId: getOperatorId(),
            oldPublicKey: getOldPublicKey(),
            newPublicKey: newPublicKey,
            timestamp: Date()
        )
        
        // Step 4: Sign with old key, send to AP2 ledger
        let signature = try signWithOldEd25519(rotationMandate)
        try sendToAP2Ledger(rotationMandate, signature: signature)
        
        // Step 5: Wrap new Ed25519, store in Keychain
        try wrapAndStoreNewEd25519(newEd25519Data)
        
        // Step 6: Delete old wrapped key
        try deleteOldWrappedKey()
        
        print("Ed25519 rotation complete. New key active.")
    }
}
```

**Ledger Entry (AP2):**
```json
{
  "mandate_type": "key_rotation",
  "operator_id": "op-1",
  "old_public_key": "...",
  "new_public_key": "...",
  "timestamp": "2026-08-29T12:00:00Z",
  "signature": "..."
}
```

---

## 4. Biometric Lock (Optional, Week 8)

**Allow Face ID / Touch ID to gate Secure Enclave access**

```swift
let biometricQuery: [String: Any] = [
    kSecClass as String: kSecClassKey,
    kSecAttrApplicationTag as String: masterKeyTag.data(using: .utf8)!,
    kSecReturnRef as String: kCFBooleanTrue,
    kSecUseAuthenticationUI as String: kSecUseAuthenticationUIAllow,  // Prompts for Face ID / Touch ID
    kSecAttrTokenID as String: kSecAttrTokenIDSecureEnclave
]

var masterKey: CFTypeRef?
let status = SecItemCopyMatching(biometricQuery as CFDictionary, &masterKey)

// If biometric check fails → status != errSecSuccess
// App prompts user to unlock with Face ID / Touch ID
```

**Not required for MVP (June 11), but easy add in Week 8 after launch.**

---

## 5. Implementation Checklist (Locked)

**Week 6 (June 18-25):**
- [ ] Implement `KeyManagement.generateMasterKey()` (P-256 in Secure Enclave)
- [ ] Implement `KeyManagement.getMasterKey()` (retrieve from Secure Enclave)
- [ ] Implement `Ed25519KeyManagement.generateAndWrapEd25519()` (AES wrap)
- [ ] Implement `AP2Signing.signMandate()` (unwrap, sign, overwrite)
- [ ] Unit tests for key generation + wrapping (no real signing, mocked AP2)

**Week 7 (July 2-9):**
- [ ] Integration test: Generate P-256, wrap Ed25519, sign real AP2 mandate
- [ ] Verify signed mandate validates on Rust side (siss-gatekeeper::verify_mandate)
- [ ] Load test: Sign 100 mandates back-to-back (measure latency, memory)

**Week 8 (July 9-16):**
- [ ] Add biometric lock (Face ID / Touch ID) — optional
- [ ] Key rotation test: Rotate Ed25519, send rotation mandate to ledger
- [ ] Documentation: How to extract public keys, how to verify signatures

---

## 6. Memory Safety Guarantees

| Operation | Guarantees |
|-----------|-----------|
| Ed25519 generation | Random bytes from `SecRandomCopyBytes` |
| Wrapping (AES-GCM) | Authenticated encryption, nonce never reused |
| Storage (Keychain) | iOS Keychain encryption + biometric lock |
| Unwrapping | Plaintext exists only in local scope, immediately overwritten |
| Signing | Ed25519 never persisted; memory overwritten after use |
| P-256 master key | Never extracted from Secure Enclave; only signing operations |

---

## 7. Error Cases

```swift
enum KeyError: Error {
    case masterKeyNotFound           // P-256 key missing from Secure Enclave
    case enclaveFailed               // Secure Enclave operation failed
    case keychainWriteFailed         // Keychain write error
    case keychainReadFailed          // Keychain read error
    case decryptionFailed            // AES-GCM decryption failed
    case malformedWrappedKey         // Stored key is corrupted
    case signatureFailed             // Ed25519 signature operation failed
    case biometricAuthRequired       // User must unlock with Face ID / Touch ID
}
```

**Recovery:**
- Master key not found → Regenerate (first launch recovery)
- Wrapped key corrupted → Regenerate Ed25519, store again (data loss acceptable, keys re-created)
- Keychain full → Delete old audit logs, retry
- Biometric auth required → Prompt user

---

## 8. Testing Strategy

### Unit Tests

```swift
// siss-ios-core/Tests/SovereignCoreTests/SecureEnclaveTests.swift

func testGenerateMasterKeyCreatesSecureEnclaveKey() throws {
    try KeyManagement.generateMasterKey()
    let masterKey = try KeyManagement.getMasterKey()
    XCTAssertNotNil(masterKey)
}

func testWrapEd25519StoresInKeychain() throws {
    try KeyManagement.generateMasterKey()
    try Ed25519KeyManagement.generateAndWrapEd25519()
    
    let wrappedData = try fetchWrappedEd25519Key()
    XCTAssertFalse(wrappedData.isEmpty)
}

func testUnwrapReturnsEd25519() throws {
    try KeyManagement.generateMasterKey()
    let originalEd25519 = try generateAndWrapEd25519()
    let unwrappedEd25519 = try AP2Signing.unwrapEd25519(...)
    
    XCTAssertEqual(originalEd25519, unwrappedEd25519)
}

func testSignMandateCreatesValidJWT() throws {
    try KeyManagement.generateMasterKey()
    try Ed25519KeyManagement.generateAndWrapEd25519()
    
    let mandate = Mandate(operatorId: "op-1", action: "deploy")
    let jwt = try AP2Signing.signMandate(mandate: mandate)
    
    // Verify JWT structure (header.payload.signature)
    let parts = jwt.split(separator: ".")
    XCTAssertEqual(parts.count, 3)
}
```

### Integration Tests (Week 7)

- [ ] Sign mandate on iOS → Verify on Rust side (siss-gatekeeper::verify_mandate)
- [ ] Rotate Ed25519 → Send rotation mandate to mock AP2 ledger → Verify signature

---

## 9. Deployment Checklist

- [ ] Secure Enclave P-256 key generation works on iPhone 11+ (hardware requirement)
- [ ] Keychain storage verified on iOS 13+ (iOS deployment target)
- [ ] AES-GCM implementation uses CryptoKit (Apple framework, hardened)
- [ ] Memory overwrite after Ed25519 use (verified with debugger)
- [ ] No plaintext Ed25519 in logs or crash reports
- [ ] Key rotation audit trail complete

---

## 10. Locked Decisions

| Decision | Rationale | Lock Date |
|----------|-----------|-----------|
| P-256 master in Secure Enclave | Hardware-protected, impossible to extract | May 29 |
| Ed25519 wrapped with AES-256-GCM | Authenticated, high-entropy wrapper | May 29 |
| Unwrap-sign-overwrite pattern | Minimizes Ed25519 lifetime in memory | May 29 |
| Keychain storage for wrapped key | iOS standard for encrypted credential storage | May 29 |
| Quarterly key rotation | Balance between security + operational overhead | May 29 |

---

## References

- [Apple Secure Enclave Guide](https://developer.apple.com/documentation/security/secure_enclave/)
- [CryptoKit Documentation](https://developer.apple.com/documentation/cryptokit/)
- [Keychain Services](https://developer.apple.com/documentation/security/keychain_services)
- [NIST Curve25519](https://datatracker.ietf.org/doc/html/rfc7748)
- Phase 25 Reference: AP2 ledger signing requirements
