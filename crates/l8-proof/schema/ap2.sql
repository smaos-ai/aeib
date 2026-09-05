-- L8 AP2 Settlement Ledger: Immutable transaction records with Merkle root anchoring
-- Each entry is signed, immutable, and linked via Merkle tree for git anchoring

CREATE TABLE IF NOT EXISTS ap2_entries (
    id TEXT PRIMARY KEY,                      -- Unique identifier (UUIDv4)
    authorization TEXT NOT NULL,              -- Authorization ID (who approved)
    signature TEXT NOT NULL,                  -- Ed25519 signature (hex, 128+ chars)
    merkle_proof TEXT NOT NULL,               -- Merkle proof path (JSON array of hashes)
    transaction_data TEXT NOT NULL,           -- Full transaction payload (JSON)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_immutable INTEGER DEFAULT 0,           -- Boolean flag (0/1) for immutability verification
    git_anchor_hash TEXT                      -- Optional Git commit digest this entry anchors to
);

CREATE TABLE IF NOT EXISTS ap2_merkle_roots (
    id TEXT PRIMARY KEY,                      -- Unique identifier (UUIDv4)
    root_hash TEXT NOT NULL UNIQUE,           -- SHA256 hash of all entries at this checkpoint
    entries_count INTEGER NOT NULL,           -- Number of entries included in this root
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    git_anchor TEXT                           -- Git commit hash for audit trail
);

-- Index for quick lookups by timestamp and authorization
CREATE INDEX IF NOT EXISTS idx_ap2_entries_created_at ON ap2_entries(created_at);
CREATE INDEX IF NOT EXISTS idx_ap2_entries_authorization ON ap2_entries(authorization);
CREATE INDEX IF NOT EXISTS idx_ap2_merkle_roots_created_at ON ap2_merkle_roots(created_at);
