# SPECCAPSULE: Ukraine Humanitarian Aid
## Spec-First Design for HumanitarianAidCapsule

**Created:** May 29, 2026 | **Target Implementation:** June 4-14, 2026  
**Crate:** `crates/siss-night-cycle` (new module: `humanitarian_aid_capsule.rs`)  
**Tests:** TDD-first (write failing tests before implementation)

---

## STRUCT DEFINITION

```rust
use crate::capsule::{Capsule, GembaProof, ProvisionSeal};
use serde::{Deserialize, Serialize};
use std::time::SystemTime;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HumanitarianAidCapsule {
    /// Core Capsule wrapper (from siss-graph-db)
    pub capsule: Capsule,
    
    /// Aid package contents and metadata
    pub aid_package: AidPackage,
    
    /// Gemba proof: photo + witness signature
    pub gemba_proof: GembaProof,
    
    /// Immutable trust chain (checkpoint tracking)
    pub trust_chain: TrustChain,
    
    /// Cryptographic sealing (AES-256-GCM-SIV)
    pub provenance_seal: ProvisionSeal,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AidPackage {
    pub contents: Vec<AidItem>, // medicine, food, shelter_material, etc.
    pub total_weight_kg: u32,
    pub destination_geopoint: (f64, f64), // (latitude, longitude)
    pub destination_name: String, // "Lviv Hospital", "Kharkiv Shelter", etc.
    pub ngo_identifier: String, // "msf-ukraine-001", "icrc-kyiv-hub", etc.
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AidItem {
    pub category: AidCategory,
    pub description: String,
    pub quantity: u32,
    pub unit: String, // "boxes", "liters", "units"
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum AidCategory {
    Medicine,
    Food,
    ShelterMaterial,
    Medical Equipment,
    Clothing,
    Water,
    Generator,
    FuelKerosene,
    Other(String),
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TrustChain {
    /// NGO that verified/initialized the aid package
    pub source_ngo: String,
    
    /// Checkpoints (transit locations + GPS + timestamp + signature)
    pub checkpoints: Vec<Checkpoint>,
    
    /// Final recipient's digital signature (proves delivery)
    pub recipient_signature: Option<String>,
    
    /// Neo4j Virtual Graph reference (immutable ledger)
    pub virtualgraph_ledger_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Checkpoint {
    pub location_name: String,
    pub geopoint: (f64, f64),
    pub timestamp: SystemTime,
    pub checkpoint_custodian: String, // NGO worker name / ID
    pub signature: String, // Crypto signature of custodian
}
```

---

## TEST CASES (TDD Template)

All tests in `crates/siss-night-cycle/tests/humanitarian_aid_capsule_test.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_aid_capsule_success() {
        // Create HumanitarianAidCapsule with valid data
        // Assert: capsule_id is UUID
        // Assert: aid_package matches input
        // Assert: gemba_proof is signed
    }

    #[tokio::test]
    async fn test_create_aid_capsule_missing_destination() {
        // Try to create with empty destination_geopoint
        // Assert: returns Err(InvalidAidPackage)
    }

    #[tokio::test]
    async fn test_add_checkpoint_success() {
        // Create capsule, add checkpoint with GPS + timestamp + signature
        // Assert: checkpoint appears in trust_chain.checkpoints
    }

    #[tokio::test]
    async fn test_checkpoint_gps_validation() {
        // Try to add checkpoint with invalid GPS (lat > 90)
        // Assert: returns Err(InvalidGeopoint)
    }

    #[tokio::test]
    async fn test_seal_capsule_encryption() {
        // Create capsule, seal with AES-256-GCM-SIV
        // Encrypt, then decrypt
        // Assert: plaintext matches original
    }

    #[tokio::test]
    async fn test_recipient_signature_required_for_delivery() {
        // Capsule with checkpoints but no recipient_signature
        // Assert: is_delivered() returns false
        // Add recipient_signature
        // Assert: is_delivered() returns true
    }

    #[tokio::test]
    async fn test_virtualgraph_ledger_append() {
        // Create capsule, send to Neo4j Virtual Graph
        // Query ledger for capsule_id
        // Assert: capsule appears in immutable ledger
    }

    #[tokio::test]
    async fn test_aid_weight_validation() {
        // Create capsule with total_weight_kg = 0
        // Assert: returns Err(InvalidPackageWeight)
    }

    #[tokio::test]
    async fn test_multiple_checkpoints_ordered_by_timestamp() {
        // Add 3 checkpoints out of order
        // Assert: trust_chain.checkpoints is sorted by timestamp
    }

    #[tokio::test]
    async fn test_capsule_immutability_after_seal() {
        // Create capsule, seal it
        // Try to modify aid_package
        // Assert: returns Err(CapsuleImmutable)
    }
}
```

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Core Structure (June 4-5)
- [ ] Implement `HumanitarianAidCapsule::new()` — creates capsule from aid_package
- [ ] Implement `HumanitarianAidCapsule::add_checkpoint()` — adds transit checkpoint
- [ ] Implement `HumanitarianAidCapsule::is_delivered()` — checks if recipient_signature exists
- [ ] Add enum `AidCategory` with all aid types
- [ ] All unit tests pass (`cargo test -p siss-night-cycle humanitarian_aid`)

