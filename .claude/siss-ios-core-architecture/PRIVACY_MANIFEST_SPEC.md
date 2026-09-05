# Privacy Manifest + App Store Checklist — siss-ios-core

**Status:** LOCKED (May 29, 2026)  
**Effective:** Phase 32 Merge (June 11, 2026)  
**Author:** Architecture Planning (TRACK H)  
**Purpose:** Define App Store privacy requirements and compliance checklist

---

## 1. Overview

Apple requires PrivacyInfo.xcprivacy for any app using:
- NSUserDefaults, Keychain, CloudKit, HealthKit
- Camera, Microphone, Photos, Contacts
- Network APIs, Advertising
- Analytics, Crash reporting

**SovereignNexus iPhone requirements:**
- Keychain (Ed25519 wrapped key storage)
- NSUserDefaults (operator session state)
- Network (localhost:8000 to Rapid-MLX)
- No camera, photos, contacts, health, location

---

## 2. Privacy Manifest Structure (PrivacyInfo.xcprivacy)

**File Location:** `siss-ios-core/PrivacyInfo.xcprivacy`

**Xcode Integration:**
```
Xcode → Project → Targets → siss-ios-core → Info
→ Add "Privacy Manifest" (Xcode auto-generates PrivacyInfo.xcprivacy)
```

### Complete Privacy Manifest (XML)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Tracking & Analytics -->
    <key>NSPrivacyTracking</key>
    <false/>
    
    <key>NSPrivacyTrackingDomains</key>
    <array/>
    
    <!-- Data Collection Declaration -->
    <key>NSPrivacyCollectedDataTypes</key>
    <array>
        <!-- 1. User ID (operator credentials) -->
        <dict>
            <key>NSPrivacyCollectedDataType</key>
            <string>NSPrivacyCollectedDataTypeUserID</string>
            
            <key>NSPrivacyCollectedDataTypeLinked</key>
            <false/>
            
            <key>NSPrivacyCollectedDataTypeTracking</key>
            <false/>
            
            <key>NSPrivacyCollectedDataTypePurposes</key>
            <array>
                <string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string>
            </array>
        </dict>
        
        <!-- 2. Sensitive Information (mandate signatures) -->
        <dict>
            <key>NSPrivacyCollectedDataType</key>
            <string>NSPrivacyCollectedDataTypeSensitiveInfo</string>
            
            <key>NSPrivacyCollectedDataTypeLinked</key>
            <false/>
            
            <key>NSPrivacyCollectedDataTypeTracking</key>
            <false/>
            
            <key>NSPrivacyCollectedDataTypePurposes</key>
            <array>
                <string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string>
            </array>
        </dict>
        
        <!-- 3. Precise Location (optional, only if enabled) -->
        <!-- LOCKED DECISION (May 29): NOT USED in MVP -->
        
        <!-- 4. Coarse Location (optional, only if enabled) -->
        <!-- LOCKED DECISION (May 29): NOT USED in MVP -->
        
        <!-- 5. Product Interaction (app usage stats) -->
        <dict>
            <key>NSPrivacyCollectedDataType</key>
            <string>NSPrivacyCollectedDataTypeProductInteraction</string>
            
            <key>NSPrivacyCollectedDataTypeLinked</key>
            <false/>
            
            <key>NSPrivacyCollectedDataTypeTracking</key>
            <false/>
            
            <key>NSPrivacyCollectedDataTypePurposes</key>
            <array>
                <string>NSPrivacyCollectedDataTypePurposeAppFunctionality</string>
            </array>
        </dict>
    </array>
    
    <!-- Encryption Info -->
    <key>NSPrivacyEncryptedDataTransport</key>
    <true/>
    
    <!-- API Declarations (Third-Party SDKs) -->
    <key>NSPrivacyAccessedAPITypes</key>
    <array>
        <!-- 1. NSUserDefaults API -->
        <dict>
            <key>NSPrivacyAccessedAPIType</key>
            <string>NSPrivacyAccessedAPICategoryUserDefaults</string>
            
            <key>NSPrivacyAccessedAPITypeReasons</key>
            <array>
                <string>CA92.1</string>  <!-- App functionality -->
            </array>
        </dict>
        
        <!-- 2. Keychain Services API -->
        <dict>
            <key>NSPrivacyAccessedAPIType</key>
            <string>NSPrivacyAccessedAPICategoryKeychainServices</string>
            
            <key>NSPrivacyAccessedAPITypeReasons</key>
            <array>
                <string>CA92.1</string>  <!-- App functionality (credential storage) -->
            </array>
        </dict>
        
        <!-- 3. File Timestamp API -->
        <dict>
            <key>NSPrivacyAccessedAPIType</key>
            <string>NSPrivacyAccessedAPICategoryFileTimestamp</string>
            
            <key>NSPrivacyAccessedAPITypeReasons</key>
            <array>
                <string>C617.1</string>  <!-- App functionality -->
            </array>
        </dict>
        
        <!-- 4. System Boot Time API -->
        <dict>
            <key>NSPrivacyAccessedAPIType</key>
            <string>NSPrivacyAccessedAPICategorySystemBootTime</string>
            
            <key>NSPrivacyAccessedAPITypeReasons</key>
            <array>
                <string>35F9.1</string>  <!-- Security/fraud prevention -->
            </array>
        </dict>
    </array>
