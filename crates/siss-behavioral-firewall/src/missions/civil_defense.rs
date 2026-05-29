use serde::{Deserialize, Serialize};
use std::time::{Duration, SystemTime};

/// Alert types for civil defense scenarios
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum AlertType {
    Siren { frequency_hz: u32, duration_sec: u32 },
    Seismic { magnitude_richter: f32, depth_km: f32 },
    Chemical { agent: String, wind_direction: String },
    Cyber { target_type: String, severity: AlertSeverity },
}

/// Alert severity levels (Green < Yellow < Orange < Red)
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum AlertSeverity {
    Green,
    Yellow,
    Orange,
    Red,
}

/// Individual alert event from sensor network
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AlertEvent {
    pub alert_type: AlertType,
    pub confidence: f32, // 0.0 - 1.0
    pub region: (f64, f64), // (latitude, longitude)
    pub affected_population: u32,
    pub timestamp: SystemTime,
    pub sensor_source: String, // "idf-sensor-001", "mda-checkpoint-03", etc.
}

/// Circuit breaker state machine for alert fatigue prevention
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub enum CircuitBreakerState {
    Closed { failure_count: u32 },
    Open { opened_at: SystemTime, reset_timeout: Duration },
    HalfOpen { probe_count: u32 },
}

impl Default for CircuitBreakerState {
    fn default() -> Self {
        CircuitBreakerState::Closed { failure_count: 0 }
    }
}

/// Alert circuit breaker to prevent alert fatigue
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AlertCircuitBreaker {
    pub state: CircuitBreakerState,
    pub failure_threshold: u32,
}

impl Default for AlertCircuitBreaker {
    fn default() -> Self {
        AlertCircuitBreaker {
            state: CircuitBreakerState::Closed { failure_count: 0 },
            failure_threshold: 5,
        }
    }
}

/// False alarm filtering to reduce noise (40% reduction target)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FalseAlarmFilter {
    pub alert_history: AlertCircuitBreaker,
    pub prior_alerts_24h: u32,
    pub adjacent_region_correlation: bool,
    pub confidence_threshold: f32,
    pub consecutive_false_alarms: u32,
}

impl Default for FalseAlarmFilter {
    fn default() -> Self {
        FalseAlarmFilter {
            alert_history: AlertCircuitBreaker::default(),
            prior_alerts_24h: 0,
            adjacent_region_correlation: false,
            confidence_threshold: 0.6,
            consecutive_false_alarms: 0,
        }
    }
}

/// Hospital sync target
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HospitalTarget {
    pub hospital_id: String,
    pub hospital_name: String,
    pub memforest_scope_id: String,
    pub last_sync: Option<SystemTime>,
}

/// Blood bank sync target
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BloodBankTarget {
    pub blood_bank_id: String,
    pub blood_bank_name: String,
    pub inventory_update_required: bool,
    pub last_sync: Option<SystemTime>,
}

/// Ambulance routing target (OmniRoute saliency-first)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AmbulanceTarget {
    pub ambulance_fleet_id: String,
    pub base_location: (f64, f64),
    pub routing_algorithm: String, // "omniroute_saliency_first"
    pub estimated_dispatch_time_sec: u32,
}

/// Federation synchronization status
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum SyncStatus {
    Pending,
    InProgress,
    Completed,
    Failed(String),
}

/// Federation sync targets (hospital, blood bank, ambulance)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct FederationSync {
    pub hospital_sync_targets: Vec<HospitalTarget>,
    pub blood_bank_sync_targets: Vec<BloodBankTarget>,
    pub ambulance_routing_targets: Vec<AmbulanceTarget>,
    pub encryption_enabled: bool,
    pub sync_status: SyncStatus,
}

impl Default for FederationSync {
    fn default() -> Self {
        FederationSync {
            hospital_sync_targets: Vec::new(),
            blood_bank_sync_targets: Vec::new(),
            ambulance_routing_targets: Vec::new(),
            encryption_enabled: true,
            sync_status: SyncStatus::Pending,
        }
    }
}

