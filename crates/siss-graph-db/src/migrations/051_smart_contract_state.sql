-- Phase 78: Smart Contract Deployment, Execution, and State Management

CREATE TABLE IF NOT EXISTS smart_contracts (
    contract_address VARCHAR(42) PRIMARY KEY,
    sovereign_id UUID NOT NULL,
    bytecode TEXT NOT NULL,
    abi JSONB NOT NULL,
    deployed_at TIMESTAMPTZ NOT NULL,
    deployer_agent_id VARCHAR(255) NOT NULL,
    state_root VARCHAR(64),
    merkle_proof_ref VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'deployed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (sovereign_id) REFERENCES sovereigns(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contract_executions (
    execution_id UUID PRIMARY KEY,
    contract_address VARCHAR(42) NOT NULL,
    function_name VARCHAR(255) NOT NULL,
    caller_agent_id VARCHAR(255) NOT NULL,
    input_args JSONB,
    output_result JSONB,
    state_changes JSONB,
    gas_used BIGINT,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (contract_address) REFERENCES smart_contracts(contract_address) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contract_state_slots (
    id UUID PRIMARY KEY,
    contract_address VARCHAR(42) NOT NULL,
    slot_key VARCHAR(66) NOT NULL,
    slot_value VARCHAR(66),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (contract_address) REFERENCES smart_contracts(contract_address) ON DELETE CASCADE,
    UNIQUE(contract_address, slot_key)
);

CREATE TABLE IF NOT EXISTS contract_settlements (
    settlement_id UUID PRIMARY KEY,
    execution_id UUID NOT NULL,
    consensus_proof VARCHAR(256),
    state_root_before VARCHAR(64),
    state_root_after VARCHAR(64),
    finalized_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (execution_id) REFERENCES contract_executions(execution_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_smart_contracts_sovereign_id ON smart_contracts(sovereign_id);
CREATE INDEX IF NOT EXISTS idx_smart_contracts_status ON smart_contracts(status);
CREATE INDEX IF NOT EXISTS idx_contract_executions_contract_address ON contract_executions(contract_address);
CREATE INDEX IF NOT EXISTS idx_contract_executions_status ON contract_executions(status);
CREATE INDEX IF NOT EXISTS idx_contract_executions_created_at ON contract_executions(created_at);
CREATE INDEX IF NOT EXISTS idx_contract_state_slots_contract_address ON contract_state_slots(contract_address);
CREATE INDEX IF NOT EXISTS idx_contract_settlements_execution_id ON contract_settlements(execution_id);
CREATE INDEX IF NOT EXISTS idx_contract_settlements_status ON contract_settlements(status);
