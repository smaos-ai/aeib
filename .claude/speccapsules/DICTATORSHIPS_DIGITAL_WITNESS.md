# SPECCAPSULE: Dictatorships Digital Witness
## Spec-First Design for DigitalWitnessCapsule + CensorshipResistantCapsule

**Created:** May 29, 2026 | **Target Implementation:** June 4-14, 2026  
**Crate:** `crates/siss-agent-shell` (new module: `digital_witness_capsule.rs`)  
**Tests:** TDD-first | **Integration:** Amnesty International, Human Rights Watch, Index on Censorship

---

## STRUCT DEFINITION

```rust
use crate::capsule::{Capsule, GembaProof};
use serde::{Deserialize, Serialize};
use std::time::SystemTime;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DigitalWitnessCapsule {
    /// Core Capsule wrapper
    pub capsule: Capsule,
    
    /// Recording (video hash + transcript)
    pub recording: RecordingData,
    
    /// Gemba proof (location GPS + ambient audio fingerprint)
    pub gemba_proof: GembaProof,
    
    /// Chain of custody (witness → human rights org → immutable ledger)
    pub chain_of_custody: ChainOfCustody,
    
    /// Optional: Censorship-resistant QR encoding
    pub censorship_resistant_export: Option<CensorshipResistantExport>,
    
    /// Optional: Andon Cord trigger (arrest → international sanctions)
    pub andon_cord: Option<AndonCordTrigger>,
    
    /// Encryption (AES-256-GCM-SIV)
    pub encryption_key_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RecordingData {
    /// SHA256 hash of video file (proves authenticity without exposing content)
    pub video_hash: String,
    
    /// Transcript of audio (manually transcribed by human rights org)
    pub audio_transcript: Option<String>,
    
    /// Location where recording was made
    pub location: (f64, f64), // (latitude, longitude)
    
    /// Timestamp when recording started
    pub timestamp: SystemTime,
    
    /// Witness identity (zero-knowledge proof, not plaintext)
    pub witness_identity_zkp: String, // Pedersen commitment of witness identity
    
    /// Duration in seconds
    pub duration_sec: u32,
    
    /// Video quality (480p, 720p, 1080p)
    pub video_quality: String,
    
    /// Device used (smartphone model, camera)
    pub device_type: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GeometricProof {
    /// GPS coordinates at recording start
    pub start_location: (f64, f64),
    
    /// GPS coordinates at recording end
    pub end_location: (f64, f64),
    
    /// Accuracy in meters
    pub gps_accuracy_m: u32,
    
    /// Ambient audio fingerprint (proves recording location)
    pub ambient_audio_fingerprint: String, // MFCC features hashed
    
    /// Device time vs. NTP check (detects time manipulation)
    pub device_ntp_delta_sec: i32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ChainOfCustody {
    /// Witness's cryptographic signature on recording hash
    pub witness_signature: String,
    
    /// Human rights organization's signature
    pub human_rights_org_signature: String,
    
    /// Name of the org (Amnesty, HRW, Index)
    pub human_rights_org_name: String,
    
    /// Neo4j ledger ID (immutable record of who accessed this)
    pub virtualgraph_ledger_id: String,
    
    /// Verification status (unverified, verified, disputed, published)
    pub verification_status: VerificationStatus,
    
    /// Access history (who downloaded/viewed)
    pub access_history: Vec<AccessRecord>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum VerificationStatus {
    Unverified,
    Verified, // HRW/Amnesty confirmed authenticity
    Disputed, // Regime claimed deepfake or manipulation
    Published, // Published in HRW report or index on censorship
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AccessRecord {
    pub accessor_org: String,
    pub access_timestamp: SystemTime,
    pub access_type: String, // "view", "download", "cite_in_report"
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CensorshipResistantExport {
    /// Video encoded as QR codes (no internet required to distribute)
    pub qr_code_chunks: Vec<QRCodeChunk>,
    
    /// Metadata: how many QR codes, which chunk numbers, decoding instructions
    pub metadata: QRMetadata,
    
    /// Distribution instructions (print on paper, hand-deliver)
    pub distribution_method: String, // "print_and_distribute", "hand_deliver_qr_codes"
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct QRCodeChunk {
    pub chunk_number: u32, // 1/50, 2/50, etc.
    pub total_chunks: u32,
    pub qr_data: String, // Base64 encoded QR payload
    pub checksum: String, // CRC32 for error detection
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct QRMetadata {
    pub total_size_bytes: u32,
    pub encoding_format: String, // "H.264", "VP9"
    pub chunk_size_bytes: u32,
    pub decoding_instructions: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AndonCordTrigger {
    /// Threshold: if witness is arrested or killed
    pub trigger_condition: String, // "witness_arrested", "witness_killed"
    
    /// Action: activate international sanctions
    pub action: String, // "activate_sanctions", "alert_icc", "diplomatic_incident"
    
    /// Target country (if arrest happens there)
    pub target_country: String,
    
    /// Authorized signatories (UN Security Council, ICC, diplomatic corps)
    pub authorized_signatories: Vec<String>,
    
    /// Status (armed, triggered, executed, expired)
    pub status: AndonCordStatus,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum AndonCordStatus {
    Armed,
    Triggered,
    Executed,
    Expired,
}
```

---