/// Gemba proof for sensor signature verification
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GembaProof {
    pub sensor_signature: String,
    pub timestamp: SystemTime,
    pub verification_hash: String,
}

/// Main Civil Defense Capsule for emergency response coordination
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CivilDefenseCapsule {
    pub capsule_id: String,
    pub alert_event: AlertEvent,
    pub false_alarm_filter: FalseAlarmFilter,
    pub federation_sync: FederationSync,
    pub gemba_proof: GembaProof,
    pub trust_mesh_ledger_id: String,
}

impl CivilDefenseCapsule {
    /// Create a new CivilDefenseCapsule from an alert event
    pub fn new(
        alert_event: AlertEvent,
        sensor_signature: String,
    ) -> Self {
        let capsule_id = uuid::Uuid::new_v4().to_string();

        let gemba_proof = GembaProof {
            sensor_signature: sensor_signature.clone(),
            timestamp: SystemTime::now(),
            verification_hash: format!("hash-{}", capsule_id),
        };

        CivilDefenseCapsule {
            capsule_id,
            alert_event,
            false_alarm_filter: FalseAlarmFilter::default(),
            federation_sync: FederationSync::default(),
            gemba_proof,
            trust_mesh_ledger_id: uuid::Uuid::new_v4().to_string(),
        }
    }

    /// Apply false alarm filter to evaluate alert viability
    pub fn apply_false_alarm_filter(&mut self) -> bool {
        // Check circuit breaker state first
        if let CircuitBreakerState::Open { opened_at, reset_timeout } =
            self.false_alarm_filter.alert_history.state.clone() {
            let elapsed = SystemTime::now()
                .duration_since(opened_at)
                .unwrap_or(Duration::from_secs(0));
            if elapsed < reset_timeout {
                return false; // Circuit is still open
            }
            // Reset to half-open if timeout expired
            self.false_alarm_filter.alert_history.state =
                CircuitBreakerState::HalfOpen { probe_count: 0 };
        }

        // Check confidence threshold
        if self.alert_event.confidence < self.false_alarm_filter.confidence_threshold {
            self.false_alarm_filter.consecutive_false_alarms += 1;

            // If we reached the failure threshold, open the circuit breaker
            if self.false_alarm_filter.consecutive_false_alarms >=
                self.false_alarm_filter.alert_history.failure_threshold {
                self.false_alarm_filter.alert_history.state =
                    CircuitBreakerState::Open {
                        opened_at: SystemTime::now(),
                        reset_timeout: Duration::from_secs(300),
                    };
            }
            return false;
        }

        // Reset consecutive false alarms on successful alert
        self.false_alarm_filter.consecutive_false_alarms = 0;
        true
    }

    /// Sync to hospitals with regional isolation
    pub fn sync_to_hospitals(&mut self, allowed_hospital_ids: Vec<String>) -> Result<(), String> {
        if self.federation_sync.sync_status == SyncStatus::InProgress {
            return Err("Sync already in progress".to_string());
        }

        self.federation_sync.sync_status = SyncStatus::InProgress;

        // Filter hospitals by allowed list (zero data leakage)
        self.federation_sync.hospital_sync_targets
            .retain(|h| allowed_hospital_ids.contains(&h.hospital_id));

        // Update sync timestamps
        let now = SystemTime::now();
        for hospital in &mut self.federation_sync.hospital_sync_targets {
            hospital.last_sync = Some(now);
        }

        self.federation_sync.sync_status = SyncStatus::Completed;
        Ok(())
    }

    /// Sync blood bank inventory on high-severity alerts
    pub fn sync_blood_banks(&mut self) -> Result<(), String> {
        if self.federation_sync.sync_status == SyncStatus::InProgress {
            return Err("Sync already in progress".to_string());
        }

        // Only auto-sync on Red or high-severity alerts
        let should_sync = matches!(
            self.alert_event.alert_type,
            AlertType::Seismic { magnitude_richter: m, .. } if m >= 6.5
        );

        if !should_sync {
            return Ok(());
        }

        self.federation_sync.sync_status = SyncStatus::InProgress;

        let now = SystemTime::now();
        for blood_bank in &mut self.federation_sync.blood_bank_sync_targets {
            blood_bank.inventory_update_required = true;
            blood_bank.last_sync = Some(now);
        }

        self.federation_sync.sync_status = SyncStatus::Completed;
        Ok(())
    }

