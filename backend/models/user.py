"""
User model and database operations
"""
from database import execute_query, get_db_connection
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class User:
    """User model for authentication and profile management"""
    
    @staticmethod
    def create_user(firebase_uid, email, phone_number=None, role='buyer', first_name=None, last_name=None):
        """
        Create a new user in the database
        """
        try:
            query = """
                INSERT INTO users (firebase_uid, email, phone_number, role, first_name, last_name, created_at, latest_sign_in)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING id, firebase_uid, email, phone_number, role, first_name, last_name, created_at, latest_sign_in
            """
            params = (firebase_uid, email, phone_number, role, first_name, last_name)
            result = execute_query(query, params, fetch_one=True)
            if result:
                return {
                    'id': str(result['id']),
                    'firebase_uid': result['firebase_uid'],
                    'email': result['email'],
                    'phone_number': result.get('phone_number'),
                    'role': result.get('role'),
                    'first_name': result.get('first_name'),
                    'last_name': result.get('last_name'),
                    'created_at': str(result['created_at']) if result.get('created_at') else None,
                    'latest_sign_in': str(result['latest_sign_in']) if result.get('latest_sign_in') else None
                }
            return None
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise
    
    @staticmethod
    def get_user_id_by_firebase_uid(firebase_uid):
        """
        Get user_id directly from users table by firebase_uid
        This method only returns the UUID id, avoiding any timestamp confusion
        Uses explicit UUID casting to ensure we get the correct column
        """
        try:
            query = """
                SELECT CAST(id AS VARCHAR) as user_id
                FROM users 
                WHERE firebase_uid = %s
                LIMIT 1
            """
            result = execute_query(query, (firebase_uid,), fetch_one=True)
            if result:
                user_id = result.get('user_id')
                logger.debug(f"Raw result from get_user_id_by_firebase_uid: {result}")
                logger.debug(f"Got user_id directly from users table: {user_id} (type: {type(user_id).__name__})")
                
                # Validate it's a UUID (not a timestamp)
                if isinstance(user_id, str) and 'T' in user_id:
                    logger.error(f"CRITICAL: get_user_id_by_firebase_uid returned timestamp '{user_id}' instead of UUID!")
                    logger.error(f"Full result: {result}")
                    return None
                
                # Validate it's a UUID
                import uuid
                if isinstance(user_id, str) and len(user_id) == 36 and user_id.count('-') == 4:
                    try:
                        uuid.UUID(user_id)
                        logger.debug(f"Validated user_id: {user_id}")
                        return user_id
                    except (ValueError, AttributeError) as e:
                        logger.error(f"user_id '{user_id}' is not a valid UUID: {e}")
                        return None
                else:
                    logger.error(f"user_id '{user_id}' has wrong format (length: {len(user_id) if isinstance(user_id, str) else 'N/A'}, dashes: {user_id.count('-') if isinstance(user_id, str) else 'N/A'})")
                    return None
            logger.warning(f"No user found with firebase_uid: {firebase_uid}")
            return None
        except Exception as e:
            logger.error(f"Error getting user_id by firebase_uid: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    @staticmethod
    def get_user_by_firebase_uid(firebase_uid):
        """
        Get user by Firebase UID
        """
        try:
            # Explicitly select columns to ensure correct order and avoid any column name issues
            query = """
                SELECT id, firebase_uid, email, phone_number, role,
                       first_name, last_name,
                       created_at, latest_sign_in, email_verified, is_active
                FROM users WHERE firebase_uid = %s
            """
            result = execute_query(query, (firebase_uid,), fetch_one=True)
            if result:
                # RealDictRow is dict-like, access columns by name
                # Log all columns for debugging
                logger.debug(f"User query result type: {type(result)}")
                if hasattr(result, 'keys'):
                    all_keys = list(result.keys())
                    logger.debug(f"User query result keys: {all_keys}")
                    # Log all values to see what we're getting
                    for key in all_keys:
                        logger.debug(f"  {key}: {result[key]} (type: {type(result[key])})")
                
                # Access each column explicitly by name to avoid any confusion
                # Use direct access, not .get() for required fields to catch errors early
                try:
                    # Log all columns first to see what we're getting
                    logger.debug("User query result - all columns")
                    if hasattr(result, 'keys'):
                        for key in result.keys():
                            val = result[key]
                            if key in ('email', 'phone_number'):
                                logger.debug(f"  {key}: [redacted]")
                            else:
                                logger.debug(f"  {key}: {val} (type: {type(val).__name__})")
                    
                    user_id_value = result['id']
                    logger.debug(f"Extracted user_id from result['id']: {user_id_value}, type: {type(user_id_value)}")
                    
                    # Validate that id is a UUID (not a timestamp)
                    if isinstance(user_id_value, str) and 'T' in user_id_value:
                        # This is definitely a timestamp string, not a UUID
                        logger.error(f"CRITICAL: result['id'] contains timestamp '{user_id_value}' instead of UUID!")
                        logger.error(f"All result keys and values:")
                        if hasattr(result, 'keys'):
                            for key in result.keys():
                                logger.error(f"  {key}: {result[key]} (type: {type(result[key])})")
                        # This should never happen - the 'id' column should be UUID
                        raise ValueError(f"Database schema error: 'id' column contains timestamp '{user_id_value}' instead of UUID")
                    
                    # Additional validation: check if it's a datetime object
                    from datetime import datetime
                    if isinstance(user_id_value, datetime):
                        logger.error(f"CRITICAL: result['id'] is a datetime object '{user_id_value}' instead of UUID!")
                        raise ValueError(f"Database schema error: 'id' column is datetime object instead of UUID")
                    
                    # Build user dict with explicit column access
                    user_dict = {
                        'id': user_id_value,
                        'firebase_uid': result['firebase_uid'],
                        'email': result['email'],
                        'phone_number': result.get('phone_number'),
                        'role': result.get('role'),
                        'first_name': result.get('first_name'),
                        'last_name': result.get('last_name'),
                        'created_at': result.get('created_at'),
                        'latest_sign_in': result.get('latest_sign_in'),
                        'email_verified': result.get('email_verified', False),
                        'is_active': result.get('is_active', True)
                    }
                    
                    # Validate it's a proper UUID format
                    if isinstance(user_id_value, str):
                        # UUIDs are 36 characters with exactly 4 dashes
                        if len(user_id_value) == 36 and user_id_value.count('-') == 4 and 'T' not in user_id_value:
                            try:
                                # Try to parse as UUID to validate
                                import uuid
                                uuid.UUID(user_id_value)
                                # Valid UUID - this is correct
                            except (ValueError, AttributeError) as e:
                                logger.warning(f"User ID '{user_id_value}' looks like UUID but failed validation: {e}")
                    
                    return user_dict
                except KeyError as e:
                    logger.error(f"Missing column in result: {e}")
                    logger.error(f"Available columns: {list(result.keys()) if hasattr(result, 'keys') else 'Unknown'}")
                    raise
            return None
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            raise
    
    @staticmethod
    def get_user_by_id(user_id):
        """Get user row by UUID primary key."""
        try:
            query = """
                SELECT id, firebase_uid, email, phone_number, role,
                       first_name, last_name,
                       created_at, latest_sign_in, email_verified, is_active
                FROM users WHERE id = %s::uuid
            """
            result = execute_query(query, (user_id,), fetch_one=True)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error get_user_by_id: {str(e)}")
            raise

    @staticmethod
    def update_email_verified(firebase_uid, email_verified):
        """Sync email_verified from Firebase token into Neon."""
        try:
            query = """
                UPDATE users
                SET email_verified = %s
                WHERE firebase_uid = %s
                RETURNING id, firebase_uid, email, email_verified
            """
            return execute_query(query, (bool(email_verified), firebase_uid), fetch_one=True)
        except Exception as e:
            logger.error(f"Error update_email_verified: {str(e)}")
            raise

    @staticmethod
    def get_user_by_email(email):
        """
        Get user by email
        """
        try:
            query = "SELECT * FROM users WHERE email = %s"
            result = execute_query(query, (email,), fetch_one=True)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting user by email: {str(e)}")
            raise
    
    @staticmethod
    def update_user_role(firebase_uid, role):
        """
        Update user role (supports multi-role as comma-separated string)
        """
        try:
            query = """
                UPDATE users 
                SET role = %s, latest_sign_in = CURRENT_TIMESTAMP
                WHERE firebase_uid = %s
                RETURNING *
            """
            params = (role, firebase_uid)
            result = execute_query(query, params, fetch_one=True)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error updating user role: {str(e)}")
            raise
    
    @staticmethod
    def update_latest_sign_in(firebase_uid):
        """
        Update the latest_sign_in timestamp to current time
        This should be called every time a user signs in
        """
        try:
            # Use CURRENT_TIMESTAMP from database for consistency
            query = """
                UPDATE users 
                SET latest_sign_in = CURRENT_TIMESTAMP
                WHERE firebase_uid = %s
                RETURNING id, firebase_uid, email, latest_sign_in
            """
            result = execute_query(query, (firebase_uid,), fetch_one=True)
            if result:
                logger.debug(f"Updated latest_sign_in for user {firebase_uid} to {result.get('latest_sign_in')}")
            return result if result else None
        except Exception as e:
            logger.error(f"Error updating sign-in time: {str(e)}")
            raise
    
    @staticmethod
    def add_user_role(user_id, role):
        """
        Add a role to user_roles table (for multi-role support)
        """
        try:
            query = """
                INSERT INTO user_roles (user_id, role)
                VALUES (%s, %s)
                ON CONFLICT (user_id, role) DO NOTHING
                RETURNING *
            """
            result = execute_query(query, (user_id, role), fetch_one=True)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error adding user role: {str(e)}")
            raise
    
    @staticmethod
    def get_user_roles(user_id):
        """
        Get all roles for a user from user_roles table
        """
        try:
            query = "SELECT role FROM user_roles WHERE user_id = %s"
            results = execute_query(query, (user_id,), fetch_all=True)
            return [row['role'] for row in results] if results else []
        except Exception as e:
            logger.error(f"Error getting user roles: {str(e)}")
            raise
    
    @staticmethod
    def user_exists(firebase_uid):
        """
        Check if user exists in database
        """
        try:
            query = "SELECT COUNT(*) as count FROM users WHERE firebase_uid = %s"
            result = execute_query(query, (firebase_uid,), fetch_one=True)
            return result['count'] > 0 if result else False
        except Exception as e:
            logger.error(f"Error checking user existence: {str(e)}")
            raise

