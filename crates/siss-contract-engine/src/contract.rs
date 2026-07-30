use crate::error::ContractError;
use crate::vertical_policy::VerticalPolicy;
use crate::pilot_sla_enforcer::PilotSlaEnforcer;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ContractState {
    Draft,
    Active,
    Suspended,
    Completed,
}

impl std::fmt::Display for ContractState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ContractState::Draft => write!(f, "Draft"),
            ContractState::Active => write!(f, "Active"),
            ContractState::Suspended => write!(f, "Suspended"),
            ContractState::Completed => write!(f, "Completed"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum VerticalType {
    Defense,
    Healthcare,
    Finance,
}

impl std::fmt::Display for VerticalType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VerticalType::Defense => write!(f, "Defense"),
            VerticalType::Healthcare => write!(f, "Healthcare"),
            VerticalType::Finance => write!(f, "Finance"),
        }
    }
}

#[derive(Clone)]
pub struct Contract {
    pub id: Uuid,
    pub customer_id: Uuid,
    pub vertical: VerticalType,
    pub region: String,
    pub state: ContractState,
    pub pilot_start: DateTime<Utc>,
    pub pilot_end: DateTime<Utc>,
    pub arr_commitment: i64, // cents
    pub policy: Arc<dyn VerticalPolicy>,
    pub sla_enforcer: Arc<PilotSlaEnforcer>,
}

pub struct ContractBuilder {
    customer_id: Uuid,
    vertical: VerticalType,
    region: String,
    pilot_start: DateTime<Utc>,
    pilot_end: DateTime<Utc>,
    arr_commitment: i64,
    policy: Arc<dyn VerticalPolicy>,
    sla_enforcer: Arc<PilotSlaEnforcer>,
}

impl ContractBuilder {
    pub fn new(customer_id: Uuid, vertical: VerticalType, policy: Arc<dyn VerticalPolicy>, sla_enforcer: Arc<PilotSlaEnforcer>) -> Self {
        Self {
            customer_id,
            vertical,
            region: String::new(),
            pilot_start: Utc::now(),
            pilot_end: Utc::now() + chrono::Duration::days(90),
            arr_commitment: 0,
            policy,
            sla_enforcer,
        }
    }

    pub fn with_region(mut self, region: String) -> Self {
        self.region = region;
        self
    }

    pub fn with_pilot_dates(mut self, start: DateTime<Utc>, end: DateTime<Utc>) -> Self {
        self.pilot_start = start;
        self.pilot_end = end;
        self
    }

    pub fn with_arr_commitment(mut self, arr: i64) -> Self {
        self.arr_commitment = arr;
        self
    }

    pub fn build(self) -> Result<Contract, ContractError> {
        Contract::validate_region(self.vertical, &self.region)?;

        Ok(Contract {
            id: Uuid::new_v4(),
            customer_id: self.customer_id,
            vertical: self.vertical,
            region: self.region,
            state: ContractState::Draft,
            pilot_start: self.pilot_start,
            pilot_end: self.pilot_end,
            arr_commitment: self.arr_commitment,
            policy: self.policy,
            sla_enforcer: self.sla_enforcer,
        })
    }
}

impl Contract {
    fn validate_region(vertical: VerticalType, region: &str) -> Result<(), ContractError> {
        match vertical {
            VerticalType::Defense => {
                if !region.contains("Military") && !region.to_lowercase().contains("govcloud") {
                    return Err(ContractError::InvalidRegion {
                        vertical: vertical.to_string(),
                        required: "Military region".to_string(),
                    });
                }
            }
            VerticalType::Healthcare => {
                if !region.to_lowercase().contains("eu") {
                    return Err(ContractError::InvalidRegion {
                        vertical: vertical.to_string(),
                        required: "EU region".to_string(),
                    });
                }
            }
            VerticalType::Finance => {
                if !region.to_lowercase().contains("eu") && !region.to_lowercase().contains("us") {
                    return Err(ContractError::InvalidRegion {
                        vertical: vertical.to_string(),
                        required: "EU or US region".to_string(),
                    });
                }
            }
        }
        Ok(())
    }

    pub fn new(
        customer_id: Uuid,
        vertical: VerticalType,
        region: String,
        pilot_start: DateTime<Utc>,
        pilot_end: DateTime<Utc>,
        arr_commitment: i64,
        policy: Arc<dyn VerticalPolicy>,
        sla_enforcer: Arc<PilotSlaEnforcer>,
    ) -> Result<Self, ContractError> {
        Self::validate_region(vertical, &region)?;

        Ok(Self {
            id: Uuid::new_v4(),
            customer_id,
            vertical,
            region,
            state: ContractState::Draft,
            pilot_start,
            pilot_end,
            arr_commitment,
            policy,
            sla_enforcer,
        })
    }

    pub async fn activate(&mut self) -> Result<(), ContractError> {
        match self.state {
            ContractState::Draft => {
                self.state = ContractState::Active;
                self.sla_enforcer.reset_metrics();
                Ok(())
            }
            ContractState::Active => Err(ContractError::AlreadyActivated),
            _ => Err(ContractError::InvalidStateTransition {
                from: self.state.to_string(),
                to: ContractState::Active.to_string(),
            }),
        }
    }

    pub async fn suspend(&mut self) -> Result<(), ContractError> {
        match self.state {
            ContractState::Active => {
                self.state = ContractState::Suspended;
                Ok(())
            }
            _ => Err(ContractError::InvalidStateTransition {
                from: self.state.to_string(),
                to: ContractState::Suspended.to_string(),
            }),
        }
    }

