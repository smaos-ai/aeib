# SPECCAPSULE: Israel Civil Defense Trust Mesh
## Spec-First Design for CivilDefenseCapsule

**Created:** May 29, 2026 | **Target Implementation:** June 4-14, 2026  
**Crate:** `crates/siss-behavioral-firewall` (new module: `civil_defense_capsule.rs`)  
**Tests:** TDD-first | **Integration:** Magen David Adom + Israeli Health Ministry

---

## STRUCT DEFINITION

```rust
use crate::capsule::{Capsule, GembaProof};
use serde::{Deserialize, Serialize};
use std::time::{Duration, SystemTime};
use std::sync::Arc;
use tokio::sync::RwLock;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CivilDefenseCapsule {
    /// Core Capsule wrapper
    pub capsule: Capsule,
    
    /// Alert event data (siren, seismic, chemical, cyber)
    pub alert_event: AlertEvent,
    
    /// False alarm filter state (reduces noise by 40%)
    pub false_alarm_filter: FalseAlarmFilter,
    
    /// Federation sync targets (hospital, blood bank, ambulance routing)
    pub federation_sync: FederationSync,
    
    /// Gemba proof: sensor signature + timestamp
    pub gemba_proof: GembaProof,
    
    /// Neo4j ledger: medical authority verification
    pub trust_mesh_ledger_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum AlertType {
    Siren { frequency_hz: u32, duration_sec: u32 },
    Seismic { magnitude_richter: f32, depth_km: f32 },
    Chemical { agent: String, wind_direction: String },
    Cyber { target_type: String, severity: AlertSeverity },
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum AlertSeverity {
    Green,   // No threat
    Yellow,  // Watch / Monitor
    Orange,  // Heightened alert
    Red,     // Immediate danger
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AlertEvent {
    pub alert_type: AlertType,
    pub confidence: f32, // 0.0 - 1.0
    pub region: (f64, f64), // (latitude, longitude)
    pub affected_population: u32,
    pub timestamp: SystemTime,
    pub sensor_source: String, // "idf-sensor-001", "mda-checkpoint-03", etc.
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FalseAlarmFilter {
    /// Circuit breaker for alert fatigue (prevents desensitization)
    pub alert_history: AlertCircuitBreaker,
    
    /// Prior alerts in past 24 hours (avoid duplicate alerts)
    pub prior_alerts_24h: u32,
    
    /// Correlation with adjacent region alerts
    pub adjacent_region_correlation: bool,
    
    /// Confidence threshold (reject alerts below threshold)
    pub confidence_threshold: f32,
    
    /// Consecutive false alarms count (triggers review after 5)
    pub consecutive_false_alarms: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AlertCircuitBreaker {
    pub state: CircuitBreakerState,
    pub failure_threshold: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub enum CircuitBreakerState {
    Closed { failure_count: u32 },
    Open { opened_at: SystemTime, reset_timeout: Duration },
    HalfOpen { probe_count: u32 },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FederationSync {
    /// Hospital sync (MemForest scope = hospital_id)
    pub hospital_sync_targets: Vec<HospitalTarget>,
    
    /// Blood bank inventory sync (immediate update)
    pub blood_bank_sync_targets: Vec<BloodBankTarget>,
    
    /// Ambulance routing (OmniRoute saliency-first)
    pub ambulance_routing_targets: Vec<AmbulanceTarget>,
    
    /// Encryption channel (AES-256-GCM-SIV)
    pub encryption_enabled: bool,
    
    /// Sync status (pending, in_progress, completed, failed)
    pub sync_status: SyncStatus,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HospitalTarget {
    pub hospital_id: String,
    pub hospital_name: String,
    pub memforest_scope_id: String,
    pub last_sync: Option<SystemTime>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BloodBankTarget {
    pub blood_bank_id: String,
    pub blood_bank_name: String,
    pub inventory_update_required: bool,
    pub last_sync: Option<SystemTime>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AmbulanceTarget {
    pub ambulance_fleet_id: String,
    pub base_location: (f64, f64),
    pub routing_algorithm: String, // "omniroute_saliency_first"
    pub estimated_dispatch_time_sec: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum SyncStatus {
    Pending,
    InProgress,
    Completed,
    Failed(String),
}
```

---

