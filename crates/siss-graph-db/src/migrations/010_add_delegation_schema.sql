-- Phase 6: Delegation Chains — Persona and Session Extensions
-- Extends personas and sessions tables to support delegation DAG

-- Add delegation fields to personas table
ALTER TABLE personas
  ADD COLUMN delegated_by UUID REFERENCES personas(id),
  ADD COLUMN delegation_ceiling_tier SMALLINT,
  ADD COLUMN delegation_timestamp TIMESTAMPTZ;

-- Create index for fast ancestor traversal
CREATE INDEX idx_personas_delegated_by ON personas(delegated_by) WHERE delegated_by IS NOT NULL;

-- Add delegation fields to sessions table
ALTER TABLE sessions
  ADD COLUMN parent_session_id UUID REFERENCES sessions(id),
  ADD COLUMN delegated_by_agent_id UUID REFERENCES personas(id),
  ADD COLUMN delegation_ceiling_envelope JSONB,
  ADD COLUMN current_effective_envelope JSONB,
  ADD COLUMN lineage_cache JSONB;

-- Create indexes for fast parent/child session traversal
CREATE INDEX idx_sessions_parent ON sessions(parent_session_id) WHERE parent_session_id IS NOT NULL;
CREATE INDEX idx_sessions_delegated_by ON sessions(delegated_by_agent_id) WHERE delegated_by_agent_id IS NOT NULL;

-- NOTE: Tenant consistency is enforced at application layer, not via CHECK constraints
-- (PostgreSQL CHECK constraints cannot use subqueries)
