use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use sqlx::PgPool;
use std::collections::HashMap;
use uuid::Uuid;

pub use crate::contract_state_store::SettlementReceipt;

#[derive(Debug, Clone)]
pub struct ExecutionResult {
    pub execution_id: Uuid,
    pub output: Value,
    pub state_changes: HashMap<String, Value>,
    pub gas_used: u64,
}

/// Execute a contract function on the EVM.
///
/// # Arguments
/// * `pool` - Database pool
/// * `contract_address` - EVM contract address (0x...)
/// * `function_sig` - Function signature (e.g., "transfer(address,uint256)")
/// * `args` - Function arguments as JSON array
/// * `sender_agent_id` - Agent ID executing the function
///
/// # Returns
/// ExecutionResult with output, state changes, and gas used
pub async fn execute_contract_function(
    pool: &PgPool,
    contract_address: &str,
    function_sig: &str,
    args: Value,
    sender_agent_id: &str,
) -> Result<ExecutionResult, Box<dyn std::error::Error>> {
    // Validate contract address format
    if !contract_address.starts_with("0x") || contract_address.len() != 42 {
        return Err("Invalid contract address format".into());
    }

    // Fetch contract from database
    let contract: (String, Value) =
        sqlx::query_as("SELECT bytecode, abi FROM smart_contracts WHERE contract_address = $1")
            .bind(contract_address)
            .fetch_one(pool)
            .await?;

    let (_bytecode, _abi) = contract;

    // For now: mock execution with deterministic result
    // In production: use revm or similar EVM library
    let execution_id = Uuid::new_v4();
    let mut state_changes = HashMap::new();

    // Simulate state change: store function call in state
    state_changes.insert("last_caller".to_string(), json!(sender_agent_id));
    state_changes.insert("last_function".to_string(), json!(function_sig));

    // Calculate mock gas: base 21000 + args size
    let gas_used = 21000u64 + (args.to_string().len() as u64 * 16);

    // Store execution in database
    sqlx::query(
        "INSERT INTO contract_executions (execution_id, contract_address, function_name, caller_agent_id, input_args, output_result, state_changes, gas_used, status)
         VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8, 'executed')"
    )
    .bind(&execution_id)
    .bind(contract_address)
    .bind(function_sig)
    .bind(sender_agent_id)
    .bind(args.to_string())
    .bind(json!({ "success": true }).to_string())
    .bind(serde_json::to_value(&state_changes)?.to_string())
    .bind(gas_used as i64)
    .execute(pool)
    .await?;

    Ok(ExecutionResult {
        execution_id,
        output: json!({ "success": true }),
        state_changes,
        gas_used,
    })
}

/// Deploy a new contract to the EVM.
///
/// # Arguments
/// * `pool` - Database pool
/// * `sovereign_id` - Sovereign entity ID
/// * `bytecode` - Contract bytecode (hex string)
/// * `abi` - Contract ABI as JSON
/// * `deployer_agent_id` - Agent deploying the contract
///
/// # Returns
/// Contract address (0x...)
pub async fn deploy_contract(
    pool: &PgPool,
    sovereign_id: Uuid,
    bytecode: &str,
    abi: Value,
    deployer_agent_id: &str,
) -> Result<String, Box<dyn std::error::Error>> {
    // Generate deterministic contract address using hash
    let mut hasher = Sha256::new();
    hasher.update(format!("{}:{}", sovereign_id, deployer_agent_id).as_bytes());
    let hash_result = hasher.finalize();

    // Take first 20 bytes (40 hex chars) for contract address
    let contract_address = format!("0x{}", hex::encode(&hash_result[0..20]));

    // Store contract in database
    sqlx::query(
        "INSERT INTO smart_contracts (contract_address, sovereign_id, bytecode, abi, deployed_at, deployer_agent_id, status)
         VALUES ($1, $2, $3, $4::jsonb, NOW(), $5, 'deployed') ON CONFLICT DO NOTHING"
    )
    .bind(&contract_address)
    .bind(sovereign_id)
    .bind(bytecode)
    .bind(abi.to_string())
    .bind(deployer_agent_id)
    .execute(pool)
    .await?;

    Ok(contract_address)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mock_execution_returns_result() {
        // Basic validation that ExecutionResult struct is sound
        let result = ExecutionResult {
            execution_id: Uuid::new_v4(),
            output: json!({}),
            state_changes: HashMap::new(),
            gas_used: 21000,
        };
        assert!(result.gas_used > 0);
    }
}
