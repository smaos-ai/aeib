-- L8 Proof Layer: Agent Account Work Receipts Schema
-- Immutable audit trail of all agent actions and cryptographic proofs

CREATE TABLE IF NOT EXISTS agentacct_receipts (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  action TEXT NOT NULL,
  result TEXT NOT NULL,
  signature TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  chain_digest TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agentacct_receipts_agent_id ON agentacct_receipts(agent_id);
CREATE INDEX IF NOT EXISTS idx_agentacct_receipts_timestamp ON agentacct_receipts(timestamp);

CREATE TABLE IF NOT EXISTS agentacct_checkpoints (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL,
  checkpoint_num INTEGER NOT NULL,
  receipt_ids TEXT NOT NULL,
  merkle_root TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (agent_id, checkpoint_num)
);

CREATE INDEX IF NOT EXISTS idx_agentacct_checkpoints_agent_id ON agentacct_checkpoints(agent_id);