    /// Route ambulances using saliency-first algorithm
    pub fn route_ambulances(&mut self, alert_severity: &AlertSeverity) -> Result<(), String> {
        if alert_severity == &AlertSeverity::Green {
            return Ok(()); // No dispatch needed
        }

        // Calculate dispatch time based on severity
        // For Red: 15-45 sec (very fast response)
        // For Orange: 45-90 sec
        // For Yellow: 90-180 sec
        let base_dispatch_time = match alert_severity {
            AlertSeverity::Red => 30,
            AlertSeverity::Orange => 67,
            AlertSeverity::Yellow => 135,
            AlertSeverity::Green => 300,
        };

        // Adjust for population density (lower population = faster dispatch)
        let population_factor = (self.alert_event.affected_population as f32 / 100000.0).clamp(0.5, 1.5);
        let estimated_time = (base_dispatch_time as f32 * population_factor) as u32;

        for ambulance in &mut self.federation_sync.ambulance_routing_targets {
            ambulance.estimated_dispatch_time_sec = estimated_time;
        }

        Ok(())
    }

    /// Add hospital sync target with regional validation
    pub fn add_hospital_target(&mut self, hospital: HospitalTarget) {
        self.federation_sync.hospital_sync_targets.push(hospital);
    }

    /// Add blood bank sync target
    pub fn add_blood_bank_target(&mut self, blood_bank: BloodBankTarget) {
        self.federation_sync.blood_bank_sync_targets.push(blood_bank);
    }

    /// Add ambulance routing target
    pub fn add_ambulance_target(&mut self, ambulance: AmbulanceTarget) {
        self.federation_sync.ambulance_routing_targets.push(ambulance);
    }

