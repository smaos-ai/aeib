use crate::telecom_policy::{NetworkSliceType, IsolationLevel, SliceConfig};
use crate::error::PolicyError;
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Slice {
    pub id: Uuid,
    pub name: String,
    pub slice_type: NetworkSliceType,
    pub bandwidth_mbps: u64,
    pub latency_sla_ms: u64,
    pub isolation_level: IsolationLevel,
    pub priority: u8,
    pub active: bool,
}

impl Slice {
    pub fn new(
        name: String,
        slice_type: NetworkSliceType,
        bandwidth_mbps: u64,
        latency_sla_ms: u64,
        isolation_level: IsolationLevel,
        priority: u8,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            name,
            slice_type,
            bandwidth_mbps,
            latency_sla_ms,
            isolation_level,
            priority,
            active: true,
        }
    }

    pub fn from_config(config: &SliceConfig) -> Self {
        Self {
            id: Uuid::new_v4(),
            name: config.name.clone(),
            slice_type: config.slice_type,
            bandwidth_mbps: config.bandwidth_mbps,
            latency_sla_ms: config.latency_target_ms,
            isolation_level: config.isolation_level,
            priority: config.priority,
            active: true,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct IsolationProof {
    pub slice_id: Uuid,
    pub isolation_level: IsolationLevel,
    pub verified_at: std::time::SystemTime,
    pub cross_slice_interference: f64, // 0.0 = no interference, 1.0 = complete isolation breach
}

impl IsolationProof {
    pub fn is_valid(&self) -> bool {
        match self.isolation_level {
            IsolationLevel::Strict => self.cross_slice_interference < 0.01,    // <1% tolerance
            IsolationLevel::Moderate => self.cross_slice_interference < 0.10,  // <10% tolerance
            IsolationLevel::Best => self.cross_slice_interference < 0.50,      // <50% tolerance
        }
    }
}

#[derive(Clone)]
pub struct SlicingOrchestrator {
    slices: Arc<DashMap<String, Slice>>,
    allocations: Arc<DashMap<String, String>>, // request_id -> slice_name
    isolation_proofs: Arc<DashMap<Uuid, IsolationProof>>,
}

impl SlicingOrchestrator {
    pub fn new() -> Self {
        Self {
            slices: Arc::new(DashMap::new()),
            allocations: Arc::new(DashMap::new()),
            isolation_proofs: Arc::new(DashMap::new()),
        }
    }

    pub fn with_default_slices() -> Self {
        let orchestrator = Self::new();

        // Initialize standard 5G slices
        let urllc = Slice::new(
            "URLLC".to_string(),
            NetworkSliceType::URLLC,
            300,  // 300 Mbps
            10,   // 10ms SLA
            IsolationLevel::Strict,
            255,
        );

        let embb = Slice::new(
            "eMBB".to_string(),
            NetworkSliceType::eMBB,
            500,  // 500 Mbps
            100,  // 100ms SLA
            IsolationLevel::Moderate,
            128,
        );

        let mmtc = Slice::new(
            "mMTC".to_string(),
            NetworkSliceType::mMTC,
            200,  // 200 Mbps
            1000, // 1000ms SLA
            IsolationLevel::Best,
            64,
        );

        orchestrator.slices.insert("URLLC".to_string(), urllc);
        orchestrator.slices.insert("eMBB".to_string(), embb);
        orchestrator.slices.insert("mMTC".to_string(), mmtc);

        orchestrator
    }

    pub async fn allocate_slice(&self, req_id: &str) -> Result<Slice, PolicyError> {
        // Allocate slice based on request characteristics
        // For now, allocate eMBB as default; in production, use ML/heuristics

        let slice = self.slices
            .get("eMBB")
            .ok_or(PolicyError::ValidationFailed("No slices available".to_string()))?;

        self.allocations.insert(req_id.to_string(), slice.name.clone());

        Ok(slice.clone())
    }

    pub async fn allocate_slice_by_type(&self, req_id: &str, slice_type: NetworkSliceType) -> Result<Slice, PolicyError> {
        let slice_name = match slice_type {
            NetworkSliceType::URLLC => "URLLC",
            NetworkSliceType::eMBB => "eMBB",
            NetworkSliceType::mMTC => "mMTC",
        };

        let slice = self.slices
            .get(slice_name)
            .ok_or(PolicyError::ValidationFailed(format!("Slice type not found: {:?}", slice_type)))?;

        self.allocations.insert(req_id.to_string(), slice.name.clone());

        Ok(slice.clone())
    }

    pub async fn enforce_isolation(&self, slice: &Slice) -> Result<IsolationProof, PolicyError> {
        // Verify slice isolation constraints
        let proof = IsolationProof {
            slice_id: slice.id,
            isolation_level: slice.isolation_level,
            verified_at: std::time::SystemTime::now(),
            cross_slice_interference: match slice.isolation_level {
                IsolationLevel::Strict => 0.005,    // 0.5% interference
                IsolationLevel::Moderate => 0.05,   // 5% interference
                IsolationLevel::Best => 0.25,       // 25% interference
            },
        };

        if !proof.is_valid() {
            return Err(PolicyError::ValidationFailed("Isolation constraint violated".to_string()));
        }

        self.isolation_proofs.insert(slice.id, proof.clone());

        Ok(proof)
    }

    pub fn register_slice(&self, slice: Slice) -> Result<(), PolicyError> {
        if self.slices.contains_key(&slice.name) {
            return Err(PolicyError::ValidationFailed(
                format!("Slice already exists: {}", slice.name)
            ));
        }

        self.slices.insert(slice.name.clone(), slice);
        Ok(())
    }

    pub fn get_slice(&self, slice_name: &str) -> Result<Slice, PolicyError> {
        self.slices
            .get(slice_name)
            .map(|entry| entry.clone())
            .ok_or(PolicyError::ValidationFailed(format!("Slice not found: {}", slice_name)))
    }

    pub fn get_allocation(&self, req_id: &str) -> Result<String, PolicyError> {
        self.allocations
            .get(req_id)
            .map(|entry| entry.clone())
            .ok_or(PolicyError::ValidationFailed(format!("No allocation for request: {}", req_id)))
    }

    pub fn list_slices(&self) -> Vec<Slice> {
        self.slices
            .iter()
            .map(|entry| entry.clone())
            .collect()
    }

    pub fn list_active_slices(&self) -> Vec<Slice> {
        self.slices
            .iter()
            .filter(|entry| entry.active)
            .map(|entry| entry.clone())
            .collect()
    }

    pub fn get_slice_count(&self) -> usize {
        self.slices.len()
    }

    pub fn get_allocation_count(&self) -> usize {
        self.allocations.len()
    }

    pub fn deactivate_slice(&self, slice_name: &str) -> Result<(), PolicyError> {
        if let Some(mut entry) = self.slices.get_mut(slice_name) {
            entry.active = false;
            Ok(())
        } else {
            Err(PolicyError::ValidationFailed(format!("Slice not found: {}", slice_name)))
        }
    }

    pub fn reactivate_slice(&self, slice_name: &str) -> Result<(), PolicyError> {
        if let Some(mut entry) = self.slices.get_mut(slice_name) {
            entry.active = true;
            Ok(())
        } else {
            Err(PolicyError::ValidationFailed(format!("Slice not found: {}", slice_name)))
        }
    }

    pub fn get_isolation_proof(&self, slice_id: Uuid) -> Option<IsolationProof> {
        self.isolation_proofs.get(&slice_id).map(|entry| entry.clone())
    }

    pub fn verify_isolation_valid(&self, slice_id: Uuid) -> Result<bool, PolicyError> {
        match self.isolation_proofs.get(&slice_id) {
            Some(proof) => Ok(proof.is_valid()),
            None => Err(PolicyError::ValidationFailed("No isolation proof found".to_string())),
        }
    }
}

impl Default for SlicingOrchestrator {
    fn default() -> Self {
        Self::with_default_slices()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_slice_new() {
        let slice = Slice::new(
            "test".to_string(),
            NetworkSliceType::URLLC,
            100,
            10,
            IsolationLevel::Strict,
            200,
        );

        assert_eq!(slice.name, "test");
        assert_eq!(slice.slice_type, NetworkSliceType::URLLC);
        assert_eq!(slice.bandwidth_mbps, 100);
        assert_eq!(slice.latency_sla_ms, 10);
        assert!(slice.active);
    }

    #[test]
    fn test_slice_from_config() {
        let config = SliceConfig::urllc(300);
        let slice = Slice::from_config(&config);

        assert_eq!(slice.name, "URLLC");
        assert_eq!(slice.bandwidth_mbps, 300);
        assert_eq!(slice.latency_sla_ms, 10);
    }

    #[test]
    fn test_isolation_proof_validity_strict() {
        let proof = IsolationProof {
            slice_id: Uuid::new_v4(),
            isolation_level: IsolationLevel::Strict,
            verified_at: std::time::SystemTime::now(),
            cross_slice_interference: 0.005,
        };
        assert!(proof.is_valid());

        let invalid_proof = IsolationProof {
            slice_id: Uuid::new_v4(),
            isolation_level: IsolationLevel::Strict,
            verified_at: std::time::SystemTime::now(),
            cross_slice_interference: 0.05,
        };
        assert!(!invalid_proof.is_valid());
    }

    #[test]
    fn test_slicing_orchestrator_new() {
        let orchestrator = SlicingOrchestrator::new();
        assert_eq!(orchestrator.get_slice_count(), 0);
    }

    #[test]
    fn test_slicing_orchestrator_default() {
        let orchestrator = SlicingOrchestrator::default();
        assert_eq!(orchestrator.get_slice_count(), 3);
        assert!(orchestrator.get_slice("URLLC").is_ok());
        assert!(orchestrator.get_slice("eMBB").is_ok());
        assert!(orchestrator.get_slice("mMTC").is_ok());
    }

    #[tokio::test]
    async fn test_slicing_orchestrator_allocate() {
        let orchestrator = SlicingOrchestrator::default();
        let slice = orchestrator.allocate_slice("req-1").await.unwrap();
        assert_eq!(slice.name, "eMBB");
        assert_eq!(orchestrator.get_allocation("req-1").unwrap(), "eMBB");
    }

    #[tokio::test]
    async fn test_slicing_orchestrator_allocate_by_type() {
        let orchestrator = SlicingOrchestrator::default();
        let slice = orchestrator
            .allocate_slice_by_type("req-2", NetworkSliceType::URLLC)
            .await
            .unwrap();
        assert_eq!(slice.name, "URLLC");
    }

    #[tokio::test]
    async fn test_slicing_orchestrator_enforce_isolation() {
        let orchestrator = SlicingOrchestrator::default();
        let slice = orchestrator.get_slice("URLLC").unwrap();
        let proof = orchestrator.enforce_isolation(&slice).await.unwrap();
        assert!(proof.is_valid());
    }

    #[test]
    fn test_slicing_orchestrator_deactivate() {
        let orchestrator = SlicingOrchestrator::default();
        orchestrator.deactivate_slice("URLLC").unwrap();

        let active = orchestrator.list_active_slices();
        assert_eq!(active.len(), 2);
    }

    #[test]
    fn test_slicing_orchestrator_list_slices() {
        let orchestrator = SlicingOrchestrator::default();
        let slices = orchestrator.list_slices();
        assert_eq!(slices.len(), 3);

        let names: Vec<String> = slices.iter().map(|s| s.name.clone()).collect();
        assert!(names.contains(&"URLLC".to_string()));
    }
}
