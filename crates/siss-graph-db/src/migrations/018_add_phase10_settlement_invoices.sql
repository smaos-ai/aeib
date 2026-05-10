-- Phase 10: Settlement Invoices
-- Cryptographically committed invoices for inter-sovereign settlement

CREATE TABLE settlement_invoices (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creditor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
    debtor_sovereign_id   UUID NOT NULL REFERENCES sovereigns(id),
    period_start          TIMESTAMPTZ NOT NULL,
    period_end            TIMESTAMPTZ NOT NULL,
    total_tokens          BIGINT NOT NULL,
    entry_count           INT NOT NULL,
    invoice_hash          TEXT NOT NULL,       -- SHA256 hex of canonical invoice payload
    invoice_signature     TEXT NOT NULL,       -- Ed25519 hex over invoice_hash by creditor sovereign
    status                VARCHAR(32) NOT NULL DEFAULT 'pending', -- pending|acknowledged|settled|disputed
    issued_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    settled_at            TIMESTAMPTZ
);

CREATE INDEX idx_invoices_pending ON settlement_invoices(creditor_sovereign_id, debtor_sovereign_id)
    WHERE status = 'pending';
CREATE INDEX idx_invoices_by_pair ON settlement_invoices(creditor_sovereign_id, debtor_sovereign_id, issued_at DESC);

-- FK constraint: credit entries link back to invoices (nullable until entry is invoiced)
ALTER TABLE sovereign_credit_entries
    ADD CONSTRAINT fk_credit_invoice FOREIGN KEY (invoice_id) REFERENCES settlement_invoices(id);
