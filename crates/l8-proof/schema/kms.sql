-- L8 Proof Layer: Local KMS Vault Schema for Ed25519 Key Management
-- Stores cryptographic keys and operation audit trail

CREATE TABLE IF NOT EXISTS kms_keys (
  key_id TEXT PRIMARY KEY,
  algorithm TEXT NOT NULL,
  private_key_base64 TEXT NOT NULL,
  public_key_hex TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_algorithm (algorithm)
);

CREATE TABLE IF NOT EXISTS kms_operations (
  id TEXT PRIMARY KEY,
  key_id TEXT NOT NULL,
  operation TEXT NOT NULL,
  success BOOLEAN NOT NULL,
  timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (key_id) REFERENCES kms_keys(key_id),
  INDEX idx_key_id (key_id),
  INDEX idx_operation (operation)
);
