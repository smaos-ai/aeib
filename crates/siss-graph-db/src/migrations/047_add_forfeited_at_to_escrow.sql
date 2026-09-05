-- Add missing forfeited_at timestamp column to escrow_ledger
-- Required by forfeit_escrow_on_timeout() function which sets this timestamp on timeout

ALTER TABLE escrow_ledger
ADD COLUMN forfeited_at TIMESTAMPTZ;

-- Add constraint requiring forfeited_at for 'forfeited' status (mirrors released/disputed)
ALTER TABLE escrow_ledger
ADD CONSTRAINT check_forfeited_has_timestamp CHECK (
    (status = 'forfeited' AND forfeited_at IS NOT NULL) OR status != 'forfeited'
);
