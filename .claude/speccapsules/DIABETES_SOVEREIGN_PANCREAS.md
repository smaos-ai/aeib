# SPECCAPSULE: Diabetes Sovereign Pancreas
## Spec-First Design for BiometricCapsule (Diabetes Focus)

**Created:** May 29, 2026 | **Target Implementation:** June 4-14, 2026  
**Crate:** `crates/siss-night-cycle` (new module: `biometric_capsule.rs`)  
**Tests:** TDD-first | **Integration:** Dexcom, Libre, Medtronic + research consortium

---

## STRUCT DEFINITION

```rust
use crate::capsule::{Capsule, GembaProof};
use crate::oracle_distillation::OracleDistillationModel; // Layer 14
use serde::{Deserialize, Serialize};
use std::time::SystemTime;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BiometricCapsule {
    /// Core Capsule wrapper
    pub capsule: Capsule,
    
    /// Device data (Garmin, Dexcom CGM)
    pub device_data: DeviceData,
    
    /// Personal metabolic model (runs locally on device)
    pub personal_metabolic_model: PersonalMetabolicModel,
    
    /// AP2 research consent + royalty tracking
    pub ap2_research_capsule: AP2ResearchCapsule,
    
    /// Gemba proof: patient + device provenance
    pub gemba_proof: GembaProof,
    
    /// Encryption (AES-256-GCM-SIV, patient holds key)
    pub encryption_key_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DeviceData {
    pub glucose_mg_dl: u32,
    pub device_timestamp: i64, // Unix timestamp from Dexcom/Garmin
    pub device_id: String, // Device serial number (cryptographically signed)
    pub device_type: DeviceType,
    pub reading_quality: f32, // 0.0 - 1.0 (confidence in reading)
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum DeviceType {
    DexcomG6,
    DexcomG7,
    LibreFreestyle,
    GarminVivosmart,
    MedtronicGuardian,
    Other(String),
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PersonalMetabolicModel {
    /// Insulin sensitivity (α parameter from Affective Core)
    pub insulin_sensitivity: f32,
    
    /// Carbs-to-insulin ratio
    pub carb_ratio: f32,
    
    /// Dawn phenomenon profile (glucose increase at specific hours)
    pub dawn_phenomenon_profile: DawnPhenomenonProfile,
    
    /// Exercise response (glucose delta per activity type)
    pub exercise_response: ExerciseResponse,
    
    /// Distillation model version (Layer 14 Oracle)
    pub distillation_model: DistillationModelRef,
    
    /// Psi drift guard (ensures coherence over time)
    pub psi_drift_score: f32, // 0.0 - 1.0 (0.0 = perfect coherence)
    
    /// Last model update
    pub last_update: SystemTime,
    
    /// Prediction: next glucose in 15 min
    pub predicted_glucose_15min: u32,
    pub prediction_confidence: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DawnPhenomenonProfile {
    pub baseline_glucose: u32, // mg/dL at 6am
    pub peak_glucose: u32, // mg/dL at peak (usually 7-8am)
    pub peak_hour: u32, // 0-23
    pub duration_hours: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExerciseResponse {
    pub exercise_types: Vec<ExerciseType>,
    pub glucose_delta_per_type: std::collections::HashMap<String, i32>, // mg/dL change
    pub lag_minutes: u32, // how long until glucose drops after exercise
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExerciseType {
    pub activity: String, // "walking", "running", "cycling", "swimming"
    pub intensity: u32, // 1-10
    pub duration_minutes: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DistillationModelRef {
    pub model_version: String, // "qwen3.5-4b-v1.0"
    pub checkpoint_hash: String, // SHA256 of model weights
    pub adapter_rank: u32, // LoRA rank (4-32, replaced by OPLoRA)
    pub orthogonal_projection: bool, // Use OPLoRA (orthogonal) instead of standard LoRA
    pub training_date: SystemTime,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AP2ResearchCapsule {
    /// Anonymized data hash (zero re-identification risk)
    pub anonymized_data_hash: String,
    
    /// Consent level (basic, research_basic, research_advanced)
    pub consent_level: ConsentLevel,
    
    /// Royalty earned from research (1% of commercial value)
    pub royalty_earned_usd: u32,
    
    /// Last royalty payment
    pub last_royalty_payment: Option<SystemTime>,
    
    /// Neo4j ledger: research institution signatures
    pub virtualgraph_ledger_id: String,
    
    /// Data sharing partners (which institutions can access)
    pub sharing_partners: Vec<ResearchPartner>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ConsentLevel {
    Basic, // No data sharing
    ResearchBasic, // Anonymized data to non-profit research
    ResearchAdvanced, // Anonymized data to for-profit + pharma
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResearchPartner {
    pub institution_name: String,
    pub institution_type: String, // "pharma", "university", "hospital"
    pub access_granted_date: SystemTime,
    pub access_scope: String, // "glucose_only", "full_metabolic", etc.
}
```

---