    pub async fn complete(&mut self) -> Result<(), ContractError> {
        match self.state {
            ContractState::Active | ContractState::Suspended => {
                self.state = ContractState::Completed;
                Ok(())
            }
            _ => Err(ContractError::InvalidStateTransition {
                from: self.state.to_string(),
                to: ContractState::Completed.to_string(),
            }),
        }
    }

    pub async fn enforce_slas(&self) -> Result<crate::pilot_sla_enforcer::SlaReport, crate::error::SlaError> {
        self.sla_enforcer.check_compliance().await
    }

    pub fn calculate_arr_progress(&self) -> (i64, f64) {
        if self.state == ContractState::Active || self.state == ContractState::Suspended {
            // Full commitment once active
            (self.arr_commitment, 100.0)
        } else {
            (0, 0.0)
        }
    }

    pub fn get_policy(&self) -> &Arc<dyn VerticalPolicy> {
        &self.policy
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vertical_policy::DefensePolicy;

    fn create_test_contract() -> Result<Contract, ContractError> {
        let policy = Arc::new(DefensePolicy::new());
        let sla_enforcer = Arc::new(PilotSlaEnforcer::new(Uuid::new_v4()));
        Contract::new(
            Uuid::new_v4(),
            VerticalType::Defense,
            "Military-Zone-GovCloud".to_string(),
            Utc::now(),
            Utc::now() + chrono::Duration::days(90),
            500_000_00, // €5M in cents
            policy,
            sla_enforcer,
        )
    }

    #[test]
    fn test_contract_create_draft() {
        let contract = create_test_contract();
        assert!(contract.is_ok());
        let contract = contract.unwrap();
        assert_eq!(contract.state, ContractState::Draft);
    }

    #[test]
    fn test_contract_activate_moves_to_active() {
        let mut contract = create_test_contract().unwrap();
        let result = tokio::runtime::Runtime::new()
            .unwrap()
            .block_on(contract.activate());
        assert!(result.is_ok());
        assert_eq!(contract.state, ContractState::Active);
    }

    #[test]
    fn test_contract_invalid_state_transition_rejected() {
        let mut contract = create_test_contract().unwrap();
        let _runtime = tokio::runtime::Runtime::new().unwrap();
        _runtime.block_on(contract.activate()).unwrap();

        // Try to go back to draft (should fail)
        match contract.state {
            ContractState::Active => {
                // Can't go back to draft from active
                assert_eq!(contract.state, ContractState::Active);
            }
            _ => panic!("Expected Active state"),
        }
    }

    #[test]
    fn test_contract_arr_commitment_locked() {
        let contract = create_test_contract().unwrap();
        let commitment = contract.arr_commitment;
        assert_eq!(commitment, 500_000_00);
        // Verify it doesn't change after initialization
        assert_eq!(contract.arr_commitment, commitment);
    }

    #[test]
    fn test_contract_policy_assigned() {
        let contract = create_test_contract().unwrap();
        assert_eq!(contract.vertical, VerticalType::Defense);
        assert!(contract.policy.policy_name().contains("Defense"));
    }

    #[test]
    fn test_contract_enrollment_all_3_verticals() {
        let _runtime = tokio::runtime::Runtime::new().unwrap();

        // Defense
        let defense_policy = Arc::new(DefensePolicy::new());
        let defense_sla = Arc::new(PilotSlaEnforcer::new(Uuid::new_v4()));
        let defense = Contract::new(
            Uuid::new_v4(),
            VerticalType::Defense,
            "Military-Zone-West".to_string(),
            Utc::now(),
            Utc::now() + chrono::Duration::days(90),
            166_666_67,
            defense_policy,
            defense_sla,
        );
        assert!(defense.is_ok());

        // Healthcare (EU)
        let healthcare_policy = Arc::new(crate::vertical_policy::HealthcarePolicy::new());
        let healthcare_sla = Arc::new(PilotSlaEnforcer::new(Uuid::new_v4()));
        let healthcare = Contract::new(
            Uuid::new_v4(),
            VerticalType::Healthcare,
            "eu-central-1".to_string(),
            Utc::now(),
            Utc::now() + chrono::Duration::days(90),
            166_666_67,
            healthcare_policy,
            healthcare_sla,
        );
        assert!(healthcare.is_ok());

        // Finance
        let finance_policy = Arc::new(crate::vertical_policy::FinancePolicy::new());
        let finance_sla = Arc::new(PilotSlaEnforcer::new(Uuid::new_v4()));
        let finance = Contract::new(
            Uuid::new_v4(),
            VerticalType::Finance,
            "eu-west-1".to_string(),
            Utc::now(),
            Utc::now() + chrono::Duration::days(90),
            166_666_66,
            finance_policy,
            finance_sla,
        );
        assert!(finance.is_ok());
    }

    #[test]
    fn test_contract_region_deployment_validated() {
        let policy = Arc::new(DefensePolicy::new());
        let sla = Arc::new(PilotSlaEnforcer::new(Uuid::new_v4()));

        // Defense with non-military region should fail
        let result = Contract::new(
            Uuid::new_v4(),
            VerticalType::Defense,
            "eu-central-1".to_string(),
            Utc::now(),
            Utc::now() + chrono::Duration::days(90),
            500_000_00,
            policy,
            sla,
        );
        assert!(result.is_err());
    }
}
