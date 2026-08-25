use crate::asil::{AssilLevel, AssilValidator};
use crate::errors::{SafetyError, SafetyResult};
use crate::hazard::HazardLevel;
use crate::sotif::SotifValidator;
use dashmap::DashMap;
use siss_swarm_consensus::{Agent, ConsensusProof, Proposal, Vote, VoteType, BftEngine};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

/// Safety decision that requires Byzantine consensus
#[derive(Clone, Debug)]
pub struct SafetyDecision {
    pub id: Uuid,
    pub decision_type: SafetyDecisionType,
    pub hazard_level: HazardLevel,
    pub asil_requirement: AssilLevel,
    pub timestamp: SystemTime,
}

/// Types of safety-critical decisions
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SafetyDecisionType {
    /// Emergency stop required
    EmergencyStop,
    /// Graceful degradation needed
    GracefulDegradation,
    /// Route deviation required
    RouteDeviation,
    /// Manual intervention required
    ManualIntervention,
}

impl SafetyDecision {
    pub fn new(
        decision_type: SafetyDecisionType,
        hazard_level: HazardLevel,
        asil_requirement: AssilLevel,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            decision_type,
            hazard_level,
            asil_requirement,
            timestamp: SystemTime::now(),
        }
    }

    /// Encode decision as proposal content for consensus
    pub fn encode(&self) -> Vec<u8> {
        let type_byte = match self.decision_type {
            SafetyDecisionType::EmergencyStop => 0u8,
            SafetyDecisionType::GracefulDegradation => 1u8,
            SafetyDecisionType::RouteDeviation => 2u8,
            SafetyDecisionType::ManualIntervention => 3u8,
        };

        let hazard_byte = self.hazard_level.as_numeric();
        let asil_byte = match self.asil_requirement {
            AssilLevel::A => 1u8,
            AssilLevel::B => 2u8,
            AssilLevel::C => 3u8,
            AssilLevel::D => 4u8,
        };

        let mut encoded = Vec::new();
        encoded.push(type_byte);
        encoded.push(hazard_byte);
        encoded.push(asil_byte);
        encoded.extend_from_slice(self.id.as_bytes());

        let timestamp = self
            .timestamp
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        encoded.extend_from_slice(&timestamp.to_le_bytes());

        encoded
    }
}

/// Safety consensus validator that integrates ASIL + Byzantine consensus
pub struct SafetyConsensusValidator {
    bft_engine: Arc<BftEngine>,
    asil_validator: Arc<AssilValidator>,
    sotif_validator: Arc<SotifValidator>,
    decisions: Arc<DashMap<Uuid, (SafetyDecision, ConsensusProof)>>,
}

impl SafetyConsensusValidator {
    /// Create new safety consensus validator
    pub fn new(
        bft_engine: Arc<BftEngine>,
        asil_level: AssilLevel,
    ) -> SafetyResult<Self> {
        let asil_validator = Arc::new(AssilValidator::new(asil_level));
        let sotif_validator = Arc::new(SotifValidator::new(asil_level));

        Ok(Self {
            bft_engine,
            asil_validator,
            sotif_validator,
            decisions: Arc::new(DashMap::new()),
        })
    }

    /// Validate a safety decision and reach consensus
    pub async fn validate_and_decide(
        &self,
        decision: SafetyDecision,
        proposer_id: Uuid,
    ) -> SafetyResult<ConsensusProof> {
        // Step 1: Validate against ASIL level
        let max_hazard = self.asil_validator.level().max_hazard_severity();
        if decision.hazard_level > max_hazard {
            return Err(SafetyError::AssilViolation(format!(
                "Decision hazard {:?} exceeds ASIL limit {:?}",
                decision.hazard_level, max_hazard
            )));
        }

        // Step 2: Validate against SOTIF
        self.sotif_validator
            .validate_malfunction_severity(decision.hazard_level)?;

        // Step 3: Encode decision as proposal
        let proposal = Proposal::new(decision.encode(), proposer_id);

        // Step 4: Reach Byzantine consensus
        let consensus_proof = self
            .bft_engine
            .reach_consensus(proposal)
            .await
            .map_err(|e| SafetyError::InvalidConsensusProof(e.to_string()))?;

        // Step 5: Verify merkle root integrity
        if !consensus_proof.verify_merkle_root() {
            return Err(SafetyError::InvalidConsensusProof(
                "Merkle root verification failed".to_string(),
            ));
        }

        // Step 6: Store decision with proof
        self.decisions
            .insert(consensus_proof.proposal_id, (decision, consensus_proof.clone()));

        Ok(consensus_proof)
    }

