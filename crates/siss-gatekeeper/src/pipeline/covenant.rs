use uuid::Uuid;
use sqlx::PgPool;
use crate::types::GatekeeperError;
use siss_behavioral_firewall::covenant_firewall::{CovenantFirewall, EconomicIntent};

pub struct CapsuleCovenant {
    pub merkle_root: [u8; 32],
    pub steward_pct: u8,
    pub beneficiary_pct: u8,
    pub covenant_signature: Vec<u8>,
    pub verifying_key: Vec<u8>,
}

pub fn enforce(c: &CapsuleCovenant) -> Result<(), GatekeeperError> {
    let intent = EconomicIntent {
        steward_pct: c.steward_pct,
        beneficiary_pct: c.beneficiary_pct,
    };
    CovenantFirewall::verify(&c.merkle_root, &intent, &c.covenant_signature, &c.verifying_key)
        .map_err(|e| GatekeeperError::CovenantViolation {
            merkle_root: hex::encode(c.merkle_root),
            violation: e.to_string(),
        })
}

/// Pipeline step: Check covenant signature against declared economic intent.
/// Fail-closed: hard failure if covenant is violated or missing.
///
/// For now, this is a placeholder that returns Ok(()) until the full
/// covenant data is available in the task/capsule schema.
pub async fn check_covenant(
    _pool: &PgPool,
    _intent_mandate_id: Uuid,
) -> Result<(), GatekeeperError> {
    // TODO: Query covenant data from task/capsule schema
    // TODO: Call enforce() with retrieved covenant data
    // For June 2 filing, covenant infrastructure is in place;
    // database integration follows post-Series A
    Ok(())
}
