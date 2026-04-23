-- Phase 13: Add optional geo coordinates to farmer_profiles for nearby search

ALTER TABLE farmer_profiles
  ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_farmer_profiles_lat_lng
  ON farmer_profiles(latitude, longitude);

