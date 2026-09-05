-- Phase 13 Task 67: Escrow Ledger
-- Atomic multi-party token escrow for settlement invoices
-- Constitutional invariant: ESCROW_ATOMICITY (tokens held atomically until acknowledged or timeout)

CREATE TABLE escrow_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Settlement reference (1:1 with invoice via UNIQUE constraint)
    invoice_id UUID NOT NULL UNIQUE REFERENCES settlement_invoices(id),
    creditor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    debtor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),

    -- Token hold amount (immutable, from invoice.total_tokens)
    tokens_held BIGINT NOT NULL CHECK (tokens_held > 0),

    -- State machine: pending → held → (released | forfeited | disputed)
    status VARCHAR(32) NOT NULL DEFAULT 'pending',

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    held_at TIMESTAMPTZ,                        -- Set when debtor acknowledges (pending → held)
    release_at TIMESTAMPTZ,                     -- Set when creditor releases (held → released)
    timeout_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '48 hours'),  -- Auto-forfeit time

    -- Debtor acknowledgement (marks escrow as "held")
    debtor_acknowledged_at TIMESTAMPTZ,
    debtor_acknowledged_by_sovereign_id UUID REFERENCES sovereigns(id),

    -- Creditor release authorization
    release_signature TEXT,                     -- Ed25519(creditor.private_key, escrow_id || nonce)

    -- Dispute tracking
    disputed_at TIMESTAMPTZ,
    dispute_reason TEXT,
    dispute_evidence JSONB,
    arbitration_result TEXT,                    -- "creditor_wins" | "debtor_wins" | "split"

    -- Vector clock for causality tracking (map of sovereign_uuid → sequence_number)
    vector_clock JSONB NOT NULL DEFAULT '{}',

    -- Audit trail
    created_by_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),

    -- Status machine constraints
    CONSTRAINT check_status_valid CHECK (
        status IN ('pending', 'held', 'released', 'forfeited', 'disputed')
    ),
    CONSTRAINT check_pending_no_held_at CHECK (
        (status = 'pending' AND held_at IS NULL) OR status != 'pending'
    ),
    CONSTRAINT check_non_pending_has_held_at CHECK (
        (status IN ('held', 'released', 'forfeited', 'disputed') AND held_at IS NOT NULL) OR
        status = 'pending'
    ),
    CONSTRAINT check_released_has_timestamp CHECK (
        (status = 'released' AND release_at IS NOT NULL) OR status != 'released'
    ),
    CONSTRAINT check_disputed_has_timestamp CHECK (
        (status = 'disputed' AND disputed_at IS NOT NULL) OR status != 'disputed'
    ),

    -- Timeout constraint: must be in future at creation
    CONSTRAINT check_timeout_future CHECK (timeout_at > created_at),

    -- Prevent self-escrow (no creditor == debtor)
    CONSTRAINT check_not_self_escrow CHECK (creditor_sovereign_id != debtor_sovereign_id)
);

-- Index for debtor queries (pending escrows they need to acknowledge)
CREATE INDEX idx_escrow_debtor ON escrow_ledger(debtor_sovereign_id)
    WHERE status IN ('pending', 'held');

-- Index for creditor queries (pending escrows they can release)
CREATE INDEX idx_escrow_creditor ON escrow_ledger(creditor_sovereign_id)
    WHERE status IN ('pending', 'held');

-- Index for timeout background job (find held escrows past their timeout)
CREATE INDEX idx_escrow_timeout ON escrow_ledger(timeout_at)
    WHERE status = 'held' AND debtor_acknowledged_at IS NULL;

-- Index for direct invoice lookup (escrow_repo::fetch_escrow_by_invoice)
CREATE INDEX idx_escrow_invoice ON escrow_ledger(invoice_id);
