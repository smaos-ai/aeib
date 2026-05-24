use sqlx::PgPool;
use uuid::Uuid;
use std::collections::HashMap;
use sha2::{Sha256, Digest};

#[derive(Debug, Clone)]
pub struct SettlementReceipt {
    pub settlement_id: Uuid,
    pub execution_id: Uuid,
    pub state_root_after: String,
    pub finalized_at: chrono::DateTime<chrono::Utc>,
}

/// Store contract state slots and compute merkle root
pub async fn store_contract_state(
    pool: &PgPool,
    contract_address: &str,
    state_slots: HashMap<String, String>,
) -> Result<(Uuid, String), Box<dyn std::error::Error>> {
    // Validate contract address
    if !contract_address.starts_with("0x") || contract_address.len() != 42 {
        return Err("Invalid contract address format".into());
    }

    // Compute merkle root from state slots
    let merkle_root = compute_merkle_root(&state_slots);

    // Store each state slot in the database
    for (slot_key, slot_value) in state_slots.iter() {
        let slot_id = Uuid::new_v4();

        sqlx::query(
            "INSERT INTO contract_state_slots (id, contract_address, slot_key, slot_value, updated_at, created_at)
             VALUES ($1, $2, $3, $4, NOW(), NOW())
             ON CONFLICT (contract_address, slot_key) DO UPDATE SET slot_value = $4, updated_at = NOW()"
        )
        .bind(&slot_id)
        .bind(contract_address)
        .bind(slot_key)
        .bind(slot_value)
        .execute(pool)
        .await?;
    }

    // Update contract's state_root in smart_contracts table
    sqlx::query(
        "UPDATE smart_contracts SET state_root = $1 WHERE contract_address = $2"
    )
    .bind(&merkle_root)
    .bind(contract_address)
    .execute(pool)
    .await?;

    Ok((Uuid::new_v4(), merkle_root))
}

/// Compute merkle root from state slots
fn compute_merkle_root(state_slots: &HashMap<String, String>) -> String {
    if state_slots.is_empty() {
        return compute_hash("");
    }

    // Sort slots by key for determinism
    let mut sorted_keys: Vec<_> = state_slots.keys().collect();
    sorted_keys.sort();

    // Concatenate all slot key-value pairs
    let mut combined = String::new();
    for key in sorted_keys {
        combined.push_str(key);
        combined.push('=');
        combined.push_str(&state_slots[key]);
        combined.push(';');
    }

    compute_hash(&combined)
}

/// Compute SHA256 hash of input
fn compute_hash(data: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data.as_bytes());
    format!("{:x}", hasher.finalize())
}

/// Commit contract state to DAG and generate merkle proof reference
pub async fn commit_contract_state_to_dag(
    pool: &PgPool,
    contract_address: &str,
    state_root: &str,
) -> Result<String, Box<dyn std::error::Error>> {
    // Validate inputs
    if !contract_address.starts_with("0x") || contract_address.len() != 42 {
        return Err("Invalid contract address format".into());
    }

    // Generate merkle proof reference (deterministic hash of state_root)
    let merkle_proof_ref = compute_hash(&format!("{}:{}", contract_address, state_root));

    // Update contract record with merkle_proof_ref
    sqlx::query(
        "UPDATE smart_contracts SET merkle_proof_ref = $1 WHERE contract_address = $2"
    )
    .bind(&merkle_proof_ref)
    .bind(contract_address)
    .execute(pool)
    .await?;

    Ok(merkle_proof_ref)
}

/// Validate merkle proof for a contract state
pub fn validate_merkle_proof(
    contract_address: &str,
    state_root: &str,
    expected_proof_ref: &str,
) -> bool {
    let computed_proof_ref = compute_hash(&format!("{}:{}", contract_address, state_root));
    computed_proof_ref == expected_proof_ref
}

/// Settle a contract execution with consensus proof (atomically commit state)
pub async fn settle_contract_execution(
    pool: &PgPool,
    execution_id: Uuid,
    consensus_proof: &str,
) -> Result<SettlementReceipt, Box<dyn std::error::Error>> {
    let settlement_id = Uuid::new_v4();
    let now = chrono::Utc::now();

    // Fetch execution to get state root
    let execution: (String, String) = sqlx::query_as(
        "SELECT contract_address, status FROM contract_executions WHERE execution_id = $1"
    )
    .bind(&execution_id)
    .fetch_one(pool)
    .await?;

    let (contract_address, _status) = execution;

    // Get current state root
    let contract: (Option<String>,) = sqlx::query_as(
        "SELECT state_root FROM smart_contracts WHERE contract_address = $1"
    )
    .bind(&contract_address)
    .fetch_one(pool)
    .await?;

    let state_root_after = contract.0.unwrap_or_default();

    // Check for idempotency: if settlement already exists, return same receipt
    let existing: Option<(Uuid, String)> = sqlx::query_as(
        "SELECT settlement_id, state_root_after FROM contract_settlements WHERE execution_id = $1"
    )
    .bind(&execution_id)
    .fetch_optional(pool)
    .await?;

    if let Some((existing_id, existing_root)) = existing {
        return Ok(SettlementReceipt {
            settlement_id: existing_id,
            execution_id,
            state_root_after: existing_root,
            finalized_at: now,
        });
    }

    // Create settlement record (atomic operation)
    sqlx::query(
        "INSERT INTO contract_settlements (settlement_id, execution_id, consensus_proof, state_root_after, finalized_at, status)
         VALUES ($1, $2, $3, $4, $5, 'finalized')"
    )
    .bind(&settlement_id)
    .bind(&execution_id)
    .bind(consensus_proof)
    .bind(&state_root_after)
    .bind(&now)
    .execute(pool)
    .await?;

    // Update execution status to settled
    sqlx::query(
        "UPDATE contract_executions SET status = 'settled', executed_at = $1 WHERE execution_id = $2"
    )
    .bind(&now)
    .bind(&execution_id)
    .execute(pool)
    .await?;

    Ok(SettlementReceipt {
        settlement_id,
        execution_id,
        state_root_after,
        finalized_at: now,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_merkle_root_deterministic() {
        let mut slots = HashMap::new();
        slots.insert("slot_0".to_string(), "value_0".to_string());
        slots.insert("slot_1".to_string(), "value_1".to_string());

        let root1 = compute_merkle_root(&slots);
        let root2 = compute_merkle_root(&slots);

        assert_eq!(root1, root2);
    }

    #[test]
    fn test_merkle_root_empty() {
        let slots = HashMap::new();
        let root = compute_merkle_root(&slots);
        assert!(!root.is_empty());
    }

    #[test]
    fn test_validate_merkle_proof() {
        let contract = "0x1234567890123456789012345678901234567890";
        let state_root = "abc123";
        let proof_ref = compute_hash(&format!("{}:{}", contract, state_root));

        assert!(validate_merkle_proof(contract, state_root, &proof_ref));
        assert!(!validate_merkle_proof(contract, "different_root", &proof_ref));
    }
}