### Phase 2: Cryptography & Ledger (June 6-8)
- [ ] Integrate `crates/siss-tools` AES-256-GCM-SIV for `ProvisionSeal`
- [ ] Integrate `crates/siss-graph-brain::virtual_graph` for Neo4j ledger
- [ ] Implement `HumanitarianAidCapsule::seal()` → encrypted Capsule
- [ ] Implement `HumanitarianAidCapsule::verify_ledger()` → query Neo4j
- [ ] Benchmark: encryption <100ms, Neo4j query <200ms

### Phase 3: Integration (June 9-12)
- [ ] Add `gemba_proof` photo hash validation (verify EXIF, prevent deepfake)
- [ ] Integrate World Mobile partner API stub (identity verification)
- [ ] Add AP2 ledger integration (tracks royalty for research participation)
- [ ] Integration tests with actual Neo4j instance
- [ ] Load test: 1,000 capsules created concurrently, verify no data corruption

### Phase 4: Launch Readiness (June 13-14)
- [ ] All tests green: `cargo test -p siss-night-cycle`
- [ ] No clippy warnings: `cargo clippy -p siss-night-cycle -- -D warnings`
- [ ] Documentation: 100% of public APIs documented
- [ ] Success metric: Create 100 test capsules, verify all in Neo4j ledger

---

## INTEGRATION POINTS

### Existing Crates Used
- **siss-graph-db:** Capsule struct, GembaProof, serialization
- **siss-graph-brain:** Neo4j VirtualGraph for ledger
- **siss-tools:** AES-256-GCM-SIV encryption for ProvisionSeal
- **siss-night-cycle:** MemForest scope (compress 200K events to 2K for efficient transport)

### New Crate/Module
- **siss-night-cycle::humanitarian_aid_capsule** (new)
- **siss-night-cycle::tests::humanitarian_aid_capsule_test** (new)

### Partner APIs (Stubs for Phase 25)
- **World Mobile Identity API:** `verify_volunteer_identity(signature: String) -> Result<VolunteerID>`
- **Neo4j Virtual Graph:** `append_capsule_to_ledger(capsule_id: UUID, ...) -> Result<()>`

---

## SUCCESS CRITERIA (Must Pass Before June 30)

- [ ] 100,000+ HumanitarianAidCapsules created in production
- [ ] Zero data corruption in Neo4j ledger (audit: cross-check 100 random capsules)
- [ ] Encryption unbroken (zero security incidents in bug bounty window)
- [ ] Latency <100ms for capsule creation on 4G network
- [ ] 50+ NGOs actively using the system (World Mobile partnership)
- [ ] No capsule tampered after recipient delivery (immutability verified)

---

## FILES TO CREATE

```
crates/siss-night-cycle/src/
└── humanitarian_aid_capsule.rs (estimated 300-400 LOC)

crates/siss-night-cycle/tests/
└── humanitarian_aid_capsule_test.rs (estimated 200-300 LOC)

crates/siss-night-cycle/src/
└── lib.rs (add: pub mod humanitarian_aid_capsule; +1 LOC)
```

---

## OWNER & DEADLINE

**Owner:** Agent-Cluster-A (Parallel Implementation Team)  
**Target Completion:** June 14, 2026 (with all tests passing)  
**Launch Date:** June 30, 2026 (Live PoC in Ukraine)
