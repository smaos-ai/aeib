-- Phase 11: Full Invoice Lifecycle
-- Constitutional invariant: INVOICE_STATUS_MONOTONIC
-- Permitted: pending → acknowledged → (settled | disputed). No backward transitions.

ALTER TABLE settlement_invoices
    ADD COLUMN acknowledged_at TIMESTAMPTZ,
    ADD COLUMN disputed_at TIMESTAMPTZ,
    ADD COLUMN dispute_reason TEXT,
    ADD COLUMN dispute_evidence JSONB,
    ADD COLUMN dispute_resolved_at TIMESTAMPTZ,
    ADD COLUMN dispute_resolution TEXT,
    ADD CONSTRAINT check_acknowledged_at_with_status CHECK (
        (status = 'acknowledged' AND acknowledged_at IS NOT NULL) OR status != 'acknowledged'
    ),
    ADD CONSTRAINT check_disputed_at_with_status CHECK (
        (status = 'disputed' AND disputed_at IS NOT NULL) OR status != 'disputed'
    );

CREATE INDEX idx_invoices_disputed ON settlement_invoices(creditor_sovereign_id, debtor_sovereign_id)
    WHERE status = 'disputed';
CREATE INDEX idx_invoices_acknowledged ON settlement_invoices(creditor_sovereign_id, debtor_sovereign_id)
    WHERE status = 'acknowledged';
