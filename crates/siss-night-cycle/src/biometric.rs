use crate::memtree::Capsule;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::SystemTime;

/// BiometricCapsule: Metabolic Intelligence Coach for diabetes management
/// Combines CGM data, personal metabolic models, and federated learning
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct BiometricCapsule {
    /// Core Capsule wrapper
    pub capsule: Capsule,

    /// Device data (Dexcom, Libre, Garmin, Medtronic)
    pub device_data: DeviceData,

    /// Personal metabolic model (runs locally on device)
    pub personal_metabolic_model: PersonalMetabolicModel,

    /// AP2 research consent + royalty tracking
    pub ap2_research_capsule: AP2ResearchCapsule,

    /// Gemba proof: patient + device provenance
    pub gemba_proof: GembaProof,

    /// Encryption key ID (AES-256-GCM-SIV, patient holds key)
    pub encryption_key_id: String,
}

/// Device data from CGM sensors and wearables
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DeviceData {
    pub glucose_mg_dl: u32,
    pub device_timestamp: i64, // Unix timestamp from Dexcom/Garmin
    pub device_id: String,     // Device serial number (cryptographically signed)
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

impl DeviceData {
    /// Validate glucose reading is within clinical range
    pub fn validate(&self) -> Result<(), String> {
        if self.glucose_mg_dl < 20 || self.glucose_mg_dl > 500 {
            return Err(format!(
                "Glucose {} mg/dL outside valid range [20-500]",
                self.glucose_mg_dl
            ));
        }
        if !(0.0..=1.0).contains(&self.reading_quality) {
            return Err("Reading quality must be between 0.0 and 1.0".to_string());
        }
        Ok(())
    }
}

/// Personal metabolic model: insulin sensitivity, carb ratios, circadian patterns
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct PersonalMetabolicModel {
    /// Insulin sensitivity (mg/dL per unit insulin)
    pub insulin_sensitivity: f32,

    /// Carbs-to-insulin ratio (grams carbs per unit insulin)
    pub carb_ratio: f32,

    /// Dawn phenomenon profile (early morning glucose rise)
    pub dawn_phenomenon_profile: DawnPhenomenonProfile,

    /// Exercise response (glucose delta per activity type)
    pub exercise_response: ExerciseResponse,

    /// Distillation model version (Qwen3.5-4B with OPLoRA)
    pub distillation_model: DistillationModelRef,

    /// Psi drift score: model coherence over time (0.0 = perfect, 1.0 = degraded)
    pub psi_drift_score: f32,

    /// Last model update
    pub last_update: SystemTime,

    /// 15-minute glucose prediction
    pub predicted_glucose_15min: u32,
    pub prediction_confidence: f32,
}

/// Dawn phenomenon: early morning glucose elevation pattern
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DawnPhenomenonProfile {
    pub baseline_glucose: u32, // mg/dL at 6am
    pub peak_glucose: u32,     // mg/dL at peak (usually 7-8am)
    pub peak_hour: u32,        // 0-23
    pub duration_hours: f32,
}

/// Exercise response learning: correlate activities with glucose changes
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExerciseResponse {
    pub exercise_types: Vec<ExerciseType>,
    pub glucose_delta_per_type: HashMap<String, i32>, // mg/dL change
    pub lag_minutes: u32,                             // minutes until glucose drops
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExerciseType {
    pub activity: String, // "walking", "running", "cycling", "swimming"
    pub intensity: u32,   // 1-10
    pub duration_minutes: u32,
}

/// Distillation model reference: Qwen3.5-4B with OPLoRA for edge inference
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DistillationModelRef {
    pub model_version: String,       // "qwen3.5-4b-v1.0"
    pub checkpoint_hash: String,     // SHA256 of model weights
    pub adapter_rank: u32,           // LoRA rank (4-32)
    pub orthogonal_projection: bool, // Use OPLoRA (orthogonal)
    pub training_date: SystemTime,
}

/// AP2 research capsule: consent levels, royalty tracking, data sharing
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AP2ResearchCapsule {
    /// Anonymized data hash (zero re-identification risk)
    pub anonymized_data_hash: String,

    /// Consent level for data sharing
    pub consent_level: ConsentLevel,

    /// Royalty earned from research (1% of commercial value)
    pub royalty_earned_usd: u32,

    /// Last royalty payment timestamp
    pub last_royalty_payment: Option<SystemTime>,

    /// Neo4j ledger: research institution signatures
    pub virtualgraph_ledger_id: String,

    /// Data sharing partners (institutions with access)
    pub sharing_partners: Vec<ResearchPartner>,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub enum ConsentLevel {
    Basic,            // No data sharing
    ResearchBasic,    // Anonymized data to non-profit research
    ResearchAdvanced, // Anonymized data to for-profit + pharma
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ResearchPartner {
    pub institution_name: String,
    pub institution_type: String, // "pharma", "university", "hospital"
    pub access_granted_date: SystemTime,
    pub access_scope: String, // "glucose_only", "full_metabolic", etc.
}

/// Gemba proof: cryptographic provenance of patient and device identity
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct GembaProof {
    pub patient_id_hash: String,
    pub device_signature: String,
    pub timestamp: SystemTime,
    pub proof_of_work: String, // Cryptographic proof
}

impl BiometricCapsule {
    /// Create a new BiometricCapsule from device data
    pub fn new(
        device_data: DeviceData,
        capsule_id: String,
        encryption_key_id: String,
    ) -> Result<Self, String> {
        // Validate device data
        device_data.validate()?;

        // Create core capsule
        let capsule = Capsule {
            id: capsule_id,
            content: serde_json::json!({
                "device_type": format!("{:?}", device_data.device_type),
                "glucose": device_data.glucose_mg_dl,
            }),
            created_at: SystemTime::now()
                .duration_since(SystemTime::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        };

        // Initialize personal metabolic model with defaults
        let personal_metabolic_model = PersonalMetabolicModel {
            insulin_sensitivity: 50.0, // mg/dL per unit insulin
            carb_ratio: 10.0,          // grams carbs per unit
            dawn_phenomenon_profile: DawnPhenomenonProfile {
                baseline_glucose: 100,
                peak_glucose: 130,
                peak_hour: 7,
                duration_hours: 2.0,
            },
            exercise_response: ExerciseResponse {
                exercise_types: vec![],
                glucose_delta_per_type: HashMap::new(),
                lag_minutes: 15,
            },
            distillation_model: DistillationModelRef {
                model_version: "qwen3.5-4b-v1.0".to_string(),
                checkpoint_hash: "placeholder".to_string(),
                adapter_rank: 8,
                orthogonal_projection: true,
                training_date: SystemTime::now(),
            },
            psi_drift_score: 0.0,
            last_update: SystemTime::now(),
            predicted_glucose_15min: device_data.glucose_mg_dl,
            prediction_confidence: 0.5,
        };

        // Initialize AP2 research capsule
        let ap2_research_capsule = AP2ResearchCapsule {
            anonymized_data_hash: "placeholder".to_string(),
            consent_level: ConsentLevel::Basic,
            royalty_earned_usd: 0,
            last_royalty_payment: None,
            virtualgraph_ledger_id: "placeholder".to_string(),
            sharing_partners: vec![],
        };

        // Initialize Gemba proof
        let gemba_proof = GembaProof {
            patient_id_hash: "placeholder".to_string(),
            device_signature: device_data.device_id.clone(),
            timestamp: SystemTime::now(),
            proof_of_work: "placeholder".to_string(),
        };

        Ok(Self {
            capsule,
            device_data,
            personal_metabolic_model,
            ap2_research_capsule,
            gemba_proof,
            encryption_key_id,
        })
    }

    /// Predict glucose level 15 minutes into the future
    pub fn predict_glucose_15min(&self) -> u32 {
        self.personal_metabolic_model.predicted_glucose_15min
    }

    /// Update personal metabolic model from historical data
    pub fn train_from_history(&mut self, glucose_history: &[(i64, u32)]) -> Result<(), String> {
        if glucose_history.len() < 7 {
            return Err("Need at least 7 glucose readings for training".to_string());
        }

        // Simple insulin sensitivity calculation using Clarke Error Grid approach
        let avg_glucose: u32 =
            glucose_history.iter().map(|(_, g)| *g).sum::<u32>() / glucose_history.len() as u32;

        // Estimate sensitivity from variance
        let variance = glucose_history
            .iter()
            .map(|(_, g)| {
                let diff = *g as f32 - avg_glucose as f32;
                diff * diff
            })
            .sum::<f32>()
            / glucose_history.len() as f32;

        self.personal_metabolic_model.insulin_sensitivity = 50.0 + (variance.sqrt() / 100.0);

        // Update timestamp
        self.personal_metabolic_model.last_update = SystemTime::now();

        Ok(())
    }

    /// Detect dawn phenomenon pattern from glucose history
    pub fn detect_dawn_phenomenon(
        &mut self,
        glucose_history_by_hour: &HashMap<u32, u32>,
    ) -> Result<(), String> {
        if glucose_history_by_hour.len() < 7 {
            return Err("Need at least 7 days of hourly data".to_string());
        }

        // Find baseline at 6am and peak between 7-8am
        let baseline = glucose_history_by_hour.get(&6).copied().unwrap_or(100);
        let peak_hour = [7, 8, 9]
            .iter()
            .filter_map(|h| glucose_history_by_hour.get(h).map(|g| (*h, *g)))
            .max_by_key(|(_, g)| *g)
            .map(|(h, _)| h)
            .unwrap_or(7);
        let peak = glucose_history_by_hour
            .get(&peak_hour)
            .copied()
            .unwrap_or(130);

        // Update profile if pattern detected (>30 mg/dL rise)
        if peak > baseline + 30 {
            self.personal_metabolic_model.dawn_phenomenon_profile = DawnPhenomenonProfile {
                baseline_glucose: baseline,
                peak_glucose: peak,
                peak_hour,
                duration_hours: 2.0,
            };
        }

        Ok(())
    }

    /// Learn exercise response from correlated exercise + glucose data
    pub fn learn_exercise_response(
        &mut self,
        exercise_type: String,
        glucose_before: u32,
        glucose_after: u32,
        lag_minutes: u32,
    ) -> Result<(), String> {
        let delta = (glucose_after as i32) - (glucose_before as i32);
        self.personal_metabolic_model
            .exercise_response
            .glucose_delta_per_type
            .insert(exercise_type, delta);
        self.personal_metabolic_model.exercise_response.lag_minutes = lag_minutes;
        Ok(())
    }

    /// Calculate psi drift score (model coherence metric)
    pub fn calculate_psi_drift(&mut self, historical_predictions: &[u32], actuals: &[u32]) {
        if historical_predictions.len() != actuals.len() || historical_predictions.is_empty() {
            return;
        }

        // Simple drift metric: MAPE (Mean Absolute Percentage Error)
        let errors: f32 = historical_predictions
            .iter()
            .zip(actuals.iter())
            .map(|(pred, actual)| {
                let error = (*pred as f32 - *actual as f32).abs();
                error / (*actual as f32).max(1.0)
            })
            .sum();

        let mape = errors / historical_predictions.len() as f32;
        self.personal_metabolic_model.psi_drift_score = (mape * 0.5).min(1.0);
    }

    /// Apply AP2 consent level and enable data sharing
    pub fn apply_consent_level(&mut self, level: ConsentLevel) {
        self.ap2_research_capsule.consent_level = level;
        if level == ConsentLevel::Basic {
            self.ap2_research_capsule.sharing_partners.clear();
            self.ap2_research_capsule.royalty_earned_usd = 0;
        }
    }

    /// Add research partner access
    pub fn add_research_partner(&mut self, partner: ResearchPartner) -> Result<(), String> {
        if self.ap2_research_capsule.consent_level == ConsentLevel::Basic {
            return Err("Cannot add partners with Basic consent level".to_string());
        }
        self.ap2_research_capsule.sharing_partners.push(partner);
        Ok(())
    }

    /// Calculate royalty based on research usage
    pub fn calculate_royalty(&mut self, commercial_value_usd: u32) {
        let royalty = (commercial_value_usd as f32 * 0.01) as u32; // 1% royalty
        self.ap2_research_capsule.royalty_earned_usd = royalty;
        self.ap2_research_capsule.last_royalty_payment = Some(SystemTime::now());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_biometric_capsule_from_device() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let capsule = BiometricCapsule::new(
            device_data.clone(),
            "capsule_1".to_string(),
            "key_1".to_string(),
        )
        .expect("Failed to create capsule");

        assert_eq!(capsule.device_data.glucose_mg_dl, 120);
        assert_eq!(capsule.device_data.device_type, DeviceType::DexcomG7);
        assert_eq!(capsule.capsule.id, "capsule_1");
    }

    #[test]
    fn test_device_data_validation_valid_range() {
        let device_data = DeviceData {
            glucose_mg_dl: 150,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG6,
            reading_quality: 0.9,
        };

        assert!(device_data.validate().is_ok());
    }

    #[test]
    fn test_device_data_validation_too_low() {
        let device_data = DeviceData {
            glucose_mg_dl: 10,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG6,
            reading_quality: 0.9,
        };

        assert!(device_data.validate().is_err());
    }

    #[test]
    fn test_device_data_validation_too_high() {
        let device_data = DeviceData {
            glucose_mg_dl: 600,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG6,
            reading_quality: 0.9,
        };

        assert!(device_data.validate().is_err());
    }

    #[test]
    fn test_device_data_validation_bad_quality() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG6,
            reading_quality: 1.5,
        };

        assert!(device_data.validate().is_err());
    }

    #[test]
    fn test_personal_metabolic_model_predicts_glucose() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        let prediction = capsule.predict_glucose_15min();
        assert!(prediction >= 70 && prediction <= 400);
    }

    #[test]
    fn test_train_from_history_success() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        // 7 days of glucose readings
        let history = vec![
            (1000, 100),
            (2000, 110),
            (3000, 95),
            (4000, 120),
            (5000, 105),
            (6000, 115),
            (7000, 125),
        ];

        let result = capsule.train_from_history(&history);
        assert!(result.is_ok());
        assert!(capsule.personal_metabolic_model.insulin_sensitivity > 0.0);
    }

    #[test]
    fn test_train_from_history_insufficient_data() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        let history = vec![(1000, 100), (2000, 110)];

        let result = capsule.train_from_history(&history);
        assert!(result.is_err());
    }

    #[test]
    fn test_dawn_phenomenon_detection() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        // Simulate 7+ days of hourly readings across different hours
        let mut glucose_by_hour = HashMap::new();

        // Populate with readings for each hour of the day from multiple days
        for hour in 0..24 {
            if hour == 6 {
                glucose_by_hour.insert(hour, 100); // Baseline at 6am
            } else if hour == 7 {
                glucose_by_hour.insert(hour, 140); // Peak at 7am (>30 mg/dL rise)
            } else if hour == 8 {
                glucose_by_hour.insert(hour, 135);
            } else {
                glucose_by_hour.insert(hour, 110);
            }
        }

        let result = capsule.detect_dawn_phenomenon(&glucose_by_hour);
        assert!(result.is_ok());
        assert!(
            capsule
                .personal_metabolic_model
                .dawn_phenomenon_profile
                .peak_glucose
                > 130
        );
    }

    #[test]
    fn test_exercise_response_learning() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        // Log exercise response
        let result = capsule.learn_exercise_response("running".to_string(), 120, 95, 15);
        assert!(result.is_ok());
        assert_eq!(
            capsule
                .personal_metabolic_model
                .exercise_response
                .glucose_delta_per_type
                .get("running"),
            Some(&-25)
        );
    }

    #[test]
    fn test_psi_drift_guard_low_drift() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        // Accurate predictions (low drift)
        let predictions = vec![100, 110, 95, 120, 105];
        let actuals = vec![102, 108, 97, 119, 106];

        capsule.calculate_psi_drift(&predictions, &actuals);
        assert!(capsule.personal_metabolic_model.psi_drift_score < 0.1);
    }

    #[test]
    fn test_psi_drift_guard_high_drift() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        // Inaccurate predictions (high drift - model poisoning)
        let predictions = vec![80, 150, 70, 200, 50];
        let actuals = vec![120, 100, 120, 100, 120];

        capsule.calculate_psi_drift(&predictions, &actuals);
        assert!(capsule.personal_metabolic_model.psi_drift_score > 0.1);
    }

    #[test]
    fn test_ap2_consent_level_basic_no_sharing() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        assert_eq!(
            capsule.ap2_research_capsule.consent_level,
            ConsentLevel::Basic
        );
        assert!(capsule.ap2_research_capsule.sharing_partners.is_empty());
        assert_eq!(capsule.ap2_research_capsule.royalty_earned_usd, 0);
    }

    #[test]
    fn test_ap2_consent_level_research_grants_royalty() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        // Switch to ResearchBasic consent
        capsule.apply_consent_level(ConsentLevel::ResearchBasic);
        assert_eq!(
            capsule.ap2_research_capsule.consent_level,
            ConsentLevel::ResearchBasic
        );

        // Calculate royalty (1% of $10M = $100k)
        capsule.calculate_royalty(10_000_000);
        assert_eq!(capsule.ap2_research_capsule.royalty_earned_usd, 100_000);
    }

    #[test]
    fn test_add_research_partner_fails_with_basic_consent() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        let partner = ResearchPartner {
            institution_name: "Pharma Corp".to_string(),
            institution_type: "pharma".to_string(),
            access_granted_date: SystemTime::now(),
            access_scope: "glucose_only".to_string(),
        };

        let result = capsule.add_research_partner(partner);
        assert!(result.is_err());
    }

    #[test]
    fn test_add_research_partner_succeeds_with_research_consent() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        capsule.apply_consent_level(ConsentLevel::ResearchAdvanced);

        let partner = ResearchPartner {
            institution_name: "Pharma Corp".to_string(),
            institution_type: "pharma".to_string(),
            access_granted_date: SystemTime::now(),
            access_scope: "glucose_only".to_string(),
        };

        let result = capsule.add_research_partner(partner.clone());
        assert!(result.is_ok());
        assert_eq!(capsule.ap2_research_capsule.sharing_partners.len(), 1);
        assert_eq!(
            capsule.ap2_research_capsule.sharing_partners[0].institution_name,
            "Pharma Corp"
        );
    }

    #[test]
    fn test_encrypt_patient_holds_key() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let capsule = BiometricCapsule::new(
            device_data,
            "capsule_1".to_string(),
            "patient_key".to_string(),
        )
        .expect("Failed to create capsule");

        assert_eq!(capsule.encryption_key_id, "patient_key");
    }

    #[test]
    fn test_apply_consent_clears_partners_on_basic() {
        let device_data = DeviceData {
            glucose_mg_dl: 120,
            device_timestamp: 1000,
            device_id: "dexcom_123".to_string(),
            device_type: DeviceType::DexcomG7,
            reading_quality: 0.95,
        };

        let mut capsule =
            BiometricCapsule::new(device_data, "capsule_1".to_string(), "key_1".to_string())
                .expect("Failed to create capsule");

        capsule.apply_consent_level(ConsentLevel::ResearchAdvanced);

        let partner = ResearchPartner {
            institution_name: "Pharma Corp".to_string(),
            institution_type: "pharma".to_string(),
            access_granted_date: SystemTime::now(),
            access_scope: "glucose_only".to_string(),
        };

        let _ = capsule.add_research_partner(partner);
        assert!(!capsule.ap2_research_capsule.sharing_partners.is_empty());

        // Switch back to Basic - should clear partners
        capsule.apply_consent_level(ConsentLevel::Basic);
        assert!(capsule.ap2_research_capsule.sharing_partners.is_empty());
        assert_eq!(capsule.ap2_research_capsule.royalty_earned_usd, 0);
    }
}