## TEST CASES (TDD Template)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_digital_witness_capsule() {
        // Create capsule from video recording
        // Assert: video_hash is SHA256
        // Assert: location is within valid GPS bounds
    }

    #[tokio::test]
    async fn test_witness_identity_zero_knowledge_proof() {
        // Create capsule with witness identity
        // Assert: witness_identity_zkp does NOT reveal identity
        // Assert: human rights org can verify "this is the same witness" without knowing who
    }

    #[tokio::test]
    async fn test_gemba_proof_location_authenticity() {
        // Create capsule with GPS + ambient audio fingerprint
        // Mock regime attempt to deepfake location
        // Assert: audio fingerprint proves recording was actually there
        // Assert: GPS cannot be spoofed without matching audio
    }

    #[tokio::test]
    async fn test_chain_of_custody_immutable_ledger() {
        // Create capsule, send to Amnesty
        // Amnesty signs it
        // Query Neo4j ledger
        // Assert: ledger shows [timestamp, amnesty_org, signature]
        // Assert: ledger cannot be modified (immutable)
    }

    #[tokio::test]
    async fn test_censorship_resistant_qr_encoding() {
        // Create capsule, export as QR codes
        // Print on paper
        // Scan QR codes with offline phone
        // Assert: video decodes correctly
        // Assert: no internet access required
    }

    #[tokio::test]
    async fn test_qr_code_error_correction() {
        // Encode video as 50 QR codes
        // Intentionally damage 1 QR code (40% pixel loss)
        // Attempt to decode
        // Assert: video still decodes (Reed-Solomon error correction)
    }

    #[tokio::test]
    async fn test_device_time_manipulation_detection() {
        // Record video with manipulated device time (fake timestamp)
        // Assert: device_ntp_delta_sec detects discrepancy
        // Assert: verification_status flags "timestamp_suspicious"
    }

    #[tokio::test]
    async fn test_andon_cord_activation() {
        // Create witness capsule with andon_cord armed
        // Simulate: witness arrested in Syria
        // Assert: andon_cord.status changes to Triggered
        // Assert: diplomatic notification sent to UN
    }

    #[tokio::test]
    async fn test_access_history_audit_trail() {
        // Create capsule, publish in HRW report
        // Query access_history
        // Assert: shows [2026-06-15 HRW download, 2026-07-01 HRW cite_in_report, ...]
    }

    #[tokio::test]
    async fn test_encryption_witness_controls_key() {
        // Create capsule, encrypt
        // Only witness has decryption key
        // Regime attempts to decrypt without key
        // Assert: Err(KeyNotFound)
    }

    #[tokio::test]
    async fn test_verification_status_transitions() {
        // Create capsule: status = Unverified
        // Amnesty verifies: status = Verified
        // Regime disputes: status = Disputed (both coexist)
        // HRW publishes: status = Published
    }
}
```

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Recording Capture (June 4-5)
- [ ] Implement `DigitalWitnessCapsule::new()` — create from video file
- [ ] Implement `RecordingData::hash()` — SHA256 of video (proves authenticity)
- [ ] Implement GPS + ambient audio fingerprint collection
- [ ] All unit tests pass

### Phase 2: Zero-Knowledge Proof (June 6-7)
- [ ] Implement witness identity as Pedersen commitment (not plaintext)
- [ ] Implement verification: org can confirm "this is the same witness" without knowing identity
- [ ] Research + implement: device time validation (NTP check)
- [ ] Benchmark: ZKP generation <1 second

### Phase 3: Chain of Custody (June 8-10)
- [ ] Integrate Neo4j VirtualGraph for immutable ledger
- [ ] Implement digital signatures (witness signs hash, org signs hash)
- [ ] Implement access history tracking
- [ ] Integration tests with mock Amnesty/HRW endpoints

### Phase 4: Censorship-Resistant QR (June 11-13)
- [ ] Implement QR encoding (video → 50 QR codes with Reed-Solomon error correction)
- [ ] Implement QR metadata + decoding instructions
- [ ] Integrate optional Andon Cord trigger (arrest → international sanctions)
- [ ] All tests green: `cargo test -p siss-agent-shell`

### Phase 5: Launch Readiness (June 14)
- [ ] Integration test: record → upload → verify → export QR → scan offline → decode
- [ ] Benchmark: QR encoding <5 seconds for 5-min video
- [ ] Documentation: 100% of APIs documented

---

## INTEGRATION POINTS

### Existing Crates Used
- **siss-graph-db:** Capsule, Neo4j VirtualGraph for ledger
- **siss-tools:** AES-256-GCM-SIV encryption
- **siss-agent-shell:** Device integration stubs (camera, GPS, microphone)

### Partner APIs
- **Amnesty International:** Verification endpoint, report publishing
- **Human Rights Watch:** Access endpoint, evidence intake
- **Index on Censorship:** Publishing endpoint, censorship monitoring
- **ICC (International Criminal Court):** Evidence submission for war crimes

---

## SUCCESS CRITERIA (Must Pass Before September 30)

- [ ] 1,000+ DigitalWitnessCapsules collected
- [ ] 10+ dictatorial regimes documented with corroborated evidence
- [ ] 50+ human rights defenders active on platform
- [ ] 5+ Andon Cord triggers activated → diplomatic incidents
- [ ] Zero encryption breaks (cryptographic audit by security researchers)
- [ ] 10+ published HRW reports using capsule evidence
- [ ] ICC uses capsule chain-of-custody in 3+ prosecutions

---

## FILES TO CREATE

```
crates/siss-agent-shell/src/
└── digital_witness_capsule.rs (estimated 400-500 LOC)

crates/siss-agent-shell/tests/
└── digital_witness_capsule_test.rs (estimated 300-400 LOC)
```

---

## OWNER & DEADLINE

**Owner:** Agent-Cluster-D (Parallel Implementation Team)  
**Target Completion:** June 14, 2026  
**Launch Date:** August 1, 2026 (Live PoC with Amnesty + HRW)
