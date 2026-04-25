-- Phase 14: Add phone sharing controls + terms acceptance tracking

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS phone_sharing_enabled BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS phone_terms_accepted_at TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_users_phone_sharing_enabled ON users(phone_sharing_enabled);
CREATE INDEX IF NOT EXISTS idx_users_phone_terms_accepted_at ON users(phone_terms_accepted_at);