    /// Get stored safety decision with consensus proof
    pub fn get_decision(&self, decision_id: Uuid) -> Option<(SafetyDecision, ConsensusProof)> {
        self.decisions
            .get(&decision_id)
            .map(|entry| entry.clone())
    }

    /// Verify that a decision was reached through proper consensus
    pub fn verify_decision_consensus(&self, decision_id: Uuid) -> SafetyResult<bool> {
        let entry = self
            .decisions
            .get(&decision_id)
            .ok_or(SafetyError::InvalidConsensusProof(
                "Decision not found".to_string(),
            ))?;

        let (_, proof) = entry.value();
        Ok(proof.verify_merkle_root())
    }

    /// Get count of quorum members required for fault tolerance
    pub fn required_quorum(&self) -> usize {
        self.bft_engine.agent_count() - (self.bft_engine.agent_count() / 3)
    }

    /// Check if system has sufficient agents for fault tolerance
    pub fn has_sufficient_fault_tolerance(&self) -> bool {
        // BFT requires at least 3f+1 agents, where f is max faulty agents
        let agent_count = self.bft_engine.agent_count();
        agent_count >= 4 // Minimum: 3*1+1 = 4 agents for f=1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_safety_decision_creation() {
        let decision = SafetyDecision::new(
            SafetyDecisionType::EmergencyStop,
            HazardLevel::Critical,
            AssilLevel::D,
        );

        assert_eq!(decision.decision_type, SafetyDecisionType::EmergencyStop);
        assert_eq!(decision.hazard_level, HazardLevel::Critical);
        assert_eq!(decision.asil_requirement, AssilLevel::D);
    }

    #[test]
    fn test_safety_decision_encode() {
        let decision = SafetyDecision::new(
            SafetyDecisionType::EmergencyStop,
            HazardLevel::Critical,
            AssilLevel::D,
        );

        let encoded = decision.encode();
        assert!(encoded.len() > 0);
        assert_eq!(encoded[0], 0u8); // EmergencyStop = 0
        assert_eq!(encoded[1], 3u8); // Critical = 3
        assert_eq!(encoded[2], 4u8); // ASIL-D = 4
    }

    #[test]
    fn test_safety_decision_encode_all_types() {
        let types = vec![
            (SafetyDecisionType::EmergencyStop, 0u8),
            (SafetyDecisionType::GracefulDegradation, 1u8),
            (SafetyDecisionType::RouteDeviation, 2u8),
            (SafetyDecisionType::ManualIntervention, 3u8),
        ];

        for (decision_type, expected_byte) in types {
            let decision = SafetyDecision::new(decision_type, HazardLevel::Major, AssilLevel::B);
            let encoded = decision.encode();
            assert_eq!(encoded[0], expected_byte);
        }
    }

    #[test]
    fn test_safety_decision_encode_asil_levels() {
        let levels = vec![
            (AssilLevel::A, 1u8),
            (AssilLevel::B, 2u8),
            (AssilLevel::C, 3u8),
            (AssilLevel::D, 4u8),
        ];

        for (asil_level, expected_byte) in levels {
            let decision =
                SafetyDecision::new(SafetyDecisionType::EmergencyStop, HazardLevel::Major, asil_level);
            let encoded = decision.encode();
            assert_eq!(encoded[2], expected_byte);
        }
    }

    #[tokio::test]
    async fn test_safety_consensus_validator_creation() {
        let bft = Arc::new(BftEngine::new(7, 0.67).expect("BFT creation failed"));
        for i in 0..7 {
            let _ = bft.register_agent(Uuid::new_v4(), [i as u8; 32]);
        }

        let validator = SafetyConsensusValidator::new(bft, AssilLevel::D)
            .expect("Validator creation failed");

        assert!(validator.has_sufficient_fault_tolerance());
    }

    #[test]
    fn test_safety_consensus_required_quorum_calculation() {
        let bft = Arc::new(BftEngine::new(7, 0.67).expect("BFT creation failed"));
        for i in 0..7 {
            let _ = bft.register_agent(Uuid::new_v4(), [i as u8; 32]);
        }
        let validator = SafetyConsensusValidator::new(bft, AssilLevel::D)
            .expect("Validator creation failed");

        let quorum = validator.required_quorum();
        assert_eq!(quorum, 5); // 7 - (7/3) = 7 - 2 = 5
    }

