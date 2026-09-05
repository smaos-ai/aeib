use sqlx::PgPool;
use uuid::Uuid;

use crate::repo::capability_negotiation::CapabilityRequest;
use crate::repo::transitive_delegation_repo::DelegationChain;

#[derive(Debug, Clone)]
pub enum CeilingError {
    Escalation,
    InvalidCeiling,
    DatabaseError(String),
}

pub async fn validate_ceiling_compliance(
    _pool: &PgPool,
    request: &CapabilityRequest,
    delegation_chain: &DelegationChain,
) -> Result<bool, CeilingError> {
    let effective_ceiling = compute_effective_ceiling_internal(&delegation_chain.ceiling_tiers);

    // Check if request ceiling is lower than effective ceiling
    if !is_lower_tier(&request.ceiling_tier_limit, &effective_ceiling) {
        return Err(CeilingError::Escalation);
    }

    Ok(true)
}

pub async fn compute_effective_ceiling(
    _pool: &PgPool,
    delegation_chain: &DelegationChain,
) -> Result<String, CeilingError> {
    Ok(compute_effective_ceiling_internal(
        &delegation_chain.ceiling_tiers,
    ))
}

pub async fn enforce_ceiling_on_grant(
    _pool: &PgPool,
    _request_id: Uuid,
    grant_ceiling: &str,
    chain_effective_ceiling: &str,
) -> Result<(), CeilingError> {
    // Grant ceiling must be lower (higher tier number) than chain ceiling
    // e.g., if chain ceiling is TIER_2, grant can be TIER_3 or TIER_4
    if !is_lower_tier(grant_ceiling, chain_effective_ceiling) {
        return Err(CeilingError::Escalation);
    }

    Ok(())
}

fn compute_effective_ceiling_internal(ceilings: &[String]) -> String {
    if ceilings.is_empty() {
        return "TIER_4".to_string();
    }

    let tier_order = |tier: &str| -> i32 {
        match tier {
            "TIER_1" => 1,
            "TIER_2" => 2,
            "TIER_3" => 3,
            "TIER_4" => 4,
            _ => 4,
        }
    };

    let mut lowest = ceilings[0].clone();
    for ceiling in ceilings.iter().skip(1) {
        if tier_order(ceiling) < tier_order(&lowest) {
            lowest = ceiling.clone();
        }
    }

    lowest
}

// Helper: returns true if grant_tier is lower (more permissive) than ceiling_tier
// TIER_1 is highest (most restrictive), TIER_4 is lowest (most permissive)
fn is_lower_tier(grant_tier: &str, ceiling_tier: &str) -> bool {
    let tier_order = |tier: &str| -> i32 {
        match tier {
            "TIER_1" => 1,
            "TIER_2" => 2,
            "TIER_3" => 3,
            "TIER_4" => 4,
            _ => 4,
        }
    };

    tier_order(grant_tier) > tier_order(ceiling_tier)
}