</dict>
</plist>
```

---

## 3. Privacy Categories (Detailed Explanation)

### 1. NSUserDefaults

**What it is:** iOS key-value storage (encrypted by iOS)

**What we store:**
```swift
UserDefaults.standard.set("op-1", forKey: "operator_id")
UserDefaults.standard.set("true", forKey: "authenticated")
UserDefaults.standard.set("2026-05-29T12:00:00Z", forKey: "session_timestamp")
```

**Privacy category:** `NSPrivacyCollectedDataTypeUserID`
**Purpose:** App Functionality (authentication state)
**Linked:** No (operator ID is not linked to other data)
**Tracking:** No (not used for tracking)

**Apple Justification:**
- Necessary for app to know who's logged in
- Stored locally on device
- No transmission to third parties

### 2. Keychain Services

**What it is:** iOS encrypted credential vault

**What we store:**
```swift
// P-256 master key (Secure Enclave-protected)
SecItemAdd([
    kSecClass: kSecClassKey,
    kSecAttrApplicationTag: "com.sovereignnexus.p256.master",
    kSecAttrTokenID: kSecAttrTokenIDSecureEnclave
])

// Ed25519 wrapped key (AES-GCM encrypted)
SecItemAdd([
    kSecClass: kSecClassGenericPassword,
    kSecAttrAccount: "ed25519-key",
    kSecValueData: <AES-wrapped JSON>
])
```

**Privacy category:** `NSPrivacyCollectedDataTypeSensitiveInfo`
**Purpose:** App Functionality (mandate signing)
**Linked:** No (keys not linked to identity)
**Tracking:** No

**Apple Justification:**
- Cryptographic keys are not "personal data" by Apple definition
- Necessary for AP2 mandate signing
- Never transmitted; used only locally
- Protected by Keychain encryption + Secure Enclave

### 3. NSUserDefaults + Keychain APIs

**Why we declare them:**
- App calls SecItemAdd, SecItemCopyMatching, SecItemDelete
- App calls UserDefaults.standard.set/value(forKey:)
- Apple requires these API accesses declared

**Declaration in Privacy Manifest:**
```xml
<dict>
    <key>NSPrivacyAccessedAPIType</key>
    <string>NSPrivacyAccessedAPICategoryKeychainServices</string>
    <key>NSPrivacyAccessedAPITypeReasons</key>
    <array>
        <string>CA92.1</string>  <!-- App functionality reason code -->
    </array>
