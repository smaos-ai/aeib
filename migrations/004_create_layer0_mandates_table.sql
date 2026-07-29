-- Layer 0 Persistence: Mandates Table (Claim 2 from Patent Brief)
-- Cryptographic mandate storage for intent verification and action authorization

CREATE TABLE IF NOT EXISTS layer0_mandates (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Cryptographic Material (immutable, verified on insert)
    intent_hash BYTEA NOT NULL CHECK (octet_length(intent_hash) = 32),
        -- SHA256 hash of original intent. 32 bytes for cryptographic strength.

    public_key BYTEA NOT NULL CHECK (octet_length(public_key) = 32),
        -- Ed25519 public key. 32 bytes. Used to verify mandate authenticity.

    signature BYTEA NOT NULL CHECK (octet_length(signature) = 64),
        -- Ed25519 signature over (intent_hash || jurisdiction || action_scope || expires_at).
        -- 64 bytes. Must be verified on insert via application layer trigger.

    -- Authorization Scope
    jurisdiction TEXT NOT NULL,
        -- Sovereignty domain: 'EU', 'US', 'Global', etc.
        -- Used for jurisdiction-based compliance and action filtering.

    action_scope JSONB NOT NULL,
        -- JSON array of permitted actions: ["spawn_agent", "invoke_tool_x", "revoke_mandate"]
        -- Enforced at query time; defines the mandate's capability envelope.

    -- Lifecycle Timestamps (immutable)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        -- When mandate was created. Immutable after creation.

    expires_at TIMESTAMPTZ NOT NULL,
        -- Mandatory expiration time. After this, mandate is no longer valid.
        -- Constraint checked on create: expires_at > created_at.

    revoked_at TIMESTAMPTZ,
        -- Soft-delete marker. Set when mandate is revoked (not deleted from table).
        -- NULL = mandate active; non-NULL = mandate revoked at this timestamp.
        -- Immutable once set (no re-activation allowed).

    -- Integrity Constraints
    CONSTRAINT valid_expiry CHECK (expires_at > created_at),
    CONSTRAINT valid_revocation CHECK (
        revoked_at IS NULL
        OR (revoked_at >= created_at AND revoked_at <= NOW() + INTERVAL '1 second')
    )
);

-- Indexes for efficient queries and Merkle proof traversal
CREATE INDEX idx_layer0_mandates_public_key ON layer0_mandates(public_key);
    -- Fast lookup by signer identity. Used to find all mandates from a given keypair.

CREATE INDEX idx_layer0_mandates_expires ON layer0_mandates(expires_at);
    -- Fast expiration queries. Used to evict stale mandates from cache.

CREATE INDEX idx_layer0_mandates_jurisdiction ON layer0_mandates(jurisdiction);
    -- Fast lookup by regulatory domain. Used for jurisdiction-scoped authorization checks.

CREATE INDEX idx_layer0_mandates_revoked ON layer0_mandates(revoked_at);
    -- Fast lookup of revoked mandates. Used to exclude revoked entries from active sets.

-- Unique index on (public_key, intent_hash) to prevent duplicate mandates from same signer
CREATE UNIQUE INDEX idx_layer0_mandates_signer_intent ON layer0_mandates(public_key, intent_hash)
    WHERE revoked_at IS NULL;
    -- Ensures no two active mandates with identical signer + intent. Allows revocation and re-issuance.

-- Prevent accidental modifications
ALTER TABLE layer0_mandates ENABLE ROW LEVEL SECURITY;

CREATE POLICY layer0_mandates_no_delete ON layer0_mandates AS RESTRICTIVE
    FOR DELETE
    USING (false);  -- Block all DELETE operations. Mandates are append-only.

CREATE POLICY layer0_mandates_limited_update ON layer0_mandates AS RESTRICTIVE
    FOR UPDATE
    USING (true)
    WITH CHECK (
        -- Only allow UPDATE to set revoked_at. No other field changes permitted.
        revoked_at IS NOT NULL
        AND revoked_at > old.revoked_at  -- Fail if trying to clear revocation
        AND public_key = old.public_key
        AND intent_hash = old.intent_hash
        AND signature = old.signature
        AND jurisdiction = old.jurisdiction
        AND action_scope = old.action_scope
        AND created_at = old.created_at
        AND expires_at = old.expires_at
    );  -- Only revoked_at can change; all other fields must remain identical.
