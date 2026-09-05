-- Slashing events audit trail (Phase 18)
CREATE TABLE slashing_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    escrow_id UUID NOT NULL REFERENCES escrow_ledger(id),
    tokens_slashed BIGINT NOT NULL CHECK (tokens_slashed > 0),
    slash_percentage SMALLINT NOT NULL CHECK (slash_percentage BETWEEN 1 AND 100),
    severity VARCHAR(16) NOT NULL,
    slash_reason TEXT NOT NULL,
    slashed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_slashing_sovereign ON slashing_events(sovereign_id, slashed_at DESC);
CREATE INDEX idx_slashing_escrow ON slashing_events(escrow_id);