    #[test]
    fn test_safety_consensus_insufficient_agents() {
        let result = BftEngine::new(2, 0.67);
        // May fail due to insufficient agents for BFT
        if let Ok(bft) = result {
            let validator =
                SafetyConsensusValidator::new(Arc::new(bft), AssilLevel::D).expect("Validator");
            // With only 2 agents, fault tolerance is limited
            let has_ft = validator.has_sufficient_fault_tolerance();
            assert!(!has_ft); // Needs at least 4
        }
    }

    #[test]
    fn test_safety_decision_hazard_to_asil_mapping() {
        let critical = SafetyDecision::new(
            SafetyDecisionType::EmergencyStop,
            HazardLevel::Critical,
            AssilLevel::D,
        );
        assert_eq!(critical.asil_requirement, AssilLevel::D);

        let major = SafetyDecision::new(
            SafetyDecisionType::GracefulDegradation,
            HazardLevel::Major,
            AssilLevel::C,
        );
        assert_eq!(major.asil_requirement, AssilLevel::C);
    }

    #[test]
    fn test_safety_decision_timestamp_set() {
        let before = SystemTime::now();
        let decision = SafetyDecision::new(
            SafetyDecisionType::ManualIntervention,
            HazardLevel::Major,
            AssilLevel::B,
        );
        let after = SystemTime::now();

        assert!(decision.timestamp >= before);
        assert!(decision.timestamp <= after);
    }

    #[tokio::test]
    async fn test_safety_consensus_store_and_retrieve() {
        let bft = Arc::new(BftEngine::new(7, 0.67).expect("BFT creation failed"));
        let validator = SafetyConsensusValidator::new(bft, AssilLevel::D)
            .expect("Validator creation failed");

        let decision = SafetyDecision::new(
            SafetyDecisionType::EmergencyStop,
            HazardLevel::Major,
            AssilLevel::D,
        );

        let decision_id = decision.id;

        // Store decision (without consensus proof for this test)
        // This tests the storage mechanism
        validator
            .decisions
            .insert(decision_id, (decision.clone(), ConsensusProof::new(decision_id, vec![])));

        let retrieved = validator.get_decision(decision_id);
        assert!(retrieved.is_some());
        let (retrieved_decision, _) = retrieved.unwrap();
        assert_eq!(retrieved_decision.id, decision_id);
    }

    #[test]
    fn test_safety_decision_type_all_variants() {
        let types = vec![
            SafetyDecisionType::EmergencyStop,
            SafetyDecisionType::GracefulDegradation,
            SafetyDecisionType::RouteDeviation,
            SafetyDecisionType::ManualIntervention,
        ];

        for decision_type in types {
            let decision = SafetyDecision::new(decision_type.clone(), HazardLevel::Major, AssilLevel::C);
            assert_eq!(decision.decision_type, decision_type);
        }
    }

    #[test]
    fn test_safety_consensus_merkle_verification() {
        let bft = Arc::new(BftEngine::new(7, 0.67).expect("BFT creation failed"));
        let validator = SafetyConsensusValidator::new(bft, AssilLevel::D)
            .expect("Validator creation failed");

        let decision = SafetyDecision::new(
            SafetyDecisionType::EmergencyStop,
            HazardLevel::Major,
            AssilLevel::D,
        );

        let decision_id = decision.id;
        let proof = ConsensusProof::new(decision_id, vec![]);

        validator
            .decisions
            .insert(decision_id, (decision.clone(), proof));

        let is_valid = validator.verify_decision_consensus(decision_id);
        assert!(is_valid.is_ok());
        assert!(is_valid.unwrap());
    }

    #[test]
    fn test_safety_consensus_verify_nonexistent_decision() {
        let bft = Arc::new(BftEngine::new(7, 0.67).expect("BFT creation failed"));
        let validator = SafetyConsensusValidator::new(bft, AssilLevel::D)
            .expect("Validator creation failed");

        let nonexistent_id = Uuid::new_v4();
        let result = validator.verify_decision_consensus(nonexistent_id);
        assert!(result.is_err());
    }
}