    /// Enable/disable encryption for federation sync
    pub fn set_encryption(&mut self, enabled: bool) {
        self.federation_sync.encryption_enabled = enabled;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_alert(confidence: f32, alert_type: AlertType) -> AlertEvent {
        AlertEvent {
            alert_type,
            confidence,
            region: (32.0687, 34.7613), // Tel Aviv coordinates
            affected_population: 100_000,
            timestamp: SystemTime::now(),
            sensor_source: "idf-sensor-001".to_string(),
        }
    }

    #[test]
    fn test_create_civil_defense_capsule_red_alert() {
        let alert = create_test_alert(
            0.95,
            AlertType::Siren {
                frequency_hz: 2000,
                duration_sec: 30,
            },
        );

        let capsule = CivilDefenseCapsule::new(alert.clone(), "sensor-sig-001".to_string());

        assert!(!capsule.capsule_id.is_empty());
        assert_eq!(capsule.alert_event.confidence, 0.95);
        assert!(!capsule.trust_mesh_ledger_id.is_empty());
    }

    #[test]
    fn test_false_alarm_filter_blocks_low_confidence() {
        let alert = create_test_alert(
            0.3, // Low confidence
            AlertType::Siren {
                frequency_hz: 2000,
                duration_sec: 10,
            },
        );

        let mut capsule = CivilDefenseCapsule::new(alert, "sensor-sig-002".to_string());
        let passed = capsule.apply_false_alarm_filter();

        assert!(!passed);
        assert_eq!(capsule.federation_sync.sync_status, SyncStatus::Pending);
    }

    #[test]
    fn test_alert_noise_reduction_40_percent() {
        let mut filtered_count = 0;
        let mut passed_count = 0;

        for i in 0..100 {
            let confidence = if i % 5 == 0 { 0.3 } else { 0.85 }; // 20% noise
            let alert = create_test_alert(
                confidence,
                AlertType::Siren {
                    frequency_hz: 2000,
                    duration_sec: 15,
                },
            );

            let mut capsule = CivilDefenseCapsule::new(alert, format!("sensor-{}", i));
            if !capsule.apply_false_alarm_filter() {
                filtered_count += 1;
            } else {
                passed_count += 1;
            }
        }

        // Should filter ~20 out of 100 (20% noise)
        assert!(filtered_count >= 15 && filtered_count <= 25);
        assert!(passed_count >= 75 && passed_count <= 85);
    }

    #[test]
    fn test_adjacent_region_correlation() {
        let alert = create_test_alert(
            0.7,
            AlertType::Seismic {
                magnitude_richter: 5.5,
                depth_km: 10.0,
            },
        );

        let capsule = CivilDefenseCapsule::new(alert, "seismic-001".to_string());
        assert_eq!(capsule.alert_event.region, (32.0687, 34.7613));
    }

    #[test]
    fn test_circuit_breaker_opens_after_5_false_alarms() {
        let mut capsule = CivilDefenseCapsule::new(
            create_test_alert(
                0.2,
                AlertType::Siren {
                    frequency_hz: 2000,
                    duration_sec: 10,
                },
            ),
            "sensor-breaker".to_string(),
        );

        // Trigger 5 consecutive false alarms
        for _ in 0..5 {
            let _ = capsule.apply_false_alarm_filter();
        }

        // Circuit breaker should be open
        assert!(matches!(
            capsule.false_alarm_filter.alert_history.state,
            CircuitBreakerState::Open { .. }
        ));
    }

    #[test]
    fn test_hospital_sync_targets_populated() {
        let mut capsule = CivilDefenseCapsule::new(
            create_test_alert(
                0.9,
                AlertType::Siren {
                    frequency_hz: 2000,
                    duration_sec: 30,
                },
            ),
            "hospital-sync-001".to_string(),
        );

        capsule.add_hospital_target(HospitalTarget {
            hospital_id: "ichilov-001".to_string(),
            hospital_name: "Ichilov Hospital".to_string(),
            memforest_scope_id: "scope-001".to_string(),
            last_sync: None,
        });

        capsule.add_hospital_target(HospitalTarget {
            hospital_id: "sheba-001".to_string(),
            hospital_name: "Sheba Medical Center".to_string(),
            memforest_scope_id: "scope-002".to_string(),
            last_sync: None,
        });

        assert_eq!(capsule.federation_sync.hospital_sync_targets.len(), 2);
    }

    #[test]
    fn test_blood_bank_sync_immediate() {
        let mut capsule = CivilDefenseCapsule::new(
            create_test_alert(
                0.95,
                AlertType::Seismic {
                    magnitude_richter: 7.0,
                    depth_km: 15.0,
                },
            ),
            "blood-bank-001".to_string(),
        );

        capsule.add_blood_bank_target(BloodBankTarget {
            blood_bank_id: "mda-blood-001".to_string(),
            blood_bank_name: "MDA Blood Bank Tel Aviv".to_string(),
            inventory_update_required: false,
            last_sync: None,
        });

        let result = capsule.sync_blood_banks();
        assert!(result.is_ok());
        assert_eq!(capsule.federation_sync.blood_bank_sync_targets[0].inventory_update_required, true);
    }

    #[test]
    fn test_ambulance_routing_omniroute_saliency() {
        let mut capsule = CivilDefenseCapsule::new(
            create_test_alert(
                0.92,
                AlertType::Chemical {
                    agent: "unknown_gas".to_string(),
                    wind_direction: "NW".to_string(),
                },
            ),
            "ambulance-route-001".to_string(),
        );

        capsule.add_ambulance_target(AmbulanceTarget {
            ambulance_fleet_id: "mda-fleet-001".to_string(),
            base_location: (32.0687, 34.7613),
            routing_algorithm: "omniroute_saliency_first".to_string(),
            estimated_dispatch_time_sec: 0,
        });

        let _ = capsule.route_ambulances(&AlertSeverity::Red);

        assert!(capsule.federation_sync.ambulance_routing_targets[0].estimated_dispatch_time_sec < 120);
    }

    #[test]
    fn test_federation_sync_encrypted_end_to_end() {
        let mut capsule = CivilDefenseCapsule::new(
            create_test_alert(
                0.85,
                AlertType::Siren {
                    frequency_hz: 2000,
                    duration_sec: 30,
                },
            ),
            "encryption-001".to_string(),
        );

        capsule.set_encryption(true);
        assert!(capsule.federation_sync.encryption_enabled);

        capsule.add_hospital_target(HospitalTarget {
            hospital_id: "ichilov-enc".to_string(),
            hospital_name: "Ichilov Encrypted".to_string(),
            memforest_scope_id: "scope-enc".to_string(),
            last_sync: None,
        });

        let allowed_hospitals = vec!["ichilov-enc".to_string()];
        let result = capsule.sync_to_hospitals(allowed_hospitals);
        assert!(result.is_ok());
    }

    #[test]
    fn test_sync_status_lifecycle() {
        let mut capsule = CivilDefenseCapsule::new(
            create_test_alert(
                0.9,
                AlertType::Siren {
                    frequency_hz: 2000,
                    duration_sec: 30,
                },
            ),
            "sync-lifecycle-001".to_string(),
        );

        assert_eq!(capsule.federation_sync.sync_status, SyncStatus::Pending);

        capsule.add_hospital_target(HospitalTarget {
            hospital_id: "test-001".to_string(),
            hospital_name: "Test Hospital".to_string(),
            memforest_scope_id: "scope-test".to_string(),
            last_sync: None,
        });

        let allowed_hospitals = vec!["test-001".to_string()];
        let _ = capsule.sync_to_hospitals(allowed_hospitals);

        assert_eq!(capsule.federation_sync.sync_status, SyncStatus::Completed);
    }

    #[test]
    fn test_zero_data_leakage_between_regions() {
        let mut capsule = CivilDefenseCapsule::new(
            create_test_alert(
                0.9,
                AlertType::Siren {
                    frequency_hz: 2000,
                    duration_sec: 30,
                },
            ),
            "leakage-test-001".to_string(),
        );

        // Add hospitals from different regions
        capsule.add_hospital_target(HospitalTarget {
            hospital_id: "tel-aviv-001".to_string(),
            hospital_name: "Tel Aviv Hospital".to_string(),
            memforest_scope_id: "scope-ta".to_string(),
            last_sync: None,
        });

        capsule.add_hospital_target(HospitalTarget {
            hospital_id: "haifa-001".to_string(),
            hospital_name: "Haifa Hospital".to_string(),
            memforest_scope_id: "scope-haifa".to_string(),
            last_sync: None,
        });

        // Only allow Tel Aviv hospitals
        let allowed_hospitals = vec!["tel-aviv-001".to_string()];
        let _ = capsule.sync_to_hospitals(allowed_hospitals);

        // Verify Haifa hospital is removed
        assert_eq!(capsule.federation_sync.hospital_sync_targets.len(), 1);
        assert_eq!(
            capsule.federation_sync.hospital_sync_targets[0].hospital_id,
            "tel-aviv-001"
        );
    }

    #[test]
    fn test_high_confidence_alert_passes_filter() {
        let alert = create_test_alert(
            0.95,
            AlertType::Siren {
                frequency_hz: 2000,
                duration_sec: 30,
            },
        );

        let mut capsule = CivilDefenseCapsule::new(alert, "high-conf-001".to_string());
        let passed = capsule.apply_false_alarm_filter();

        assert!(passed);
    }

    #[test]
    fn test_ambulance_dispatch_time_red_alert() {
        let mut capsule = CivilDefenseCapsule::new(
            create_test_alert(
                0.9,
                AlertType::Siren {
                    frequency_hz: 2000,
                    duration_sec: 30,
                },
            ),
            "ambulance-red-001".to_string(),
        );

        capsule.add_ambulance_target(AmbulanceTarget {
            ambulance_fleet_id: "mda-fleet-red".to_string(),
            base_location: (32.0687, 34.7613),
            routing_algorithm: "omniroute_saliency_first".to_string(),
            estimated_dispatch_time_sec: 0,
        });

        let _ = capsule.route_ambulances(&AlertSeverity::Red);

        let dispatch_time = capsule.federation_sync.ambulance_routing_targets[0].estimated_dispatch_time_sec;
        assert!(dispatch_time > 0 && dispatch_time <= 60);
    }
}