## TEST CASES (TDD Template)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_civil_defense_capsule_red_alert() {
        // Create high-confidence Red alert
        // Assert: alert_type == Red
        // Assert: confidence >= 0.9
    }

    #[tokio::test]
    async fn test_false_alarm_filter_blocks_low_confidence() {
        // Create alert with confidence = 0.3
        // Assert: false_alarm_filter rejects it
        // Assert: sync_status == Pending (not triggered)
    }

    #[tokio::test]
    async fn test_alert_noise_reduction_40_percent() {
        // Create 100 random alerts (60% real, 40% noise)
        // Apply false_alarm_filter
        // Assert: ~40 alerts filtered out
    }

    #[tokio::test]
    async fn test_adjacent_region_correlation() {
        // Create alert in Region A
        // Assert: adjacent_region_correlation checks Region B + C
        // Assert: if Region B also has alert, confidence increases
    }

    #[tokio::test]
    async fn test_circuit_breaker_opens_after_5_false_alarms() {
        // Create 5 consecutive false alarms
        // Assert: alert_history.state == Open (alert fatigue)
    }

    #[tokio::test]
    async fn test_hospital_sync_targets_populated() {
        // Create capsule for Tel Aviv
        // Assert: federation_sync.hospital_sync_targets includes Ichilov + Sheba
    }

    #[tokio::test]
    async fn test_blood_bank_sync_immediate() {
        // Alert: Red severity, seismic magnitude 7.0
        // Assert: blood_bank_sync_targets updated immediately
        // Assert: inventory_update_required == true
    }

    #[tokio::test]
    async fn test_ambulance_routing_omniroute_saliency() {
        // Alert: chemical threat, 50K affected population
        // Assert: ambulance routing uses saliency-first algorithm
        // Assert: estimated_dispatch_time_sec < 120
    }

    #[tokio::test]
    async fn test_federation_sync_encrypted_end_to_end() {
        // Create capsule, enable encryption
        // Sync to hospital
        // Decrypt and verify at hospital
        // Assert: plaintext matches original
    }

    #[tokio::test]
    async fn test_sync_status_lifecycle() {
        // Create capsule
        // Assert: sync_status == Pending
        // Trigger sync
        // Assert: sync_status == InProgress, then Completed
    }

    #[tokio::test]
    async fn test_zero_data_leakage_between_regions() {
        // Create alert in Tel Aviv
        // Assert: Haifa hospital does NOT receive alert
        // Assert: only affected region hospitals receive
    }
}
```

---

## IMPLEMENTATION CHECKLIST

### Phase 1: Core Structures (June 4-5)
- [ ] Implement `CivilDefenseCapsule::new()` — create from AlertEvent
- [ ] Implement `CivilDefenseCapsule::apply_false_alarm_filter()` — apply confidence + history checks
- [ ] Implement `AlertType` enum with all alert types
- [ ] All unit tests pass

### Phase 2: Circuit Breaker & Filtering (June 6-8)
- [ ] Integrate `crates/siss-multi-region::health_check::CircuitBreaker` for alert fatigue
- [ ] Implement `FalseAlarmFilter::evaluate()` — 40% noise reduction
- [ ] Implement adjacent region correlation logic
- [ ] Benchmark: filter decision <50ms

### Phase 3: Federation Sync (June 9-11)
- [ ] Integrate MemForest for hospital scope sync
- [ ] Integrate Neo4j VirtualGraph for medical authority trust ledger
- [ ] Implement `FederationSync::sync_to_hospitals()` — endpoint calls
- [ ] Implement `FederationSync::sync_to_blood_banks()` — inventory updates
- [ ] Implement `FederationSync::route_ambulances()` — OmniRoute integration

### Phase 4: Encryption & Launch (June 12-14)
- [ ] Integrate AES-256-GCM-SIV encryption for federation messages
- [ ] Integration tests with mock hospital endpoints
- [ ] Load test: 1,000 simultaneous alerts, verify <50ms latency
- [ ] All tests green: `cargo test -p siss-behavioral-firewall`

---

## INTEGRATION POINTS

### Existing Crates Used
- **siss-multi-region:** CircuitBreaker state machine for alert fatigue
- **siss-graph-db:** Capsule, Neo4j VirtualGraph for trust ledger
- **siss-night-cycle:** MemForest for hospital scope compression
- **siss-context-cartography:** Region geo-spatial correlation
- **siss-agent-shell:** OmniRoute saliency-first ambulance routing

### Partner APIs
- **Magen David Adom:** Alert subscription endpoint, ambulance dispatch
- **Israeli Health Ministry:** Hospital list, blood bank inventory
- **Sheba + Ichilov + other Tel Aviv hospitals:** MemForest scope endpoints

---

## SUCCESS CRITERIA (Must Pass Before July 15)

- [ ] 15+ Israeli hospitals + 50+ Magen David Adom stations live
- [ ] <50ms alert propagation end-to-end (hospital receives alert <50ms after detection)
- [ ] 40% false alarm reduction documented (audit: compare to baseline)
- [ ] Zero data leakage between regions (audit: verify regional isolation)
- [ ] Zero encryption breaks (security audit by Israeli defense ministry)
- [ ] Circuit breaker prevents desensitization (no alert fatigue incidents)

---

## FILES TO CREATE

```
crates/siss-behavioral-firewall/src/
└── civil_defense_capsule.rs (estimated 400-500 LOC)

crates/siss-behavioral-firewall/tests/
└── civil_defense_capsule_test.rs (estimated 250-350 LOC)

crates/siss-behavioral-firewall/src/
└── lib.rs (add: pub mod civil_defense_capsule; +1 LOC)
```

---

## OWNER & DEADLINE

**Owner:** Agent-Cluster-B (Parallel Implementation Team)  
**Target Completion:** June 14, 2026  
**Launch Date:** July 1, 2026 (Live PoC with Magen David Adom)