## TEST CASES (TDD Template)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_biometric_capsule_from_device() {
        // Read glucose from mock Dexcom device
        // Create BiometricCapsule
        // Assert: glucose_mg_dl is captured
        // Assert: device_id is signed
    }

    #[tokio::test]
    async fn test_personal_metabolic_model_predicts_glucose() {
        // Create capsule with 7-day history
        // Call predict_glucose_15min()
        // Assert: prediction within ±20 mg/dL of actual (clinical accuracy)
    }

    #[tokio::test]
    async fn test_dawn_phenomenon_detection() {
        // Create capsule with 14-day glucose history
        // Analyze for dawn phenomenon pattern
        // Assert: dawn_phenomenon_profile detected if baseline < peak by >30 mg/dL
    }

    #[tokio::test]
    async fn test_exercise_response_learning() {
        // Log 5 exercise events (running, 30 min, glucose drop logged)
        // Train model
        // Assert: exercise_response.glucose_delta_per_type["running"] == -25 ± 5
    }

    #[tokio::test]
    async fn test_psi_drift_guard_detects_model_degradation() {
        // Train model, use for 30 days
        // Calculate psi_drift_score every day
        // Assert: psi_drift_score < 0.1 (model remains coherent)
        // Simulate model poisoning (inject bad data)
        // Assert: psi_drift_score > 0.5 (drift detected, flag alert)
    }

    #[tokio::test]
    async fn test_ap2_consent_level_basic_no_sharing() {
        // Create capsule with consent_level = Basic
        // Assert: sharing_partners is empty
        // Assert: royalty_earned_usd == 0
    }

    #[tokio::test]
    async fn test_ap2_consent_level_research_grants_royalty() {
        // Create capsule with consent_level = ResearchBasic
        // Pharma uses anonymized data for insulin trial
        // Trial succeeds, commercial value = $10M
        // Assert: royalty_earned_usd == $100k (1% royalty)
    }

    #[tokio::test]
    async fn test_anonymization_prevents_reidentification() {
        // Create capsule with patient demographics
        // Hash for research sharing
        // Attempt reidentification attack (quasi-identifier linking)
        // Assert: zero reidentification risk (cryptographic proof)
    }

    #[tokio::test]
    async fn test_orthogonal_projection_lora_vs_standard_lora() {
        // Train model with standard LoRA for 5 rounds of distillation
        // Measure capability drift (patient loses hypoglycemia awareness)
        // Train same model with OPLoRA for 5 rounds
        // Assert: OPLoRA capability drift < standard LoRA drift by 3x
    }

    #[tokio::test]
    async fn test_virtualgraph_ledger_research_audit_trail() {
        // Create capsule, consent to research
        // Pharma accesses anonymized data
        // Query Neo4j ledger for access history
        // Assert: ledger shows [timestamp, institution, access_scope]
    }

    #[tokio::test]
    async fn test_encryption_patient_holds_key() {
        // Create capsule, encrypt with patient's private key
        // Attempt to decrypt without key
        // Assert: Err(KeyNotFound)
        // Provide key
        // Assert: decryption succeeds
    }
}
```

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Core Glucose Capture (June 4-5)
- [ ] Implement `BiometricCapsule::new()` — create from DeviceData
- [ ] Implement device integration stubs (Dexcom, Libre, Garmin APIs)
- [ ] Implement `DeviceData::validate()` — check glucose range (70-400 mg/dL)
- [ ] All unit tests pass

### Phase 2: Personal Metabolic Model (June 6-8)
- [ ] Implement `PersonalMetabolicModel::train_from_history()` — 7+ days of data
- [ ] Implement insulin sensitivity calculation (Clarke error grid)
- [ ] Implement dawn phenomenon detection (7-day pattern analysis)
- [ ] Implement exercise response learning (correlate exercise + glucose delta)
- [ ] Benchmark: model training <5 seconds on CPU-only

### Phase 3: Layer 14 Distillation + Psi Guard (June 9-11)
- [ ] Integrate `crates/siss-graph-db::oracle_distillation::OracleDistillationModel`
- [ ] Implement OPLoRA (orthogonal projection) instead of standard LoRA
- [ ] Implement `psi_drift_guard()` — BGE-M3 embeddings to detect model coherence
- [ ] Implement `General Capability Benchmark` gate (reject models if degradation >3%)
- [ ] Benchmark: distillation inference <500ms on Raspberry Pi

### Phase 4: AP2 & Research Integration (June 12-14)
- [ ] Implement `AP2ResearchCapsule::apply_consent()` — control data sharing
- [ ] Integrate Neo4j VirtualGraph for research ledger
- [ ] Implement royalty calculation (1% of commercial value)
- [ ] Integration tests with Dexcom + mock pharma endpoints
- [ ] All tests green: `cargo test -p siss-night-cycle`

---

## INTEGRATION POINTS

### Existing Crates Used
- **siss-graph-db:** Capsule, Neo4j VirtualGraph, oracle_distillation module
- **siss-night-cycle:** MemForest for efficient glucose history compression
- **siss-gatekeeper:** AP2 ledger for research consent + royalty tracking

### Partner APIs
- **Dexcom Cloud API:** `GET /v2/users/self/readings` (with user consent)
- **Abbott Libre:** `GET /libreapi/v3/connections/user/glucose` (with user consent)
- **Garmin Health API:** `GET /wellness-sdk/rest/userprofile.json` (with user consent)
- **Medtronic Guardian:** Similar OAuth2 device data endpoint

---

## SUCCESS CRITERIA (Must Pass Before August 31)

- [ ] 10,000+ active BiometricCapsule users
- [ ] 30%+ improvement in time-in-range (vs. control group)
- [ ] 3+ pharmaceutical partners using AP2 research cohort
- [ ] $1M+ in direct patient royalties distributed
- [ ] 5+ published papers using AP2 anonymized data
- [ ] Zero reidentification incidents (cryptographic audit)
- [ ] Psi drift guard prevents model poisoning (100% detection rate)

---

## FILES TO CREATE

```
crates/siss-night-cycle/src/
└── biometric_capsule.rs (estimated 500-600 LOC)

crates/siss-night-cycle/tests/
└── biometric_capsule_test.rs (estimated 300-400 LOC)

crates/siss-graph-db/src/
└── oracle_distillation.rs (if not exists; estimated 200 LOC for OPLoRA + psi guard)
```

---

## OWNER & DEADLINE

**Owner:** Agent-Cluster-C (Parallel Implementation Team)  
**Target Completion:** June 14, 2026  
**Launch Date:** July 15, 2026 (Live PoC with Dexcom + diabetes research)
