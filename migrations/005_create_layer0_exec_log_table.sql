-- Layer 0 Persistence: Execution Log Table (Claim 2 from Patent Brief)
-- Append-only Merkle-linked audit ledger for immutable action tracking

CREATE TABLE IF NOT EXISTS layer0_exec_log (
    -- Primary Key (immutable sequential identifier)
    id BIGSERIAL PRIMARY KEY,
        -- Immutable sequential counter. Used for Merkle tree traversal and chain integrity.
        -- PostgreSQL's BIGSERIAL guarantees strictly monotonic, gap-free numbering.

    -- Foreign Key to Authorization
    mandate_id UUID NOT NULL REFERENCES layer0_mandates(id),
        -- Links execution to the mandate that authorized it.
        -- NOT ON DELETE CASCADE (preserve audit trail even if mandate is revoked).

    -- Action Metadata
    action TEXT NOT NULL,
        -- What was attempted: 'spawn_agent', 'invoke_tool_x', 'revoke_mandate', etc.
        -- Used for audit filtering and compliance reporting.

    tool_name TEXT,
        -- Which tool was invoked. NULL if action doesn't involve a tool.
        -- Examples: 'gatekeeper', 'job_router', 'behavioral_firewall'.

    result_hash BYTEA NOT NULL CHECK (octet_length(result_hash) = 32),
        -- SHA256 hash of the execution result. 32 bytes.
        -- If action succeeded, hash of return value. If failed, hash of error message.
        -- Allows result verification without storing full result in audit table.

    -- Merkle Integrity Chain
    merkle_hash BYTEA NOT NULL CHECK (octet_length(merkle_hash) = 32) UNIQUE,
        -- SHA256(parent_merkle_hash || mandate_id || action || tool_name || result_hash)
        -- 32 bytes. Forms the backbone of immutable audit chain.
        -- UNIQUE prevents hash collisions and enables fast lookup by chain position.

    parent_merkle_hash BYTEA NOT NULL CHECK (octet_length(parent_merkle_hash) = 32),
        -- merkle_hash of the previous log entry (or 32 zero bytes for genesis block).
        -- Allows reconstruction of full Merkle path for chain-of-custody proofs.

    -- Lifecycle Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        -- When action was executed. Immutable after creation.

    -- Integrity Constraints
    CONSTRAINT valid_merkle_genesis CHECK (
        -- Ensure genesis (id=1) has parent_merkle = 0x00...00
        id > 1 OR parent_merkle_hash = '\x0000000000000000000000000000000000000000000000000000000000000000'
    )
);

-- Indexes for efficient Merkle proof traversal and queries
CREATE INDEX idx_layer0_exec_log_mandate ON layer0_exec_log(mandate_id);
    -- Fast lookup of all actions under a mandate. Used for mandate-scoped audit trails.

CREATE INDEX idx_layer0_exec_log_created ON layer0_exec_log(created_at DESC);
    -- Reverse chronological queries. Used for "recent actions" dashboards.

CREATE INDEX idx_layer0_exec_log_merkle ON layer0_exec_log(merkle_hash);
    -- Fast lookup by chain position. Used to verify Merkle path integrity.

CREATE INDEX idx_layer0_exec_log_parent ON layer0_exec_log(parent_merkle_hash);
    -- Fast traversal backwards up the chain. Used for chain-of-custody reconstruction.

-- Prevent accidental modifications to immutable ledger
ALTER TABLE layer0_exec_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY layer0_exec_log_no_delete ON layer0_exec_log AS RESTRICTIVE
    FOR DELETE
    USING (false);  -- Block all DELETE operations. Ledger is append-only.

CREATE POLICY layer0_exec_log_no_update ON layer0_exec_log AS RESTRICTIVE
    FOR UPDATE
    USING (false);  -- Block all UPDATE operations. Ledger entries are immutable.

-- Trigger to validate Merkle hash on insert
CREATE OR REPLACE FUNCTION validate_layer0_exec_log_merkle()
RETURNS TRIGGER AS $$
DECLARE
    expected_merkle BYTEA;
    parent_entry layer0_exec_log;
BEGIN
    -- Fetch parent entry to verify chain continuity
    SELECT * INTO parent_entry FROM layer0_exec_log
    WHERE id = (NEW.id - 1) AND NEW.id > 1;

    -- For non-genesis entries, verify parent_merkle_hash matches the previous entry's merkle_hash
    IF NEW.id > 1 THEN
        IF parent_entry IS NULL THEN
            RAISE EXCEPTION 'Gap in exec_log chain: entry % references non-existent parent at %',
                NEW.id, (NEW.id - 1);
        END IF;

        IF NEW.parent_merkle_hash != parent_entry.merkle_hash THEN
            RAISE EXCEPTION 'Merkle chain broken: entry % parent_merkle_hash does not match previous entry merkle_hash',
                NEW.id;
        END IF;
    END IF;

    -- Validate that merkle_hash was computed correctly
    expected_merkle := digest(
        NEW.parent_merkle_hash || NEW.mandate_id::bytea || NEW.action || COALESCE(NEW.tool_name, '') || NEW.result_hash,
        'sha256'
    );

    IF NEW.merkle_hash != expected_merkle THEN
        RAISE EXCEPTION 'Invalid merkle_hash in exec_log entry %: expected %, got %',
            NEW.id, encode(expected_merkle, 'hex'), encode(NEW.merkle_hash, 'hex');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER layer0_exec_log_validate_merkle
BEFORE INSERT ON layer0_exec_log
FOR EACH ROW
EXECUTE FUNCTION validate_layer0_exec_log_merkle();

-- Trigger to prevent updates (defensive)
CREATE OR REPLACE FUNCTION prevent_layer0_exec_log_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Updates to layer0_exec_log are forbidden. Ledger is immutable.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER layer0_exec_log_prevent_update
BEFORE UPDATE ON layer0_exec_log
FOR EACH ROW
EXECUTE FUNCTION prevent_layer0_exec_log_update();
