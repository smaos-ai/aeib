-- Phase 9: Settlement Ledger
-- sovereign_credit_entries: append-only ledger of inter-sovereign resource consumption
-- Records tokens consumed by foreign agents; basis for settlement invoicing (Phase 10)

CREATE TABLE sovereign_credit_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  creditor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  debtor_sovereign_id UUID NOT NULL REFERENCES sovereigns(id),
  session_id UUID NOT NULL REFERENCES sessions(id),
  tokens_consumed BIGINT NOT NULL,
  cost_breakdown JSONB NOT NULL DEFAULT '{}',
  scored_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  settled_at TIMESTAMPTZ  -- NULL until settled; never changed after set
);

CREATE INDEX idx_credit_entries_creditor ON sovereign_credit_entries(creditor_sovereign_id);
CREATE INDEX idx_credit_entries_debtor ON sovereign_credit_entries(debtor_sovereign_id);
CREATE INDEX idx_credit_entries_unsettled ON sovereign_credit_entries(creditor_sovereign_id, debtor_sovereign_id)
  WHERE settled_at IS NULL;