</dict>
```

---

## 4. What We DON'T Use (Locked Exclusions)

| Framework | Status | Reason |
|-----------|--------|--------|
| Camera / Microphone | NOT USED | No video/voice recording |
| Photos Library | NOT USED | No photo access |
| Contacts | NOT USED | No contact list access |
| Health/Fitness | NOT USED | Not a health app |
| Location Services | NOT USED | No GPS/geolocation (future: could enable for field ops) |
| Advertising | NOT USED | No ads or ad tracking |
| Analytics (Mixpanel, Google) | NOT USED | No third-party SDKs |
| CloudKit / iCloud | NOT USED | Local-only operation |

**PrivacyInfo.xcprivacy consequence:** Don't declare these → smaller, cleaner manifest.

---

## 5. Network & Data Transmission

### HTTPS Requirement (Locked)

**All network requests use HTTPS:**

```swift
// HTTP to localhost:8000 (Rapid-MLX, local process)
let url = URL(string: "http://localhost:8000/v1/chat/completions")!
// Exception: localhost is exempt from HTTPS requirement (local IPC)

// Any external API calls (future)
let url = URL(string: "https://api.sovereignnexus.com/mandates")!
// HTTPS only; no cleartext HTTP
```

**App Transport Security (ATS) Configuration:**

```xml
<!-- siss-ios-core/Info.plist -->
<key>NSAppTransportSecurity</key>
<dict>
    <!-- Allow localhost (Rapid-MLX) without TLS -->
    <key>NSExceptionDomains</key>
    <dict>
        <key>localhost</key>
        <dict>
            <key>NSIncludesSubdomains</key>
            <true/>
            <key>NSTemporaryExceptionAllowsInsecureHTTPLoads</key>
            <true/>
            <key>NSTemporaryExceptionMinimumTLSVersion</key>
            <string>TLSv1.2</string>
        </dict>
    </dict>
    
    <!-- All other domains: HTTPS only -->
    <key>NSAllowsArbitraryLoads</key>
    <false/>
</dict>
```

**Privacy Manifest Declaration:**
```xml
<key>NSPrivacyEncryptedDataTransport</key>
<true/>  <!-- All data encrypted in transit -->
```

---

## 6. Third-Party SDKs (None Included)

**Locked Decision (May 29):** SovereignNexus iOS uses only Apple frameworks. No:
- Google Analytics
- Firebase
- Mixpanel
- Sentry
- Fabric
- Any other third-party SDK

**Consequence:** PrivacyInfo.xcprivacy is minimal; no SDK privacy concerns.

---

## 7. App Store Metadata (Review Checklist)

### Submission Form: App Privacy

**Question 1: "Does your app collect, use, or share user data?"**
- **Answer:** Yes
- **Reason:** Stores operator credentials + mandate signatures

**Question 2: "Does your app use IDFA or other device identifiers for tracking?"**
- **Answer:** No
- **Reason:** No advertising or tracking

**Question 3: "Does your app comply with California Consumer Privacy Act (CCPA)?"**
- **Answer:** Yes
- **Reason:** No data shared with third parties; user can delete app (all data local)

---

### Privacy Policy URL

**Requirement:** Link to privacy policy on App Store.

**Expected Content:**

```markdown
# SovereignNexus Privacy Policy

## What Data We Collect
- Operator credentials (username, session token)
- API request logs (timestamp, action, success/failure)
- Device encryption keys (stored locally)

## How We Use It
- Authenticate operator sessions
- Log audit trail for compliance
- Sign Mandate instances for AP2 ledger

## Who We Share It With
- No one. Data never leaves your device.

## How We Protect It
- Encrypted in Keychain
- P-256 master key in Secure Enclave
- All local storage encrypted by iOS

## How to Delete Data
- Delete the app
- All data is deleted from device

## Updates to This Policy
Last updated: May 29, 2026
```

**Host:** `https://sovereignnexus.com/privacy` (or GitHub Pages)

---

### App Store Screenshots & Description

**Screenshot 1:** "Secure operator dashboard"
- Show A2UI interface (no sensitive data)
- Caption: "Operator control interface"

**Screenshot 2:** "Encrypted mandate signing"
- Show Keychain lock icon
- Caption: "All mandates cryptographically signed locally"

