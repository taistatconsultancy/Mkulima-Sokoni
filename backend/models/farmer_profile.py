"""
Farmer Profile model and database operations
"""
from database import execute_query, get_db_connection
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FarmerProfile:
    """Farmer Profile model for storing farmer-specific information"""

    @staticmethod
    def normalize_kenya_coords(lat, lng):
        """
        Fix accidental latitude/longitude swap (common when easting ~34–37 was saved as latitude).
        Kenya mainland: lat roughly −5…6, lng roughly 33…42.
        """
        try:
            la = float(lat)
            ln = float(lng)
        except (TypeError, ValueError):
            return lat, lng
        if 28.0 <= la <= 45.0 and -10.0 <= ln <= 12.0:
            return ln, la
        return la, ln

    @staticmethod
    def create_profile(user_id, farm_name=None, location=None, county=None,
                      latitude=None, longitude=None,
                      farm_size_acres=None, farming_experience_years=None,
                      certification_status='pending', bio=None, profile_image_url=None,
                      national_id=None, id_front_url=None, id_back_url=None,
                      profile_selfie_url=None, ward=None, crops=None, livestock=None,
                      referral_source=None, referral_other=None):
        """
        Create a new farmer profile
        """
        try:
            # Validate user_id is a UUID before inserting
            if isinstance(user_id, str) and 'T' in user_id:
                logger.error(f"CRITICAL: create_profile received timestamp '{user_id}' instead of UUID!")
                raise ValueError(f"Invalid user_id: expected UUID, got timestamp '{user_id}'")
            
            # Use explicit UUID casting in the query
            query = """
                INSERT INTO farmer_profiles 
                (user_id, farm_name, location, county, latitude, longitude, farm_size_acres, 
                 farming_experience_years, certification_status, bio, profile_image_url,
                 national_id, id_front_url, id_back_url, profile_selfie_url, ward, crops, livestock,
                 referral_source, referral_other, created_at, updated_at)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING *
            """
            params = (user_id, farm_name, location, county, latitude, longitude, farm_size_acres,
                     farming_experience_years, certification_status, bio, profile_image_url,
                     national_id, id_front_url, id_back_url, profile_selfie_url, ward, crops, livestock,
                     referral_source, referral_other)
            result = execute_query(query, params, fetch_one=True)
            # RealDictRow is dict-like, return as-is
            return result if result else None
        except Exception as e:
            logger.error(f"Error creating farmer profile: {str(e)}")
            raise
    
    @staticmethod
    def get_user_id_by_firebase_uid(firebase_uid):
        """
        Get user_id from farmer_profiles table by joining with users table using firebase_uid
        This avoids the timestamp issue by getting user_id directly from the profile table
        Uses explicit UUID casting to ensure correct type
        """
        try:
            query = """
                SELECT CAST(fp.user_id AS VARCHAR) as user_id
                FROM farmer_profiles fp
                INNER JOIN users u ON fp.user_id = u.id
                WHERE u.firebase_uid = %s
                LIMIT 1
            """
            result = execute_query(query, (firebase_uid,), fetch_one=True)
            if result:
                user_id = result.get('user_id')
                logger.info(f"Raw result from get_user_id_by_firebase_uid: {result}")
                logger.info(f"Got user_id from farmer_profiles: {user_id} (type: {type(user_id).__name__})")
                
                # Validate it's not a timestamp
                if isinstance(user_id, str) and 'T' in user_id:
                    logger.error(f"CRITICAL: get_user_id_by_firebase_uid returned timestamp '{user_id}'!")
                    return None
                
                # Validate it's a UUID
                import uuid
                if isinstance(user_id, str) and len(user_id) == 36 and user_id.count('-') == 4:
                    try:
                        uuid.UUID(user_id)
                        return user_id
                    except (ValueError, AttributeError):
                        logger.error(f"user_id '{user_id}' is not a valid UUID")
                        return None
            return None
        except Exception as e:
            logger.error(f"Error getting user_id from farmer_profiles: {str(e)}")
            raise
    
    @staticmethod
    def get_profile_by_user_id(user_id):
        """
        Get farmer profile by user_id
        """
        try:
            # Validate user_id is a UUID before querying
            if isinstance(user_id, str) and 'T' in user_id:
                logger.error(f"CRITICAL: get_profile_by_user_id received timestamp '{user_id}' instead of UUID!")
                raise ValueError(f"Invalid user_id: expected UUID, got timestamp '{user_id}'")
            
            query = "SELECT * FROM farmer_profiles WHERE user_id = %s"
            result = execute_query(query, (user_id,), fetch_one=True)
            # RealDictRow is dict-like, return as-is
            return result if result else None
        except Exception as e:
            logger.error(f"Error getting farmer profile: {str(e)}")
            raise
    
    @staticmethod
    def get_profile_by_firebase_uid(firebase_uid):
        """
        Get farmer profile directly by firebase_uid using join
        This gets user_id from the profile table, avoiding timestamp issues
        """
        try:
            query = """
                SELECT fp.*, u.email, u.phone_number
                FROM farmer_profiles fp
                INNER JOIN users u ON fp.user_id = u.id
                WHERE u.firebase_uid = %s
            """
            result = execute_query(query, (firebase_uid,), fetch_one=True)
            return result if result else None
        except Exception as e:
            logger.error(f"Error getting farmer profile by firebase_uid: {str(e)}")
            raise
    
    @staticmethod
    def update_profile(user_id, **kwargs):
        """
        Update farmer profile fields
        """
        try:
            # Validate user_id is a UUID before querying
            import uuid
            from datetime import datetime
            
            logger.debug(f"update_profile received user_id: {user_id} (type: {type(user_id).__name__})")
            
            # Check if it's a datetime object
            if isinstance(user_id, datetime):
                logger.error(f"CRITICAL: update_profile received datetime object '{user_id}' instead of UUID!")
                raise ValueError(f"Invalid user_id: expected UUID, got datetime object '{user_id}'")
            
            # Check if it's a string that looks like a timestamp
            if isinstance(user_id, str):
                if 'T' in user_id or (len(user_id) > 10 and user_id.count('-') >= 2 and ':' in user_id):
                    try:
                        datetime.fromisoformat(user_id.replace('Z', '+00:00'))
                        logger.error(f"CRITICAL: update_profile received timestamp string '{user_id}' instead of UUID!")
                        raise ValueError(f"Invalid user_id: expected UUID, got timestamp string '{user_id}'")
                    except (ValueError, AttributeError):
                        pass
                
                # Validate it's a valid UUID format
                if len(user_id) == 36 and user_id.count('-') == 4:
                    try:
                        uuid.UUID(user_id)
                    except (ValueError, AttributeError):
                        logger.error(f"Invalid user_id format: '{user_id}' - not a valid UUID")
                        raise ValueError(f"Invalid user_id: '{user_id}' is not a valid UUID format")
                else:
                    logger.error(f"Invalid user_id format: '{user_id}' - wrong length or dash count")
                    raise ValueError(f"Invalid user_id: '{user_id}' is not a valid UUID format")
            
            # Build dynamic update query
            allowed_fields = ['farm_name', 'location', 'county', 'latitude', 'longitude', 'farm_size_acres',
                            'farming_experience_years', 'certification_status', 'bio', 'profile_image_url',
                            'national_id', 'id_front_url', 'id_back_url', 'profile_selfie_url', 'ward', 'crops', 'livestock',
                            'referral_source', 'referral_other']
            
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = %s")
                    params.append(value)
            
            if not updates:
                return None
            
            params.append(user_id)
            query = f"""
                UPDATE farmer_profiles 
                SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s::uuid
                RETURNING *
            """
            result = execute_query(query, params, fetch_one=True)
            # RealDictRow is dict-like, return as-is
            return result if result else None
        except Exception as e:
            logger.error(f"Error updating farmer profile: {str(e)}")
            raise

    @staticmethod
    def list_nearby(*, lat=None, lng=None, radius_km=25, limit=24, county=None):
        """
        List farmers near a point (lat/lng) with an optional radius cutoff.
        Fallback mode: if county is provided (and lat/lng isn't), return farmers in that county first.

        Returns rows including u.firebase_uid to support linking: /seller/<firebase_uid>
        """
        try:
            limit = int(limit or 24)
        except Exception:
            limit = 24
        limit = max(1, min(100, limit))

        if lat is not None and lng is not None:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                radius_f = float(radius_km or 25)
            except Exception:
                raise ValueError("Invalid lat/lng/radius_km")
            radius_f = max(1.0, min(500.0, radius_f))
            lat_f, lng_f = FarmerProfile.normalize_kenya_coords(lat_f, lng_f)

            # Haversine distance (km); normalize swapped lat/lng in DB before measuring.
            query = """
                WITH fpw AS (
                  SELECT
                    u.firebase_uid,
                    fp.farm_name,
                    fp.location,
                    fp.county,
                    fp.profile_image_url,
                    CASE
                      WHEN fp.latitude BETWEEN 28 AND 45 AND fp.longitude BETWEEN -10 AND 12
                      THEN fp.longitude
                      ELSE fp.latitude
                    END AS plat,
                    CASE
                      WHEN fp.latitude BETWEEN 28 AND 45 AND fp.longitude BETWEEN -10 AND 12
                      THEN fp.latitude
                      ELSE fp.longitude
                    END AS plng
                  FROM farmer_profiles fp
                  JOIN users u ON u.id = fp.user_id
                  WHERE fp.latitude IS NOT NULL
                    AND fp.longitude IS NOT NULL
                )
                SELECT
                  firebase_uid,
                  farm_name,
                  location,
                  county,
                  profile_image_url,
                  plat AS latitude,
                  plng AS longitude,
                  (
                    6371 * 2 * ASIN(
                      SQRT(
                        LEAST(1.0,
                          POWER(SIN(RADIANS(plat - %s)) / 2, 2) +
                          COS(RADIANS(%s)) * COS(RADIANS(plat)) *
                          POWER(SIN(RADIANS(plng - %s)) / 2, 2)
                        )
                      )
                    )
                  ) AS distance_km
                FROM fpw
                ORDER BY distance_km ASC
                LIMIT %s
            """
            rows = execute_query(query, (lat_f, lat_f, lng_f, limit), fetch_all=True) or []
            # Apply radius filter in Python (keeps SQL simple + portable).
            out = []
            for r in rows:
                d = r.get("distance_km")
                try:
                    if d is None or float(d) > radius_f:
                        continue
                except Exception:
                    continue
                out.append(dict(r))
            return out

        if county:
            c = str(county).strip()
            if not c:
                return []
            query = """
                SELECT
                  u.firebase_uid,
                  fp.farm_name,
                  fp.location,
                  fp.county,
                  fp.profile_image_url,
                  NULL::double precision AS distance_km
                FROM farmer_profiles fp
                JOIN users u ON u.id = fp.user_id
                WHERE fp.county ILIKE %s
                ORDER BY COALESCE(fp.updated_at, fp.created_at) DESC
                LIMIT %s
            """
            rows = execute_query(query, (c, limit), fetch_all=True) or []
            return [dict(r) for r in rows]

        return []
    
    @staticmethod
    def profile_exists(user_id):
        """
        Check if farmer profile exists for user
        """
        try:
            # Comprehensive validation: check for timestamps in any form
            import uuid
            from datetime import datetime
            
            # Log what we received
            logger.debug(f"profile_exists received user_id: {user_id} (type: {type(user_id).__name__})")
            
            # Check if it's a datetime object
            if isinstance(user_id, datetime):
                logger.error(f"CRITICAL: profile_exists received datetime object '{user_id}' instead of UUID!")
                raise ValueError(f"Invalid user_id: expected UUID, got datetime object '{user_id}'")
            
            # Check if it's a string that looks like a timestamp
            if isinstance(user_id, str):
                # Check for ISO timestamp format (contains 'T' or looks like a date)
                if 'T' in user_id or (len(user_id) > 10 and user_id.count('-') >= 2 and 'T' not in user_id and ':' in user_id):
                    # Might be a timestamp string
                    try:
                        # Try to parse as datetime to confirm
                        datetime.fromisoformat(user_id.replace('Z', '+00:00'))
                        logger.error(f"CRITICAL: profile_exists received timestamp string '{user_id}' instead of UUID!")
                        raise ValueError(f"Invalid user_id: expected UUID, got timestamp string '{user_id}'")
                    except (ValueError, AttributeError):
                        pass
                
                # Validate it's a valid UUID format
                if len(user_id) == 36 and user_id.count('-') == 4:
                    try:
                        uuid.UUID(user_id)
                        # Valid UUID, proceed
                    except (ValueError, AttributeError):
                        logger.error(f"Invalid user_id format: '{user_id}' - not a valid UUID")
                        raise ValueError(f"Invalid user_id: '{user_id}' is not a valid UUID format")
                else:
                    logger.error(f"Invalid user_id format: '{user_id}' - wrong length or dash count")
                    raise ValueError(f"Invalid user_id: '{user_id}' is not a valid UUID format")
            
            # FINAL CHECK: Log exactly what we're about to send to the database
            logger.error(f"FINAL CHECK BEFORE DB QUERY: user_id = {user_id} (type: {type(user_id).__name__})")
            if isinstance(user_id, str) and 'T' in user_id:
                logger.error(f"CRITICAL: About to query with timestamp '{user_id}' - THIS SHOULD NEVER HAPPEN!")
                raise ValueError(f"Invalid user_id: timestamp '{user_id}' detected right before database query")
            
            query = "SELECT COUNT(*) as count FROM farmer_profiles WHERE user_id = %s::uuid"
            result = execute_query(query, (user_id,), fetch_one=True)
            return result['count'] > 0 if result else False
        except Exception as e:
            logger.error(f"Error checking farmer profile existence: {str(e)}")
            raise

