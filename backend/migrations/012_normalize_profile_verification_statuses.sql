-- Ensure farmer/buyer verification statuses are consistent and use verified.
-- This migration is idempotent and safe on existing data.

UPDATE farmer_profiles
SET certification_status = 'verified'
WHERE LOWER(COALESCE(certification_status, '')) = 'approved';

UPDATE buyer_profiles
SET verification_status = 'verified'
WHERE LOWER(COALESCE(verification_status, '')) = 'approved';

ALTER TABLE farmer_profiles
DROP CONSTRAINT IF EXISTS farmer_profiles_certification_status_check;

ALTER TABLE farmer_profiles
ADD CONSTRAINT farmer_profiles_certification_status_check
CHECK (
  LOWER(COALESCE(certification_status, 'pending')) IN ('pending', 'verified', 'rejected')
);

ALTER TABLE buyer_profiles
DROP CONSTRAINT IF EXISTS buyer_profiles_verification_status_check;

ALTER TABLE buyer_profiles
ADD CONSTRAINT buyer_profiles_verification_status_check
CHECK (
  LOWER(COALESCE(verification_status, 'pending')) IN ('pending', 'verified', 'rejected')
);