**Description Summary:**
```
SovereignNexus iOS: Agent Control Node
- Deploy and manage agents on iPhone
- Sign AP2 mandates with local encryption
- Monitor agent activity in real time
- Privacy-first: All data stays on device

No cloud sync. No tracking. No ads.
```

---

### Keywords

```
sovereign, agent, operator, control, management, encryption, privacy, ap2, 
mandate, gatekeeper, deployment, monitoring
```

---

## 8. Submission & Review Timeline (Locked)

**Week 10 (July 16-23):**
- [ ] Finalize Privacy Manifest (PrivacyInfo.xcprivacy)
- [ ] Draft privacy policy (5 min read)
- [ ] Prepare App Store screenshots (3-4 images)
- [ ] Write app description (100 words)

**Week 11 (July 23-30):**
- [ ] Submit to TestFlight (internal testing)
- [ ] Internal review: Privacy + functionality
- [ ] Verify PrivacyInfo.xcprivacy is included in build

**Week 12 (July 30 - Aug 6):**
- [ ] Submit to App Store Review
- [ ] Apple review: ~2-3 business days
- [ ] If rejected: Fix + resubmit
- [ ] Expected approval: Aug 6-8

**Week 13 (Aug 8-15):**
- [ ] Released to public App Store
- [ ] Monitor review ratings
- [ ] Respond to user feedback

---

## 9. Testing Checklist (Before Submission)

### Build Verification

```bash
# 1. Verify PrivacyInfo.xcprivacy is in bundle
unzip -l siss-ios-core.app | grep PrivacyInfo.xcprivacy
# Expected: PrivacyInfo.xcprivacy present

# 2. Validate XML syntax
xmllint --noout PrivacyInfo.xcprivacy

# 3. Check App Transport Security config
grep -A 10 "NSAppTransportSecurity" siss-ios-core/Info.plist
```

### Privacy Audit

- [ ] Keychain access is declared (NSPrivacyAccessedAPICategoryKeychainServices)
- [ ] UserDefaults access is declared (NSPrivacyAccessedAPICategoryUserDefaults)
- [ ] No third-party SDKs included
- [ ] No camera, photos, contacts permissions requested
- [ ] No location services enabled
- [ ] NSPrivacyTracking = false
- [ ] NSPrivacyEncryptedDataTransport = true
- [ ] Privacy policy URL is valid & accessible

### Deployment

```swift
// Verify at app launch:
if let privacyPath = Bundle.main.path(forResource: "PrivacyInfo", ofType: "xcprivacy") {
    print("Privacy manifest found: \(privacyPath)")
} else {
    assertionFailure("Privacy manifest missing!")
}
```

---

## 10. Locked Decisions

| Decision | Rationale | Lock Date |
|----------|-----------|-----------|
| Keychain + Secure Enclave (not iCloud) | Local-only, no cloud sync | May 29 |
| No third-party SDKs | Privacy-first, smaller attack surface | May 29 |
| Include Keychain API in manifest | Required by Apple; necessary for mandate signing | May 29 |
| No location, camera, health | Not needed for MVP; future extension possible | May 29 |
| HTTPS for external APIs | Future-proofing; localhost exempt | May 29 |
| Privacy policy hosted externally | SovereignNexus website + GitHub backup | May 29 |

---

## 11. Revision History

| Date | Change | Reason |
|------|--------|--------|
| May 29, 2026 | Initial spec | Architecture planning (TRACK H) |

---

## References

- [Apple App Privacy Guidance](https://developer.apple.com/app-privacy/)
- [PrivacyInfo.xcprivacy Format](https://developer.apple.com/documentation/bundleresources/privacy)
- [App Transport Security](https://developer.apple.com/documentation/security/preventing-insecure-network-connections)
- [Keychain Services](https://developer.apple.com/documentation/security/keychain_services)
- [CCPA Compliance](https://oag.ca.gov/privacy/ccpa)
- Phase 29 Reference: AP2 mandate signing architecture
