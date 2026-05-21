-- Add unique constraint for revocation_certificates to support ON CONFLICT
ALTER TABLE revocation_certificates
ADD CONSTRAINT unique_agent_source UNIQUE (agent_id, source_sovereign_id);
