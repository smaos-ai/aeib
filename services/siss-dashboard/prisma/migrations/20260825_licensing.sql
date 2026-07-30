-- CreateTable licenses
CREATE TABLE IF NOT EXISTS licenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL,
  license_key VARCHAR(100) NOT NULL UNIQUE,
  sku VARCHAR(20) NOT NULL CHECK (sku IN ('Starter', 'Pro', 'Enterprise')),
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
  revoked BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_licenses_customer_id ON licenses(customer_id);
CREATE INDEX idx_licenses_license_key ON licenses(license_key);

-- CreateTable usage_events
CREATE TABLE IF NOT EXISTS usage_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  license_key VARCHAR(100) NOT NULL,
  call_count BIGINT NOT NULL,
  recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  day DATE NOT NULL,
  FOREIGN KEY (license_key) REFERENCES licenses(license_key) ON DELETE CASCADE
);

CREATE INDEX idx_usage_events_license_key_day ON usage_events(license_key, day);

-- CreateTable audit_log
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('Generated', 'Validated', 'UsageRecorded', 'Renewed', 'Revoked', 'PaymentReceived')),
  customer_id UUID,
  details JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '7 years'),
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_log_customer_id_created_at ON audit_log(customer_id, created_at);

-- CreateTable stripe_webhook_events
CREATE TABLE IF NOT EXISTS stripe_webhook_events (
  event_id VARCHAR(100) PRIMARY KEY,
  payload JSONB NOT NULL,
  processed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable stripe_subscriptions
CREATE TABLE IF NOT EXISTS stripe_subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  stripe_subscription_id VARCHAR(100) NOT NULL UNIQUE,
  customer_id UUID NOT NULL,
  status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'paused', 'cancelled', 'expired')),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  cancelled_at TIMESTAMP WITH TIME ZONE,
  FOREIGN KEY (customer_id) REFERENCES licenses(customer_id) ON DELETE CASCADE
);

CREATE INDEX idx_stripe_subscriptions_customer_id ON stripe_subscriptions(customer_id);

-- CreateTable invoices
CREATE TABLE IF NOT EXISTS invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id UUID NOT NULL,
  amount_cents BIGINT NOT NULL,
  sku VARCHAR(20) NOT NULL CHECK (sku IN ('Starter', 'Pro', 'Enterprise')),
  status VARCHAR(20) NOT NULL CHECK (status IN ('draft', 'pending', 'paid', 'failed', 'cancelled')),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES licenses(customer_id) ON DELETE CASCADE
);

CREATE INDEX idx_invoices_customer_id ON invoices(customer_id);
