-- Multi-Currency Settlement Migration
-- Created: 2026-08-05

CREATE TABLE fx_rates (
  id UUID PRIMARY KEY,
  from_currency VARCHAR(3) NOT NULL,
  to_currency VARCHAR(3) NOT NULL,
  rate DECIMAL(18,8) NOT NULL,
  fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE(from_currency, to_currency)
);

CREATE TABLE multi_currency_settlements (
  id UUID PRIMARY KEY,
  status VARCHAR(20) NOT NULL, -- Active, Completed, Aborted
  merkle_root BYTEA NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE settlement_legs (
  id UUID PRIMARY KEY,
  settlement_id UUID NOT NULL REFERENCES multi_currency_settlements(id),
  from_currency VARCHAR(3) NOT NULL,
  to_currency VARCHAR(3) NOT NULL,
  amount_cents BIGINT NOT NULL,
  status VARCHAR(20) NOT NULL
);

CREATE TABLE stablecoin_settlements (
  id UUID PRIMARY KEY,
  amount_cents BIGINT NOT NULL,
  cryptographic_hash VARCHAR(100) NOT NULL, -- sha256: prefix
  state VARCHAR(20) NOT NULL, -- Active, Archived
  created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE mifid_transaction_reports (
  id UUID PRIMARY KEY,
  settlement_leg_id UUID NOT NULL REFERENCES settlement_legs(id),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL,
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL, -- created_at + 7 years
  INDEX(expires_at)
);

CREATE TABLE stripe_webhook_events (
  event_id VARCHAR(100) PRIMARY KEY,
  payload JSONB NOT NULL,
  processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
