-- Phase 14 Task 71: Terminal resolved status for disputed invoices
-- Constitutional invariant: INVOICE_STATUS_MONOTONIC extended
-- Adds co-presence CHECK for resolved status (dispute_resolved_at must be set)

ALTER TABLE settlement_invoices
    ADD CONSTRAINT check_resolved_at_with_status CHECK (
        (status = 'resolved' AND dispute_resolved_at IS NOT NULL)
        OR status != 'resolved'
    );

CREATE INDEX idx_invoices_resolved
    ON settlement_invoices(creditor_sovereign_id, debtor_sovereign_id)
    WHERE status = 'resolved';
